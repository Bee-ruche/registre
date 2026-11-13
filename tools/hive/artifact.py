#!/usr/bin/env python3
"""How a job of the hive's run takes the files an earlier job of the same run left (docs/hive-workflow.md).

A job that is about to hold a key never unpacks another job's files with a general tool: an archive names its own
paths, and a file written where code is later run from is run. This tool asks GitHub for the archive, reads from
it the members it was told to expect, by their exact names and up to a size each, and writes each one, under that
same name, in a folder of its own. An archive that holds anything else is refused whole, and nothing of it is kept.

It reads the archive itself, and accepts one layout only, the one the upload action writes: the members one after
the other from the first byte, each a header that leaves its sizes for later, its deflated data, then sixteen
bytes that give its checksum and sizes; then the directory that lists exactly them; then the end record; then the
end of the file. No comment, no extra field, no other flag or method, nothing between two parts. Every byte is
accounted for, so no other reader of the same archive can find in it a member this one did not see; and what the
reading costs is bounded by the sizes asked for and a block at a time, never by what the archive says of itself
(docs/hive-workflow.md says what could not be tried against GitHub).

What it takes is still only data from a job that held no key: the caller checks it (the plan against the SHA-256
its job published, the bundle against the plan) or believes it for nothing more than what that job may say (the
judge's answers).

    artifact.py take --name plan --member plan.json:33554432 --member candidates.bundle:2147483648 --into taken

reads GITHUB_REPOSITORY and GITHUB_RUN_ID, and calls `gh` (which reads GH_TOKEN: a token that may read the
repository's Actions is enough). Exit codes: 0 taken; 3 the run has no artifact of that name; 1 refused, or failed.
Standard library only.
"""
import argparse
import json
import os
import re
import resource
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}\Z")
RUN_ID = re.compile(r"[0-9]{1,20}\Z")
ARTIFACT_NAME = re.compile(r"[a-z][a-z0-9-]{0,40}\Z")
MEMBER_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}\Z")  # one file name: no folder, nothing that leaves one
MOST_BYTES = 8 << 30  # no member is ever expected to be larger
SLACK_BYTES = 1 << 20  # what an archive may weigh beyond its members (stored members do not shrink)
BLOCK = 1 << 20
NOT_THERE = 3
# The zip format, as far as this tool reads it (little-endian; sizes of 4 bytes only: no ZIP64, nothing beyond 4 GiB).
END = struct.Struct("<4s4H2LH")  # signature, 2 disk numbers, 2 counts of entries, the directory's size and offset, comment length
ENTRY = struct.Struct("<4s6H3L5H2L")  # one member in the directory
LOCAL = struct.Struct("<4s5H3L2H")  # the header in front of a member's data
AFTER = struct.Struct("<4s3L")  # after a member's data: a signature, its checksum, its packed and unpacked sizes
SIZES_AFTER_DATA, DEFLATED = 0x0008, 8  # the one flag and the one method the upload action writes

class Refused(Exception):
    """The archive, or GitHub's answer, is not what this step expects: nothing of it is used."""


def gh(*args, timeout=120):
    try:
        result = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (subprocess.TimeoutExpired, OSError) as error:
        raise Refused(f"gh api: {type(error).__name__}") from None
    if result.returncode != 0:
        raise Refused("gh api failed")
    return result.stdout


def find(repository, run_id, name, api=gh):
    """The id of this run's artifact of that exact name (the latest, if the run was run again), or None."""
    if not (REPOSITORY.match(repository or "") and RUN_ID.match(run_id or "") and ARTIFACT_NAME.match(name or "")):
        raise Refused("a repository, a run or an artifact name that is not one")
    listed = api("--paginate", f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100&name={name}",
                 "--jq", ".artifacts[] | {id, name, expired}")
    found = []
    for line in listed.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            raise Refused("GitHub's list of artifacts is unreadable") from None
        if not isinstance(entry, dict) or type(entry.get("id")) is not int or entry["id"] <= 0:
            raise Refused("GitHub's list of artifacts is unreadable")
        if entry.get("name") == name and entry.get("expired") is False:
            found.append(entry["id"])
    return max(found) if found else None


def download(repository, artifact_id, path, most):
    """Writes the artifact's archive to `path`: `most` bytes at most, whatever GitHub sends."""
    if not REPOSITORY.match(repository or "") or type(artifact_id) is not int or artifact_id <= 0:
        raise Refused("a repository or an artifact that is not one")

    def bounded():  # in the child only: it cannot write a file larger than this
        resource.setrlimit(resource.RLIMIT_FSIZE, (most, most))

    try:
        with open(path, "xb") as out:
            result = subprocess.run(["gh", "api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip"], stdout=out,
                                    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=900, preexec_fn=bounded)
    except (subprocess.TimeoutExpired, OSError) as error:
        raise Refused(f"the download failed ({type(error).__name__})") from None
    if result.returncode != 0:
        raise Refused("the download failed, or the archive is larger than this step takes")


def listed(source, size, members):
    """What the archive's directory lists, and where that directory starts: ([(name, checksum, packed, unpacked,
    offset)] in the order the members lie in the file, the directory's offset). The archive must end with one end
    record, without comment, right after a directory of exactly as many entries as there are `members`, each named
    like one of them, deflated, with no comment and no extra field: so the directory is read whole at a known, small
    cost."""
    different = Refused("the archive does not hold exactly the members expected")
    if size < END.size:
        raise Refused("not an archive this step reads")
    source.seek(size - END.size)
    signature, disk, first_disk, here, total, length, offset, comment = END.unpack(source.read(END.size))
    if signature != b"PK\x05\x06":
        raise Refused("not an archive this step reads")
    if disk or first_disk or comment or here != len(members) or total != len(members) \
            or length != sum(ENTRY.size + len(name) for name in members) or offset + length != size - END.size:
        raise different
    source.seek(offset)
    directory, at, entries = source.read(length), 0, []
    for _ in members:  # (the directory is exactly as long as these entries, each with its whole name: each is read inside it)
        (signature, _, _, flags, method, _, _, checksum, packed, unpacked, name_length, extra, comment, disk, _, _,
         start) = ENTRY.unpack_from(directory, at)
        name = directory[at + ENTRY.size:at + ENTRY.size + name_length].decode("ascii", errors="replace")
        at += ENTRY.size + name_length
        if signature != b"PK\x01\x02" or (flags, method) != (SIZES_AFTER_DATA, DEFLATED) or extra or comment or disk \
                or name_length != len(name) or name not in members or name in (entry[0] for entry in entries):
            raise different
        entries.append((name, checksum, packed, unpacked, start))
    return sorted(entries, key=lambda entry: entry[4]), offset


def unfolded(source, packed, unpacked):
    """A member's bytes, a block at a time, unfolded from its `packed` bytes of deflated data: never more than a
    block at once, never more than one byte beyond the `unpacked` it declares (the caller sees that byte and stops),
    and Refused if its data is not exactly one deflated stream, from its first byte to its last."""
    unfold, left, waiting, given = zlib.decompressobj(-15), packed, b"", 0
    while not unfold.eof:
        if not waiting:
            waiting = source.read(min(BLOCK, left))
            left = left - len(waiting) if waiting else 0  # (a file that ended early: nothing is left to read)
        try:
            plain = unfold.decompress(waiting, min(BLOCK, unpacked - given + 1))
        except zlib.error:
            raise Refused("unreadable (not deflated data)") from None
        waiting = unfold.unconsumed_tail  # what this call did not use, because it had given as much as it may at once
        if not plain and not left and not unfold.eof:
            raise Refused("unreadable (its data ends before it does)")  # nothing came of what was left, and nothing is left to read
        given += len(plain)
        yield plain  # (the caller stops at the first byte beyond `unpacked`: it is never asked for more)
    if left or unfold.unused_data:
        raise Refused("unreadable (bytes after the end of its data)")


def take(archive, members, folder):
    """Writes into `folder` (which it creates, in a folder that exists) each of `members` ({name: the most bytes it
    may hold}) read from the zip file `archive`, and returns the folder. The archive must be exactly these members,
    each once, no larger than allowed, in the one layout this tool reads, and not one byte more: otherwise Refused,
    and the folder is not left behind.

    Nothing is extracted: no path of the archive is ever joined to a folder. The names written are the caller's."""
    if not members or not all(isinstance(name, str) and MEMBER_NAME.match(name) and type(most) is int and 0 < most <= MOST_BYTES
                              for name, most in members.items()):
        raise Refused("the members asked for are not plain file names with a size")
    folder = Path(folder)
    try:
        folder.mkdir()  # a folder of this step's own: an existing one is not written into
    except OSError:
        raise Refused("the folder to write into exists already, or cannot be made") from None
    different = Refused("the archive does not hold exactly the members expected")
    try:
        try:
            source = open(archive, "rb")
        except OSError as error:
            raise Refused(f"not an archive this step reads ({type(error).__name__})") from None
        with source:
            size = source.seek(0, os.SEEK_END)
            entries, directory = listed(source, size, members)
            position = 0  # where the next member must start: the first byte, then where the one before it ended
            for index, (name, checksum, packed, unpacked, start) in enumerate(entries):
                if unpacked > members[name]:
                    raise Refused(f"{name}: larger than allowed")
                # The header in front of the data: where the member before it ended, and as the upload action writes it.
                source.seek(start)
                header = source.read(LOCAL.size + len(name))
                signature, _, flags, method, _, _, *figures, name_length, extra = LOCAL.unpack_from(header)
                if start != position or signature != b"PK\x03\x04" or (flags, method) != (SIZES_AFTER_DATA, DEFLATED) or figures != [0, 0, 0] \
                        or name_length != len(name) or extra or header[LOCAL.size:] != name.encode():
                    raise different
                position = entries[index + 1][4] if index + 1 < len(entries) else directory  # where this member must end
                if position - (start + len(header) + packed) != AFTER.size:
                    raise different
                descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
                with os.fdopen(descriptor, "wb") as out:
                    written, crc = 0, 0
                    try:
                        for plain in unfolded(source, packed, unpacked):
                            written += len(plain)
                            if written > unpacked:
                                raise Refused("larger than it says")  # seen, and never written
                            crc = zlib.crc32(plain, crc)
                            out.write(plain)
                    except Refused as refusal:
                        raise Refused(f"{name}: {refusal}") from None
                if written != unpacked or crc != checksum:
                    raise Refused(f"{name}: unreadable (its size or its checksum is not what the archive says)")
                if source.read(AFTER.size) != AFTER.pack(b"PK\x07\x08", checksum, packed, unpacked):
                    raise different
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


def members_of(texts):
    """{name: most bytes} from the command line's NAME:BYTES."""
    members = {}
    for text in texts:
        name, _, most = text.partition(":")
        if name in members or not MEMBER_NAME.match(name) or not re.fullmatch(r"[1-9][0-9]{0,10}", most) or int(most) > MOST_BYTES:
            raise Refused("--member NAME:BYTES, each name once")
        members[name] = int(most)
    return members


def main(argv=None):
    parser = argparse.ArgumentParser(description="Takes named files, and nothing else, from an artifact of this run.")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("take")
    command.add_argument("--name", required=True, help="the artifact's name")
    command.add_argument("--member", action="append", required=True, metavar="NAME:BYTES",
                         help="a file the archive must hold, and the most bytes it may hold (repeat)")
    command.add_argument("--into", required=True, help="the folder to create and write the members into")
    command.add_argument("--archive", help="read this zip file instead of asking GitHub (tests)")
    args = parser.parse_args(argv)
    work = None
    try:
        members = members_of(args.member)
        archive = args.archive
        if archive is None:
            repository, run_id = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", "")
            found = find(repository, run_id, args.name)
            if found is None:
                print(f"artifact: this run has no artifact « {args.name} »", file=sys.stderr)
                return NOT_THERE
            work = tempfile.mkdtemp(prefix="artifact-")
            archive = os.path.join(work, "archive.zip")
            download(repository, found, archive, sum(members.values()) + SLACK_BYTES)
        take(archive, members, args.into)
    except Refused as refusal:
        print(f"artifact: refused: {refusal}", file=sys.stderr)
        return 1
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
    print(f"artifact: took {', '.join(sorted(members))} from « {args.name} »", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
