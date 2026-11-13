#!/usr/bin/env python3
"""Tests of tools/hive/artifact.py: what a job that is about to hold a key takes from an earlier job's archive.
Every archive here is made by the tests; nothing is asked of GitHub (a `gh` of the tests' own stands in for it)."""
import io
import json
import os
import shutil
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
ONE = {"plan.json": 100}


class Pipe(io.RawIOBase):
    """Something that can only be written to, as the upload action writes its archive: zipfile then writes each
    member's sizes after its data, like that action does."""

    def __init__(self):
        self.data = bytearray()

    def writable(self):
        return True

    def write(self, block):
        self.data += block
        return len(block)


def zipped(entries, compression=zipfile.ZIP_DEFLATED, streamed=False):
    """The bytes of a zip that holds these (name or ZipInfo, bytes), in this order, as zipfile writes them."""
    buffer = Pipe() if streamed else io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z, mock.patch("warnings.warn"):  # (a name twice is only a warning)
        for name, data in entries:
            z.writestr(name, data)
    return bytes(buffer.data) if streamed else buffer.getvalue()


def end_of(data):
    """(where the end record is, the directory's size, the directory's offset) of an archive without comment."""
    at = len(data) - 22
    assert data[at:at + 4] == b"PK\x05\x06"
    return (at, *struct.unpack_from("<2L", data, at + 12))


def with_directory_at(data, offset):
    """The same archive, its end record saying the directory starts at `offset`."""
    data = bytearray(data)
    struct.pack_into("<L", data, len(data) - 6, offset)
    return bytes(data)


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

    def taken(self, data, members=ONE):
        """What was written for an archive that is accepted: {name: bytes}; the folder is removed for the next one."""
        folder = artifact.take(self.archive(data), members, self.into)
        self.assertEqual(folder, self.into)
        found = {path.name: path.read_bytes() for path in folder.iterdir()}
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in folder.iterdir()))
        shutil.rmtree(folder)
        return found

    def refused(self, data, members=None, saying=None):
        with self.assertRaises(artifact.Refused) as refusal:
            artifact.take(self.archive(data), members or WANTED, self.into)
        self.assertFalse(self.into.exists(), "nothing of a refused archive is left behind")
        self.assertEqual([path.name for path in self.root.iterdir() if path.name != "archive.zip"], [], "nor anywhere near")
        if saying:
            self.assertIn(saying, str(refusal.exception))
        return str(refusal.exception)


class TestTake(Base):
    def test_the_members_expected_are_written_under_their_names_and_nothing_else(self):
        for compression in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED):
            for streamed in (False, True):
                with self.subTest(compression=compression, streamed=streamed):
                    data = zipped([("candidates.bundle", BUNDLE), ("plan.json", PLAN)], compression, streamed)
                    self.assertEqual(self.taken(data, WANTED), {"plan.json": PLAN, "candidates.bundle": BUNDLE})
        self.assertEqual(self.taken(zipped([("verdicts.json", b"")]), {"verdicts.json": 1}), {"verdicts.json": b""}, "an empty file is a file")
        self.assertEqual(self.taken(zipped([("verdicts.json", b"")], streamed=True), {"verdicts.json": 1}), {"verdicts.json": b""})
        large = os.urandom(3 * artifact.BLOCK + 17) + b"\0" * (2 * artifact.BLOCK)  # several blocks, of both kinds
        for streamed in (False, True):
            self.assertEqual(self.taken(zipped([("plan.json", large)], streamed=streamed), {"plan.json": len(large)}), {"plan.json": large})

    def test_an_archive_as_the_upload_action_writes_it(self):
        """Each member: a header that leaves its sizes for later, its deflated data, then 16 bytes that give them."""
        data = zipped([("plan.json", PLAN)], streamed=True)
        flags, method, checksum, packed, unpacked = struct.unpack_from("<2H4x3L", data, 6)
        self.assertEqual((flags & 8, method, checksum, packed, unpacked), (8, 8, 0, 0, 0))
        at, _, offset = end_of(data)
        self.assertEqual(data[offset - 16:offset - 12], b"PK\x07\x08")
        self.assertEqual(self.taken(data), {"plan.json": PLAN})
        bare = with_directory_at(data[:offset - 16] + data[offset - 12:], offset - 4)  # the same, without those 16 bytes' own signature
        self.assertEqual(self.taken(bare), {"plan.json": PLAN})
        for label, wrong in (("sizes that are not the member's", data[:offset - 4] + b"\x01\0\0\0" + data[offset:]),
                             ("another signature", data[:offset - 16] + b"PK\x07\x09" + data[offset - 12:]),
                             ("cut by four bytes more", with_directory_at(data[:offset - 16] + data[offset - 8:], offset - 8)),
                             ("given twice", with_directory_at(data[:offset] + data[offset - 16:offset] + data[offset:], offset + 16)),
                             ("absent", with_directory_at(data[:offset - 16] + data[offset:], offset - 16))):
            with self.subTest(label):
                self.refused(wrong, ONE, saying="exactly")

    def test_one_member_more_and_the_archive_is_refused_whole(self):
        """The file a taken-over job would add: code, at the path the next step runs code from."""
        for extra in ("registry/tools/hive/hive.py", "hive.py", "x/../../registry/tools/hive/hive.py", "../hive.py",
                      "/home/runner/work/_actions/x/main.cjs", "..", "plan.json/", "plan.json/x", "PLAN.JSON", "plan.json ", "./plan.json",
                      "verdicts.json", "sub/"):
            for streamed in (False, True):
                with self.subTest(extra, streamed=streamed):
                    self.refused(zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE), (extra, b"import os\n")], streamed=streamed),
                                 saying="exactly")
        self.assertEqual(list(self.root.rglob("hive.py")) + list(self.root.parent.glob("hive.py")), [], "and written nowhere")

    def test_a_name_that_is_not_exactly_the_one_expected(self):
        for name in ("x/../plan.json", "./plan.json", "/plan.json", "plan.json/", "Plan.json", "plan.jsonx", "sub/plan.json", "plan.json\\",
                     "plan.jsoñ", "candidates.bundle"):
            with self.subTest(name):
                self.refused(zipped([(name, PLAN), ("candidates.bundle", BUNDLE)]), saying="exactly")

    def test_a_member_missing_or_given_twice(self):
        self.refused(zipped([("plan.json", PLAN)]), saying="exactly")
        self.refused(zipped([]), saying="exactly")
        self.refused(zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE), ("plan.json", b'{"protocol": 2}\n')]), saying="exactly")
        self.refused(zipped([("plan.json", PLAN), ("plan.json", PLAN)]), ONE, saying="exactly")
        self.refused(zipped([("plan.json", PLAN), ("plan.json", PLAN)]), {"plan.json": 100, "plan.jso": 100}, saying="exactly")
        self.refused(zipped([("a.json", PLAN), ("a.json", PLAN)]), {"a.json": 100, "b.json": 100}, saying="exactly")  # as many, as long: twice the same
        hidden = os.urandom(3 * artifact.BLOCK)  # after the end of a member's deflated data, more than one block of something else
        data = zipped([("plan.json", PLAN)])
        _, length, offset = end_of(data)
        out = bytearray(data[:offset] + hidden + data[offset:])
        for at in (18, len(out) - 22 - length + 20):  # the packed size, before the data and in the directory
            struct.pack_into("<L", out, at, offset - 39 + len(hidden))
        self.refused(with_directory_at(bytes(out), offset + len(hidden)), ONE, saying="plan.json: unreadable (bytes after the end of its data)")

    def test_a_name_cut_short_by_a_zero_byte_is_not_the_name_expected(self):
        """Readers stop a name at a zero byte: « plan.json » to one tool, something else to the next."""
        data = zipped([("plan.jsonXY", PLAN), ("candidates.bundle", BUNDLE)])
        self.assertEqual(data.count(b"plan.jsonXY"), 2)  # once before the member, once in the archive's directory
        data = data.replace(b"plan.jsonXY", b"plan.json\0Y")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(sorted(entry.filename for entry in z.infolist()), ["candidates.bundle", "plan.json"], "as a careless reader sees it")
        self.refused(data, saying="exactly")

    def test_a_member_larger_than_allowed(self):
        self.refused(zipped([("plan.json", b"x" * 101)]), ONE, saying="size allowed")
        self.assertEqual(self.taken(zipped([("plan.json", b"x" * 100)])), {"plan.json": b"x" * 100}, "exactly as large as allowed is taken")

    def test_a_member_that_says_it_is_smaller_than_it_is(self):
        """A few bytes that unfold into gigabytes: the size the archive declares is not believed, and what is written
        never exceeds it."""
        for streamed in (False, True):
            data = bytearray(zipped([("plan.json", b"\0" * (64 << 20))], streamed=streamed))
            self.assertLess(len(data), 100_000)
            at = data.rindex(b"PK\x01\x02")  # the archive's directory entry: the unpacked size is at offset 24
            self.assertEqual(struct.unpack_from("<L", data, at + 24)[0], 64 << 20)
            struct.pack_into("<L", data, at + 24, 50)
            if streamed:
                struct.pack_into("<L", data, at - 4, 50)  # and after the data
            else:
                struct.pack_into("<L", data, 22, 50)  # and in the header before the data
            written = []
            real = os.fdopen

            def spy(descriptor, *args):
                out = real(descriptor, *args)
                write = out.write
                out.write = lambda block: (written.append(len(block)), write(block))[1]
                return out

            with self.subTest(streamed=streamed), mock.patch.object(artifact.os, "fdopen", side_effect=spy):
                self.refused(bytes(data), ONE, saying="plan.json: larger than it says")
                self.assertLessEqual(sum(written), 50, "what it declared, and not one byte more, reached the disk")

    def test_a_member_whose_data_is_not_one_stream_from_its_first_byte_to_its_last(self):
        data = zipped([("plan.json", PLAN)])
        _, length, offset = end_of(data)
        start = 30 + len("plan.json")
        packed = offset - start
        hidden = b"PK\x03\x04 a member another reader would find here"

        def repacked(stream, unpacked=len(PLAN), checksum=zlib.crc32(PLAN), method=8):
            """The same one-member archive, its data replaced by `stream`."""
            out = bytearray(data[:start] + stream + data[offset:])
            for at in (14, len(out) - 22 - length + 16):  # checksum, packed and unpacked sizes: before the data, and in the directory
                struct.pack_into("<3L", out, at, checksum, len(stream), unpacked)
            for at in (8, len(out) - 22 - length + 10):
                struct.pack_into("<H", out, at, method)
            return with_directory_at(bytes(out), start + len(stream))

        self.assertEqual(self.taken(repacked(data[start:offset])), {"plan.json": PLAN}, "the helper rebuilds the archive it started from")
        self.refused(repacked(data[start:offset] + hidden), ONE, saying="plan.json: unreadable (bytes after the end of its data)")
        self.refused(repacked(data[start:offset - 1]), ONE, saying="plan.json: unreadable (its data ends before it does)")
        self.refused(repacked(b"\xff" * packed), ONE, saying="plan.json: unreadable (not deflated data)")
        self.refused(repacked(b""), ONE, saying="plan.json: unreadable (its data ends before it does)")
        self.refused(repacked(data[start:offset], unpacked=len(PLAN) + 1), ONE, saying="its size or its checksum")
        self.refused(repacked(data[start:offset], checksum=zlib.crc32(PLAN) ^ 1), ONE, saying="its size or its checksum")
        self.assertEqual(self.taken(repacked(PLAN, method=0)), {"plan.json": PLAN}, "stored: its bytes as they are")
        self.refused(repacked(PLAN + hidden, method=0), ONE, saying="plain member")  # stored, and longer than it says
        self.refused(repacked(PLAN[:-1] + b"X", method=0), ONE, saying="its size or its checksum")

    def test_every_byte_of_the_archive_is_one_of_its_members(self):
        """What another reader of the same file could find and this one would not: a member no directory lists, a
        second archive, a second directory, a comment. Each is refused."""
        one = zipped([("plan.json", PLAN)])
        other = zipped([("plan.json", b'{"protocol": 666}\n')])
        at, length, offset = end_of(one)
        unlisted = zipped([("hive.py", b"import os\n")])[:-22 - (46 + 7)]  # a member's header and data, and no directory
        shifted = bytearray(unlisted + one)  # the listed member no longer starts the file
        struct.pack_into("<L", shifted, len(shifted) - 6, offset + len(unlisted))
        struct.pack_into("<L", shifted, len(shifted) - 22 - length + 42, len(unlisted))
        with zipfile.ZipFile(io.BytesIO(bytes(shifted))) as z:
            self.assertEqual(z.read("plan.json"), PLAN, "an archive like any other, for a reader that goes by the directory")
        commented = bytearray(one + other[end_of(other)[2]:])  # the first archive's end record, with the second's directory as its « comment »
        struct.pack_into("<H", commented, at + 20, len(other) - end_of(other)[2])
        cases = {"a member no directory lists, before the one it lists": bytes(shifted),
                 "a member no directory lists, after it": with_directory_at(one[:offset] + unlisted + one[offset:], offset + len(unlisted)),
                 "a whole archive in front": other + one,
                 "a whole archive behind": one + other,
                 "bytes behind": one + b"\0",
                 "a comment that is another directory and end record": bytes(commented),
                 "a comment": one[:-2] + b"\x05\0hello",
                 "a comment announced, and not there": one[:-2] + b"\x05\0",
                 "bytes at the end of the directory, counted in it": (lambda out: (struct.pack_into("<L", out, len(out) - 10, length + 3), bytes(out))[1])(
                     bytearray(one[:at] + b"\0\0\0" + one[at:])),
                 "one byte between the member and the directory": with_directory_at(one[:offset] + b"\0" + one[offset:], offset + 1),
                 "one byte between the directory and the end": one[:at] + b"\0" + one[at:]}
        for label, data in cases.items():
            with self.subTest(label):
                self.assertIn(self.refused(data, ONE), ("the archive does not hold exactly the members expected", "not an archive this step reads"))

    def test_the_header_before_a_member_says_what_the_directory_says(self):
        data = zipped([("plan.json", PLAN)])
        _, length, offset = end_of(data)
        entry = len(data) - 22 - length

        def changed(at, packing, value):
            out = bytearray(data)
            struct.pack_into(packing, out, at, value)
            return bytes(out)

        for label, wrong in (("another name before the data", data[:30] + b"plan.jsoN" + data[39:]),
                             ("another method", changed(8, "<H", 0)), ("other flags", changed(6, "<H", 0x800)),
                             ("another checksum", changed(14, "<L", 7)), ("another packed size", changed(18, "<L", 7)),
                             ("another unpacked size", changed(22, "<L", 7)), ("a longer name", changed(26, "<H", 10)),
                             ("an extra field", changed(28, "<H", 4)), ("another signature", changed(0, "<4s", b"PK\x03\x05")),
                             ("the directory's signature", changed(entry, "<4s", b"PK\x01\x03")),
                             ("an extra field in the directory", changed(entry + 30, "<H", 4)),
                             ("a comment in the directory", changed(entry + 32, "<H", 4)),
                             ("another disk", changed(entry + 34, "<H", 1)), ("an offset that is not the member's", changed(entry + 42, "<L", 1)),
                             ("the end record: another disk", changed(len(data) - 18, "<H", 1)),
                             ("the end record: the directory on another disk", changed(len(data) - 16, "<H", 1)),
                             ("the end record: more entries here", changed(len(data) - 14, "<H", 2)),
                             ("the end record: more entries in all", changed(len(data) - 12, "<H", 2)),
                             ("the end record: a longer directory", changed(len(data) - 10, "<L", length + 1)),
                             ("the end record: a directory elsewhere", changed(len(data) - 6, "<L", offset - 1))):
            with self.subTest(label):
                self.refused(wrong, ONE, saying="exactly")
        for label, wrong in (("sizes left for later, and never given", changed(6, "<H", 8)),):
            with self.subTest(label):
                self.refused(wrong, ONE, saying="exactly")
        self.assertEqual(self.taken(changed(4, "<H", 63)), {"plan.json": PLAN}, "the version a member says it needs is not this tool's affair")

    def test_two_entries_of_the_directory_for_one_member(self):
        """A directory can point twice at the same bytes, or at members in another order than it lists them."""
        data = zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE)])
        self.assertEqual(self.taken(data, WANTED), {"plan.json": PLAN, "candidates.bundle": BUNDLE})
        _, length, offset = end_of(data)
        first, second = offset, offset + 46 + len("plan.json")
        swapped = data[:offset] + data[second:offset + length] + data[first:second] + data[offset + length:]
        self.assertEqual(self.taken(swapped, WANTED), {"plan.json": PLAN, "candidates.bundle": BUNDLE}, "listed in another order: the same archive")
        same = bytearray(data)
        struct.pack_into("<L", same, second + 42, 0)  # the second entry points at the first member
        self.refused(bytes(same), saying="exactly")

    def test_an_archive_of_another_kind(self):
        with zipfile.ZipFile(io.BytesIO(), "w") as z:
            pass
        big = io.BytesIO()
        with zipfile.ZipFile(big, "w") as z, z.open("plan.json", "w", force_zip64=True) as member:
            member.write(PLAN)
        self.refused(big.getvalue(), ONE, saying="exactly")  # sizes of eight bytes, in an « extra field »
        many = zipped([(f"m{i}", b"") for i in range(70000)])  # more members than an end record can count: a second, larger one
        self.refused(many, ONE, saying="exactly")

    def test_a_directory_of_a_million_entries_costs_nothing_to_refuse(self):
        """What reading an archive costs is set by what was asked for, never by what the archive says of itself."""
        import tracemalloc
        entry = struct.pack("<4s6H3L5H2L", b"PK\x01\x02", 20, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        count = 1_000_000
        data = entry * count + struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, count & 0xFFFF, count & 0xFFFF, len(entry) * count, 0, 0)
        path = self.archive(data)
        del data
        tracemalloc.start()
        try:
            with self.assertRaisesRegex(artifact.Refused, "exactly"):
                artifact.take(path, ONE, self.into)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 1 << 20, "the directory was not read")
        one = struct.pack("<4s6H3L5H2L", b"PK\x01\x02", 20, 20, 0, 0, 0, 0, 0, 0, 0, 9, 0, 0, 0, 0, 0, 0) + b"plan.json"
        lying = one * 1000 + struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, len(one) * 1000, 0, 0)  # « one entry », and a thousand
        self.refused(lying, ONE, saying="exactly")

    def test_a_member_that_is_not_a_plain_stored_or_deflated_file(self):
        encrypted = bytearray(zipped([("plan.json", PLAN)]))
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):  # the « encrypted » bit, in both places
            at = encrypted.index(signature) + offset
            struct.pack_into("<H", encrypted, at, struct.unpack_from("<H", encrypted, at)[0] | 1)
        self.refused(bytes(encrypted), ONE, saying="plain member")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_BZIP2), ONE, saying="plain member")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_LZMA), ONE, saying="plain member")
        hinted = bytearray(zipped([("plan.json", PLAN)]))
        for at in (6, hinted.rindex(b"PK\x01\x02") + 8):  # a hint about how hard it was compressed, and a name said to be UTF-8
            struct.pack_into("<H", hinted, at, 0x0806)
        self.assertEqual(self.taken(bytes(hinted)), {"plan.json": PLAN})

    def test_a_member_marked_as_a_link_is_written_as_a_file(self):
        link = zipfile.ZipInfo("verdicts.json")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        artifact.take(self.archive(zipped([(link, b"/etc/passwd")])), {"verdicts.json": 100}, self.into)
        written = self.into / "verdicts.json"
        self.assertTrue(written.is_file() and not written.is_symlink())
        self.assertEqual((written.read_bytes(), stat.S_IMODE(written.stat().st_mode) & 0o133), (b"/etc/passwd", 0), "its bytes, and no right to run it")

    def test_what_is_not_an_archive(self):
        whole = zipped([("plan.json", PLAN)])
        for data in (b"", b"PK", b"not a zip at all\n" * 100, whole[:-8], whole[:30], b"\0" * 4096, whole[:21], b"PK\x05\x06" + b"\0" * 17):
            with self.subTest(length=len(data)):
                self.refused(data, ONE, saying="not an archive")
        with self.assertRaisesRegex(artifact.Refused, "not an archive this step reads .FileNotFoundError."):
            artifact.take(self.root / "absent.zip", ONE, self.into)
        self.assertFalse(self.into.exists())

    def test_a_member_whose_bytes_were_changed_after_it_was_packed(self):
        data = bytearray(zipped([("plan.json", PLAN)], zipfile.ZIP_STORED))
        at = data.index(PLAN)
        data[at] ^= 0xFF
        self.refused(bytes(data), ONE, saying="plan.json: unreadable (its size or its checksum")

    def test_a_folder_that_exists_is_not_written_into_and_one_whose_parent_does_not_is_not_made(self):
        """Nor through a link someone left where the folder was to be."""
        data = zipped([("plan.json", PLAN)])
        self.into.mkdir()
        (self.into / "kept").write_text("someone's\n")
        with self.assertRaisesRegex(artifact.Refused, "exists already"):
            artifact.take(self.archive(data), ONE, self.into)
        self.assertEqual([p.name for p in self.into.iterdir()], ["kept"], "and an existing folder is not removed either")
        elsewhere, link = self.root / "elsewhere", self.root / "link"
        elsewhere.mkdir()
        link.symlink_to(elsewhere)
        with self.assertRaisesRegex(artifact.Refused, "exists already"):
            artifact.take(self.archive(data), ONE, link)
        self.assertEqual(list(elsewhere.iterdir()), [])
        with self.assertRaisesRegex(artifact.Refused, "cannot be made"):
            artifact.take(self.archive(data), ONE, self.root / "no" / "such" / "parent")
        self.assertFalse((self.root / "no").exists(), "a refusal leaves no folder behind, its own or a parent's")

    def test_the_members_asked_for_are_plain_names_with_a_size(self):
        data = zipped([("plan.json", PLAN)])
        for members in ({}, {"../plan.json": 100}, {"a/b": 100}, {"": 100}, {".hidden": 100}, {"plan.json": 0}, {"plan.json": -1},
                        {"plan.json": "100"}, {"plan.json": artifact.MOST_BYTES + 1}, {"plan.json": True}, {7: 100}):
            with self.subTest(members=members), self.assertRaisesRegex(artifact.Refused, "plain file names"):
                artifact.take(self.archive(data), members, self.into)
            self.assertFalse(self.into.exists())
        self.assertEqual(self.taken(data, {"plan.json": artifact.MOST_BYTES}), {"plan.json": PLAN}, "the largest size there is")

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
