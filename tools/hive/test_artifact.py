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
LOCAL, ENTRY, END, AFTER = artifact.LOCAL, artifact.ENTRY, artifact.END, artifact.AFTER


def deflated(data, level=6):
    squeeze = zlib.compressobj(level, zlib.DEFLATED, -15)
    return squeeze.compress(data) + squeeze.flush()


def member(name, data=b"", **changes):
    """One member as the upload action writes it, described field by field so that a test can change one of them."""
    stream = deflated(data) if changes.get("stream") is None else changes.pop("stream")
    changes.pop("stream", None)
    if "local_name" in changes:  # the name in front of the data, when a test wants it to differ from the directory's
        changes.setdefault("entry_name", name.encode())
        name = changes.pop("local_name").decode("latin-1")
    return {"name": name.encode("latin-1"), "stream": stream, "checksum": zlib.crc32(data), "packed": len(stream), "unpacked": len(data),
            "signature": b"PK\x03\x04", "version": 20, "flags": 8, "method": 8, "figures": (0, 0, 0), "name_length": None, "extra": b"",
            "extra_length": None, "after": None, "then": b"",
            "entry_signature": b"PK\x01\x02", "entry_flags": None, "entry_method": None, "entry_name": None, "entry_name_length": None,
            "entry_extra": b"", "entry_extra_length": None, "entry_comment": b"", "entry_comment_length": None, "disk": 0,
            "attributes": 0o100644 << 16, "offset": None, **changes}


def packed(members, order=None, before_directory=b"", before_end=b"", comment=b"", tail=b"", **record):
    """The bytes of an archive of these members: each a header, its data, sixteen bytes of sizes; the directory; the
    end record. `record` changes fields of the end record; the other arguments add bytes where there should be none."""
    out, entries = bytearray(), []
    for m in members:
        start = len(out)
        out += LOCAL.pack(m["signature"], m["version"], m["flags"], m["method"], 0, 0, *m["figures"],
                          len(m["name"]) if m["name_length"] is None else m["name_length"],
                          len(m["extra"]) if m["extra_length"] is None else m["extra_length"])
        out += m["name"] + m["extra"] + m["stream"]
        out += AFTER.pack(b"PK\x07\x08", m["checksum"], m["packed"], m["unpacked"]) if m["after"] is None else m["after"]
        out += m["then"]
        name = m["name"] if m["entry_name"] is None else m["entry_name"]
        entries.append(ENTRY.pack(m["entry_signature"], 0x0314, m["version"], m["flags"] if m["entry_flags"] is None else m["entry_flags"],
                                  m["method"] if m["entry_method"] is None else m["entry_method"], 0, 0, m["checksum"], m["packed"], m["unpacked"],
                                  len(name) if m["entry_name_length"] is None else m["entry_name_length"],
                                  len(m["entry_extra"]) if m["entry_extra_length"] is None else m["entry_extra_length"],
                                  len(m["entry_comment"]) if m["entry_comment_length"] is None else m["entry_comment_length"],
                                  m["disk"], 0, m["attributes"], start if m["offset"] is None else m["offset"])
                       + name + m["entry_extra"] + m["entry_comment"])
    out += before_directory
    directory = b"".join(entries[i] for i in (order or range(len(entries))))
    fields = {"signature": b"PK\x05\x06", "disk": 0, "first": 0, "here": len(members), "total": len(members), "length": len(directory),
              "offset": len(out), "comment": len(comment), **{"comment" if key == "comment_length" else key: value for key, value in record.items()}}
    out += directory + before_end + END.pack(*(fields[key] for key in ("signature", "disk", "first", "here", "total", "length", "offset", "comment")))
    return bytes(out + comment + tail)


class Pipe(io.RawIOBase):
    """Something that can only be written to: Python's own zip writer then writes each member's sizes after its data."""

    def __init__(self):
        self.data = bytearray()

    def writable(self):
        return True

    def write(self, block):
        self.data += block
        return len(block)


def zipped(entries, compression=zipfile.ZIP_DEFLATED, streamed=True):
    """The bytes of a zip that holds these (name or ZipInfo, bytes), as Python's zipfile writes them: to a pipe
    (`streamed`: the layout the upload action writes too) or to a file (sizes in the headers, nothing after the data)."""
    buffer = Pipe() if streamed else io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as z, mock.patch("warnings.warn"):  # (a name twice is only a warning)
        for name, data in entries:
            z.writestr(name, data)
    return bytes(buffer.data) if streamed else buffer.getvalue()


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
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in folder.iterdir()))
        found = {path.name: path.read_bytes() for path in folder.iterdir()}
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
        both = [member("candidates.bundle", BUNDLE), member("plan.json", PLAN)]
        self.assertEqual(self.taken(packed(both), WANTED), {"plan.json": PLAN, "candidates.bundle": BUNDLE})
        self.assertEqual(self.taken(packed(both, order=[1, 0]), WANTED), {"plan.json": PLAN, "candidates.bundle": BUNDLE},
                         "listed in another order than they lie: the same archive")
        self.assertEqual(self.taken(packed([member("verdicts.json")]), {"verdicts.json": 1}), {"verdicts.json": b""}, "an empty file is a file")
        self.assertEqual(self.taken(packed([member("plan.json", PLAN, version=45)])), {"plan.json": PLAN}, "the version it says it needs: not this tool's affair")

    def test_the_archives_another_writer_makes_the_same_way(self):
        """Python's own zip writer, writing to a pipe: the same layout, from other hands."""
        self.assertEqual(self.taken(zipped([("candidates.bundle", BUNDLE), ("plan.json", PLAN)]), WANTED), {"plan.json": PLAN, "candidates.bundle": BUNDLE})
        self.assertEqual(self.taken(zipped([("verdicts.json", b"")]), {"verdicts.json": 1}), {"verdicts.json": b""})
        data = zipped([("plan.json", PLAN)])
        flags, method, checksum, size, unfolded_size = struct.unpack_from("<2H4x3L", data, 6)
        self.assertEqual((flags, method, checksum, size, unfolded_size), (8, 8, 0, 0, 0), "sizes left for after the data")

    def test_a_large_member_is_read_and_written_a_block_at_a_time(self):
        large = os.urandom(3 * artifact.BLOCK + 17) + b"\0" * (64 << 20)  # blocks that do not shrink, then 64 MiB that fold into a few KB
        written, real = [], os.fdopen

        def spy(descriptor, *args):
            out = real(descriptor, *args)
            write = out.write
            out.write = lambda block: (written.append(len(block)), write(block))[1]
            return out

        import tracemalloc
        for level in (6, 0, 9):
            path = self.archive(packed([member("plan.json", large, stream=deflated(large, level))]))
            written.clear()
            tracemalloc.start()
            try:
                with mock.patch.object(artifact.os, "fdopen", side_effect=spy):
                    folder = artifact.take(path, {"plan.json": len(large)}, self.into)
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            with self.subTest(level=level):
                self.assertEqual((sum(written), max(written) <= artifact.BLOCK), (len(large), True))
                self.assertLess(peak, 8 * artifact.BLOCK, "a few blocks in memory, whatever the member's size")
                with open(folder / "plan.json", "rb") as f:
                    self.assertEqual(zlib.crc32(f.read()), zlib.crc32(large))
            shutil.rmtree(folder)

    def test_a_block_at_a_time_at_the_two_places_where_that_could_lose_or_refuse_good_data(self):
        """One: the data is all read, and what it unfolds to is not all given yet. Two: a member's last bytes, which
        unfold to nothing, are cut in two by the end of a read, right after a call that gave all it may."""
        block = artifact.BLOCK
        pending = b"\0" * (block + 5)
        probe = zlib.decompressobj(-15)
        self.assertEqual((len(probe.decompress(deflated(pending), block)), probe.unconsumed_tail, probe.eof), (block, b"", False),
                         "all of it read, a block given, five bytes still to come")
        self.assertEqual(self.taken(packed([member("plan.json", pending)]), {"plan.json": len(pending)}), {"plan.json": pending})
        # Zeros that fold small, then random bytes in stored blocks, then an empty last block of five bytes: the sizes are chosen
        # so that the data unfolds to exactly two blocks and its five last bytes lie two before the end of the first read, three after.
        for zeros in range(block, block + 4000):
            squeeze = zlib.compressobj(6, zlib.DEFLATED, -15)
            head = squeeze.compress(b"\0" * zeros) + squeeze.flush(zlib.Z_FULL_FLUSH)  # ends on a byte, and is not the last block
            noise = 2 * block - zeros
            pieces = [noise - 65535 * (noise // 65535)] * (noise % 65535 > 0) + [65535] * (noise // 65535)
            if len(head) + noise + 5 * len(pieces) == block - 2:
                break
        else:
            self.fail("no such sizes")
        random = os.urandom(noise)
        stream, at = bytearray(head), 0
        for size in pieces:
            stream += b"\0" + struct.pack("<2H", size, size ^ 0xFFFF) + random[at:at + size]
            at += size
        stream += b"\x01\0\0\xff\xff"
        data = b"\0" * zeros + random
        self.assertEqual((len(stream), len(data), zlib.decompress(bytes(stream), -15) == data), (block + 3, 2 * block, True))
        self.assertEqual(self.taken(packed([member("plan.json", data, stream=bytes(stream))]), {"plan.json": len(data)}), {"plan.json": data})
        # And a whole read that unfolds to nothing (empty blocks, a megabyte of them) before the data: odd, and still one stream.
        slow = b"\0\0\0\xff\xff" * (block // 5 + 7) + b"\x01" + struct.pack("<2H", len(PLAN), len(PLAN) ^ 0xFFFF) + PLAN
        self.assertEqual(zlib.decompress(slow, -15), PLAN)
        self.assertEqual(self.taken(packed([member("plan.json", PLAN, stream=slow)])), {"plan.json": PLAN})

    def test_one_member_more_and_the_archive_is_refused_whole(self):
        """The file a taken-over job would add: code, at the path the next step runs code from."""
        for extra in ("registry/tools/hive/hive.py", "hive.py", "x/../../registry/tools/hive/hive.py", "../hive.py",
                      "/home/runner/work/_actions/x/main.cjs", "..", "plan.json/", "plan.json/x", "PLAN.JSON", "plan.json ", "./plan.json",
                      "verdicts.json", "sub/"):
            with self.subTest(extra):
                self.refused(packed([member("plan.json", PLAN), member("candidates.bundle", BUNDLE), member(extra, b"import os\n")]), saying="exactly")
                self.refused(zipped([("plan.json", PLAN), ("candidates.bundle", BUNDLE), (extra, b"import os\n")]), saying="exactly")
        self.assertEqual(list(self.root.rglob("hive.py")) + list(self.root.parent.glob("hive.py")), [], "and written nowhere")

    def test_a_name_that_is_not_exactly_the_one_expected(self):
        for name in ("x/../plan.json", "./plan.json", "/plan.json", "plan.json/", "Plan.json", "plan.jsonx", "sub/plan.json", "plan.json\\",
                     "plan.jso\xf1", "candidates.bundle", "plan.jso", ""):
            with self.subTest(name):
                self.refused(packed([member(name, PLAN), member("candidates.bundle", BUNDLE)]), saying="exactly")

    def test_a_member_missing_or_given_twice(self):
        plan, bundle = member("plan.json", PLAN), member("candidates.bundle", BUNDLE)
        self.refused(packed([plan]), saying="exactly")
        self.refused(packed([]), saying="exactly")
        self.refused(packed([plan, bundle, member("plan.json", b'{"protocol": 2}\n')]), saying="exactly")
        self.refused(packed([plan, plan]), ONE, saying="exactly")
        self.refused(packed([plan, plan]), {"plan.json": 100, "plan.jso": 100}, saying="exactly")
        self.refused(packed([member("a.json", PLAN), member("a.json", PLAN)]), {"a.json": 100, "b.json": 100}, saying="exactly")  # as many, as long

    def test_a_name_cut_short_by_a_zero_byte_or_said_longer_than_it_is(self):
        """Readers stop a name at a zero byte, or read it as long as its length says: « plan.json » to one tool,
        something else to the next."""
        zero = member("plan.json\0Y", PLAN)
        with zipfile.ZipFile(io.BytesIO(packed([zero]))) as z:
            self.assertEqual([entry.filename for entry in z.infolist()], ["plan.json"], "as a careless reader sees it")
        self.refused(packed([zero]), ONE, saying="exactly")
        self.refused(packed([zero]), {"plan.jsonXY": 100}, saying="exactly")
        longer = packed([member("plan.json", PLAN, entry_name_length=13)])  # the directory says 13 bytes of name: they run into the end record
        self.assertEqual(self.taken(packed([member("plan.json", PLAN)])), {"plan.json": PLAN})
        self.refused(longer, ONE, saying="exactly")
        self.refused(packed([member("plan.json", PLAN, entry_name_length=8)]), ONE, saying="exactly")
        self.refused(packed([member("plan.json", PLAN, entry_name_length=8)]), {"plan.jso": 100}, saying="exactly")
        self.refused(packed([member("plan.json", PLAN, name_length=8)]), ONE, saying="exactly")
        self.refused(packed([member("plan.json", PLAN, name_length=10)]), ONE, saying="exactly")

    def test_a_member_larger_than_allowed(self):
        self.refused(packed([member("plan.json", b"x" * 101)]), ONE, saying="plan.json: larger than allowed")
        self.assertEqual(self.taken(packed([member("plan.json", b"x" * 100)])), {"plan.json": b"x" * 100}, "exactly as large as allowed is taken")

    def test_a_member_that_says_it_is_smaller_than_it_is(self):
        """A few bytes that unfold into gigabytes: the size the archive declares is not believed, and what is written
        never exceeds it."""
        bomb = member("plan.json", b"\0" * (64 << 20), unpacked=50, checksum=zlib.crc32(b"\0" * 50))
        data = packed([bomb])
        self.assertLess(len(data), 100_000)
        written, real = [], os.fdopen

        def spy(descriptor, *args):
            out = real(descriptor, *args)
            write = out.write
            out.write = lambda block: (written.append(len(block)), write(block))[1]
            return out

        with mock.patch.object(artifact.os, "fdopen", side_effect=spy):
            self.refused(data, ONE, saying="plan.json: larger than it says")
        self.assertLessEqual(sum(written), 50, "what it declared, and not one byte more, reached the disk")

    def test_a_member_whose_data_is_not_one_stream_from_its_first_byte_to_its_last(self):
        stream, hidden = deflated(PLAN), b"PK\x03\x04 a member another reader would find here"

        def with_stream(data, **changes):
            return packed([member("plan.json", PLAN, stream=data, **changes)])

        self.assertEqual(self.taken(with_stream(stream)), {"plan.json": PLAN})
        self.refused(with_stream(stream + hidden), ONE, saying="plan.json: unreadable (bytes after the end of its data)")
        self.refused(with_stream(stream + os.urandom(3 * artifact.BLOCK)), ONE, saying="plan.json: unreadable (bytes after the end of its data)")
        self.refused(with_stream(stream[:-1]), ONE, saying="plan.json: unreadable (its data ends before it does)")
        self.refused(with_stream(b""), ONE, saying="plan.json: unreadable (its data ends before it does)")
        self.refused(with_stream(b"\xff" * len(stream)), ONE, saying="plan.json: unreadable (not deflated data)")
        self.refused(with_stream(stream, unpacked=len(PLAN) + 1), ONE, saying="its size or its checksum")
        self.refused(with_stream(stream, checksum=zlib.crc32(PLAN) ^ 1), ONE, saying="its size or its checksum")
        self.refused(with_stream(PLAN), ONE, saying="plan.json: ")  # its bytes as they are, not deflated
        changed = bytearray(with_stream(stream))
        changed[30 + len("plan.json") + 3] ^= 0x55  # one bit pattern of the data, after it was packed
        self.assertIn("plan.json: unreadable", self.refused(bytes(changed), ONE))

    def test_data_that_ends_exactly_where_a_block_read_ends(self):
        """The stream is over at the last byte of one read, and the member says its data goes on: what follows is
        never read as part of it."""
        pieces = [os.urandom(65535)] * 15 + [os.urandom(artifact.BLOCK - 15 * 65540 - 5)]  # stored blocks: 5 bytes of header each
        stream = b"".join(bytes([index == len(pieces) - 1]) + struct.pack("<2H", len(piece), len(piece) ^ 0xFFFF) + piece
                          for index, piece in enumerate(pieces))
        data = b"".join(pieces)
        self.assertEqual((len(stream), zlib.decompress(stream, -15)), (artifact.BLOCK, data))
        whole = {"plan.json": len(data)}
        self.assertEqual(self.taken(packed([member("plan.json", data, stream=stream)]), whole), {"plan.json": data})
        for hidden in (b"X", b"PK\x03\x04" + os.urandom(2 * artifact.BLOCK)):
            self.refused(packed([member("plan.json", data, stream=stream + hidden)]), whole, saying="plan.json: unreadable (bytes after the end of its data)")

    def test_every_byte_of_the_archive_is_one_of_its_members(self):
        """What another reader of the same file could find and this one would not: a member no directory lists, a
        second archive, a second directory, a comment. Each is refused."""
        plan = member("plan.json", PLAN)
        one, other = packed([plan]), packed([member("plan.json", b'{"protocol": 666}\n')])
        unlisted = packed([member("hive.py", b"import os\n")])
        unlisted = unlisted[:unlisted.index(b"PK\x01\x02")]  # a member's header, data and sizes, and no directory
        shifted = packed([member("hive.py", b"import os\n"), plan])
        cut = shifted.index(b"PK\x01\x02")
        entry = ENTRY.size + len("hive.py")
        hidden_before = bytearray(shifted[:cut] + shifted[cut + entry:])  # the directory lists the second member only
        END.pack_into(hidden_before, len(hidden_before) - END.size, b"PK\x05\x06", 0, 0, 1, 1, ENTRY.size + len("plan.json"), cut, 0)
        with zipfile.ZipFile(io.BytesIO(bytes(hidden_before))) as z:
            self.assertEqual(z.read("plan.json"), PLAN, "an archive like any other, for a reader that goes by the directory")
        second = other[other.index(b"PK\x01\x02"):]  # another archive's directory and end record
        cases = {"a member no directory lists, before the one it lists": bytes(hidden_before),
                 "a member no directory lists, after it": packed([plan], before_directory=unlisted),
                 "a member no directory lists, after it, counted in the one before": packed([member("plan.json", PLAN, then=unlisted)]),
                 "a whole archive in front": other + one,
                 "a whole archive behind": one + other,
                 "bytes behind": packed([plan], tail=b"\0"),
                 "a comment that is another directory and end record": packed([plan], comment=second),
                 "a comment": packed([plan], comment=b"hello"),
                 "a comment announced, and not there": packed([plan], comment_length=5),
                 "one byte between the member and the directory": packed([plan], before_directory=b"\0"),
                 "one byte between the directory and the end": packed([plan], before_end=b"\0"),
                 "bytes at the end of the directory, counted in it": packed([plan], before_end=b"\0\0\0", length=ENTRY.size + len("plan.json") + 3)}
        for label, data in cases.items():
            with self.subTest(label):
                self.assertIn(self.refused(data, ONE), ("the archive does not hold exactly the members expected", "not an archive this step reads"))

    def test_one_layout_and_no_other(self):
        """Each field as the upload action writes it. A reader that walks the file member by member, and one that goes
        by the directory, must see the same thing: any other spelling is refused, the harmless ones included."""
        sizes = (zlib.crc32(PLAN), len(deflated(PLAN)), len(PLAN))
        good = AFTER.pack(b"PK\x07\x08", *sizes)
        changes = {"another signature before the member": {"signature": b"PK\x03\x05"},
                   "no flag": {"flags": 0}, "a name said to be UTF-8": {"flags": 0x0808}, "a hint about the compression": {"flags": 0x000E},
                   "encrypted": {"flags": 0x0009}, "sizes not left for later": {"flags": 0, "figures": sizes, "after": b""},
                   "sizes given twice, before and after": {"figures": sizes},
                   "only a checksum before": {"figures": (sizes[0], 0, 0)},
                   "stored": {"method": 0, "stream": PLAN}, "another method": {"method": 12},
                   "stored, with sizes after the data that a reader walking the file would stop at":
                       {"method": 0, "stream": b"{}" + AFTER.pack(b"PK\x07\x08", zlib.crc32(b"{}"), 2, 2) + b"PK\x03\x04..." + PLAN},
                   "an extra field before the member": {"extra": b"\x75\x70\x05\x00\x01" + b"\0" * 4},
                   "an extra field announced before the member, and not there": {"extra_length": 4},
                   "no flag before the member only": {"flags": 0, "entry_flags": 8},
                   "a name said to be UTF-8 before the member only": {"flags": 0x0808, "entry_flags": 8},
                   "stored, before the member only": {"method": 0, "entry_method": 8},
                   "another name before the member": {"local_name": b"plan.jsoN"},
                   "the sizes after the data, without their signature": {"after": good[4:]},
                   "the sizes after the data, another signature": {"after": b"PK\x07\x09" + good[4:]},
                   "the sizes after the data, not the member's": {"after": good[:-4] + b"\x01\0\0\0"},
                   "the checksum after the data, not the member's": {"after": good[:4] + b"\x01\0\0\0" + good[8:]},
                   "nothing after the data": {"after": b""}, "the sizes twice": {"after": good + good},
                   "another signature in the directory": {"entry_signature": b"PK\x01\x03"},
                   "other flags in the directory": {"entry_flags": 0x0808}, "no flag in the directory": {"entry_flags": 0},
                   "another method in the directory": {"entry_method": 0},
                   "an extra field in the directory": {"entry_extra": b"\x75\x70\x05\x00\x01" + b"\0" * 4},
                   "an extra field announced in the directory, and not there": {"entry_extra_length": 4},
                   "a comment in the directory": {"entry_comment": b"hello"},
                   "a comment announced in the directory, and not there": {"entry_comment_length": 4}, "another disk": {"disk": 1},
                   "an offset that is not the member's": {"offset": 1}}
        for label, change in changes.items():
            with self.subTest(label):
                self.refused(packed([member("plan.json", PLAN, **change)]), ONE, saying="exactly")
        for label, record in (("another disk", {"disk": 1}), ("the directory on another disk", {"first": 1}), ("more entries here", {"here": 2}),
                              ("more entries in all", {"total": 2}), ("no entry", {"here": 0, "total": 0}),
                              ("a longer directory", {"length": ENTRY.size + len("plan.json") + 1}),
                              ("a directory elsewhere", {"offset": 1})):
            with self.subTest("the end record: " + label):
                self.refused(packed([member("plan.json", PLAN)], **record), ONE, saying="exactly")
        self.assertEqual(self.refused(packed([member("plan.json", PLAN)], signature=b"PK\x05\x07"), ONE), "not an archive this step reads")

    def test_two_entries_of_the_directory_for_one_member(self):
        plan, bundle = member("plan.json", PLAN), member("candidates.bundle", BUNDLE, offset=0)  # the second entry points at the first member
        self.refused(packed([plan, bundle]), saying="exactly")
        self.refused(packed([plan, member("candidates.bundle", BUNDLE, offset=7)]), saying="exactly")
        whole = packed([plan])
        for elsewhere in (len(whole), len(whole) - 10, len(whole) + 4096, 0xFFFFFFFF):  # past the end, or inside the end record
            self.refused(packed([member("plan.json", PLAN, offset=elsewhere)]), ONE, saying="exactly")

    def test_an_archive_of_another_kind(self):
        """What Python's writer makes when it writes to a file, and what any writer makes for more than 4 GiB or 65,535
        members: other layouts, each a real zip, none the upload action's."""
        self.refused(zipped([("plan.json", PLAN)], streamed=False), ONE, saying="exactly")  # sizes in the header, nothing after the data
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_STORED), ONE, saying="exactly")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_STORED, streamed=False), ONE, saying="exactly")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_BZIP2), ONE, saying="exactly")
        self.refused(zipped([("plan.json", PLAN)], zipfile.ZIP_LZMA), ONE, saying="exactly")
        big = Pipe()
        with zipfile.ZipFile(big, "w", zipfile.ZIP_DEFLATED) as z, z.open("plan.json", "w", force_zip64=True) as inside:
            inside.write(PLAN)
        self.refused(bytes(big.data), ONE, saying="exactly")  # sizes of eight bytes
        many = zipped([(f"m{i}", b"") for i in range(70000)])  # more members than an end record can count: a second, larger one
        self.refused(many, ONE, saying="exactly")

    def test_a_directory_of_a_million_entries_costs_nothing_to_refuse(self):
        """What reading an archive costs is set by what was asked for, never by what the archive says of itself."""
        import tracemalloc
        entry = ENTRY.pack(b"PK\x01\x02", 20, 20, 8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        count = 1_000_000
        data = entry * count + END.pack(b"PK\x05\x06", 0, 0, count & 0xFFFF, count & 0xFFFF, len(entry) * count, 0, 0)
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
        one = ENTRY.pack(b"PK\x01\x02", 20, 20, 8, 8, 0, 0, 0, 0, 0, 9, 0, 0, 0, 0, 0, 0) + b"plan.json"
        lying = one * 1000 + END.pack(b"PK\x05\x06", 0, 0, 1, 1, len(one) * 1000, 0, 0)  # « one entry », and a thousand
        self.refused(lying, ONE, saying="exactly")

    def test_a_member_marked_as_a_link_is_written_as_a_file(self):
        link = member("verdicts.json", b"/etc/passwd", attributes=(stat.S_IFLNK | 0o777) << 16)
        artifact.take(self.archive(packed([link])), {"verdicts.json": 100}, self.into)
        written = self.into / "verdicts.json"
        self.assertTrue(written.is_file() and not written.is_symlink())
        self.assertEqual((written.read_bytes(), stat.S_IMODE(written.stat().st_mode) & 0o133), (b"/etc/passwd", 0), "its bytes, and no right to run it")

    def test_what_is_not_an_archive(self):
        whole = packed([member("plan.json", PLAN)])
        for data in (b"", b"PK", b"not a zip at all\n" * 100, whole[:-8], whole[:30], b"\0" * 4096, whole[:21], b"PK\x05\x06" + b"\0" * 17):
            with self.subTest(length=len(data)):
                self.refused(data, ONE, saying="not an archive")
        with self.assertRaisesRegex(artifact.Refused, "not an archive this step reads .FileNotFoundError."):
            artifact.take(self.root / "absent.zip", ONE, self.into)
        self.assertFalse(self.into.exists())

    def test_a_folder_that_exists_is_not_written_into_and_one_whose_parent_does_not_is_not_made(self):
        """Nor through a link someone left where the folder was to be."""
        data = packed([member("plan.json", PLAN)])
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
        data = packed([member("plan.json", PLAN)])
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
        with FakeGh(self, found, packed([member("plan.json", PLAN), member("candidates.bundle", BUNDLE)])) as gh:
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
        with FakeGh(self, found, packed([member("plan.json", PLAN), member("candidates.bundle", BUNDLE)]), fail="/zip"):
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
        huge = packed([member("plan.json", PLAN), member("candidates.bundle", os.urandom(3 << 20))])  # (random bytes do not shrink)
        self.assertGreater(len(huge), 1000 + 100000 + artifact.SLACK_BYTES)
        with FakeGh(self, found, huge):
            code, said = self.run_take()
        self.assertEqual((code, self.into.exists()), (1, False))
        self.assertIn("larger than this step takes", said)
        self.assertEqual(list(Path(tempfile.gettempdir()).glob("artifact-*")), [])

    def test_the_command_line(self):
        data = self.archive(packed([member("plan.json", PLAN), member("candidates.bundle", BUNDLE)]))
        self.assertEqual(self.run_take("--archive", str(data))[0], 0)
        self.assertEqual((self.into / "plan.json").read_bytes(), PLAN)
        code, said = self.run_take("--archive", str(data))
        self.assertEqual(code, 1, "the folder exists now")
        self.assertIn("refused", said)
        for members in (["plan.json"], ["plan.json:"], ["plan.json:0"], ["plan.json:1e3"], ["plan.json:-5"], ["plan.json:100", "plan.json:200"],
                        ["../x:100"], ["plan.json:99999999999999"]):
            with self.subTest(members=members), mock.patch("sys.stderr", new_callable=io.StringIO):
                arguments = ["take", "--name", "plan", "--into", str(self.root / "other"), "--archive", str(data)]
                for text in members:
                    arguments += ["--member", text]
                self.assertEqual((artifact.main(arguments), (self.root / "other").exists()), (1, False))


if __name__ == "__main__":
    unittest.main()
