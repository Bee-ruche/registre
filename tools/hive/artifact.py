#!/usr/bin/env python3
"""How a job of the hive's run takes the files an earlier job of the same run left (docs/hive-workflow.md).

A job that is about to hold a key never unpacks another job's files with a general tool: an archive names its own
paths, and a file written where code is later run from is run. This tool asks GitHub for the archive, reads from
it the members it was told to expect, by their exact names and up to a size each, and writes each one, under that
same name, in a folder of its own. An archive that holds anything else is refused whole, and nothing of it is kept.

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
import subprocess
import sys
import tempfile
import zipfile
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


def take(archive, members, folder):
    """Writes into `folder` (which it creates) each of `members` ({name: the most bytes it may hold}) read from the
    zip file `archive`, and returns the folder. The archive must hold exactly these members, each once, as plain
    stored or deflated files no larger than allowed: otherwise Refused, and the folder is not left behind.

    Nothing is extracted: no path of the archive is ever joined to a folder. The names written are the caller's."""
    if not members or not all(isinstance(name, str) and MEMBER_NAME.match(name) and type(most) is int and 0 < most <= MOST_BYTES
                              for name, most in members.items()):
        raise Refused("the members asked for are not plain file names with a size")
    folder = Path(folder)
    try:
        folder.mkdir(parents=True)  # a folder of this step's own: an existing one is not written into
    except OSError:
        raise Refused("the folder to write into exists already, or cannot be made") from None
    try:
        try:
            opened = zipfile.ZipFile(archive)
        except (zipfile.BadZipFile, OSError, ValueError, EOFError, NotImplementedError) as error:
            raise Refused(f"not an archive this step reads ({type(error).__name__})") from None
        with opened:
            entries = opened.infolist()
            if sorted(entry.orig_filename for entry in entries) != sorted(members):
                raise Refused("the archive does not hold exactly the members expected")
            for entry in entries:
                name, most = entry.orig_filename, members[entry.orig_filename]
                if entry.flag_bits & 0x1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or entry.file_size > most:
                    raise Refused(f"{name}: not a plain member of the size allowed")
                descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
                try:
                    with os.fdopen(descriptor, "wb") as out, opened.open(entry) as source:
                        left = most
                        while True:
                            block = source.read(min(BLOCK, left + 1))
                            if not block:
                                break
                            left -= len(block)
                            if left < 0:
                                raise Refused(f"{name}: larger than allowed")  # whatever size the archive's reader went by
                            out.write(block)
                except (zipfile.BadZipFile, zlib.error, OSError, ValueError, EOFError, NotImplementedError, RuntimeError) as error:
                    raise Refused(f"{name}: unreadable ({type(error).__name__})") from None
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
