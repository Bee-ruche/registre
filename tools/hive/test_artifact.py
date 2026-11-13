#!/usr/bin/env python3
"""Tests of tools/hive/artifact.py: what a job that is about to hold a key takes from an earlier job's archive.
Every archive here is made by the tests; nothing is asked of GitHub (a `gh` of the tests' own stands in for it)."""
import io
import json
import os
import stat
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact  # noqa: E402

PLAN, BUNDLE = b'{"protocol": 1}\n', b"# v2 git bundle\n" + bytes(range(256)) * 64
WANTED = {"plan.json": 1 << 20, "candidates.bundle": 1 << 20}


def zipped(entries, compression=zipfile.ZIP_DEFLATED):
    """The bytes of a zip that holds these (name or ZipInfo, bytes), in this order, as zipfile writes them."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z, mock.patch("warnings.warn"):  # (a name twice is only a warning)
        for name, data in entries:
            z.writestr(name, data)
    return buffer.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.into = self.root / "taken"

    def archive(self, data, name="archive.zip"):
        path = self.root / name
        path.write_bytes(data)
        return path

    def refused(self, data, members=None, saying=None):
        with self.assertRaises(artifact.Refused) as refusal:
            artifact.take(self.archive(data), members or WANTED, self.into)
        self.assertFalse(self.into.exists(), "nothing of a refused archive is left behind")
        if saying:
            self.assertIn(saying, str(refusal.exception))
        return str(refusal.exception)


class TestTake(Base):
    def test_the_members_expected_are_written_under_their_names_and_nothing_else(self):
        for compression in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED):
            with self.subTest(compression=compression):
                into = self.root / f"taken-{compression}"
                data = zipped([("candidates.bundle", BUNDLE), ("plan.json", PLAN)], compression)
                self.assertEqual(artifact.take(self.archive(data), WANTED, into), into)
                self.assertEqual(sorted(p.name for p in into.iterdir()), ["candidates.bundle", "plan.json"])
                self.assertEqual(((into / "plan.json").read_bytes(), (into / "candidates.bundle").read_bytes()), (PLAN, BUNDLE))
        self.assertEqual(artifact.take(self.archive(zipped([("verdicts.json", b"")])), {"verdicts.json": 1}, self.into), self.into)
        self.assertEqual((self.into / "verdicts.json").read_bytes(), b"", "an empty file is a file")

    def test_one_member_more_and_the_archive_is_refused_whole(self):
        """The file a taken-over job would add: code, at the path the next step runs code from."""
        for extra in ("registry/tools/hive/hive.py", "hive.py", "x/../../registry/tools/hive/hive.py", "../hive.py",
                      "/home/runner/work/_actions/x/main.cjs", "..", "plan.json/", "plan.json/x", "PLAN.JSON", "plan.json ", "./plan.json",
                      "verdicts.json", "sub/"):
            with self.subTest(extra):
                self.refused(zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE), (extra, b"import os\n")]), saying="exactly")
        self.assertEqual(list(self.root.rglob("hive.py")) + list(self.root.parent.glob("hive.py")), [], "and written nowhere")

    def test_a_name_that_is_not_exactly_the_one_expected(self):
        for name in ("x/../plan.json", "./plan.json", "/plan.json", "plan.json/", "Plan.json", "plan.jsonx", "sub/plan.json", "plan.json\\"):
            with self.subTest(name):
                self.refused(zipped([(name, PLAN), ("candidates.bundle", BUNDLE)]), saying="exactly")

    def test_a_member_missing_or_given_twice(self):
        self.refused(zipped([("plan.json", PLAN)]), saying="exactly")
        self.refused(zipped([]), saying="exactly")
        self.refused(zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE), ("plan.json", b'{"protocol": 2}\n')]), saying="exactly")
        self.refused(zipped([("plan.json", PLAN), ("plan.json", PLAN)]), {"plan.json": 100}, saying="exactly")

    def test_a_name_cut_short_by_a_zero_byte_is_not_the_name_expected(self):
        """Readers stop a name at a zero byte: « plan.json » to one tool, something else to the next."""
        data = zipped([("plan.jsonXY", PLAN), ("candidates.bundle", BUNDLE)])
        self.assertEqual(data.count(b"plan.jsonXY"), 2)  # once before the member, once in the archive's directory
        data = data.replace(b"plan.jsonXY", b"plan.json\0Y")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(sorted(entry.filename for entry in z.infolist()), ["candidates.bundle", "plan.json"], "as a careless reader sees it")
        self.refused(data, saying="exactly")

    def test_a_member_larger_than_allowed(self):
        self.refused(zipped([("plan.json", b"x" * 101)]), {"plan.json": 100}, saying="size allowed")
        self.assertEqual((artifact.take(self.archive(zipped([("plan.json", b"x" * 100)])), {"plan.json": 100}, self.into) / "plan.json").stat().st_size,
                         100, "exactly as large as allowed is taken")

    def test_a_member_that_says_it_is_smaller_than_it_is(self):
        """A few bytes that unfold into gigabytes: the size the archive declares is not believed."""
        data = bytearray(zipped([("plan.json", b"\0" * (4 << 20))]))
        self.assertLess(len(data), 10_000)
        at = data.rindex(b"PK\x01\x02")  # the archive's directory entry: sizes at offsets 20 (packed) and 24 (unpacked)
        self.assertEqual(struct.unpack_from("<I", data, at + 24)[0], 4 << 20)
        struct.pack_into("<I", data, at + 24, 50)
        local = data.index(b"PK\x03\x04")
        struct.pack_into("<I", data, local + 22, 50)
        self.refused(bytes(data), {"plan.json": 100}, saying="unreadable")
        self.assertEqual(sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file() and p.name != "archive.zip"), 0, "nothing was unfolded to disk")
        checksum = zlib.crc32(b"\0" * 50)  # and with a checksum made to fit the size it declares: that size, and no more
        struct.pack_into("<I", data, at + 16, checksum)
        struct.pack_into("<I", data, local + 14, checksum)
        self.assertEqual((artifact.take(self.archive(bytes(data)), {"plan.json": 100}, self.into) / "plan.json").read_bytes(), b"\0" * 50)

    def test_the_size_the_archives_reader_goes_by_is_not_believed_either(self):
        """Should the library that reads the archive hand over more than the member declared, the tool stops."""
        packed = self.archive(zipped([("plan.json", PLAN)]))
        endless = mock.patch.object(zipfile.ZipFile, "open", side_effect=lambda entry, *a, **k: io.BytesIO(b"x" * 5000))
        with endless, self.assertRaisesRegex(artifact.Refused, "larger than allowed"):
            artifact.take(packed, {"plan.json": 100}, self.into)
        self.assertFalse(self.into.exists())

    def test_a_member_that_is_not_a_plain_stored_or_deflated_file(self):
        encrypted = bytearray(zipped([("plan.json", PLAN)]))
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):  # the « encrypted » bit, in both places
            at = encrypted.index(signature) + offset
            struct.pack_into("<H", encrypted, at, struct.unpack_from("<H", encrypted, at)[0] | 1)
        self.refused(bytes(encrypted), {"plan.json": 100}, saying="plain member")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_BZIP2), {"plan.json": 100}, saying="plain member")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_LZMA), {"plan.json": 100}, saying="plain member")

    def test_a_member_marked_as_a_link_is_written_as_a_file(self):
        link = zipfile.ZipInfo("verdicts.json")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        artifact.take(self.archive(zipped([(link, b"/etc/passwd")])), {"verdicts.json": 100}, self.into)
        written = self.into / "verdicts.json"
        self.assertTrue(written.is_file() and not written.is_symlink())
        self.assertEqual((written.read_bytes(), stat.S_IMODE(written.stat().st_mode) & 0o133), (b"/etc/passwd", 0), "its bytes, and no right to run it")

    def test_what_is_not_an_archive(self):
        whole = zipped([("plan.json", PLAN)])
        for data in (b"", b"PK", b"not a zip at all\n" * 100, whole[:-8], whole[:30], b"\0" * 4096):
            with self.subTest(length=len(data)):
                self.refused(data, {"plan.json": 100}, saying="not an archive")
        with self.assertRaisesRegex(artifact.Refused, "not an archive"):
            artifact.take(self.root / "absent.zip", {"plan.json": 100}, self.into)
        self.assertFalse(self.into.exists())

    def test_a_member_whose_bytes_were_changed_after_it_was_packed(self):
        data = bytearray(zipped([("plan.json", PLAN)], zipfile.ZIP_STORED))
        at = data.index(PLAN)
        data[at] ^= 0xFF
        self.refused(bytes(data), {"plan.json": 100}, saying="unreadable")

    def test_a_folder_that_exists_is_not_written_into(self):
        """Nor through a link someone left where the folder, or a file, was to be."""
        data = zipped([("plan.json", PLAN)])
        self.into.mkdir()
        (self.into / "kept").write_text("someone's\n")
        with self.assertRaisesRegex(artifact.Refused, "exists already"):
            artifact.take(self.archive(data), {"plan.json": 100}, self.into)
        self.assertEqual([p.name for p in self.into.iterdir()], ["kept"], "and an existing folder is not removed either")
        elsewhere, link = self.root / "elsewhere", self.root / "link"
        elsewhere.mkdir()
        link.symlink_to(elsewhere)
        with self.assertRaisesRegex(artifact.Refused, "exists already"):
            artifact.take(self.archive(data), {"plan.json": 100}, link)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_the_members_asked_for_are_plain_names_with_a_size(self):
        data = zipped([("plan.json", PLAN)])
        for members in ({}, {"../plan.json": 100}, {"a/b": 100}, {"": 100}, {".hidden": 100}, {"plan.json": 0}, {"plan.json": -1},
                        {"plan.json": "100"}, {"plan.json": artifact.MOST_BYTES + 1}, {"plan.json": True}, {7: 100}):
            with self.subTest(members=members), self.assertRaisesRegex(artifact.Refused, "plain file names"):
                artifact.take(self.archive(data), members, self.into)
            self.assertFalse(self.into.exists())
        self.assertTrue(artifact.take(self.archive(data), {"plan.json": artifact.MOST_BYTES}, self.into).is_dir(), "the largest size there is")

    def test_the_members_named_on_the_command_line(self):
        self.assertEqual(artifact.members_of(["plan.json:100", f"candidates.bundle:{artifact.MOST_BYTES}"]),
                         {"plan.json": 100, "candidates.bundle": artifact.MOST_BYTES})
        for texts in (["plan.json"], ["plan.json:"], ["plan.json:0"], ["plan.json:1e3"], ["plan.json:-5"], ["plan.json:100", "plan.json:200"],
                      ["../x:100"], ["a/b:100"], [":100"], [f"plan.json:{artifact.MOST_BYTES + 1}"], ["plan.json:99999999999999"], ["plan.json: 100"]):
            with self.subTest(texts=texts), self.assertRaisesRegex(artifact.Refused, "NAME:BYTES"):
                artifact.members_of(texts)


class FakeGh:
    """A `gh` of the tests' own, first on the PATH: answers the two calls the tool makes, from files of the test."""

    def __init__(self, test, listing="", archive=b"", fail=""):
        self.folder = test.root / "bin"
        self.folder.mkdir()
        (test.root / "listing").write_text(listing)
        (test.root / "zip").write_bytes(archive)
        script = ("#!/bin/sh\n"
                  f'echo "$*" >> "{test.root}/calls"\n'
                  f'case "$*" in *{fail or "NOTHING-FAILS"}*) echo "gh: boom" >&2; exit 1;; esac\n'
                  f'case "$*" in */zip) cat "{test.root}/zip";; *) cat "{test.root}/listing";; esac\n')
        (self.folder / "gh").write_text(script)
        os.chmod(self.folder / "gh", 0o755)
        self.patch = mock.patch.dict(os.environ, {"PATH": f"{self.folder}{os.pathsep}{os.environ['PATH']}",
                                                  "GITHUB_REPOSITORY": "Bee-ruche/registre", "GITHUB_RUN_ID": "4242"})
        self.calls = test.root / "calls"

    def __enter__(self):
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()


def listing(*entries):
    return "".join(json.dumps(entry) + "\n" for entry in entries)


class TestFromGitHub(Base):
    def run_take(self, *extra):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as said:
            code = artifact.main(["take", "--name", "plan", "--member", "plan.json:1000", "--member", "candidates.bundle:100000",
                                  "--into", str(self.into), *extra])
        return code, said.getvalue()

    def test_the_runs_artifact_of_that_name_is_found_downloaded_and_taken(self):
        found = "\n" + listing({"id": 7, "name": "plan", "expired": False}, {"id": 9, "name": "plan", "expired": False}) + "  \n\n" \
            + listing({"id": 11, "name": "plan", "expired": True}, {"id": 12, "name": "plan-b", "expired": False})
        with FakeGh(self, found, zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE)])) as gh:
            code, said = self.run_take()
            calls = gh.calls.read_text().splitlines()
        self.assertEqual((code, (self.into / "plan.json").read_bytes(), (self.into / "candidates.bundle").read_bytes()), (0, PLAN, BUNDLE))
        self.assertEqual(calls, ["api --paginate repos/Bee-ruche/registre/actions/runs/4242/artifacts?per_page=100&name=plan "
                                 "--jq .artifacts[] | {id, name, expired}", "api repos/Bee-ruche/registre/actions/artifacts/9/zip"],
                         "this run's artifacts; the latest of that exact name that GitHub still holds")
        self.assertIn("took candidates.bundle, plan.json", said)
        self.assertEqual(list(Path(tempfile.gettempdir()).glob("artifact-*")), [], "the archive itself is not kept")

    def test_no_artifact_of_that_name_is_said_with_a_code_of_its_own(self):
        for found in ("", listing({"id": 12, "name": "plan-b", "expired": False}), listing({"id": 11, "name": "plan", "expired": True}),
                      listing({"id": 5, "name": "plan"})):
            with self.subTest(found), FakeGh(self, found) as gh:
                self.assertEqual((self.run_take()[0], gh.calls.read_text().count("\n"), self.into.exists()), (artifact.NOT_THERE, 1, False))
            for left in ("bin", "calls"):
                path = self.root / left
                path.unlink() if path.is_file() else __import__("shutil").rmtree(path)

    def test_an_answer_of_githubs_that_is_not_the_list_expected(self):
        for found in ("not json\n", "[]\n", listing({"id": "9", "name": "plan", "expired": False}), listing({"id": -1, "name": "plan", "expired": False}),
                      listing({"id": True, "name": "plan", "expired": False}), listing({"name": "plan", "expired": False}), "7\n",
                      listing({"id": 0, "name": "plan", "expired": False})):
            with self.subTest(found):
                with self.assertRaisesRegex(artifact.Refused, "unreadable"):
                    artifact.find("Bee-ruche/registre", "4242", "plan", api=lambda *args: found)

    def test_a_repository_a_run_or_a_name_that_is_not_one_is_never_put_in_a_request(self):
        def never(*args):
            raise AssertionError("asked GitHub")

        for repository, run_id, name in (("Bee-ruche/registre/../x", "1", "plan"), ("Bee-ruche", "1", "plan"), ("", "1", "plan"),
                                         ("Bee-ruche/registre", "1; rm", "plan"), ("Bee-ruche/registre", "", "plan"), ("Bee-ruche/registre", "-1", "plan"),
                                         ("Bee-ruche/registre", "1", "plan&name=x"), ("Bee-ruche/registre", "1", "../plan"), ("Bee-ruche/registre", "1", ""),
                                         (None, None, None)):
            with self.subTest(repository=repository, run_id=run_id, name=name), self.assertRaisesRegex(artifact.Refused, "not one"):
                artifact.find(repository, run_id, name, api=never)
        for repository, number in (("Bee-ruche/registre/x", 9), ("Bee-ruche/registre", "9"), ("Bee-ruche/registre", 0), ("Bee-ruche/registre", True),
                                   (None, 9), ("", 9)):
            with self.subTest(repository=repository, number=number), self.assertRaisesRegex(artifact.Refused, "not one"):
                artifact.download(repository, number, self.root / "never.zip", 1000)
        self.assertFalse((self.root / "never.zip").exists())

    def test_github_failing_is_a_refusal_not_a_crash(self):
        found = listing({"id": 9, "name": "plan", "expired": False})
        with FakeGh(self, found, zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE)]), fail="/zip"):
            code, said = self.run_take()
        self.assertEqual((code, self.into.exists()), (1, False))
        self.assertIn("refused: the download failed", said)
        self.assertNotIn("boom", said, "what gh prints is not repeated")

    def test_github_not_listing_the_runs_artifacts_is_a_refusal_too(self):
        with FakeGh(self, listing({"id": 9, "name": "plan", "expired": False}), fail="artifacts?"):
            code, said = self.run_take()
        self.assertEqual((code, self.into.exists()), (1, False))
        self.assertIn("refused: gh api failed", said)
        self.assertNotIn("boom", said)

    def test_a_machine_without_gh_is_a_refusal_too(self):
        nowhere = self.root / "empty-bin"
        nowhere.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(nowhere), "GITHUB_REPOSITORY": "Bee-ruche/registre", "GITHUB_RUN_ID": "4242"}):
            code, said = self.run_take()
            self.assertEqual((code, self.into.exists()), (1, False))
            self.assertIn("refused: gh api: FileNotFoundError", said)
            with self.assertRaisesRegex(artifact.Refused, "the download failed .FileNotFoundError."):
                artifact.download("Bee-ruche/registre", 9, self.root / "never.zip", 1000)

    def test_an_archive_larger_than_its_members_may_be_is_not_downloaded_to_the_end(self):
        found = listing({"id": 9, "name": "plan", "expired": False})
        huge = zipped([("plan.json", PLAN), ("candidates.bundle", os.urandom(3 << 20))], zipfile.ZIP_STORED)
        self.assertGreater(len(huge), 1000 + 100000 + artifact.SLACK_BYTES)
        with FakeGh(self, found, huge):
            code, said = self.run_take()
        self.assertEqual((code, self.into.exists()), (1, False))
        self.assertIn("larger than this step takes", said)
        self.assertEqual(list(Path(tempfile.gettempdir()).glob("artifact-*")), [])

    def test_the_command_line(self):
        data = self.archive(zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE)]))
        self.assertEqual(self.run_take("--archive", str(data))[0], 0)
        self.assertEqual((self.into / "plan.json").read_bytes(), PLAN)
        code, said = self.run_take("--archive", str(data))
        self.assertEqual(code, 1, "the folder exists now")
        self.assertIn("refused", said)
        for members in (["plan.json"], ["plan.json:"], ["plan.json:0"], ["plan.json:1e3"], ["plan.json:-5"], ["plan.json:100", "plan.json:200"],
                        ["../x:100"], ["plan.json:99999999999999"]):
            with self.subTest(members=members), mock.patch("sys.stderr", new_callable=io.StringIO):
                arguments = ["take", "--name", "plan", "--into", str(self.root / "other"), "--archive", str(data)]
                for member in members:
                    arguments += ["--member", member]
                self.assertEqual((artifact.main(arguments), (self.root / "other").exists()), (1, False))


if __name__ == "__main__":
    unittest.main()
