#!/usr/bin/env python3
"""Bee's judge of the second kind, « reference »: a candidate is right when its unit answers exactly as a
reference does, on cases drawn when it is judged (docs/reference-judge.md).

  reference.py --tip TREE --candidate TREE --unit NAME --task-file PATH [--task-file PATH …] --budget SECONDS
               [--tip-itself] [--seed HEX] [--workdir DIR] [--json FILE] [--keep]
  reference.py --tip TREE --image-only

Exit code: 0 correct, 1 refused (the candidate's doing), 2 failure to judge (the machine's, the project's or the
registry's own).

Who holds what. This file, the isolation (container.py) and the safe reading (lecture.py) are the registry's: they
run on the judge's machine. The project's part is at ITS TIP, under paths a candidate cannot change: a manifest
that is data (bee/reference/project.json), two build scripts, two drivers, a generator, the reference itself. The
candidate brings the files of ONE unit. Nothing of the tip and nothing of the candidate runs on the host: scripts,
compilers, drivers and the generator run in containers without network, each bounded by this file.

The two rules (docs/reference-judge.md):
  R1  a candidate answers only for binaries of its own unit, built from the tip's skeleton and its own files;
  R2  a unit is right when it is right in every build and every run drawn for it: several binaries built with
      different nonces, each run several times on the cases in different orders, every file of answers exactly
      the expected one.
"""

import argparse
import contextlib
import hashlib
import json
import os
import random
import re
import secrets
import shutil
import stat
import struct
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import container  # noqa: E402
from lecture import Erreur, Panne, Refus, journal, lire_sortie, propre  # noqa: E402

MANIFEST = "bee/reference/project.json"
BUILD_REFERENCE, BUILD_UNIT = "bee/reference/build-reference", "bee/reference/build-unit"
MANIFEST_BYTES = 256 * 1024
NAME = re.compile(r"[a-z0-9_]{1,32}")
# A path of the project's tree as the manifest may name one: plain names, no « . » or « .. », nothing hidden.
PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}(?:/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}){0,15}")
# Every number of the manifest lies between a floor and a cap of the kind's own: (floor, cap).
NUMBERS = {"variants": (2, 8), "runs": (2, 8), "build_seconds": (5, 900), "run_seconds": (1, 300),
           "reference_seconds": (5, 900), "memory_mb": (64, 4096), "build_processes": (8, 256), "output_mb": (1, 1024),
           "unit_bytes": (1, 1 << 20)}
UNIT_NUMBERS = {"cases": (1, 100000), "case_bytes": (1, 65536), "answer_bytes": (1, 1 << 20)}
STREAM_BYTES = 64 << 20  # a whole file of cases, or of answers
SOURCE_BYTES = 64 << 20  # what one container is given of the project's tree
ENTRIES = 20000          # files and folders under the paths one container is given
IMAGES = {"common": ()}  # an image's name -> the packages added to the common judge's image (tools/judge/Dockerfile.base)
CONTROL = 3              # the tip's own builds are given this many times the candidate's time
OVERHEAD = 10            # seconds counted for one container's start and end
SEED = re.compile(r"[0-9a-f]{64}")
STATE = {}               # what the report says of a judgement that stops: the step, the seed


# ---------------------------------------------------------------- the manifest: data, every field checked

def whole(value, bounds, name):
    low, high = bounds
    if type(value) is not int or not low <= value <= high:
        raise Erreur(f"the manifest's {name}: a whole number from {low} to {high}")
    return value


def paths(value, name, least=1):
    if not isinstance(value, list) or not least <= len(value) <= 64 or not all(isinstance(p, str) and PATH.fullmatch(p) for p in value):
        raise Erreur(f"the manifest's {name}: a list of plain relative paths")
    if len(set(value)) != len(value):
        raise Erreur(f"the manifest's {name}: a path is listed twice")
    return list(value)


def within(path, others):
    """True if path is one of others, or lies under one, or holds one."""
    return any(path == o or path.startswith(o + "/") or o.startswith(path + "/") for o in others)


def check_manifest(raw):
    """The manifest as the kind uses it. Anything else than the fields below, in the shapes below: a failure to judge."""
    if not isinstance(raw, dict) or set(raw) != {"image", "reference", "skeleton", "units", *NUMBERS}:
        raise Erreur("the manifest: exactly the fields image, reference, skeleton, units, " + ", ".join(sorted(NUMBERS)))
    if not isinstance(raw["image"], str) or raw["image"] not in IMAGES:
        raise Erreur("the manifest's image: the name of an image the registry holds (" + ", ".join(sorted(IMAGES)) + ")")
    manifest = {"image": raw["image"], "reference": paths(raw["reference"], "reference"), "skeleton": paths(raw["skeleton"], "skeleton")}
    for name, bounds in NUMBERS.items():
        manifest[name] = whole(raw[name], bounds, name)
    for needed, where in ((BUILD_REFERENCE, "reference"), (BUILD_UNIT, "skeleton")):
        if not any(needed == p or needed.startswith(p + "/") for p in manifest[where]):
            raise Erreur(f"the manifest's {where} must hold {needed}")
    units = raw["units"]
    if not isinstance(units, dict) or not 1 <= len(units) <= 256 or not all(isinstance(n, str) and NAME.fullmatch(n) for n in units):
        raise Erreur("the manifest's units: names of lower-case letters, digits and underscores")
    manifest["units"], taken = {}, []
    for name, unit in units.items():
        if not isinstance(unit, dict) or set(unit) != {"files", "refuses", *UNIT_NUMBERS}:
            raise Erreur(f"the manifest's unit {name}: exactly the fields files, refuses, " + ", ".join(sorted(UNIT_NUMBERS)))
        files = paths(unit["files"], f"unit {name}: files")
        if type(unit["refuses"]) is not bool:
            raise Erreur(f"the manifest's unit {name}: refuses is true or false")
        checked = {"files": files, "refuses": unit["refuses"]}
        for key, bounds in UNIT_NUMBERS.items():
            checked[key] = whole(unit[key], bounds, f"unit {name}: {key}")
        if checked["cases"] * (4 + checked["case_bytes"]) > STREAM_BYTES or checked["cases"] * (9 + checked["answer_bytes"]) > STREAM_BYTES:
            raise Erreur(f"the manifest's unit {name}: its cases, or their answers, could pass {STREAM_BYTES} bytes")
        for path in files:
            # A unit's file is the candidate's: never a path the reference's side or the skeleton is read from, never
            # under bee/ (the project's own tooling), never another unit's.
            if within(path, manifest["reference"] + manifest["skeleton"] + taken) or path == "bee" or path.startswith("bee/"):
                raise Erreur(f"the manifest's unit {name}: {path} is also the project's own, or another unit's")
        taken += files
        manifest["units"][name] = checked
    return manifest


def budget(manifest, tip_itself):
    """The worst case of a whole judgement, in seconds: every container at its time bound."""
    reference = 3 * (manifest["reference_seconds"] + OVERHEAD)  # its build, the generator, its run
    control = 2 * (CONTROL * manifest["build_seconds"] + OVERHEAD) + manifest["run_seconds"] + OVERHEAD
    if tip_itself:
        return reference + control
    return (reference + control + manifest["variants"] * (manifest["build_seconds"] + OVERHEAD)
            + manifest["variants"] * manifest["runs"] * (manifest["run_seconds"] + OVERHEAD))


# ---------------------------------------------------------------- trees on the host: read as bytes, nothing followed

def descend(root, parts):
    """A descriptor on root/parts…, each part a real folder (a link is not followed: OSError)."""
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            deeper = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = deeper
    except BaseException:
        os.close(fd)
        raise
    return fd


def regular_files(root, relative, found):
    """The regular files at root/relative, a file or a folder: [(relative path, executable)] added to found. A link,
    a special file, a missing path, too many entries: OSError or ValueError."""
    parts = relative.split("/")
    fd = descend(root, parts[:-1])
    try:
        mode = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False).st_mode
    finally:
        os.close(fd)
    if stat.S_ISREG(mode):
        found.append((relative, bool(mode & 0o111)))
    elif stat.S_ISDIR(mode):
        fd = descend(root, parts)
        try:
            names = sorted(os.listdir(fd))
        finally:
            os.close(fd)
        for name in names:
            if len(found) > ENTRIES or relative.count("/") > 32:
                raise ValueError("too many entries")
            regular_files(root, f"{relative}/{name}", found)
    else:
        raise ValueError(f"{relative} is neither a file nor a folder")


def copy_paths(root, listed, target, blame, limit=SOURCE_BYTES, file_limit=None):
    """The files at root/<each listed path> written under target with the same relative paths, readable by the
    container's user. Nothing is followed and nothing special is copied; blame says whose fault a bad path is."""
    found = []
    try:
        for relative in listed:
            regular_files(root, relative, found)
    except (OSError, ValueError) as error:
        raise blame(f"a path that is not a plain file or folder ({propre(str(error), 200)})") from None
    total = 0
    for relative, executable in found:
        try:
            data = lire_sortie(root, relative, min(limit - total, file_limit or limit) if limit > total else 0)
        except Refus as error:
            raise blame(f"{relative}: {propre(str(error), 200)}") from None
        if data is None:
            raise blame(f"{relative}: missing")
        total += len(data)
        path = os.path.join(target, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "xb") as f:
            f.write(data)
        os.chmod(path, 0o755 if executable else 0o644)
    for folder, _, _ in os.walk(target):
        os.chmod(folder, 0o755)
    return [relative for relative, _ in found]


def snapshot(root):
    """{relative path: what it is} of a whole tree, no link followed: a file's size and mode, a link's target."""
    seen = {}
    for folder, folders, files in os.walk(root):
        for name in folders + files:
            path = os.path.join(folder, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            status = os.lstat(path)
            if stat.S_ISLNK(status.st_mode):
                seen[relative] = ("link", os.readlink(path))
            elif stat.S_ISDIR(status.st_mode):
                seen[relative] = ("folder",)
            elif stat.S_ISREG(status.st_mode):
                seen[relative] = ("file", status.st_size, status.st_mode & 0o111 != 0)
            else:
                seen[relative] = ("other",)
            if len(seen) > 400000:
                raise Erreur("the project's tree holds too many entries for this judge")
    return seen


def same_bytes(one, other):
    with open(one, "rb") as a, open(other, "rb") as b:
        while True:
            block = a.read(1 << 20)
            if block != b.read(1 << 20):
                return False
            if not block:
                return True


def only_the_unit_differs(tip, candidate, files):
    """Refus unless the candidate's tree is the tip's everywhere but at the unit's files. The base integrates the
    whole tree a candidate gives: what this judge does not build must be what the project already holds."""
    ours, theirs = snapshot(tip), snapshot(candidate)
    for relative in files:  # the unit's files, and the folders that lead to them, are the candidate's to hold
        ours.pop(relative, None), theirs.pop(relative, None)
    if ours != theirs:
        raise Refus("the candidate changes something else than its unit's files")
    for relative, what in ours.items():
        if what[0] == "file" and not same_bytes(os.path.join(tip, relative), os.path.join(candidate, relative)):
            raise Refus("the candidate changes something else than its unit's files")


# ---------------------------------------------------------------- containers: what each outcome means is said here

@contextlib.contextmanager
def bounded_folder(path, megabytes):
    """A folder a container may write in, of bounded size: a memory file system of its own, gone when the step ends."""
    os.mkdir(path)
    container.mount_point("mount", "-t", "tmpfs", "-o", f"size={megabytes}m,nr_inodes=16384,mode=0777,nosuid,nodev", "tmpfs", path)
    try:
        yield path
    finally:
        container.mount_point("umount", path)
        os.rmdir(path)


def launch(docker, command, mounts, pids, seconds, blame, what, entry=None):
    """One container, to its end. A time bound reached, or an exit status that is not 0, is `blame`'s (Refus: the
    candidate's doing; Erreur: the project's or the machine's). Docker's own failure is always the machine's."""
    try:
        ran = docker.launch(command, mounts, pids=pids, entry=entry, timeout_seconds=seconds)
    except Panne:
        raise
    except Refus:  # container.Docker.launch's word for a container that ran and was stopped at its time
        raise blame(f"{what}: stopped at its time bound ({seconds} s)") from None
    if ran.returncode != 0:
        raise blame(f"{what}: exit status {ran.returncode}. " + propre(ran.stderr, 600))
    return ran


def left(root, name, maximum, blame, what):
    """A file a container left in root, read without following anything, or None when there is none."""
    try:
        return lire_sortie(root, name, maximum)
    except Refus as error:
        raise blame(f"{what}: {propre(str(error), 200)}") from None


def keep_file(folder, name, data, executable=False):
    os.makedirs(folder, exist_ok=True)
    os.chmod(folder, 0o755)
    with open(os.path.join(folder, name), "xb") as f:
        f.write(data)
    os.chmod(os.path.join(folder, name), 0o755 if executable else 0o644)
    return folder


def megabytes(size):
    return size // (1 << 20) + 2


class Judgement:
    """The containers of one judgement: the image, the manifest's bounds, the work folder."""

    def __init__(self, image, manifest, work):
        self.docker, self.manifest, self.work, self.count = container.Docker(image, memoire=f"{manifest['memory_mb']}m"), manifest, work, 0

    def folder(self, name):
        self.count += 1
        return os.path.join(self.work, f"{self.count:03d}-{name}")

    def build_reference(self, sources):
        """The reference's driver and the generator, as the tip's own script leaves them: a folder to mount."""
        kept = self.folder("reference")
        with bounded_folder(self.folder("out"), self.manifest["output_mb"]) as out:
            launch(self.docker, ["sh", "/src/" + BUILD_REFERENCE], [(sources, "/src", True), (out, "/out", False)],
                   self.manifest["build_processes"], self.manifest["reference_seconds"], Erreur, "the reference's build")
            for name in ("reference", "generate"):
                data = left(out, name, self.manifest["output_mb"] << 20, Erreur, f"the reference's build: /out/{name}")
                if data is None:
                    raise Erreur(f"the reference's build left no /out/{name}")
                keep_file(kept, name, data, executable=True)
        return kept

    def build_unit(self, sources, unit, blame, factor=1):
        """One binary of a unit, built with a nonce of its own: (a folder that holds it, its fingerprint)."""
        nonce, what = secrets.token_hex(32), f"the build of unit {unit}"
        with bounded_folder(self.folder("out"), self.manifest["output_mb"]) as out:
            launch(self.docker, ["sh", "/src/" + BUILD_UNIT, unit], [(sources, "/src", True), (out, "/out", False)],
                   self.manifest["build_processes"], factor * self.manifest["build_seconds"], blame, what, entry=(nonce + "\n").encode())
            binary = left(out, "driver", self.manifest["output_mb"] << 20, blame, what + ": /out/driver")
        if not binary:
            raise blame(what + " left no /out/driver")
        return keep_file(self.folder("unit"), "driver", binary, executable=True), hashlib.sha256(binary).hexdigest()

    def generate(self, reference, unit, count, seed):
        with bounded_folder(self.folder("cases"), megabytes(STREAM_BYTES)) as out:
            launch(self.docker, ["/ref/generate", unit, str(count)], [(reference, "/ref", True), (out, "/cases", False)],
                   self.manifest["build_processes"], self.manifest["reference_seconds"], Erreur, "the generator", entry=(seed.hex() + "\n").encode())
            data = left(out, "cases", STREAM_BYTES, Erreur, "the generator: /cases/cases")
        if data is None:
            raise Erreur("the generator left no /cases/cases")
        return data

    def answers(self, command, binary, where, cases, most, seconds, blame, what):
        """The file of answers a driver writes for a file of cases, or None; `most` bytes of it are read at most."""
        given = keep_file(self.folder("given"), "cases", cases)
        with bounded_folder(self.folder("answers"), megabytes(most)) as out:
            launch(self.docker, command, [(binary, where, True), (given, "/cases", True), (out, "/answers", False)], 2, seconds, blame, what)
            return left(out, "answers", most, blame, what + ": /answers/answers")


# ---------------------------------------------------------------- the framing: the host builds what it expects

def parse_cases(data, unit):
    """The cases the generator wrote: exactly the manifest's count, each within its bound, nothing more."""
    cases, at = [], 0
    for _ in range(unit["cases"]):
        if at + 4 > len(data):
            raise Erreur("the generator wrote fewer cases than the manifest's count")
        (size,) = struct.unpack_from("<I", data, at)
        at += 4
        if size > unit["case_bytes"] or at + size > len(data):
            raise Erreur("the generator wrote a case longer than the manifest's bound, or cut short")
        cases.append(data[at:at + size])
        at += size
    if at != len(data):
        raise Erreur("the generator wrote more than the manifest's count of cases")
    if len(set(cases)) < (len(cases) + 3) // 4:
        raise Erreur("the generator wrote the same cases over and over")
    return cases


def parse_answers(data, unit):
    """The reference's answers, one per case in order: [(status, bytes)]. Checked on the reference only: a
    candidate's file is never parsed, it is compared whole."""
    answers, at = [], 0
    for index in range(unit["cases"]):
        if at + 9 > len(data):
            raise Erreur("the reference answered fewer cases than it was given")
        position, status, size = struct.unpack_from("<IBI", data, at)
        at += 9
        if position != index or status not in (0, 1) or size > unit["answer_bytes"] or (status == 1 and size) or at + size > len(data):
            raise Erreur("the reference wrote an answer that is not well framed")
        answers.append((status, data[at:at + size]))
        at += size
    if at != len(data):
        raise Erreur("the reference wrote more than one answer per case")
    refused = sum(status for status, _ in answers)
    if unit["refuses"] and (refused == 0 or refused == len(answers)):
        raise Erreur("the manifest says the unit refuses some inputs: the cases drawn must hold a refusal and an answer")
    if not unit["refuses"] and refused:
        raise Erreur("the manifest says the unit refuses nothing, and the reference refused a case")
    if len(answers) > 1 and len(set(answers)) < 2:
        raise Erreur("every case drawn has the same answer: a unit that always says it would pass")
    return answers


def frame_cases(cases):
    return b"".join(struct.pack("<I", len(case)) + case for case in cases)


def frame_answers(answers):
    return b"".join(struct.pack("<IBI", index, status, len(data)) + data for index, (status, data) in enumerate(answers))


# ---------------------------------------------------------------- one judgement

def image_of(manifest):
    label = container.build_image(IMAGES[manifest["image"]], os.environ.get("BEE_JUGE_RESEAU"))
    return container.image_id(label)


def read_manifest(tip):
    try:
        data = lire_sortie(tip, MANIFEST, MANIFEST_BYTES)
    except (Refus, OSError) as error:
        raise Erreur(f"the project's manifest ({MANIFEST}) cannot be read: {propre(str(error), 200)}") from None
    if data is None:
        raise Erreur(f"the project's tip holds no manifest ({MANIFEST})")
    try:
        return check_manifest(json.loads(data.decode("utf-8")))
    except (ValueError, RecursionError) as error:
        raise Erreur(f"the project's manifest is not JSON: {propre(str(error), 200)}") from None


def judge(args, work):
    """Steps 0 to 9 of docs/reference-judge.md. Returns the report's figures; Refus: code 1; Erreur: code 2."""
    STATE["step"] = 1
    manifest = read_manifest(args.tip)
    if not NAME.fullmatch(args.unit or "") or args.unit not in manifest["units"]:
        raise Erreur("the task names no unit of the project's manifest")
    unit = manifest["units"][args.unit]
    if sorted(args.task_file or []) != sorted(unit["files"]):
        raise Erreur("the task's files are not exactly its unit's files")
    needed = budget(manifest, args.tip_itself)
    if needed > args.budget:
        raise Erreur(f"the manifest's bounds add up to {needed} s, above the {args.budget} s a judgement of this project is given")
    if not args.tip_itself:
        only_the_unit_differs(args.tip, args.candidate, unit["files"])
    judgement = Judgement(image_of(manifest), manifest, work)

    STATE["step"] = 2
    sources = judgement.folder("reference-sources")
    copy_paths(args.tip, manifest["reference"], sources, Erreur)
    reference = judgement.build_reference(sources)

    STATE["step"] = 3  # the control: the tip's own unit builds, twice, into two different binaries, and its driver starts
    tip_sources = judgement.folder("tip-sources")
    copy_paths(args.tip, manifest["skeleton"] + unit["files"], tip_sources, Erreur)
    (control, first), (_, second) = (judgement.build_unit(tip_sources, args.unit, Erreur, CONTROL) for _ in range(2))
    if first == second:
        raise Erreur("the project's build gives the same binary for two nonces: it must make the binary follow the nonce")
    nothing = judgement.answers(["/unit/driver"], control, "/unit", b"", 1, manifest["run_seconds"], Erreur, "the tip's driver, given no case")
    if nothing:
        raise Erreur("the tip's driver, given no case, wrote something")

    binaries = []
    if not args.tip_itself:
        STATE["step"] = 4
        candidate_sources = judgement.folder("candidate-sources")
        copy_paths(args.tip, manifest["skeleton"], candidate_sources, Erreur)
        copy_paths(args.candidate, unit["files"], candidate_sources, Refus, file_limit=manifest["unit_bytes"])
        binaries = [judgement.build_unit(candidate_sources, args.unit, Refus)[0] for _ in range(manifest["variants"])]

    STATE["step"] = 5  # only now: no build of the candidate's has seen the seed, the cases or their order
    seed = bytes.fromhex(args.seed) if args.seed else secrets.token_bytes(32)
    STATE["seed"], STATE["seed_origin"] = seed.hex(), "given" if args.seed else "drawn"
    cases = parse_cases(judgement.generate(reference, args.unit, unit["cases"], seed), unit)
    written = judgement.answers(["/ref/reference", args.unit], reference, "/ref", frame_cases(cases), STREAM_BYTES,
                                manifest["reference_seconds"], Erreur, "the reference's run")
    if written is None:
        raise Erreur("the reference's run left no /answers/answers")
    expected = parse_answers(written, unit)

    STATE["step"] = 6
    if args.tip_itself:
        return {"cases_compared": 0, "builds": 0, "runs": 0}

    STATE["step"] = 7
    for build, binary in enumerate(binaries):
        for run in range(manifest["runs"]):
            order = list(range(len(cases)))
            random.Random(hashlib.sha256(seed + f"/order/{build}/{run}".encode()).digest()).shuffle(order)
            wanted = frame_answers([expected[index] for index in order])
            what = f"build {build + 1}, run {run + 1} of unit {args.unit}"
            given = judgement.answers(["/unit/driver"], binary, "/unit", frame_cases([cases[index] for index in order]), len(wanted) + 1,
                                      manifest["run_seconds"], Refus, what)
            if given != wanted:
                raise Refus(f"{what}: its answers are not the reference's")
    STATE["step"] = 9
    return {"cases_compared": len(cases) * len(binaries) * manifest["runs"], "builds": len(binaries), "runs": len(binaries) * manifest["runs"]}


def write_report(path, report):
    """The report, whole or not at all."""
    if not path:
        return
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=".reference-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bee's judge of the second kind: answers as a reference does.")
    parser.add_argument("--tip", required=True, help="the project's tip, written out (the base's tree)")
    parser.add_argument("--candidate", help="the candidate's tree, written out")
    parser.add_argument("--unit", help="the unit the task writes")
    parser.add_argument("--task-file", action="append", help="a file the task lists (repeat)")
    parser.add_argument("--budget", type=int, default=3600, help="seconds a whole judgement of this project is given")
    parser.add_argument("--tip-itself", action="store_true", help="the commit judged is the tip's: does the machine work?")
    parser.add_argument("--seed", help="64 hexadecimal digits instead of a seed drawn here: a reproduction, never a judgement")
    parser.add_argument("--workdir", help="where this judgement's folders are made")
    parser.add_argument("--json", help="where the report is written")
    parser.add_argument("--keep", action="store_true", help="keep the work folder")
    parser.add_argument("--image-only", action="store_true", help="prepare the image the tip's manifest names, and stop")
    args = parser.parse_args(argv)
    if args.image_only:
        journal("image ready: " + image_of(read_manifest(args.tip)))
        return 0
    if args.seed is not None and not SEED.fullmatch(args.seed):
        raise Erreur("--seed: 64 hexadecimal digits")
    if not args.tip_itself and not args.candidate:
        raise Erreur("--candidate is needed, unless --tip-itself")
    if args.workdir:
        os.makedirs(args.workdir, exist_ok=True)
    work = tempfile.mkdtemp(prefix="reference-", dir=args.workdir)
    os.chmod(work, 0o755)
    try:
        figures = judge(args, work)
    finally:
        if args.keep:
            journal(f"work folder kept: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    write_report(args.json, {"kind": "reference", "code": 0, "unit": args.unit, **STATE, **figures})
    journal(f"correct: {figures}")
    return 0


def stop(code, message, json_path):
    """The judge stops (1 refused, 2 failure to judge): the reason on the error output, and in the report."""
    print(message, file=sys.stderr)
    try:
        write_report(json_path, {"kind": "reference", "code": code, "reason": message, **STATE})
    except (OSError, ValueError):
        pass
    return code


if __name__ == "__main__":
    where = next((sys.argv[i + 1] for i, word in enumerate(sys.argv[:-1]) if word == "--json"), None)
    try:
        sys.exit(main())
    except Refus as refusal:
        sys.exit(stop(1, f"judge: REFUSED: {propre(str(refusal), 2000)}", where))
    except Erreur as error:
        sys.exit(stop(2, f"judge: failure to judge: {propre(str(error), 2000)}", where))
    except Exception:  # noqa: BLE001 — a defect of the judge itself: never a success, never a raw trace
        sys.exit(stop(2, "judge: internal error: " + propre(traceback.format_exc(), 3000), where))
