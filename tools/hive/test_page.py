#!/usr/bin/env python3
"""Tests of the project page (tools/hive/page.py): the figures, what a hostile ledger cannot do, the empty state,
the same bytes for the same input, and one run on a ledger the hive itself wrote.

Standard library only, no network. `python3 tools/hive/test_page.py`
"""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock
from xml.dom import minidom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hive  # noqa: E402
import page  # noqa: E402
import test_hive  # noqa: E402  (World, Base, judge_by_content: a real ledger for the last test)

NOW = "2026-11-12T12:00:00Z"
JOIN = page.DEFAULT_JOIN_URL
MEMBER_HREF = re.compile(r"https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
COMMIT_HREF = re.compile(r"https://github\.com/Bee-ruche/toy/commit/[0-9a-f]{40}\Z")
WIN_HREF = re.compile(r"wins/[0-9a-f]{40}\.svg\Z")
# Every name the tool may write a file under, spelled here again: the tests do not rely on page.py's own patterns.
NAMED = re.compile(r"index\.html|badge\.svg|summary\.json|members/[1-9][0-9]{0,18}(?:-badge)?\.svg|wins/[0-9a-f]{40}\.svg")
# The elements an SVG of the tool may hold. « svg » is also a card's inner frame; « style » is there for one reason: a
# card must read on a light and on a dark page in ONE file, which takes a prefers-color-scheme rule. A style can also
# load and hide, so harmless() accepts one only when it is page.CARD_CSS, byte for byte, directly under the root.
SVG_TAGS = ("svg", "title", "style", "rect", "path", "text")
NEEDLES = ("<script", "onerror=", "onload=", "onmouseover", "javascript:", "<img", "../../etc", "alert(1)")
LOGINS = ('"><script>alert(1)</script>', 'a"onmouseover="x', "-dash", "a" * 40, "é", "a b", "a/b", "", "x\n")


def sha(number):
    return f"{number:040x}"


def verdict(number, at, login, member_id, task, result="accepted", judged=True, model=None, reason=None, **more):
    """A verdict line as the hive writes it (hive.verdict_event)."""
    event = {"type": "verdict", "at": at, "task": task, "member": login, "member_id": member_id, "repo_id": 1000 + number,
             "sha": sha(number), "result": result, "judged": judged, "model": model}
    if result == "accepted":
        event.update(commit=sha(5000 + number), figures={"files": 1, "lines": 3}, report={})
    else:
        event.update(reason=reason, detail={})
    return {**event, **more}


def failure(number, at, login, member_id, kind="judge"):
    event = {"type": "error", "at": at, "run": "0" * 32, "task": "toy-0001", "member": login, "member_id": member_id,
             "repo_id": 1000 + number, "sha": sha(number)}
    return {**event, **({"kind": kind} if kind else {})}


def mark(number):
    """A member's mark as the feed's deals carry it: 16 lowercase hex characters."""
    return f"{number:016x}"


def deal(task="toy-0005", at="2026-11-12T07:00:00Z", until="2026-11-13T07:00:00Z", candidate=True):
    return {"task": task, "at": at, "until": until, "candidate": candidate}


def feed(statuses, project="toy", titles=None, deals=None):
    return {"protocol": 1, "project": project, "tasks": [
        {"id": task, "title": (titles or {}).get(task, f"Title of {task}"), "files": ["lib.c"], "status": status, "tier": 1, "hint": 1}
        for task, status in statuses.items()], "deals": deals if deals is not None else {}, "wait": {}, "deals_per_day": 3}


def tree(root):
    """Every path under a folder, with each file's bytes: what a run may not change outside --out."""
    return {str(path.relative_to(root)): (path.read_bytes() if path.is_file() else None) for path in sorted(Path(root).rglob("*"))}


class Seen(HTMLParser):
    """What a browser would see in the page: the elements, their attributes, and the rows of its tables."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.attributes, self.hrefs, self.rows, self.cell = [], [], [], [], None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(name for name, _ in attrs)
        self.hrefs.extend(value for name, value in attrs if name in ("href", "src", "xlink:href", "action"))
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th") and self.rows:
            self.rows[-1].append("")
            self.cell = True

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.cell = None

    def handle_data(self, data):
        if self.cell:
            self.rows[-1][-1] += data

    def row(self, first):
        return next((row for row in self.rows if row and row[0] == first), None)


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state, self.out = self.root / "state" / "toy", self.root / "site"
        self.state.mkdir(parents=True)
        patch = mock.patch.dict(os.environ, {"HIVE_NOW": NOW})
        patch.start()
        self.addCleanup(patch.stop)

    def ledger(self, lines):
        """Writes the ledger: dicts as JSON, strings and bytes as they are (a broken line, on purpose)."""
        with open(self.state / "ledger.jsonl", "wb") as f:
            for line in lines:
                f.write((line if isinstance(line, bytes) else line.encode() if isinstance(line, str) else json.dumps(line).encode()) + b"\n")

    def put(self, name, data):
        (self.state / name).write_text(data if isinstance(data, str) else json.dumps(data))

    def tasks(self, lines):
        """Writes a task file as the registry keeps one (hive/tasks/<project>.jsonl) and returns its path: dicts as
        JSON, strings and bytes as they are."""
        path = self.root / "registry-tasks.jsonl"
        with open(path, "wb") as f:
            for line in lines:
                f.write((line if isinstance(line, bytes) else line.encode() if isinstance(line, str) else json.dumps(line).encode()) + b"\n")
        return str(path)

    def make(self, *options, out=None, code=None):
        """Runs the tool as the command line does; returns {file name: text} of what is under --out."""
        out = out or self.out
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            if code is None:
                page.main(["--state", str(self.state), "--out", str(out), *options])
            else:
                with self.assertRaises(SystemExit) as stopped:
                    page.main(["--state", str(self.state), "--out", str(out), *options])
                self.assertEqual(stopped.exception.code, code, errors.getvalue())
        return {str(path.relative_to(out)): path.read_text(encoding="utf-8") for path in sorted(Path(out).rglob("*")) if path.is_file()} \
            if Path(out).exists() else {}

    def summary(self, files):
        return json.loads(files["summary.json"])

    def harmless(self, files, join=JOIN):
        """What must hold for any output, whatever the ledger said: only the files this tool writes; no script, no
        handler, nothing loaded; no link but a member's profile, an integrated commit or the join page; SVGs that
        parse."""
        for name, text in files.items():
            self.assertTrue(NAMED.fullmatch(name), name)
            if name.endswith(".svg"):
                root = minidom.parseString(text.encode("utf-8")).documentElement
                self.assertEqual(root.tagName, "svg")
                self.assertTrue(root.getAttribute("width").isdigit() and root.getAttribute("height").isdigit(), "a fixed size")
                nodes = [root, *root.getElementsByTagName("*")]
                for node in nodes:
                    self.assertIn(node.tagName, SVG_TAGS, name)
                    for key in node.attributes.keys():
                        self.assertFalse(key.lower().startswith("on") or key.lower() in ("href", "xlink:href", "style", "src"), (name, key))
                styles = [node for node in nodes if node.tagName == "style"]
                self.assertLessEqual(len(styles), 1, name)
                for style in styles:
                    self.assertIs(style.parentNode, root, name)
                    self.assertEqual((len(style.childNodes), style.firstChild.data, len(style.attributes)), (1, str(page.CARD_CSS), 0), name)
                self.assertEqual((text.count("<style"), text.count(f"<style>{page.CARD_CSS}</style>")), (len(styles), len(styles)),
                                 "a style is the cards' constant, byte for byte, or it is not there")
                self.assertEqual(re.findall(r"https?://[^\"<> ]*", text), ["http://www.w3.org/2000/svg"], "nothing but the namespace")
            if name.endswith(".json"):
                json.loads(text)
                self.assertNotRegex(text, r"[<>&]")
        seen = Seen(files["index.html"])
        for tag in ("script", "iframe", "object", "embed", "img", "link", "form", "base", "input", "video", "audio", "frame", "applet"):
            self.assertNotIn(tag, seen.tags)
        for name in seen.attributes:
            self.assertFalse(name.startswith("on") or name in ("style", "src", "srcset", "srcdoc", "action", "formaction"), name)
        for href in seen.hrefs:
            self.assertTrue(href in (join, "join.html") or MEMBER_HREF.match(href) or COMMIT_HREF.match(href)
                            or (WIN_HREF.match(href) and href in files), href)
        for address in re.findall(r"https?://[^\"<> ]*", files["index.html"]):
            self.assertTrue(address.startswith("https://github.com/"), address)
        return seen


# ---------------------------------------------------------------------------------------------------------------


class TestFigures(Case):
    def setUp(self):
        super().setUp()
        self.ledger([
            {"type": "deal", "at": "2026-11-01T08:00:00Z", "until": "2026-11-02T08:00:00Z", "run": "4" * 32, "task": "toy-0001",
             "member": "alice", "member_id": 101, "repo_id": 1},
            {"type": "expired", "at": "2026-11-02T08:00:00Z", "run": "4" * 32, "task": "toy-0001", "member_id": 103,
             "deal": "2026-11-01T08:00:00Z", "fault": "no_candidate"},
            {**verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001", model="claude-fable-5-2"), "type": "intent", "run": "1" * 32},
            verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001", model="claude-fable-5-2"),
            verdict(2, "2026-11-03T09:00:00Z", "carol", 103, "toy-0002", "refused", judged=False, reason="path_outside_task"),
            failure(3, "2026-11-09T09:00:00Z", "bob", 102, "judge"),
            failure(4, "2026-11-09T10:00:00Z", "bob", 102, "push"),
            failure(5, "2026-11-09T11:00:00Z", "carol", 103, None),  # no kind: the hive reads it as the judge's
            failure(6, "2026-11-09T12:00:00Z", "carol", 103, "hive"),
            verdict(7, "2026-11-10T09:00:00Z", "alice-new", 101, "toy-0002"),  # the same account, renamed
            {"type": "void", "at": "2026-11-10T09:00:00Z", "run": "2" * 32, "sha": sha(8), "commit": sha(5008)},
            verdict(9, "2026-11-11T09:00:00Z", "bob", 102, "toy-0004", "refused", model="gpt-x", reason="judge_refused"),
            verdict(10, "2026-11-11T10:00:00Z", "bob", 102, "toy-0002", "refused", judged=False, reason="conflict"),
            {"type": "unused", "at": "2026-11-11T10:00:00Z", "run": "3" * 32, "task": "toy-0004", "member": "bob", "member_id": 102,
             "repo_id": 1, "sha": sha(11)},
            verdict(12, "2026-11-12T11:00:00Z", "carol", 103, "toy-0004"),
        ])
        self.put("feed.json", feed({"toy-0001": "done", "toy-0002": "done", "toy-0003": "closed", "toy-0004": "done",
                                    "toy-0005": "dealt", "toy-0006": "open", "toy-0007": "open"}))

    def test_the_figures_of_a_hand_written_ledger(self):
        files = self.make("--repo-url", "https://github.com/Bee-ruche/toy")
        data, seen = self.summary(files), self.harmless(files)
        self.assertEqual(data["totals"], {"verdicts": 6, "judged": 4, "accepted": 3, "integrations": 3, "refused": 3,
                                          "judge_failures": 2})
        self.assertEqual(data["tasks"], {"done": 3, "dealt": 1, "open": 2, "closed": 1, "total": 7})
        self.assertEqual(data["week"], {"since": "2026-11-05T12:00:00Z", "integrations": 2, "members": 2, "judged": 3, "accepted": 2,
                                        "acceptance_rate": 0.6667})
        self.assertEqual(data["measures"], {"yield": 0.75, "time_to_answer_seconds": None,
                                            "judge_runs_per_integration": 2.0, "waiting": None})
        self.assertEqual(data["refusals"], [{"reason": reason, "count": 1} for reason in ("conflict", "judge_refused", "path_outside_task")])
        self.assertEqual(data["models"], [
            {"model": None, "judged": 2, "accepted": 2, "acceptance_rate": 1.0},
            {"model": "claude-fable-5-2", "judged": 1, "accepted": 1, "acceptance_rate": 1.0},
            {"model": "gpt-x", "judged": 1, "accepted": 0, "acceptance_rate": 0.0}])
        self.assertEqual([(r["at"][:10], r["task"], r["login"], r["commit"]) for r in data["recent"]],
                         [("2026-11-12", "toy-0004", "carol", sha(5012)), ("2026-11-10", "toy-0002", "alice-new", sha(5007)),
                          ("2026-11-01", "toy-0001", "alice-new", sha(5001))])
        # The page says the same.
        self.assertEqual(seen.row("alice-new"), ["alice-new", "2", "2", "100 % (2 of 2)", "2026-11-10"])
        self.assertEqual(seen.row("carol"), ["carol", "1", "1", "100 % (1 of 1)", "2026-11-12"])
        self.assertEqual(seen.row("claude-fable-5-2"), ["claude-fable-5-2", "1", "1", "100 %"])
        self.assertEqual(seen.row("gpt-x"), ["gpt-x", "1", "0", "0 %"])
        self.assertEqual(seen.row("undeclared"), ["undeclared", "2", "2", "100 %"])
        for reason in ("conflict", "judge_refused", "path_outside_task"):
            self.assertEqual(seen.row(reason), [reason, "1", hive.REASONS[reason]])
        self.assertEqual(seen.row("2026-11-12"), ["2026-11-12", "toy-0004 Title of toy-0004", "carol", sha(5012)[:10]])
        self.assertIn(f"https://github.com/Bee-ruche/toy/commit/{sha(5012)}", seen.hrefs)
        self.assertIn("Declared by each worker: a statistic, not a proof.", files["index.html"])
        self.assertIn("3 verified contributions", files["badge.svg"])

    def test_a_renamed_account_counts_once_under_its_latest_login(self):
        files = self.make()
        data, seen = self.summary(files), self.harmless(files)
        self.assertEqual([(m["id"], m["login"], m["integrations"]) for m in data["members"]], [(101, "alice-new", 2), (103, "carol", 1)])
        self.assertIsNone(seen.row("alice"), "the former login has no row")
        self.assertIn("https://github.com/alice-new", seen.hrefs)
        self.assertNotIn("https://github.com/alice", seen.hrefs)
        self.assertEqual(sorted(name for name in files if name.startswith("members/")),
                         ["members/101-badge.svg", "members/101.svg", "members/103-badge.svg", "members/103.svg"],
                         "one card and one badge per account with an integration, named by its number")
        self.assertIn('aria-label="La Ruche · toy · 2 contributions accepted by the judge · first Nov 2026 · latest 10 Nov 2026 · GitHub account 101"',
                      files["members/101.svg"])
        self.assertIn('aria-label="La Ruche · toy · 1 contribution accepted by the judge · first Nov 2026 · latest 12 Nov 2026 · GitHub account 103"',
                      files["members/103.svg"])
        self.assertIn('aria-label="La Ruche · toy: 2 accepted by the judge"', files["members/101-badge.svg"])
        for name in ("members/101.svg", "members/101-badge.svg"):
            self.assertNotIn("alice", files[name], "a card carries no login: it stays right when the account is renamed")

    def test_a_member_is_named_only_for_accepted_work(self):
        files = self.make()
        self.assertNotIn("bob", files["index.html"] + files["summary.json"], "refused work earns no name and no link on the page")
        self.assertEqual(self.summary(files)["members_without_integration"], 1)
        self.assertNotIn("members/102.svg", files)

    def test_a_login_taken_over_by_another_account_is_no_longer_shown_for_the_first(self):
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001"), verdict(2, "2026-11-02T09:00:00Z", "Alice", 105, "toy-0002")])
        files = self.make()
        self.assertEqual([(m["id"], m["login"]) for m in self.summary(files)["members"]], [(101, None), (105, "Alice")])
        seen = self.harmless(files)
        self.assertEqual(seen.hrefs.count("https://github.com/Alice"), 2, "the members' table and the integrations, for account 105 only")
        self.assertIsNotNone(seen.row("account 101"))

    def test_this_week_moves_with_the_instant(self):
        self.assertEqual(self.summary(self.make("--now", "2026-11-19T10:00:00Z"))["week"]["integrations"], 1)
        self.assertEqual(self.summary(self.make("--now", "2026-12-25T00:00:00Z"))["week"],
                         {"since": "2026-12-18T00:00:00Z", "integrations": 0, "members": 0, "judged": 0, "accepted": 0, "acceptance_rate": None})
        with mock.patch.dict(os.environ, {"HIVE_NOW": "2026-11-08T09:00:00Z"}):
            self.assertEqual(self.summary(self.make())["week"]["integrations"], 0, "HIVE_NOW is the clock, as for the hive")

    def test_the_top_fifty_members_by_integrations_and_the_latest_thirty_integrations(self):
        lines, number = [], 0
        for member in range(59, -1, -1):  # m00 has 60 integrations, m59 has one; the most active come last in time
            for _ in range(60 - member):
                number += 1
                lines.append(verdict(number, f"2026-10-{1 + number % 28:02d}T00:00:00Z" if member else f"2026-11-{1 + number % 9:02d}T00:00:00Z",
                                     f"m{member:02d}", 1000 + member, "toy-0001"))
        self.ledger(lines)
        files = self.make()
        data, seen = self.summary(files), self.harmless(files)
        self.assertEqual([m["login"] for m in data["members"]], [f"m{member:02d}" for member in range(60)], "all of them in summary.json")
        shown = [row[0] for row in seen.rows if len(row) == 5 and row[0].startswith("m")]
        self.assertEqual(shown, [f"m{member:02d}" for member in range(50)])
        self.assertEqual(len(data["recent"]), 30)
        self.assertEqual([r["at"] for r in data["recent"]], sorted((r["at"] for r in data["recent"]), reverse=True))
        self.assertEqual({r["login"] for r in data["recent"]}, {"m00"})
        self.assertEqual(sorted(name for name in files if name.startswith("members/")),
                         sorted(f"members/{1000 + member}{end}.svg" for member in range(60) for end in ("", "-badge")),
                         "a card and a badge for every member with an integration, not only for those the table shows")

    def test_candidates_that_wait_are_counted_and_the_time_to_an_answer_is_not_invented(self):
        deals = {mark(1): deal(at="2026-11-12T07:00:00Z"), mark(2): deal("toy-0006", at="2026-11-12T11:00:00Z"),
                 mark(3): deal("toy-0007", candidate=False), mark(4): deal(at="never"), "zz": deal(), mark(5): deal(task="../x")}
        self.put("feed.json", feed({"toy-0005": "dealt", "toy-0006": "dealt", "toy-0007": "dealt"}, deals=deals))
        files = self.make()
        self.assertEqual(self.summary(files)["measures"]["waiting"], {"count": 2, "oldest_seconds": 5 * 3600})
        self.assertIsNone(self.summary(files)["measures"]["time_to_answer_seconds"])
        self.assertIn("2 waiting now, the oldest for 5 h", files["index.html"])
        self.assertRegex(files["index.html"], r"Time to an answer</div><div class=\"value\">n/a<")

    def test_stats_json_is_compared_never_believed(self):
        self.assertEqual(self.summary(self.make())["stats_json"], "absent")
        self.put("stats.json", hive.build_stats(hive.Ledger(self.state)))
        self.assertEqual(self.summary(self.make())["stats_json"], "agrees")
        self.put("stats.json", {"members": {}, "models": {"gpt-x": {"judged": 900, "accepted": 900}}})
        files = self.make()
        self.assertEqual(self.summary(files)["stats_json"], "differs")
        self.assertNotIn("900", files["index.html"])

    def test_the_join_link(self):
        self.assertIn(JOIN, self.harmless(self.make()).hrefs)
        self.assertIn("join.html", self.harmless(self.make("--join")).hrefs)
        other = "https://github.com/Bee-ruche/registre/blob/hive/docs/join.md"
        self.assertIn(other, self.harmless(self.make("--join-url", other), join=other).hrefs)


class TestHostile(Case):
    def hostile(self):
        """A ledger and its neighbours where every pattern is broken on purpose, among a few honest lines."""
        deep = "[" * 100_000 + "]" * 100_000
        lines = [verdict(20 + i, "2026-11-10T00:00:00Z", login, 201 + i, "toy-0001") for i, login in enumerate(LOGINS)]
        lines += [
            verdict(40, "2026-11-10T01:00:00Z", "mallory", 300, "../../etc", model="<img src=x>"),
            verdict(41, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001<script>", model="javascript:alert(1)"),
            verdict(42, "2026-11-10T01:00:00Z", "mallory", 300, ["toy-0001"], model=["<img src=x>"]),
            verdict(43, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", commit='"><script>alert(1)</script>'),
            verdict(44, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", commit="javascript:alert(1)"),
            verdict(45, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", commit=sha(1).upper().replace("0", "A")),
            verdict(46, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", "refused", reason="<script>alert(1)</script>"),
            verdict(47, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", "refused", reason=["judge_refused"]),
            verdict(48, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", "refused", reason={"a": 1}),
            verdict(49, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", "accepted<script>alert(1)</script>"),
            verdict(50, "2026-13-45T00:00:00Z", "mallory", 300, "toy-0001"),
            verdict(51, "<script>alert(1)</script>", "mallory", 300, "toy-0001"),
            verdict(52, 5, "mallory", 300, "toy-0001"),
            verdict(56, "0001-01-01T00:00:00Z", "mallory", 300, "toy-0001"),
            verdict(57, "0999-12-31T23:59:59Z", "mallory", 300, "toy-0001"),
            verdict(58, "9999-12-31T23:59:59Z", "mallory", 300, "toy-0001"),
            {**verdict(53, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001"), "type": ["verdict"]},
            {**verdict(54, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001"), "type": "<script>alert(1)</script>"},
            verdict(55, "2026-11-10T01:00:00Z", "mallory", 300, "toy-0001", judged="<script>alert(1)</script>"),
        ]
        # An account id that is a string, negative, zero, huge, a float, a boolean, a list: never a member, never a file.
        for i, member_id in enumerate(("301", "../../etc/passwd", "302.svg", -5, 0, 10 ** 30, 2 ** 63, 101.5, 7.0, True, None, [303], {"a": 304})):
            lines.append(verdict(60 + i, "2026-11-10T02:00:00Z", "eve", member_id, "toy-0001"))
        lines += ['{"type":"verdict","at":"2026-11-10T03:00:00Z","member":"eve","member_id":NaN,"result":"accepted","judged":true}',
                  '{"type":"verdict","at":"2026-11-10T03:00:00Z","member":"eve","member_id":1e400,"result":"accepted","judged":true}',
                  '{"type":"deal","at":"2026-11-10T03:00:00Z","member":"eve","member_id":' + "9" * 5000 + ',"task":"toy-0001"}',
                  '{"type":"deal","at":"2026-11-10T03:00:00Z","until":["<script>"],"run":7,"task":{"a":1},"member":"<script>","member_id":"x","repo_id":[]}',
                  '{"type":"expired","at":"<script>","task":null,"member_id":{},"deal":5,"fault":["<script>"]}',
                  '{"type":"expired","at":"2026-11-10T03:00:00Z","task":"<script>","member_id":"x","deal":"<script>","fault":7}',
                  json.dumps({**verdict(98, "2026-11-10T03:00:00Z", "honest", 500, "toy-0002"), "padding": "x" * page.LINE_MAX}),
                  verdict(97, "2026-11-10T03:00:00Z", "honest", 500, "toy-" + "a-" * 40 + "0001"),
                  "[]", '"<script>alert(1)</script>"', "123", "null", "{broken <script>alert(1)</script>", deep,
                  b'{"type":"verdict","at":"2026-11-10T03:00:00Z","member":"\xff\xfe<script>alert(1)</script>","member_id":399,"result":"accepted"}',
                  '{"type":"verdict","at":"2026-11-10T03:00:00Z","member":"\\ud800","member_id":398,"result":"accepted","model":"\\udfff"}',
                  verdict(99, "2026-11-11T00:00:00Z", "honest", 500, "toy-0002", model="claude-fable-5-2")]
        self.ledger(lines)
        self.put("feed.json", {"project": '"><svg onload=alert(1)>', "tasks": [
            {"id": "toy-0001", "title": "<script>alert(2)</script> & \"co\" \u202e\x00\ud800", "status": "done"},
            {"id": "toy-0001", "title": "the same task, a second time", "status": "open"},
            {"id": "toy-0002", "title": ["<script>"], "status": "done"},
            {"id": "../../etc", "title": "x", "status": "open"}, {"id": "toy-0003", "title": "x", "status": "<script>"},
            {"id": "toy-0004", "status": ["open"]}, "<script>", None, 7],
            "deals": {"<script>alert(1)</script>": deal(), mark(1): "<script>", mark(2): {"candidate": "<script>", "at": "<script>"},
                      mark(3): deal(at="<script>"), mark(4): deal(candidate="true"), mark(5): [deal()], mark(6): None}})
        self.put("stats.json", '{"models": {"<script>alert(1)</script>": ')

    def test_nothing_hostile_reaches_any_file_and_nothing_is_written_elsewhere(self):
        self.hostile()
        (self.root / "bystander.txt").write_text("untouched")
        before = tree(self.root)
        files = self.make("--title", '</title><script>alert(3)</script> "q" & \x00\x1b[31m\u202e', "--repo-url", "https://github.com/Bee-ruche/toy")
        after = tree(self.root)
        self.assertEqual({name: content for name, content in after.items() if name != "site" and not name.startswith("site/")}, before,
                         "nothing is written, changed or removed outside --out")
        valid = [201 + i for i, login in enumerate(LOGINS)] + [300, 398, 399, 500]
        wins = sorted(f"wins/{win['commit']}.svg" for win in page.collect(self.state, page.instant_of(NOW))["_wins"])
        self.assertTrue(0 < len(wins) <= 35 and all(re.fullmatch(r"wins/[0-9a-f]{40}\.svg", name) for name in wins))
        self.assertEqual(sorted(files), sorted(["index.html", "badge.svg", "summary.json", *(f"members/{i}.svg" for i in valid),
                                                *(f"members/{i}-badge.svg" for i in valid), *wins]))
        self.assertEqual(sorted(after), sorted(["bystander.txt", "state", "state/toy", *(f"state/toy/{n}" for n in ("ledger.jsonl", "feed.json", "stats.json")),
                                                "site", "site/members", "site/wins", *(f"site/{name}" for name in files)]), "no temporary file is left")
        for name, text in files.items():
            for needle in NEEDLES:
                self.assertNotIn(needle, text.lower(), (name, needle))
        seen = self.harmless(files)
        # What was dropped, and what was kept.
        data = self.summary(files)
        self.assertEqual({m["id"]: m["login"] for m in data["members"]},
                         {**{201 + i: None for i in range(len(LOGINS))}, 300: "mallory", 398: None, 399: None, 500: "honest"})
        self.assertEqual(seen.hrefs.count("https://github.com/honest"), 3)
        self.assertEqual([m["model"] for m in data["models"]], [None, "claude-fable-5-2"], "a model that is not an identifier is undeclared")
        self.assertEqual({r["task"] for r in data["recent"]}, {"toy-0001", "toy-0002", None}, "a task id that is not one is unknown")
        self.assertEqual(data["tasks"], {"done": 2, "dealt": 0, "open": 0, "closed": 0, "total": 2}, "a task counts once, under a real id and status")
        self.assertEqual(data["totals"], {"verdicts": 38, "judged": 35, "accepted": 32, "integrations": 35, "refused": 3,
                                          "judge_failures": 0}, "« judged » is true or it is not; a line too long to be honest is not read")
        self.assertEqual({r["commit"] for r in data["recent"] if r["member_id"] == 300 and r["at"] == "2026-11-10T01:00:00Z"},
                         {None, sha(5040), sha(5041), sha(5042), sha(5055)})
        self.assertEqual(data["refusals"], [{"reason": None, "count": 3}])
        self.assertEqual(data["project"], "toy", "the feed's project was not an identifier: the folder's name is used")
        # Seven lines are not JSON objects; the number of 5000 digits is one of them where Python refuses to read it.
        self.assertIn(data["ledger"]["unreadable_lines"], (7, 8))
        self.assertEqual(data["measures"]["waiting"], None)
        self.assertEqual(data["stats_json"], "absent")
        # What is trusted (the tasks' titles, the command line) is shown, escaped and without what cannot be printed.
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt; &amp; &quot;co&quot;</span>", files["index.html"])
        self.assertIn("&lt;/title&gt;&lt;script&gt;alert(3)&lt;/script&gt; &quot;q&quot; &amp; [31m</p>", files["index.html"])

    def test_everything_is_escaped_even_when_the_patterns_let_everything_through(self):
        """The patterns are one guard and the builder another: with the first one taken away, nothing runs."""
        self.hostile()
        anything = re.compile(r"(?s).*\Z")
        with mock.patch.multiple(page, LOGIN=anything, MODEL=anything, TASK_ID=anything, PROJECT=anything, SHA=anything):
            files = self.make("--title", "<script>alert(3)</script>")
        text = files["index.html"]
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text, "the hostile login did reach the builder")
        self.assertIn("&lt;img src=x&gt;", text)
        self.assertIn("a&quot;onmouseover=&quot;x", text)
        self.assertNotIn("<script", text.lower())
        self.assertNotIn("<img", text.lower())
        seen = Seen(text)
        self.assertNotIn("script", seen.tags)
        self.assertNotIn("img", seen.tags)
        self.assertEqual([name for name in seen.attributes if name.startswith("on") or name in ("src", "style")], [])
        for href in seen.hrefs:
            self.assertTrue(href == JOIN or re.match(r"https://github\.com/[A-Za-z0-9%._~-]*\Z", href) or (WIN_HREF.match(href) and href in files), href)
        for name, content in files.items():
            self.assertTrue(NAMED.fullmatch(name), name)
            if name.endswith(".svg"):
                root = minidom.parseString(content.encode("utf-8")).documentElement
                self.assertEqual({node.tagName for node in root.getElementsByTagName("*")} - set(SVG_TAGS), set())
                self.assertEqual([key for node in [root, *root.getElementsByTagName("*")] for key in node.attributes.keys() if key.startswith("on")], [])
                self.assertEqual([node.firstChild.data for node in root.getElementsByTagName("style")], [str(page.CARD_CSS)] * content.count("<style"))
        card = files[f"wins/{sha(5020)}.svg"]  # the first hostile login's integration
        self.assertIn("@&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;", card, "the hostile login did reach the card's builder too")
        self.assertNotRegex(files["summary.json"], r"[<>&]")
        self.assertIn("\\u003cscript\\u003e", files["summary.json"])

    def test_the_builder_escapes_and_refuses_what_runs_or_loads(self):
        self.assertEqual(page.el("p", "a\x00b\x1b\ud800c\u202e", title="x\x00y"), '<p title="xy">abc</p>', "nothing XML cannot hold")
        self.assertEqual(page.el("p", '<b>&"\'', class_='x"y'), '<p class="x&quot;y">&lt;b&gt;&amp;&quot;&#x27;</p>')
        self.assertEqual(page.el("p", page.el("code", "<")), "<p><code>&lt;</code></p>")
        self.assertEqual(page.el("p", page.el("code", "a") + "<b>"), "<p>&lt;code&gt;a&lt;/code&gt;&lt;b&gt;</p>",
                         "text glued to the builder's output is plain text again")
        self.assertEqual(page.el("a", "x", href=page.Link("https://github.com/a?b&c")), '<a href="https://github.com/a?b&amp;c">x</a>')
        for refused in (lambda: page.el("script", "x"), lambda: page.el("img"), lambda: page.el("iframe"),
                        lambda: page.el("p", onclick="x"), lambda: page.el("p", ONLOAD="x"), lambda: page.el("p", style="x"),
                        lambda: page.el("p", src="x"), lambda: page.el("a", "x", href="https://github.com/a"),
                        lambda: page.el("a", "x", HREF="javascript:alert(1)"), lambda: page.el("p", **{'x" onload="y': "z"})):
            with self.assertRaises(ValueError):
                refused()

    def test_links_are_built_from_a_checked_login_or_a_commit_id_and_nothing_else(self):
        self.assertEqual(page.member_link("alice-1"), "https://github.com/alice-1")
        for login in ("", "-a", "a-", "a/b", "a b", "a.b", "a" * 40, "é", "a\n", "../x", "javascript:alert(1)", None, 7, ["a"]):
            self.assertIsNone(page.member_link(login), login)
        repo = "https://github.com/Bee-ruche/toy"
        self.assertEqual(page.commit_link(repo, sha(1)), f"{repo}/commit/{sha(1)}")
        for commit in ("", "abc", sha(1) + "0", sha(1)[:-1] + "G", sha(1) + "\n", "../" + sha(1)[3:], None, 5):
            self.assertIsNone(page.commit_link(repo, commit), commit)
        for address in (None, "", "javascript:alert(1)", "http://github.com/a/b", "https://github.com.evil.example/a/b", "https://evil.example/a/b",
                        "https://github.com/a", "https://github.com/a/b/c", "https://github.com/a/b?x=1", "https://github.com/a/b#x",
                        "https://github.com/a/b\n", "https://user@github.com/a/b", " https://github.com/a/b"):
            self.assertIsNone(page.commit_link(address, sha(1)), address)

    def test_an_account_id_is_a_whole_number_in_range_and_a_file_name_is_made_of_nothing_else(self):
        self.assertEqual([page.account_id(v) for v in (1, 101, 2 ** 63 - 1)], [1, 101, 2 ** 63 - 1])
        for value in ("101", "１０１", 101.0, 1.5, True, False, None, 0, -1, 2 ** 63, 10 ** 30, [101], {"id": 101}, float("nan"), float("inf")):
            self.assertIsNone(page.account_id(value), repr(value))
            with self.assertRaises(ValueError):
                page.card_name(value)
            with self.assertRaises(ValueError):
                page.badge_name(value)
        self.assertEqual((page.card_name(101), page.badge_name(101)), ("members/101.svg", "members/101-badge.svg"))
        for name in ("../x.svg", "members/../../x.svg", "members/abc.svg", "members/1.svg/../../x", "/etc/passwd", "members/0.svg",
                     "members/1.svg\n", "index.html/../x", "members/-1.svg", "x.html", "", "members/1-badge.svg\n", "members/0-badge.svg",
                     "members/-badge.svg", "members/1-badge.svg/../../x", "members/1-badge-badge.svg", "members/1-BADGE.svg", "members/1-badge.html",
                     "wins/1-badge.svg", "members/" + sha(1) + ".svg", "wins/101.svg"):
            with self.assertRaises(page.PageError):
                page.write(self.out, {name: "x"})
        for name in ("wins/x.svg", "wins/" + sha(10).upper() + ".svg", "wins/" + sha(1) + ".svg/../../x", "wins/../x.svg", "wins/" + sha(1)[:-1] + ".svg",
                     "wins/" + sha(1) + ".svg\n", "wins/a/" + sha(1) + ".svg"):
            with self.assertRaises(page.PageError):
                page.write(self.out, {name: "x"})
        self.assertEqual(tree(self.root), {"state": None, "state/toy": None}, "a refused name writes nothing, anywhere")

    def test_an_address_given_on_the_command_line_must_be_on_github(self):
        self.ledger([verdict(1, "2026-11-10T00:00:00Z", "alice", 101, "toy-0001")])
        for address in ("javascript:alert(1)", "http://github.com/a/b", "https://github.com.evil.example/a/b", "https://evil.example/a/b",
                        "https://github.com/a/b/c", "https://github.com/a/..", "https://github.com/a/b\"onload=\"x", "https://github.com/a/b\n", "//github.com/a/b"):
            self.assertEqual(self.make("--repo-url", address, code=2), {}, address)
        for address in ("javascript:alert(1)", "https://evil.example/join", "https://github.com", "https://github.com/a/b/../../c",
                        "https://github.com/a/b?x=<script>", "data:text/html,x", "join.html"):
            self.assertEqual(self.make("--join-url", address, code=2), {}, address)
        for instant in ("yesterday", "2026-13-45T00:00:00Z", "2026-11-12", "<script>", "0001-01-02T00:00:00Z", "9999-12-31T23:59:59Z"):
            self.assertEqual(self.make("--now", instant, code=2), {}, instant)
            with mock.patch.dict(os.environ, {"HIVE_NOW": instant}):
                self.assertEqual(self.make(code=2), {}, instant)
        self.assertEqual(self.make("--join", "--join-url", JOIN, code=2), {})
        with mock.patch.dict(os.environ, {"HIVE_NOW": "soon"}):
            self.assertEqual(self.make(code=2), {})
        self.assertFalse(self.out.exists(), "a refused argument writes nothing")

    def test_what_cannot_be_printed_is_taken_out_of_a_title(self):
        self.assertEqual([page.instant_of(v) is None for v in ("2026-11-12T12:00:00Z", "2026-02-30T00:00:00Z", "0001-01-01T00:00:00Z",
                                                               "1999-12-31T23:59:59Z", "3000-01-01T00:00:00Z", "2026-11-12T12:00:00Z\n", 5, None)],
                         [False, True, True, True, True, True, True, True])
        self.assertEqual(page.plain("  a\tb\nc  \x00\x1b\u202e\u200b\ud800\ufffe d ", 50), "a b c d")
        self.assertEqual(page.plain("x" * 300, 20), "x" * 19 + "…")
        self.assertEqual(page.plain(["x"], 20), "")
        self.assertEqual(page.plain("Bibliothèque zlib · 圧縮", 50), "Bibliothèque zlib · 圧縮")


def report_verdict(number, report, **more):
    return verdict(number, f"2026-11-{number:02d}T09:00:00Z", "alice", 101, "toy-0001", report=report, **more)


class TestWins(Case):
    def wins(self, files):
        return {name: text for name, text in files.items() if name.startswith("wins/")}

    def headline_of(self, report):
        self.ledger([report_verdict(1, report)])
        files = self.make()
        self.harmless(files)
        figure = self.summary(files)["recent"][0]["headline"]
        card = files[f"wins/{sha(5001)}.svg"]
        return figure, card

    def test_the_largest_sure_gain_is_the_headline(self):
        figure, card = self.headline_of({"gain_instructions_n6": 0.032, "sure_instructions_n6": 1, "gain_time": 0.5, "sure_time": 0,
                                         "gain_size": 0.01, "sure_size": 1, "outputs_compared": 96})
        self.assertEqual(figure, {"metric": "instructions_n6", "gain": 0.032})
        self.assertIn("accepted by the judge · measured 3.2 % better · instructions n6 · in toy · 96 outputs identical to the base", card)
        self.assertNotIn("50.0", card)

    def test_a_gain_that_is_not_sure_negative_zero_or_alone_is_no_headline(self):
        for report in ({"gain_a": 0.3, "sure_a": 0}, {"gain_a": 0.3}, {"gain_a": 0.3, "sure_a": 2}, {"gain_a": -0.1, "sure_a": 1},
                       {"gain_a": 0, "sure_a": 1}, {"gain_a": 0.0, "sure_a": 1}, {"gain_a": 0.3, "sure_a": 0.5}, {"sure_a": 1}, {}, {"gain_": 0.3, "sure_": 1},
                       {"gain_a": 0.00001, "sure_a": 1}):
            figure, card = self.headline_of(report)
            self.assertIsNone(figure, report)
            self.assertIn(">accepted by the judge<", card)
            self.assertNotIn("%", card, report)

    def test_the_figure_is_chosen_among_the_sure_ones_only(self):
        figure, _ = self.headline_of({"gain_big": 0.9, "sure_big": 0, "gain_neg": -0.5, "sure_neg": 1, "gain_mid": 0.2, "sure_mid": 1.0,
                                      "gain_small": 0.05, "sure_small": 1, "gain_tie": 0.2, "sure_tie": 1})
        self.assertEqual(figure, {"metric": "mid", "gain": 0.2}, "a tie goes to the first name")

    def test_a_hostile_report_shows_nothing_of_itself(self):
        reports = [
            {"gain_a": "0.5", "sure_a": 1}, {"gain_a": 0.5, "sure_a": "1"}, {"gain_a": True, "sure_a": 1}, {"gain_a": 0.5, "sure_a": True},
            {"gain_a": None, "sure_a": 1}, {"gain_a": [0.5], "sure_a": 1}, {"gain_a": {"x": 1}, "sure_a": 1},
            {"gain_a": 10.01, "sure_a": 1}, {"gain_a": 1e300, "sure_a": 1}, {"gain_a": 10 ** 500, "sure_a": 1},
            {"gain_<script>alert(1)</script>": 0.5, "sure_<script>alert(1)</script>": 1},
            {"gain_a b": 0.5, "sure_a b": 1}, {"gain_a\n": 0.5, "sure_a\n": 1}, {"gain_é": 0.5, "sure_é": 1}, {"gain_" + "a" * 61: 0.5, "sure_" + "a" * 61: 1},
            {"gain_a": 0.5, "sure_a": float("nan")}, {"gain_a": float("inf"), "sure_a": 1}, {"gain_a": float("-inf"), "sure_a": 1},
            "<script>alert(1)</script>", ["gain_a", 0.5], 5, None, True, "gain_a",
        ]
        lines = [report_verdict(number, report) for number, report in enumerate(reports, 1)]
        # NaN and Infinity spelled in JSON, as a worker's report may hold them, and a huge number
        lines.append('{"type":"verdict","at":"2026-11-27T09:00:00Z","task":"toy-0001","member":"alice","member_id":101,"result":"accepted",'
                     '"judged":true,"commit":"' + sha(5027) + '","report":{"gain_a":NaN,"sure_a":1,"gain_b":Infinity,"sure_b":1,"gain_c":-Infinity,'
                     '"sure_c":1,"gain_d":1e999,"sure_d":1,"gain_e":0.5,"sure_e":NaN}}')
        self.ledger(lines)
        files = self.make("--repo-url", "https://github.com/Bee-ruche/toy")
        self.harmless(files)
        data = self.summary(files)
        self.assertEqual(len(data["recent"]), len(reports) + 1)
        self.assertEqual([r["headline"] for r in data["recent"]], [None] * (len(reports) + 1))
        self.assertEqual(len(self.wins(files)), len(reports) + 1)
        for name, text in files.items():
            for needle in NEEDLES:
                self.assertNotIn(needle, text.lower(), (name, needle))
        for name, text in self.wins(files).items():
            self.assertNotIn("%", text)
            self.assertNotIn("gain", text)

    def test_a_gain_of_a_thousand_percent_is_the_last_one_shown(self):
        figure, card = self.headline_of({"gain_a": 10, "sure_a": 1})
        self.assertEqual(figure, {"metric": "a", "gain": 10.0})
        self.assertIn("measured 1000.0 % better · a", card)
        self.assertIn(">1000.0 %<", card)

    def card_text(self, text):
        root = minidom.parseString(text.encode("utf-8")).documentElement
        return root, [node.firstChild.data for node in root.getElementsByTagName("text")]

    def test_every_win_card_parses_has_no_script_and_says_what_it_shows(self):
        self.ledger([
            report_verdict(1, {"gain_instructions_n6": 0.032, "sure_instructions_n6": 1}, model="claude-fable-5-2"),
            report_verdict(2, {}),
            verdict(3, "2026-11-03T09:00:00Z", "bob", 102, "toy-9999", model="gpt-x<b>", report={"gain_t": 0.1, "sure_t": 1}),
            verdict(4, "2026-11-04T09:00:00Z", "dave", 104, "toy-0001", "refused", reason="conflict"),
            report_verdict(5, {}, commit="not a commit"),
        ])
        self.put("feed.json", feed({"toy-0001": "done"}, titles={"toy-0001": '<script>x</script> & "q"'}))
        files = self.make("--repo-url", "https://github.com/Bee-ruche/toy")
        self.harmless(files)
        wins = self.wins(files)
        self.assertEqual(sorted(wins), [f"wins/{sha(5000 + n)}.svg" for n in (1, 2, 3)], "no card for a refusal or for a commit that is not one")
        for name, text in wins.items():
            self.assertNotIn("<script", text.lower())
            self.said_whole(name, text)
        root, first = self.card_text(wins[f"wins/{sha(5001)}.svg"])
        short = "commit 0000000000 · Bee-ruche/toy"
        self.assertEqual(first, ["La Ruche · toy", "accepted by the judge", "3.2 %", "better · instructions n6", "in toy", "toy-0001",
                                 "<script>x</script> & \"q\"", "@alice", "first integration · 1 Nov 2026", "declared model: claude-fable-5-2",
                                 short, page.TAGLINE])
        self.assertEqual(root.getAttribute("aria-label"),
                         "La Ruche · toy · accepted by the judge · measured 3.2 % better · instructions n6 · in toy · toy-0001 · <script>x</script> & \"q\" · "
                         f"@alice · first integration · 1 Nov 2026 · declared model: claude-fable-5-2 · {short} · {page.TAGLINE}")
        _, second = self.card_text(wins[f"wins/{sha(5002)}.svg"])
        self.assertEqual(second, ["La Ruche · toy", "accepted by the judge", "Accepted by the judge", "in toy", "toy-0001", "<script>x</script> & \"q\"",
                                  "@alice", "integrated 2 Nov 2026", short, page.TAGLINE])
        _, third = self.card_text(wins[f"wins/{sha(5003)}.svg"])
        self.assertEqual(third, ["La Ruche · toy", "accepted by the judge", "10.0 %", "better · t", "in toy", "toy-9999", "@bob",
                                 "first integration · 3 Nov 2026", short, page.TAGLINE],
                         "a task not in the feed shows its id alone; a model that is not an identifier is not shown")
        bare = self.card_text(self.wins(self.make())[f"wins/{sha(5003)}.svg"])[1]
        self.assertEqual(bare[-2:], ["commit 0000000000", page.TAGLINE], "without --repo-url, the commit's id alone")

    def said_whole(self, name, text):
        """A card's label and title say, in whole words, everything its lines show: a line may be shrunk, wrapped or
        cut (it then ends with « … »), the label is not."""
        root, visible = self.card_text(text)
        label = root.getAttribute("aria-label")
        self.assertEqual(root.getElementsByTagName("title")[0].firstChild.data, label, name)
        for shown in visible:
            if not re.fullmatch(r"\+[0-9,]+", shown):  # a member card's « +1,982 »: the cells not drawn; the label gives the number
                self.assertIn(shown.rstrip("…").lower(), label.lower(), (name, shown))
        return label, visible

    def test_the_longest_values_stay_inside_the_card_and_a_login_is_never_cut(self):
        login, long_task, model = "W" * 20 + "m" * 19, "toy-" + "a-" * 27 + "x-0001", "M" * 40
        self.assertEqual((len(login), len(long_task), len(model)), (39, 64, 40), "the longest a login, a task id and a model can be")
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", login, 101, long_task, model=model,
                             report={"gain_" + "W" * 60: 10, "sure_" + "W" * 60: 1, "outputs_compared": page.COUNT_MAX}),
                     verdict(2, "2026-11-02T09:00:00Z", "x", page.ID_MAX, "toy-0002"),
                     *(verdict(n, "2026-11-03T09:00:00Z", "y", 102, "toy-0002") for n in range(3, 2003))])
        self.put("feed.json", feed({long_task: "done", "toy-0002": "done"}, project="p" * 40,
                                   titles={long_task: "Wide words " * 9, "toy-0002": "圧縮" * 50}))
        files = self.make("--repo-url", "https://github.com/" + "O" * 39 + "/" + "R" * 100)
        for name in (f"wins/{sha(5001)}.svg", f"wins/{sha(5002)}.svg", f"wins/{sha(5003)}.svg", "members/101.svg", "members/102.svg",
                     f"members/{page.ID_MAX}.svg"):
            label, visible = self.said_whole(name, files[name])
            root = minidom.parseString(files[name].encode("utf-8")).documentElement
            inner = [node for node in root.childNodes if node.nodeType == node.ELEMENT_NODE and node.tagName == "svg"]
            self.assertEqual(len(inner), 1, "the lines sit in one inner frame, which clips what the estimate got wrong")
            self.assertLess(int(inner[0].getAttribute("width")), int(root.getAttribute("width")))
            self.assertEqual([node.parentNode is inner[0] for node in root.getElementsByTagName("text")], [True] * len(visible))
            for node in root.getElementsByTagName("text"):
                self.assertGreaterEqual(float(node.getAttribute("font-size")), 8, (name, node.firstChild.data))
                self.assertFalse(node.hasAttribute("textLength"), "a card's line is never squeezed or stretched")
        _, worst = self.card_text(files[f"wins/{sha(5001)}.svg"])
        self.assertIn("@" + login, worst, "the login is whole: a cut one could be another account's")
        self.assertIn("1000.0 %", worst)
        self.assertIn(long_task, worst, "and so is the task's id")
        self.assertTrue(any(shown.endswith("…") for shown in worst), "what is cut says so")
        _, wide = self.card_text(files[f"wins/{sha(5002)}.svg"])
        self.assertEqual([shown for shown in wide if "圧" in shown], ["圧縮" * 13 + "圧", "縮圧" * 13 + "縮…"],
                         "a title without spaces is broken where the room ends, and wide characters count for what they are")
        _, member = self.card_text(files["members/102.svg"])
        self.assertEqual(member[1:], ["GitHub account 102", "2,000", "contributions accepted by the judge", "first Nov 2026 · latest 3 Nov 2026", "+1,982"])
        self.assertEqual(files["members/102.svg"].count('<path class="e"'), page.CELLS, "the drawing is capped; the number is not")
        self.assertIn(f"GitHub account {page.ID_MAX}", self.card_text(files[f"members/{page.ID_MAX}.svg"])[1])

    def test_the_cards_style_is_one_constant_that_loads_nothing_and_the_builder_makes_no_other(self):
        for needle in ("<", ">", "&", '"', "'", "\\", "url(", "@import", "http", "expression(", "/*", "\n"):
            self.assertNotIn(needle, page.CARD_CSS.lower(), needle)
        self.assertIn("@media (prefers-color-scheme:dark)", page.CARD_CSS, "one file for a light and a dark page")
        self.assertEqual(page.el("style", page.CARD_CSS), f"<style>{page.CARD_CSS}</style>")
        self.assertEqual(page.el("style", page.CSS), f"<style>{page.CSS}</style>")
        for refused in (lambda: page.el("style", "x{}"), lambda: page.el("style", page.Markup("x{}")), lambda: page.el("style"),
                        lambda: page.el("style", page.Markup(str(page.CARD_CSS))), lambda: page.el("style", page.CARD_CSS, page.CARD_CSS),
                        lambda: page.el("style", page.CARD_CSS + "x{}"), lambda: page.el("style", page.CARD_CSS, media="all"),
                        lambda: page.el("style", page.Markup("@import url(https://evil.example/x.css);"))):
            with self.assertRaises(ValueError):
                refused()
        # The cards' class names and the pages' are apart: with a card inlined in a page, neither restyles the other.
        names = lambda css: set(re.findall(r"\.([a-z][a-z0-9-]*)", re.sub(r"[0-9]\.[0-9a-z]+", "", css)))  # noqa: E731
        self.assertEqual(names(page.CARD_CSS) & names(page.CSS), set())
        self.assertTrue(names(page.CARD_CSS) and all(len(name) == 1 for name in names(page.CARD_CSS)))
        self.ledger([report_verdict(1, {})])
        files = self.make()
        self.assertEqual({name: text.count("<style>") for name, text in files.items() if name.endswith(".svg")},
                         {"badge.svg": 0, "members/101.svg": 1, "members/101-badge.svg": 0, f"wins/{sha(5001)}.svg": 1})

    def test_the_login_is_not_shown_when_it_is_no_longer_the_account_s(self):
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001"), verdict(2, "2026-11-02T09:00:00Z", "Alice", 105, "toy-0002")])
        files = self.make()
        _, first = self.card_text(files[f"wins/{sha(5001)}.svg"])
        _, second = self.card_text(files[f"wins/{sha(5002)}.svg"])
        self.assertIn("GitHub account 101", first, "the account's number, which is what the ledger is sure of")
        self.assertNotIn("alice", files[f"wins/{sha(5001)}.svg"].lower())
        self.assertIn("@Alice", second)
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "alice", None, "toy-0001")])
        _, nobody = self.card_text(self.make()[f"wins/{sha(5001)}.svg"])
        self.assertEqual(nobody[-3:], ["integrated 1 Nov 2026", "commit 0000000000", page.TAGLINE], "no account, no name and no « first »")

    def test_the_index_and_the_summary_link_the_cards(self):
        self.ledger([report_verdict(1, {"gain_a": 0.25, "sure_a": 1}), report_verdict(2, {}), report_verdict(3, {}, commit="x")])
        files = self.make()
        seen = self.harmless(files)
        data = self.summary(files)
        self.assertEqual([(r["card"], r["headline"]) for r in data["recent"]],
                         [(None, None), (f"wins/{sha(5002)}.svg", None), (f"wins/{sha(5001)}.svg", {"metric": "a", "gain": 0.25})])
        self.assertIn(f"wins/{sha(5001)}.svg", seen.hrefs)
        self.assertIn(f"wins/{sha(5002)}.svg", seen.hrefs)
        self.assertEqual(len([h for h in seen.hrefs if h.startswith("wins/")]), 2, "no link where there is no card")
        self.assertIn("wins/&lt;commit&gt;.svg", files["index.html"])
        self.assertNotIn("_wins", files["summary.json"])

    def test_every_integration_keeps_its_card_whatever_comes_after(self):
        """A card that someone embedded must still be there later. Nothing is capped; a later run on a longer ledger
        writes every name an earlier run wrote; and the tool deletes nothing it finds in the folder."""
        lines = [verdict(n, f"2026-{1 + n // 28:02d}-{1 + n % 28:02d}T09:00:00Z", "alice", 101, "toy-0001") for n in range(1, 251)]
        self.ledger(lines)
        files = self.make()
        self.harmless(files)
        wins = self.wins(files)
        self.assertEqual(sorted(wins), sorted(f"wins/{line['commit']}.svg" for line in lines), "250 integrations, 250 cards")
        self.assertEqual(len(self.summary(files)["recent"]), page.RECENT_SHOWN, "the page's table shows the latest thirty")
        left = f"wins/{sha(9999)}.svg"
        (self.out / left).write_text("a card of an earlier run that this ledger no longer explains")
        more = [verdict(n, f"2027-01-{n - 250:02d}T09:00:00Z", "bob" if n % 2 else "alice", 102 if n % 2 else 101, "toy-0002") for n in range(251, 261)]
        self.ledger(lines + more)
        later = self.make("--now", "2027-02-01T00:00:00Z")
        self.assertEqual(set(files) - set(later), set(), "every file of the first run is written by the second")
        self.assertEqual(len(self.wins(later)), 260 + 1)
        self.assertEqual(later[left], "a card of an earlier run that this ledger no longer explains", "nothing is deleted")
        self.assertEqual([name for name in wins if later[name] != wins[name]], [], "a card whose integration did not change keeps its bytes")
        self.assertEqual(sorted(name for name in later if name.startswith("members/")),
                         ["members/101-badge.svg", "members/101.svg", "members/102-badge.svg", "members/102.svg"])

    def test_a_commit_integrated_twice_has_one_card_and_the_same_one_is_rewritten(self):
        self.ledger([report_verdict(1, {}), {**report_verdict(2, {"gain_a": 0.1, "sure_a": 1}), "commit": sha(5001)}])
        files = self.make()
        self.assertEqual(sorted(self.wins(files)), [f"wins/{sha(5001)}.svg"])
        self.assertIn("10.0 % better", files[f"wins/{sha(5001)}.svg"], "the latest integration speaks")


def task(identifier, goal=None, **more):
    """A task line as the registry's task file holds one."""
    return {"id": identifier, "title": f"Title of {identifier}", "files": ["lib.c"], **({"goal": goal} if goal is not None else {}), **more}


def gain_goal(name, **more):
    return {"kind": "metric", "name": name, "min": 0.02, **more}


MINIZ = {"suspects": 0, "outputs_compared": 9289, "gain_compression_throughput_n6": 0.037, "sure_compression_throughput_n6": 1,
         "worse_compression_throughput_n6": 0, "gain_compression_throughput_n9": 0.052, "sure_compression_throughput_n9": 1,
         "worse_compression_throughput_n9": 0, "gain_ratio_n6": 0.001, "sure_ratio_n6": 0, "worse_ratio_n6": 0,
         "gain_instructions_n6": 0.043, "gain_instructions_n9": 0.061}  # as miniz's ledger keeps one: no sure_instructions_*


class TestGoal(Case):
    """The figure a card leads with is the one its task asked for, when the page is told which (--tasks) and the
    judge's report holds it; otherwise the largest gain beyond the noise, as before."""

    def figure_of(self, report, goal, *options):
        self.ledger([report_verdict(1, report)])
        files = self.make("--tasks", self.tasks([task("toy-0001", goal)]), *options)
        self.harmless(files)
        recent = self.summary(files)["recent"][0]
        return recent["figure"], recent["headline"], files[f"wins/{sha(5001)}.svg"]

    def test_the_card_leads_with_the_figure_the_task_asked_for(self):
        figure, headline, card = self.figure_of(MINIZ, gain_goal("gain_instructions_n6", **{"and": [{"name": "sure_compression_throughput_n6", "min": 1}]}))
        self.assertEqual(figure, {"metric": "instructions_n6", "gain": 0.043, "goal": True})
        self.assertEqual(headline, {"metric": "compression_throughput_n9", "gain": 0.052}, "the headline keeps its meaning in summary.json")
        self.assertIn("4.3 %", card)
        self.assertIn("instructions n6", card)
        self.assertNotIn("5.2 %", card)
        self.assertNotIn("6.1 %", card, "a larger gain that the task did not ask for does not lead")

    def test_without_the_task_file_the_headline_leads_as_before(self):
        self.ledger([report_verdict(1, MINIZ)])
        files = self.make()
        recent = self.summary(files)["recent"][0]
        self.assertEqual(recent["figure"], {"metric": "compression_throughput_n9", "gain": 0.052, "goal": False})
        self.assertEqual(recent["headline"], {"metric": "compression_throughput_n9", "gain": 0.052})
        self.assertIn("5.2 %", files[f"wins/{sha(5001)}.svg"])
        self.ledger([report_verdict(1, {})])
        self.assertIsNone(self.summary(self.make())["recent"][0]["figure"], "no figure at all: none is invented")

    def test_a_goal_whose_figure_is_beyond_the_noise_leads_too(self):
        figure, _, _ = self.figure_of({"gain_a": 0.03, "sure_a": 1, "worse_a": 0, "gain_b": 0.5, "sure_b": 1}, gain_goal("gain_a"))
        self.assertEqual(figure, {"metric": "a", "gain": 0.03, "goal": True})

    def test_the_goal_s_figure_gives_way_to_the_headline_when_it_cannot_lead(self):
        other = {"gain_b": 0.5, "sure_b": 1}
        for report in ({}, {"gain_a": 0.3, "sure_a": 0}, {"gain_a": 0.3, "sure_a": 0.5}, {"gain_a": 0.3, "sure_a": "1"}, {"gain_a": 0.3, "sure_a": True},
                       {"gain_a": 0.3, "sure_a": None}, {"gain_a": 0.3, "sure_a": 2}, {"gain_a": 0.3, "worse_a": 1}, {"gain_a": -0.1}, {"gain_a": 0},
                       {"gain_a": 0.0004}, {"gain_a": 10.01}, {"gain_a": "0.3"}, {"gain_a": True}, {"gain_a": None}, {"gain_a": [0.3]}, {"gain_a": 1e300},
                       {"gain_a": 10 ** 500}):
            with self.subTest(report=report):
                figure, _, card = self.figure_of({**report, **other}, gain_goal("gain_a"))
                self.assertEqual(figure, {"metric": "b", "gain": 0.5, "goal": False})
                self.assertIn("50.0 %", card)
                figure, _, card = self.figure_of(report, gain_goal("gain_a"))
                self.assertIsNone(figure, "and with no other sure gain, no figure at all")
                self.assertNotIn("%", card)

    def test_a_goal_that_is_not_a_gain_names_no_figure(self):
        goals = ({"kind": "correct"}, {"kind": "metric", "name": "suspects", "max": 0}, {"kind": "metric", "name": "sure_a", "min": 1},
                 {"kind": "metric", "name": "outputs_compared", "min": 1}, {"kind": "metric", "name": "gain_"}, {"kind": "metric", "name": "gain_a b"},
                 {"kind": "metric", "name": "gain_<script>alert(1)</script>"}, {"kind": "metric", "name": "gain_" + "a" * 61},
                 {"kind": "metric", "name": "GAIN_a"}, {"kind": "metric", "name": ["gain_a"]}, {"kind": "metric", "name": 5}, {"kind": "metric"},
                 {"kind": ["metric"], "name": "gain_a"}, {"kind": "other", "name": "gain_a"}, {"name": "gain_a"}, "gain_a", ["gain_a"], 7, True)
        for goal in goals:
            with self.subTest(goal=goal):
                figure, _, card = self.figure_of({"gain_a": 0.3, "gain_b": 0.5, "sure_b": 1}, goal)
                self.assertEqual(figure, {"metric": "b", "gain": 0.5, "goal": False})
                self.assertNotIn("30.0 %", card)
        self.assertEqual([page.goal_metric({"goal": goal}) for goal in goals], [None] * len(goals))
        self.assertEqual(page.goal_metric({"goal": gain_goal("gain_instructions_n6")}), "instructions_n6")
        self.assertIsNone(page.goal_metric({}))

    def test_a_hostile_task_file_says_nothing_of_itself(self):
        deep = "[" * 100_000 + "]" * 100_000
        path = self.tasks([
            task("toy-0001", gain_goal("gain_a")), task("toy-0001", gain_goal("gain_b")),  # the first line of a task speaks
            task("toy-0002", gain_goal("gain_<script>alert(1)</script>")), task("../../etc", gain_goal("gain_a")),
            task("toy-0003<script>", gain_goal("gain_a")), task(["toy-0004"], gain_goal("gain_a")), task(5, gain_goal("gain_a")),
            {**task("toy-0005", gain_goal("gain_a")), "title": "<script>alert(1)</script>", "context": "<img src=x onerror=alert(1)>"},
            json.dumps({**task("toy-0006", gain_goal("gain_a")), "padding": "x" * page.LINE_MAX}),
            "[]", "null", "7", '"<script>alert(1)</script>"', "{broken <script>alert(1)</script>", deep, "",
            b'{"id":"toy-0007","goal":{"kind":"metric","name":"gain_\xff\xfe"}}', '{"id":"toy-0008","goal":{"kind":"metric","name":"gain_\\ud800"}}',
            '{"id":"toy-0009","goal":{"kind":"metric","name":"gain_a","min":NaN}}', '{"id":"toy-0010","goal":' + "9" * 5000 + '}',
        ])
        self.assertEqual(page.read_goals(path), {"toy-0001": "a", "toy-0005": "a", "toy-0009": "a"}, "only an identifier is kept of a goal")
        self.ledger([verdict(n, f"2026-11-{n:02d}T09:00:00Z", "alice", 101, f"toy-{n:04d}", report={"gain_a": 0.3, "gain_b": 0.5, "sure_b": 1})
                     for n in range(1, 11)])
        files = self.make("--tasks", path)
        self.harmless(files)
        for name, text in files.items():
            for needle in NEEDLES:
                self.assertNotIn(needle, text.lower(), (name, needle))
        figures = {r["task"]: r["figure"]["metric"] for r in self.summary(files)["recent"]}
        self.assertEqual(figures, {"toy-0001": "a", "toy-0005": "a", "toy-0009": "a", **{f"toy-{n:04d}": "b" for n in (2, 3, 4, 6, 7, 8, 10)}})

    def test_a_task_file_that_cannot_be_read_stops_the_tool_and_an_empty_one_does_not(self):
        self.ledger([report_verdict(1, MINIZ)])
        self.assertEqual(self.make("--tasks", str(self.root / "nowhere.jsonl"), code=2), {})
        self.assertEqual(self.make("--tasks", str(self.root), code=2), {}, "a folder is not a task file")
        self.assertFalse(self.out.exists(), "a refused argument writes nothing")
        files = self.make("--tasks", self.tasks([]))
        self.assertEqual(self.summary(files)["recent"][0]["figure"]["goal"], False)

    def test_what_the_judge_measured_is_kept_as_numbers_under_identifiers(self):
        kept = page.read_report({**MINIZ, "gain_lost": -0.03, "sure_lost": 0, "worse_lost": 1, "gain_flagless": -0.002,
                                 "gain_<script>": 0.5, "gain_text": "0.5", "gain_bool": True, "gain_nan": float("nan"), "gain_inf": float("inf"),
                                 "gain_huge": 10.5, "gain_list": [1], "sure_text": 1, "gain_odd": 0.2, "sure_odd": "1", "worse_odd": True,
                                 "outputs_compared": 9289, "suspects": 0, 5: 1}, "instructions_n6")
        self.assertEqual([(row["metric"], row["gain"], row["sure"], row["worse"], row["goal"]) for row in kept["measures"]], [
            ("instructions_n6", 0.043, None, None, True),
            ("compression_throughput_n9", 0.052, 1, 0, False), ("compression_throughput_n6", 0.037, 1, 0, False), ("lost", -0.03, 0, 1, False),
            ("odd", 0.2, None, None, False), ("instructions_n9", 0.061, None, None, False), ("ratio_n6", 0.001, 0, 0, False),
            ("flagless", -0.002, None, None, False)])
        self.assertEqual((kept["outputs"], kept["suspects"], kept["measures_left_out"]), (9289, 0, 0))
        for report in ("<script>", ["gain_a", 1], None, 5, True, {}):
            self.assertEqual(page.read_report(report), {"headline": None, "figure": None, "measures": [], "measures_left_out": 0,
                                                        "outputs": None, "suspects": None})
        for value in ("9289", 9289.0, True, -1, 10 ** 16, [1], None, float("nan")):
            self.assertEqual(page.read_report({"outputs_compared": value, "suspects": value})["outputs"], None, repr(value))
            self.assertEqual(page.read_report({"outputs_compared": value, "suspects": value})["suspects"], None, repr(value))
        many = page.read_report({f"gain_m{n:03d}": n / 1000 for n in range(1, 101)}, "m001")
        self.assertEqual((len(many["measures"]), many["measures_left_out"]), (page.MEASURES_MAX, 100 - page.MEASURES_MAX))
        self.assertEqual(many["measures"][0]["metric"], "m001", "the goal's row is kept whatever the number of rows")
        self.assertEqual(page.read_changed({"files": 1, "lines": 17}), {"files": 1, "lines": 17})
        for figures in (None, "x", {"files": "1", "lines": 3}, {"files": 1}, {"files": True, "lines": 3}, {"files": 1, "lines": -3}, {"files": 1.0, "lines": 3}):
            self.assertIsNone(page.read_changed(figures), figures)

    def test_the_first_integration_of_an_account_is_the_earliest_one_over_the_whole_ledger(self):
        self.ledger([
            verdict(1, "2026-11-03T09:00:00Z", "alice", 101, "toy-0001"), verdict(2, "2026-11-03T09:00:00Z", "alice", 101, "toy-0002"),
            verdict(3, "2026-11-01T09:00:00Z", "bob", 102, "toy-0003", "refused", reason="judge_refused"),
            verdict(4, "2026-11-04T09:00:00Z", "bob", 102, "toy-0003"), verdict(5, "2026-11-02T09:00:00Z", "bob", 102, "toy-0004"),
            verdict(6, "2026-11-05T09:00:00Z", "eve", "103", "toy-0005"), verdict(7, "2026-11-06T09:00:00Z", "eve", None, "toy-0006"),
        ])
        firsts = {r["commit"]: r["first"] for r in self.summary(self.make())["recent"]}
        self.assertEqual(firsts, {sha(5001): True, sha(5002): False, sha(5004): False, sha(5005): True, sha(5006): False, sha(5007): False},
                         "one per account: the earliest instant, then the ledger's order; never for an account without a number")


class TestEmpty(Case):
    def test_an_empty_state_folder_gives_a_page_that_says_so(self):
        files = self.make()
        self.assertEqual(sorted(files), ["badge.svg", "index.html", "summary.json"])
        self.assertIn("Nothing has been integrated yet.", files["index.html"])
        self.assertIn("0 verified contributions", files["badge.svg"])
        seen, data = self.harmless(files), self.summary(files)
        self.assertEqual(seen.rows, [], "no table without a line to show")
        self.assertEqual((data["totals"]["integrations"], data["members"], data["models"], data["recent"], data["refusals"], data["tasks"]),
                         (0, [], [], [], [], None))
        self.assertEqual(data["measures"], {"yield": None, "time_to_answer_seconds": None,
                                            "judge_runs_per_integration": None, "waiting": None})
        self.assertFalse((self.out / "members").exists())

    def test_tasks_and_no_ledger_yet(self):
        self.put("feed.json", feed({"toy-0001": "open", "toy-0002": "dealt"}))
        files = self.make()
        self.assertIn("Nothing has been integrated yet.", files["index.html"])
        self.assertEqual(self.summary(files)["tasks"], {"done": 0, "dealt": 1, "open": 1, "closed": 0, "total": 2})
        self.harmless(files)

    def test_a_project_is_named_by_an_identifier_or_not_at_all(self):
        self.put("feed.json", feed({"toy-0001": "open"}, project="p" * 41))
        self.assertEqual(self.summary(self.make())["project"], "toy", "too long for a project's id: the folder's name")
        self.put("feed.json", feed({"toy-0001": "done"}, project="a" * 40))
        self.ledger([verdict(1, "2026-11-10T00:00:00Z", "alice", 101, "toy-0001")])
        files = self.make()
        self.assertIn('aria-label="La Ruche · ' + "a" * 23 + "… · 1 contribution accepted by the judge", files["members/101.svg"])
        for name in ("members/101.svg", "members/101-badge.svg", f"wins/{sha(5001)}.svg"):
            self.assertNotIn("a" * 24, files[name], "a card has a fixed width: a long name is cut")
        self.harmless(files)
        self.state = self.root / "state" / "Not an <id>"
        self.state.mkdir()
        files = self.make()
        self.assertIsNone(self.summary(files)["project"])
        self.assertIn("<h1>A hive project</h1>", files["index.html"])
        self.assertNotIn("<id>", files["index.html"] + files["summary.json"])

    def test_a_ledger_with_refusals_only_and_a_last_line_cut_short(self):
        self.ledger([verdict(1, "2026-11-10T00:00:00Z", "bob", 102, "toy-0001", "refused", reason="judge_refused"), '{"type":"verdict","at":"2026-11-1'])
        files = self.make()
        self.assertIn("Nothing has been integrated yet.", files["index.html"])
        self.assertEqual(self.summary(files)["totals"]["refused"], 1)
        self.assertEqual(self.summary(files)["ledger"], {"lines": 2, "unreadable_lines": 1, "events_left_out": 0})
        self.assertIn("Ledger lines that could not be read and are left out: 1.", files["index.html"])

    def test_a_state_folder_that_is_not_there_or_a_ledger_that_cannot_be_read_stops_the_tool(self):
        (self.state / "ledger.jsonl").mkdir()
        self.assertEqual(self.make(code=2), {})
        self.state = self.root / "nowhere"
        self.assertEqual(self.make(code=2), {})


class TestSameBytes(Case):
    def test_two_runs_give_the_same_bytes(self):
        TestHostile.hostile(self)  # a state folder with a bit of everything
        first = self.make("--now", NOW, "--title", "Toy", "--repo-url", "https://github.com/Bee-ruche/toy")
        again = self.make("--now", NOW, "--title", "Toy", "--repo-url", "https://github.com/Bee-ruche/toy")
        other = self.make("--now", NOW, "--title", "Toy", "--repo-url", "https://github.com/Bee-ruche/toy", out=self.root / "elsewhere")
        self.assertEqual(first, again)
        self.assertEqual(first, other)
        self.assertGreater(len(first), 10)
        self.assertEqual(first, self.make("--title", "Toy", "--repo-url", "https://github.com/Bee-ruche/toy"), "HIVE_NOW is the same instant here")
        self.assertNotEqual(first["index.html"], self.make("--now", "2026-12-25T00:00:00Z", "--title", "Toy")["index.html"])
        self.assertEqual([path.name for path in self.out.rglob("*") if path.name.startswith(".")], [], "no temporary file is left")


class TestEndToEnd(test_hive.Base):
    """A ledger, a feed and statistics that the hive itself wrote, from real forks and a real run."""

    def test_the_page_of_a_real_run_shows_alice_with_one_integration(self):
        bob = self.w.fork("bob", 102)
        self.alice.submit("toy-0001", model="claude-fable-5-2")
        bob.submit("toy-0004", content=test_hive.LIB + "/* REFUSE */\n")
        results = {result["login"]: result for result in self.w.run()}
        self.assertEqual((results["alice"]["result"], results["bob"]["result"], results["bob"]["reason"]), ("accepted", "refused", "judge_refused"))
        carol = self.w.fork("carol", 103)
        carol.ready()
        self.w.run()  # carol is dealt one of the three tasks left; the feed and the statistics are the run's own files
        dealt = self.w.deal(carol, self.w.dealt_by_runs()[0][0])
        out = self.w.root / "site"
        with contextlib.redirect_stdout(io.StringIO()):
            page.main(["--state", str(self.w.state), "--out", str(out), "--title", "A toy project", "--repo-url", "https://github.com/Bee-ruche/toy",
                       "--tasks", str(self.w.registry / "hive/tasks/toy.jsonl")])  # the registry's own task file, as a run has it
        text, data = (out / "index.html").read_text(encoding="utf-8"), json.loads((out / "summary.json").read_text())
        seen = Seen(text)
        self.assertEqual(seen.row("alice"), ["alice", "1", "1", "100 % (1 of 1)", "2026-11-12"])
        self.assertIsNone(seen.row("bob"))
        self.assertEqual(seen.row("2026-11-12"), ["2026-11-12", "toy-0001 Make f0 faster", "alice", self.w.tip()[:10]])
        self.assertIn("https://github.com/alice", seen.hrefs)
        self.assertIn(f"https://github.com/Bee-ruche/toy/commit/{self.w.tip()}", seen.hrefs)
        self.assertEqual(seen.row("judge_refused"), ["judge_refused", "1", hive.REASONS["judge_refused"]])
        self.assertEqual(seen.row("claude-fable-5-2"), ["claude-fable-5-2", "1", "1", "100 %"])
        self.assertEqual(seen.row("undeclared"), ["undeclared", "1", "0", "0 %"])
        self.assertEqual((data["project"], data["totals"]["integrations"], data["totals"]["judged"], data["stats_json"]), ("toy", 1, 2, "agrees"))
        self.assertEqual(data["tasks"], {"done": 1, "dealt": 1, "open": 2, "closed": 1, "total": 5})
        self.assertEqual((dealt, data["measures"]["waiting"]), (test_hive.NOW, None), "carol's task is dealt; no candidate waits")
        self.assertEqual([(m["id"], m["login"], m["integrations"]) for m in data["members"]], [(101, "alice", 1)])
        self.assertEqual(data["measures"]["yield"], 0.5)
        self.assertEqual(sorted(path.name for path in (out / "members").iterdir()), ["101-badge.svg", "101.svg"])
        card = minidom.parse(str(out / "members" / "101.svg")).documentElement
        self.assertEqual(card.getAttribute("aria-label"),
                         "La Ruche · toy · 1 contribution accepted by the judge · first Nov 2026 · latest 12 Nov 2026 · GitHub account 101")
        self.assertIn("1 verified contribution<", (out / "badge.svg").read_text(encoding="utf-8"))
        self.assertIn(">1 accepted by the judge<", (out / "members" / "101-badge.svg").read_text(encoding="utf-8"))
        win = minidom.parse(str(out / "wins" / f"{self.w.tip()}.svg")).documentElement
        self.assertIn(f"@alice · first integration · 12 Nov 2026 · declared model: claude-fable-5-2 · commit {self.w.tip()[:10]} · Bee-ruche/toy",
                      win.getAttribute("aria-label"))
        self.assertIn("toy-0001 · Make f0 faster", win.getAttribute("aria-label"))
        self.assertEqual(sorted(path.name for path in (out / "wins").iterdir()), [f"{self.w.tip()}.svg"])
        self.assertNotIn("<script", text)


class TestPatterns(unittest.TestCase):
    def test_the_patterns_written_again_here_are_the_hives(self):
        for name in ("LOGIN", "TASK_ID", "MODEL", "SHA", "ISO"):
            self.assertEqual(getattr(page, name).pattern, getattr(hive, name).pattern, name)

    def test_every_reason_of_the_hive_has_a_text_the_page_can_show(self):
        self.assertTrue(all(isinstance(text, str) and text for text in hive.REASONS.values()))


if __name__ == "__main__":
    unittest.main()
