#!/usr/bin/env python3
"""Tests of Bee's judge of the second kind (tools/judge/reference.py, docs/reference-judge.md).

  python3 tools/judge/test_reference.py                          what needs no container
  BEE_JUGE_INTEGRATION=1 python3 tools/judge/test_reference.py   + the whole judge, in containers, on the toy project
                                                                 (tools/judge/reference_toy/), honest and HOSTILE
  BEE_JUGE_RESEAU=host                                           the network of « docker build » (machines without a bridge)

The hostile units below are texts of C written here, built and run ONLY in the judge's containers.
"""

import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "hive"))

import reference  # noqa: E402
from lecture import Erreur, Panne, Refus  # noqa: E402

TOY = HERE / "reference_toy"
MANIFEST = json.loads((TOY / "bee/reference/project.json").read_text())
CONTAINERS = os.environ.get("BEE_JUGE_INTEGRATION") == "1" and shutil.which("docker")

UPPER = """#include "unit.h"

int answer(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)
{
    size_t i;
    if (n > cap)
        return 1;
    for (i = 0; i < n; i++) {
        if (in[i] > 127)
            return 1;
        out[i] = (in[i] >= 'a' && in[i] <= 'z') ? (unsigned char)(in[i] - 32) : in[i];
    }
    *len = n;
    return 0;
}
"""
SQUEEZE = """#include "unit.h"

int answer(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)
{
    size_t i, k = 0;
    for (i = 0; i < n && k < cap; i++) {
        if (in[i] == ' ' && k > 0 && out[k - 1] == ' ')
            continue;
        out[k++] = in[i];
    }
    *len = k;
    return 0;
}
"""


def hostile(before="", inside="", after_loop="", includes=""):
    """The honest « upper » with something added: `before` the function, `inside` at its start, `after_loop` before
    it answers."""
    text = UPPER.replace('#include "unit.h"\n', '#include "unit.h"\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'
                         '#include <unistd.h>\n#include <sys/stat.h>\n' + includes + before, 1)
    text = text.replace("    size_t i;\n", "    size_t i;\n" + inside, 1)
    return text.replace("    *len = n;\n", after_loop + "    *len = n;\n", 1)


WRONG_SOMETIMES = hostile(after_loop="    if (n > 40 && memchr(in, 'x', n)) out[0] ^= 1;\n")
CORPUS_ONLY = hostile(before="""static const char *known[] = {"", "a", "abc", "Hello, World", "two  spaces", "   lead and trail   ", "MiXeD 123 case"};
static int is_known(const unsigned char *in, size_t n)
{
    size_t k;
    for (k = 0; k < sizeof known / sizeof *known; k++)
        if (strlen(known[k]) == n && !memcmp(known[k], in, n))
            return 1;
    return 0;
}
""", after_loop="    if (!is_known(in, n)) memcpy(out, in, n);\n")
BUILD_BLOWS_UP = hostile(before="#define A0 1,1\n" + "".join(f"#define A{i} A{i - 1},A{i - 1}\n" for i in range(1, 34)) + "static int big[] = {A33};\n",
                         inside="    (void)big;\n")
NEVER_ANSWERS = hostile(inside="    for (;;) { }\n")
FLOOD = hostile(before="""static void fill(void)
{
    static char block[1 << 16];
    FILE *f = fopen("/answers/more", "wb");
    if (f) while (fwrite(block, 1, sizeof block, f) == sizeof block) { }
    { int more; for (more = 0; more < 128 && fwrite(block, 1, sizeof block, stdout) == sizeof block; more++) { } }
}
""", inside="    static int done; if (!done++) fill();\n")
LINK_FOR_ANSWERS = hostile(before="static void swap(void) { unlink(\"/answers/answers\"); if (symlink(\"/etc/hostname\", \"/answers/answers\")) _exit(9); }\n",
                           inside="    static int set; if (!set++) atexit(swap);\n")
PIPE_FOR_ANSWERS = hostile(before="static void swap(void) { unlink(\"/answers/answers\"); if (mkfifo(\"/answers/answers\", 0666)) _exit(9); }\n",
                           inside="    static int set; if (!set++) atexit(swap);\n")
ONE_BYTE_MORE = hostile(before="static void more(void) { FILE *f = fopen(\"/answers/answers\", \"ab\"); if (f) { fputc(0, f); fclose(f); } }\n",
                        inside="    static int set; if (!set++) atexit(more);\n")
RIGHT_AND_EXIT_7 = hostile(before="static void leave(void) { _exit(7); }\n", inside="    static int set; if (!set++) atexit(leave);\n")
READS_THE_ORIGINAL = ('#include "unit.h"\n#include "/src/reference/original.c"\n'
                      "int answer(const unsigned char *in, size_t n, unsigned char *out, size_t cap, size_t *len)\n"
                      "{ return original_upper(in, n, out, cap, len); }\n")
READS_THE_ORIGINAL_BESIDE = READS_THE_ORIGINAL.replace("/src/reference/original.c", "../reference/original.c")
KEEPS_STATE = hostile(inside="    static unsigned long calls;\n", after_loop="    if (++calls > 100 && n) out[0] ^= 1;\n")
# Right only where the unit lies at one distance, among many, from the driver's own code: the build moves it with the nonce.
ONE_LAYOUT_ONLY = hostile(before="extern int main(void);\n",
                          after_loop="    if (n && ((((unsigned long)answer - (unsigned long)main) >> 3) % 256) != 77) out[0] ^= 1;\n")
# Right one run in sixteen: it reads where the system put its stack, which is drawn at each run.
ONE_RUN_IN_SIXTEEN = hostile(inside="    static int coin; unsigned long here = (unsigned long)&here; if (!coin) coin = (((here >> 4) & 15) == 3) ? 1 : 2;\n",
                             after_loop="    if (coin == 2 && n) out[0] ^= 1;\n")


def write_tree(target, changes=None, source=TOY):
    """A copy of the toy at target, with `changes`: {relative path: text, bytes, None (removed) or a function of the tree}."""
    shutil.copytree(source, target, symlinks=True)
    for relative, content in (changes or {}).items():
        path = Path(target) / relative
        if callable(content):
            content(Path(target))
        elif content is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return Path(target)


def manifest_with(**changes):
    return json.dumps({**MANIFEST, **changes})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("BEE_TEST_TMP"))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.chmod(self.root, 0o755)


class TestTheManifest(Base):
    """The manifest is the project's, at its tip: data. Every field is checked before anything is done with it."""

    def test_the_toys_manifest_is_taken_as_it_is(self):
        manifest = reference.check_manifest(MANIFEST)
        self.assertEqual((manifest["units"]["upper"]["files"], manifest["variants"], manifest["image"]), (["port/upper.c"], 2, "common"))
        self.assertEqual(reference.read_manifest(str(TOY)), manifest)

    def test_anything_else_is_a_failure_to_judge(self):
        unit = MANIFEST["units"]["upper"]
        for wrong in ([], "x", {}, {**MANIFEST, "extra": 1}, {k: v for k, v in MANIFEST.items() if k != "runs"},
                      {**MANIFEST, "image": "ubuntu"}, {**MANIFEST, "image": "--privileged"}, {**MANIFEST, "image": 3}, {**MANIFEST, "image": None},
                      {**MANIFEST, "variants": 1}, {**MANIFEST, "runs": 1}, {**MANIFEST, "variants": 9}, {**MANIFEST, "variants": True},
                      {**MANIFEST, "variants": 2.0}, {**MANIFEST, "variants": "2"}, {**MANIFEST, "build_seconds": 0}, {**MANIFEST, "run_seconds": 0},
                      {**MANIFEST, "run_seconds": 301}, {**MANIFEST, "memory_mb": 0}, {**MANIFEST, "memory_mb": 63}, {**MANIFEST, "build_processes": 0},
                      {**MANIFEST, "build_processes": 7}, {**MANIFEST, "output_mb": 0}, {**MANIFEST, "unit_bytes": 0}, {**MANIFEST, "reference_seconds": -5},
                      {**MANIFEST, "reference": []}, {**MANIFEST, "reference": ["reference"]}, {**MANIFEST, "skeleton": ["harness"]},
                      {**MANIFEST, "skeleton": "harness"}, {**MANIFEST, "reference": ["/etc", "bee/reference"]},
                      {**MANIFEST, "reference": ["../x", "bee/reference"]}, {**MANIFEST, "reference": ["a/./b", "bee/reference"]},
                      {**MANIFEST, "reference": ["reference/", "bee/reference"]}, {**MANIFEST, "reference": [".git", "bee/reference"]},
                      {**MANIFEST, "reference": ["a b", "bee/reference"]}, {**MANIFEST, "reference": ["a,b", "bee/reference"]},
                      {**MANIFEST, "reference": ["reference", "reference", "bee/reference"]}, {**MANIFEST, "reference": [7, "bee/reference"]},
                      {**MANIFEST, "units": {}}, {**MANIFEST, "units": []}, {**MANIFEST, "units": {"Upper": unit}}, {**MANIFEST, "units": {"a-b": unit}},
                      {**MANIFEST, "units": {"": unit}}, {**MANIFEST, "units": {"x" * 33: unit}}, {**MANIFEST, "units": {"upper": []}},
                      {**MANIFEST, "units": {"upper": {**unit, "extra": 1}}}, {**MANIFEST, "units": {"upper": {k: v for k, v in unit.items() if k != "refuses"}}},
                      {**MANIFEST, "units": {"upper": {**unit, "refuses": 1}}}, {**MANIFEST, "units": {"upper": {**unit, "cases": 0}}},
                      {**MANIFEST, "units": {"upper": {**unit, "cases": 100001}}}, {**MANIFEST, "units": {"upper": {**unit, "case_bytes": 0}}},
                      {**MANIFEST, "units": {"upper": {**unit, "answer_bytes": 0}}}, {**MANIFEST, "units": {"upper": {**unit, "cases": 100000, "case_bytes": 65536}}},
                      {**MANIFEST, "units": {"upper": {**unit, "cases": 100000, "answer_bytes": 1 << 20}}}, {**MANIFEST, "units": {"upper": {**unit, "files": []}}},
                      {**MANIFEST, "units": {"upper": {**unit, "files": ["../x.c"]}}}, {**MANIFEST, "units": {"upper": {**unit, "files": ["/x.c"]}}},
                      # a unit's file is never the project's own, nor another unit's
                      {**MANIFEST, "units": {"upper": {**unit, "files": ["harness/unit.h"]}}}, {**MANIFEST, "units": {"upper": {**unit, "files": ["harness"]}}},
                      {**MANIFEST, "units": {"upper": {**unit, "files": ["reference/original.c"]}}}, {**MANIFEST, "units": {"upper": {**unit, "files": ["bee/x"]}}},
                      {**MANIFEST, "units": {"upper": {**unit, "files": ["bee"]}}}, {**MANIFEST, "units": {"upper": {**unit, "files": ["bee/reference/build-unit"]}}},
                      {**MANIFEST, "units": {"upper": unit, "other": unit}}, {**MANIFEST, "units": {"upper": unit, "other": {**unit, "files": ["port"]}}},
                      {**MANIFEST, "units": {"upper": unit, "other": {**unit, "files": ["port/upper.c/x"]}}}):
            with self.subTest(wrong=str(wrong)[-90:]), self.assertRaises(Erreur) as raised:
                reference.check_manifest(wrong)
            self.assertNotIsInstance(raised.exception, Panne)
        for number, text in enumerate((b"{", b"\xff", b"[" * 100000, b"null", b"")):
            tip = write_tree(self.root / f"tip{number}", {"bee/reference/project.json": text})
            with self.subTest(text=text[:10]), self.assertRaises(Erreur):
                reference.read_manifest(str(tip))
        gone = write_tree(self.root / "gone", {"bee/reference/project.json": None})
        linked = write_tree(self.root / "linked", {"bee/reference/project.json": lambda tree: (
            (tree / "bee/reference/project.json").unlink(), os.symlink(TOY / "bee/reference/project.json", tree / "bee/reference/project.json"))})
        large = write_tree(self.root / "large", {"bee/reference/project.json": manifest_with() + " " * reference.MANIFEST_BYTES})
        for tip in (gone, linked, large):
            with self.subTest(tip=tip.name), self.assertRaises(Erreur):
                reference.read_manifest(str(tip))

    def test_the_bounds_add_up_to_a_whole_judgements_worst_case(self):
        manifest = reference.check_manifest(MANIFEST)
        side = 3 * (60 + 10) + 2 * (3 * 60 + 10) + (10 + 10)
        self.assertEqual((reference.budget(manifest, True), reference.budget(manifest, False)), (side, side + 2 * (60 + 10) + 4 * (10 + 10)))
        longest = reference.check_manifest({**MANIFEST, **{name: cap for name, (_, cap) in reference.NUMBERS.items()}})
        self.assertEqual(reference.budget(longest, False), 3 * 910 + 2 * 2710 + 310 + 8 * 910 + 64 * 310, "every container at its cap, counted")


class TestTheFraming(unittest.TestCase):
    """The host checks what the project's own side wrote, builds what it expects, and never parses a candidate's file."""

    unit = {"cases": 3, "case_bytes": 4, "answer_bytes": 4, "refuses": True}

    def test_cases_exactly_the_count_within_the_bound_nothing_more(self):
        data = reference.frame_cases([b"", b"ab", b"abcd"])
        self.assertEqual(data, b"\0\0\0\0" + b"\2\0\0\0ab" + b"\4\0\0\0abcd")
        self.assertEqual(reference.parse_cases(data, self.unit), [b"", b"ab", b"abcd"])
        for wrong in (b"", data[:-1], data + b"\0", data + b"\0\0\0\0", reference.frame_cases([b"", b"ab"]), reference.frame_cases([b"", b"ab", b"abcde"]),
                      b"\xff\xff\xff\xff" + data[4:], reference.frame_cases([b"", b"ab", b"abcd", b"x"])):
            with self.subTest(wrong=wrong), self.assertRaises(Erreur):
                reference.parse_cases(wrong, self.unit)
        many = {**self.unit, "cases": 8}
        with self.assertRaisesRegex(Erreur, "over and over"):
            reference.parse_cases(reference.frame_cases([b"a"] * 8), many)
        self.assertEqual(len(reference.parse_cases(reference.frame_cases([b"a"] * 7 + [b"b"]), many)), 8, "two different cases among eight: enough to go on")

    def test_answers_one_per_case_in_order_well_framed(self):
        answers = [(0, b"AB"), (1, b""), (0, b"")]
        data = reference.frame_answers(answers)
        self.assertEqual(data, b"\0\0\0\0\0\2\0\0\0AB" + b"\1\0\0\0\1\0\0\0\0" + b"\2\0\0\0\0\0\0\0\0")
        self.assertEqual(reference.parse_answers(data, self.unit), answers)

        def framed(*records):
            return b"".join(struct.pack("<IBI", index, status, size) + body for index, status, size, body in records)

        for wrong in (b"", data[:-1], data + b"\0", framed((0, 0, 2, b"AB"), (1, 1, 0, b"")),  # one answer short
                      framed((0, 0, 2, b"AB"), (2, 1, 0, b""), (1, 0, 0, b"")),  # the indexes are positions
                      framed((1, 0, 2, b"AB"), (2, 1, 0, b""), (3, 0, 0, b"")),
                      framed((0, 0, 2, b"AB"), (1, 2, 0, b""), (2, 0, 0, b"")),  # a status that is neither
                      framed((0, 0, 2, b"AB"), (1, 1, 1, b"x"), (2, 0, 0, b"")),  # a refusal carries nothing
                      framed((0, 0, 5, b"ABCDE"), (1, 1, 0, b""), (2, 0, 0, b"")),  # longer than the unit's bound
                      framed((0, 0, 9, b"AB"), (1, 1, 0, b""), (2, 0, 0, b"")),  # a length beyond the file
                      framed((0, 0, 2, b"AB"), (1, 0, 0, b""), (2, 0, 0, b"")),  # the unit refuses some inputs: none here
                      framed((0, 1, 0, b""), (1, 1, 0, b""), (2, 1, 0, b""))):  # and not all of them
            with self.subTest(wrong=wrong), self.assertRaises(Erreur):
                reference.parse_answers(wrong, self.unit)
        never = {**self.unit, "refuses": False}
        self.assertEqual(reference.parse_answers(framed((0, 0, 1, b"A"), (1, 0, 0, b""), (2, 0, 1, b"B")), never), [(0, b"A"), (0, b""), (0, b"B")])
        with self.assertRaisesRegex(Erreur, "refuses nothing"):
            reference.parse_answers(data, never)
        with self.assertRaisesRegex(Erreur, "the same answer"):
            reference.parse_answers(framed((0, 0, 1, b"A"), (1, 0, 1, b"A"), (2, 0, 1, b"A")), never)
        self.assertEqual(reference.parse_answers(framed((0, 0, 1, b"A")), {**never, "cases": 1}), [(0, b"A")], "one case has one answer")


class TestTreesOnTheHost(Base):
    """What the judge reads of the two trees it is given: bytes, by paths it checks, nothing followed."""

    def test_only_the_units_files_may_differ(self):
        tip = write_tree(self.root / "tip")
        files = ["port/upper.c"]
        reference.only_the_unit_differs(str(tip), str(write_tree(self.root / "same")), files)
        reference.only_the_unit_differs(str(tip), str(write_tree(self.root / "written", {"port/upper.c": UPPER})), files)
        reference.only_the_unit_differs(str(tip), str(write_tree(self.root / "gone", {"port/upper.c": None})), files)

        def linked(relative, to):
            return lambda tree: ((tree / relative).unlink(), os.symlink(to, tree / relative))

        for name, changes in (("other-unit", {"port/squeeze.c": SQUEEZE}), ("driver", {"harness/unit_driver.c": "int main(void) { return 0; }\n"}),
                              ("manifest", {"bee/reference/project.json": manifest_with(runs=3)}), ("added", {"port/extra.c": "int x;\n"}),
                              ("added-folder", {"new/file": "x"}), ("removed", {"README.md": None}), ("same-size", {"README.md": (TOY / "README.md").read_text().replace("toy", "tOy", 1)}),
                              ("mode", {"README.md": lambda tree: os.chmod(tree / "README.md", 0o755)}), ("link", {"README.md": linked("README.md", "/etc/hostname")}),
                              ("link-to-itself", {"harness/unit.h": linked("harness/unit.h", "unit.h")}),
                              ("empty-folder", {"x": lambda tree: (tree / "newdir").mkdir()}),
                              ("pipe", {"x": lambda tree: os.mkfifo(tree / "pipe")})):
            candidate = write_tree(self.root / name, {"port/upper.c": UPPER, **changes})
            with self.subTest(change=name), self.assertRaisesRegex(Refus, "something else than its unit's files"):
                reference.only_the_unit_differs(str(tip), str(candidate), files)
        # a link the project itself holds is compared by where it points, and never followed
        with_link = write_tree(self.root / "tip-link", {"x": lambda tree: os.symlink("/etc/passwd", tree / "doc")})
        reference.only_the_unit_differs(str(with_link), str(write_tree(self.root / "cand-link", {"port/upper.c": UPPER}, source=with_link)), files)
        moved = write_tree(self.root / "cand-moved", {"x": lambda tree: ((tree / "doc").unlink(), os.symlink("/etc/shadow", tree / "doc"))}, source=with_link)
        with self.assertRaises(Refus):
            reference.only_the_unit_differs(str(with_link), str(moved), files)

    def test_paths_are_copied_as_bytes_and_nothing_is_followed(self):
        tip = write_tree(self.root / "tip")
        target = self.root / "copied"
        listed = reference.copy_paths(str(tip), ["harness", "bee/reference/build-unit"], str(target), Erreur)
        self.assertEqual(sorted(listed), ["bee/reference/build-unit", "harness/frames.h", "harness/generate.c", "harness/reference_driver.c",
                                          "harness/unit.h", "harness/unit_driver.c"])
        self.assertEqual((target / "harness/unit.h").read_bytes(), (TOY / "harness/unit.h").read_bytes())
        modes = {str(p.relative_to(target)): stat.S_IMODE(p.stat().st_mode) for p in target.rglob("*")}
        self.assertEqual((modes["bee/reference/build-unit"], modes["harness/unit.h"], modes["harness"], modes["bee/reference"]), (0o755, 0o644, 0o755, 0o755))
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "secret").write_text("host\n")

        def trapped(name, make):
            tree = write_tree(self.root / name)
            make(tree)
            return str(tree)

        for name, make, listed in (
                ("file-link", lambda t: ((t / "harness/unit.h").unlink(), os.symlink(outside / "secret", t / "harness/unit.h")), ["harness"]),
                ("file-link-named", lambda t: ((t / "harness/unit.h").unlink(), os.symlink(outside / "secret", t / "harness/unit.h")), ["harness/unit.h"]),
                ("folder-link", lambda t: (shutil.rmtree(t / "harness"), os.symlink(outside, t / "harness")), ["harness"]),
                ("folder-link-above", lambda t: (shutil.rmtree(t / "harness"), os.symlink(outside, t / "harness")), ["harness/secret"]),
                ("pipe", lambda t: os.mkfifo(t / "harness/pipe"), ["harness"]),
                ("missing", lambda t: None, ["harness/none.h"])):
            for blame in (Refus, Erreur):
                with self.subTest(trap=name, blame=blame.__name__), self.assertRaises(blame) as raised:
                    reference.copy_paths(trapped(f"{name}-{blame.__name__}", make), listed, str(self.root / f"to-{name}-{blame.__name__}"), blame)
                self.assertIs(type(raised.exception), blame)
        big = trapped("big", lambda t: (t / "port/upper.c").write_bytes(b"/" * 70000))
        with self.assertRaises(Refus):
            reference.copy_paths(big, ["port/upper.c"], str(self.root / "to-big"), Refus, file_limit=65536)
        self.assertEqual(reference.copy_paths(big, ["port/upper.c"], str(self.root / "to-big-2"), Refus, file_limit=70000), ["port/upper.c"])
        with self.assertRaises(Erreur):
            reference.copy_paths(big, ["port", "harness"], str(self.root / "to-big-3"), Erreur, limit=70100)


class TestWhatAnOutcomeMeans(unittest.TestCase):
    """The kind says what each container's outcome means, step by step: the isolation's own words are not verdicts."""

    def test_a_time_bound_or_an_exit_status_is_the_steps_to_blame_and_dockers_failure_never_is(self):
        class Docker:
            def __init__(self, outcome):
                self.outcome = outcome

            def launch(self, command, mounts, pids=2, entry=None, timeout_seconds=3600):
                self.asked = (command, mounts, pids, entry, timeout_seconds)
                if isinstance(self.outcome, Exception):
                    raise self.outcome
                return subprocess.CompletedProcess(command, self.outcome, b"", b"said ::warning:: \x1b[31m")

        for blame in (Refus, Erreur):
            with self.assertRaisesRegex(blame, r"the step: stopped at its time bound \(7 s\)") as raised:
                reference.launch(Docker(Refus("timeout of 7 s exceeded in the container (sh)")), ["sh"], [], 5, 7, blame, "the step")
            self.assertIs(type(raised.exception), blame)
            with self.assertRaisesRegex(blame, r"the step: exit status 137\. said : :warning: : \?\[31m") as raised:
                reference.launch(Docker(137), ["sh"], [], 5, 7, blame, "the step")
            self.assertIs(type(raised.exception), blame)
            with self.assertRaises(Panne):
                reference.launch(Docker(Panne("failure of the judge's machine")), ["sh"], [], 5, 7, blame, "the step")
        docker = Docker(0)
        self.assertEqual(reference.launch(docker, ["x"], [("a", "/a", True)], 9, 11, Refus, "s", entry=b"n\n").returncode, 0)
        self.assertEqual(docker.asked, (["x"], [("a", "/a", True)], 9, b"n\n", 11))

    def test_the_command_line(self):
        for wrong in (["--tip", "t", "--seed", "xyz"], ["--tip", "t", "--seed", "A" * 64], ["--tip", "t"]):
            with self.subTest(wrong=wrong), self.assertRaises(Erreur):
                reference.main(wrong)
        with mock.patch.object(reference, "image_of", return_value="sha256:" + "0" * 64) as image:
            self.assertEqual(reference.main(["--tip", str(TOY), "--image-only"]), 0)
        self.assertEqual(image.call_args[0][0]["image"], "common")


@unittest.skipUnless(CONTAINERS, "the whole judge: BEE_JUGE_INTEGRATION=1 and Docker")
class TestTheJudgeInContainers(Base):
    """The whole judge, in containers, on the toy project: honest units, then hostile ones."""

    def judge(self, candidate=None, unit="upper", files=None, tip=None, seed=None, budget=3600):
        """(exit status, the report, what the judge said) of one judgement, run as the base runs it."""
        self.count = getattr(self, "count", 0) + 1
        tip = tip or self.tip
        out = self.root / f"report-{self.count}.json"
        command = [sys.executable, "-B", str(HERE / "reference.py"), "--tip", str(tip), "--unit", unit, "--budget", str(budget), "--json", str(out),
                   "--workdir", str(self.root / "work")]
        for path in files or [f"port/{unit}.c"]:
            command += ["--task-file", path]
        command += ["--candidate", str(candidate)] if candidate else ["--tip-itself"]
        if seed:
            command += ["--seed", seed]
        ran = subprocess.run(command, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
        report = json.loads(out.read_text())
        self.assertEqual(report["code"], ran.returncode, ran.stderr)
        self.assertEqual(os.listdir(self.root / "work"), [], "nothing of a judgement stays")
        self.assertNotIn(str(self.root), Path("/proc/mounts").read_text(), "nothing stays mounted")
        return ran.returncode, report, ran.stderr

    def candidate(self, changes, tip=None):
        self.made = getattr(self, "made", 0) + 1
        return write_tree(self.root / f"candidate-{self.made}", changes, source=tip or self.tip)

    def setUp(self):
        super().setUp()
        self.tip = write_tree(self.root / "tip")

    def refused(self, text, said, **options):
        code, report, err = self.judge(self.candidate({"port/upper.c": text}, options.get("tip")), **options)
        self.assertEqual(code, 1, err)
        self.assertRegex(report["reason"], said)
        return report

    def test_an_honest_unit_is_right_and_the_tip_against_itself_too(self):
        code, report, err = self.judge(self.candidate({"port/upper.c": UPPER}))
        self.assertEqual((code, report["cases_compared"], report["builds"], report["runs"], report["seed_origin"], report["step"]),
                         (0, 300 * 2 * 2, 2, 4, "drawn", 9), err)
        code, other, err = self.judge(self.candidate({"port/squeeze.c": SQUEEZE}), unit="squeeze")
        self.assertEqual((code, other["cases_compared"]), (0, 1200), err)
        self.assertNotEqual(report["seed"], other["seed"], "each judgement draws its own")
        # the tip against itself: its unit is not written, and nothing is asked of it
        code, report, err = self.judge()
        self.assertEqual((code, report["cases_compared"], report["step"]), (0, 0, 6), err)
        # the same tip judged as a candidate is a candidate: its unit is asked, and aborts
        self.refused((TOY / "port/upper.c").read_text(), r"build 1, run 1 of unit upper: exit status")
        # once a unit is written at the tip, the tip against itself is still right, and so is a candidate that rewrites it
        written = write_tree(self.root / "written", {"port/upper.c": UPPER})
        self.assertEqual(self.judge(tip=written)[0], 0)
        self.assertEqual(self.judge(self.candidate({"port/upper.c": UPPER.replace("size_t i;", "size_t i = 0;")}, written), tip=written)[0], 0)

    def test_a_unit_wrong_on_some_inputs_or_right_on_the_corpus_only(self):
        self.refused(WRONG_SOMETIMES, "its answers are not the reference's")
        self.refused(CORPUS_ONLY, "its answers are not the reference's")
        self.refused(SQUEEZE, "its answers are not the reference's|output too large")  # another unit's code under this unit's name

    def test_a_unit_that_keeps_something_from_one_call_to_the_next(self):
        self.refused(KEEPS_STATE, "its answers are not the reference's")

    def test_a_unit_right_in_one_layout_only_and_a_build_that_ignores_the_nonce(self):
        self.refused(ONE_LAYOUT_ONLY, "its answers are not the reference's")
        deaf = write_tree(self.root / "deaf", {"bee/reference/build-unit": (
            "#!/bin/sh\nset -eu\nhead -c 64 > /dev/null\n"
            'cc -O1 -std=gnu99 -Wall -Wextra -I/src/harness -o /out/driver /src/harness/unit_driver.c "/src/port/$1.c"\n')})
        for candidate in (None, self.candidate({"port/upper.c": UPPER}, deaf)):
            code, report, err = self.judge(candidate, tip=deaf)
            self.assertEqual((code, report["step"]), (2, 3), err)
            self.assertIn("the same binary for two nonces", report["reason"])

    @unittest.skipIf(Path("/proc/sys/kernel/randomize_va_space").read_text().strip() == "0", "this machine draws no address")
    def test_a_unit_right_one_run_in_sixteen(self):
        self.refused(ONE_RUN_IN_SIXTEEN, "its answers are not the reference's")

    def test_what_a_unit_does_to_its_file_of_answers_or_its_exit(self):
        self.refused(LINK_FOR_ANSWERS, r"/answers/answers: invalid output \(link or special file\)")
        self.refused(PIPE_FOR_ANSWERS, r"/answers/answers: invalid output")
        self.refused(ONE_BYTE_MORE, "its answers are not the reference's")
        self.refused(RIGHT_AND_EXIT_7, "exit status 7")
        self.refused(FLOOD, "exit status|its answers are not the reference's|output too large")

    def test_a_build_that_reads_the_original_or_blows_up_and_a_unit_that_never_answers(self):
        self.refused(READS_THE_ORIGINAL, "the build of unit upper: exit status")
        self.refused(READS_THE_ORIGINAL_BESIDE, "the build of unit upper: exit status")
        quick = write_tree(self.root / "quick", {"bee/reference/project.json": manifest_with(build_seconds=20, run_seconds=3, memory_mb=128)})
        self.refused(BUILD_BLOWS_UP, r"the build of unit upper: (exit status|stopped at its time bound \(20 s\))", tip=quick)
        self.refused(NEVER_ANSWERS, r"build 1, run 1 of unit upper: stopped at its time bound \(3 s\)", tip=quick)

    def test_a_candidate_that_is_more_than_its_units_files_or_less(self):
        for changes, said in (({"port/upper.c": UPPER, "harness/frames.h": "#error\n"}, "something else than its unit's files"),
                              ({"port/upper.c": UPPER, "port/squeeze.c": SQUEEZE}, "something else than its unit's files"),
                              ({"port/upper.c": UPPER, "bee/reference/project.json": manifest_with(runs=3)}, "something else than its unit's files"),
                              ({"port/upper.c": None}, "No such file"),
                              ({"port/upper.c": lambda tree: ((tree / "port/upper.c").unlink(), os.symlink("../reference/original.c", tree / "port/upper.c"))},
                               "not a plain file or folder"),
                              ({"port/upper.c": UPPER + "/" * 70000 + "\n"}, "port/upper.c: output too large")):
            with self.subTest(said=said):
                code, report, err = self.judge(self.candidate(changes))
                self.assertEqual((code, report["step"]), (1, 1), err)
                self.assertIn(said, report["reason"])

    def test_what_is_the_projects_or_the_registrys_own_fault_is_a_failure_to_judge(self):
        honest = {"port/upper.c": UPPER}
        for name, changes, said, step in (
                ("no-cases", {"bee/reference/project.json": manifest_with(units={**MANIFEST["units"], "upper": {**MANIFEST["units"]["upper"], "cases": 0}})},
                 "cases: a whole number from 1", 1),
                ("no-time", {"bee/reference/project.json": manifest_with(run_seconds=0)}, "run_seconds: a whole number from 1", 1),
                ("image", {"bee/reference/project.json": manifest_with(image="ubuntu:latest")}, "the name of an image the registry holds", 1),
                ("broken-reference", {"reference/original.c": "#error broken\n"}, "the reference's build: exit status", 2),
                ("broken-skeleton", {"harness/unit.h": "#error broken\n"}, "the build of unit upper: exit status", 3),
                ("driver-fails", {"harness/unit_driver.c": "int main(void) { return 5; }\n"}, "the tip's driver, given no case: exit status 5", 3),
                ("generator-short", {"harness/generate.c": (TOY / "harness/generate.c").read_text().replace("for (i = 0; i < count; i++) {\n        unsigned char b[4]",
                                                                                                           "for (i = 1; i < count; i++) {\n        unsigned char b[4]")},
                 "fewer cases than the manifest's count", 5),
                ("never-refuses", {"reference/original.c": (TOY / "reference/original.c").read_text().replace("return 1; /* not ASCII: refused */", "{ }")},
                 "must hold a refusal and an answer", 5)):
            tip = write_tree(self.root / name, changes)
            for candidate in (self.candidate(honest, tip), None):
                with self.subTest(fault=name, candidate=bool(candidate)):
                    code, report, err = self.judge(candidate, tip=tip)
                    self.assertEqual((code, report["step"]), (2, step), err)
                    self.assertIn(said, report["reason"])
        # the task and the manifest must agree; the bounds must fit the time a judgement is given
        for options, said in (({"unit": "lower"}, "names no unit"), ({"files": ["port/"]}, "not exactly its unit's files"),
                              ({"files": ["port/upper.c", "port/squeeze.c"]}, "not exactly its unit's files"), ({"budget": 700}, "add up to 830 s")):
            code, report, err = self.judge(self.candidate(honest), **options)
            self.assertEqual((code, report["step"]), (2, 1), err)
            self.assertIn(said, report["reason"])
        self.assertEqual(self.judge(budget=610)[0], 0, "the tip against itself needs less")

    def test_what_fails_on_the_cases_drawn_fails_again_for_the_tip_with_the_same_seed(self):
        """A reference or a generator that fails on some draws: the candidate's judgement is a failure to judge, and
        the question about the tip, asked with that judgement's seed, fails too."""
        sour = write_tree(self.root / "sour", {"harness/generate.c": (TOY / "harness/generate.c").read_text().replace(
            "    state[0] |= 1;\n", "    state[0] |= 1;\n    if (seed[0] < '8')\n        return 3;\n")})
        low, high = "0" * 64, "f" * 64
        code, report, err = self.judge(self.candidate({"port/upper.c": UPPER}, sour), tip=sour, seed=low)
        self.assertEqual((code, report["step"], report["seed"], report["seed_origin"]), (2, 5, low, "given"), err)
        self.assertIn("the generator: exit status 3", report["reason"])
        self.assertEqual(self.judge(tip=sour, seed=low)[0], 2)
        self.assertEqual(self.judge(tip=sour, seed=high)[0], 0)
        code, report, err = self.judge(self.candidate({"port/upper.c": UPPER}, sour), tip=sour, seed=high)
        self.assertEqual((code, report["seed_origin"]), (0, "given"), "a reproduction: the base does not take it for a judgement")

    def test_through_the_base(self):
        """The judge as the hive's judging step makes it and calls it."""
        import hive
        judge = hive.judge_of(str(HERE.parent.parent), {"kind": "reference", "timeout_seconds": 1200}, str(self.root / "work"))
        task = {"id": "toy-0001", "files": ["port/upper.c"], "options": {"unit": "upper"}}
        trees = self.root / "trees"
        base = write_tree(trees / "base")
        answer = judge(base, write_tree(trees / "right", {"port/upper.c": UPPER}), task, "T" * 40, "C" * 40)
        self.assertEqual(answer, {"code": 0, "report": {"cases_compared": 1200, "builds": 2, "runs": 4}})
        self.assertEqual(judge(base, write_tree(trees / "wrong", {"port/upper.c": CORPUS_ONLY}), task, "T" * 40, "D" * 40), {"code": 1, "report": {}})
        self.assertEqual(judge(base, base, task, "T" * 40, "T" * 40), {"code": 0, "report": {"cases_compared": 0, "builds": 0, "runs": 0}})
        self.assertEqual(judge(base, base, {**task, "files": ["port/"]}, "T" * 40, "T" * 40)["code"], 2, "a task that is not its unit's files")


if __name__ == "__main__":
    unittest.main()
