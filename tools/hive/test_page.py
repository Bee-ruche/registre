#!/usr/bin/env python3
"""Tests of the project page (tools/hive/page.py): the figures, what a hostile ledger cannot do, the empty state,
the same bytes for the same input, and one run on a ledger the hive itself wrote.

Standard library only, no network. `python3 tools/hive/test_page.py`
"""

import contextlib
import html
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
REPO = "https://github.com/Bee-ruche/toy"
SITE = "https://bee-ruche.github.io/hive/toy"
MEMBER_HREF = re.compile(r"https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
COMMIT_HREF = re.compile(r"https://github\.com/Bee-ruche/toy/commit/[0-9a-f]{40}\Z")
# Every name the tool may write a file under, spelled here again: the tests do not rely on page.py's own patterns.
NAMED = re.compile(r"index\.html|badge\.svg|summary\.json|members/[1-9][0-9]{0,18}(?:-badge)?\.svg|wins/[0-9a-f]{40}\.(?:svg|html)")
# The files of the site that index.html may link to (a link must also name a file that was written), and the one a
# page under wins/ may: its own card, beside it.
LOCAL_HREF = re.compile(r"(?:wins/[0-9a-f]{40}\.html|members/[1-9][0-9]{0,18}(?:-badge)?\.svg)\Z")
BESIDE_HREF = re.compile(r"[0-9a-f]{40}\.svg\Z")
# The elements an SVG of the tool may hold. « svg » is also a card's inner frame; « style » is there for one reason: a
# card must read on a light and on a dark page in ONE file, which takes a prefers-color-scheme rule. A style can also
# load and hide, so harmless() accepts one only when it is page.CARD_CSS, byte for byte, directly under the root.
SVG_TAGS = ("svg", "title", "style", "rect", "path", "text")
NO_TAGS = ("script", "iframe", "object", "embed", "img", "image", "link", "form", "base", "input", "button", "video", "audio", "frame", "applet",
           "use", "foreignobject", "animate", "set", "textarea", "select")
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
    """What a browser would see in a page: the elements, their attributes, the rows of its tables, its styles, the
    anchors it defines, and the text of its body."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.attributes, self.hrefs, self.rows, self.cell = [], [], [], [], None
        self.styles, self.ids, self.metas, self.open, self.words, self.heads = [], [], {}, [], [], []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(name for name, _ in attrs)
        self.hrefs.extend(value for name, value in attrs if name in ("href", "src", "xlink:href", "action"))
        self.ids.extend(value for name, value in attrs if name == "id")
        if tag == "meta":
            self.metas[dict(attrs).get("property") or dict(attrs).get("name") or dict(attrs).get("http-equiv")] = dict(attrs).get("content")
            return
        self.open.append(tag)
        if tag in ("h1", "h2"):
            self.heads.append("")
        if tag == "style":
            self.styles.append("")
        elif tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th") and self.rows:
            self.rows[-1].append("")
            self.cell = True

    def handle_endtag(self, tag):
        if tag in self.open:
            while self.open.pop() != tag:
                pass
        if tag in ("td", "th"):
            self.cell = None

    def handle_data(self, data):
        if self.open and self.open[-1] == "style":
            self.styles[-1] += data
        elif "body" in self.open and "svg" not in self.open:
            self.words.append(data)
            if "h1" in self.open or "h2" in self.open:
                self.heads[-1] += data
        if self.cell:
            self.rows[-1][-1] += data

    def row(self, first):
        return next((row for row in self.rows if row and row[0] == first), None)

    @property
    def said(self):
        """The body's text, as one string (a card inlined in the page says its own in its label: it is left out)."""
        return "".join(self.words)


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
        self.errors = errors.getvalue()  # what the run said on its standard error
        return {str(path.relative_to(out)): path.read_text(encoding="utf-8") for path in sorted(Path(out).rglob("*")) if path.is_file()} \
            if Path(out).exists() else {}

    def summary(self, files):
        return json.loads(files["summary.json"])

    def harmless(self, files, join=JOIN, site=None):
        """What must hold for any output, whatever the ledger said: only the files this tool writes; no script, no
        handler, nothing loaded; no style but the two constants; no link but a member's profile, the project's
        repository, an integrated commit, the join page, a file of the site that was written, or an anchor of the
        same page; SVGs that parse. Returns what a browser would see in index.html."""
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
            if name.endswith(".html"):
                self.harmless_page(name, text, files, join, site)
        return Seen(files["index.html"])

    def harmless_page(self, name, text, files, join, site):
        seen, under_wins = Seen(text), name.startswith("wins/")
        for tag in NO_TAGS:
            self.assertNotIn(tag, seen.tags, name)
        for attribute in seen.attributes:
            self.assertFalse(attribute.startswith("on") or attribute in ("style", "src", "srcset", "srcdoc", "action", "formaction"), (name, attribute))
        # The styles: the pages' own constant, once, in the head; then the cards' constant, once for each inlined card.
        cards = text.count("<svg xmlns=")
        self.assertEqual(seen.styles, [str(page.CSS)] + [str(page.CARD_CSS)] * cards, name)
        self.assertEqual((text.count("<style"), text.count(f"<style>{page.CSS}</style>"), text.count(f"<style>{page.CARD_CSS}</style>")),
                         (1 + cards, 1, cards), "byte for byte")
        self.assertEqual(cards, 1 if under_wins else 0, "a card is inlined in its own page and nowhere else")
        for href in seen.hrefs:
            if href.startswith("#"):
                self.assertIn(href[1:], seen.ids, (name, href))
            elif under_wins:
                self.assertTrue(href in (join, "../join.html", REPO) or MEMBER_HREF.match(href) or COMMIT_HREF.match(href)
                                or (href == "../index.html" and "index.html" in files)
                                or (BESIDE_HREF.match(href) and name == f"wins/{href[:40]}.html" and f"wins/{href}" in files), (name, href))
            else:
                self.assertTrue(href in (join, "join.html", REPO) or MEMBER_HREF.match(href) or COMMIT_HREF.match(href)
                                or (LOCAL_HREF.match(href) and href in files), (name, href))
        self.assertEqual(len(seen.ids), len(set(seen.ids)), "an anchor names one place")
        for address in re.findall(r"https?://[^\"<> ]*", text):
            self.assertTrue(address.startswith("https://github.com/") or address == "http://www.w3.org/2000/svg"
                            or (site is not None and under_wins and address.startswith(f"{site}/wins/{name[5:45]}.")), (name, address))
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
        self.assertEqual(data["totals"], {"verdicts": 6, "judged": 4, "accepted": 3, "integrations": 3, "refused": 3, "ended_by_hive": 0,
                                          "judge_failures": 2})
        self.assertEqual(data["tasks"], {"done": 3, "dealt": 1, "open": 2, "closed": 1, "total": 7})
        self.assertEqual(data["week"], {"since": "2026-11-05T12:00:00Z", "integrations": 2, "members": 2, "judged": 3, "accepted": 2,
                                        "acceptance_rate": 0.6667})
        self.assertEqual(data["measures"], {"yield": 0.75, "time_to_answer_seconds": None,
                                            "judge_runs_per_integration": 2.0, "waiting": None})
        self.assertEqual(data["refusals"], [{"reason": reason, "count": 1} for reason in ("conflict", "judge_refused", "path_outside_task")])
        # Three accounts in all: no model has enough members behind it for its judged count and its rate to be shown
        # (TestNobodyIsRanked holds the models' table when there are enough).
        self.assertEqual(data["models"], [
            {"model": None, "judged": None, "accepted": 2, "acceptance_rate": None, "too_few_members": True},
            {"model": "claude-fable-5-2", "judged": None, "accepted": 1, "acceptance_rate": None, "too_few_members": True},
            {"model": "gpt-x", "judged": None, "accepted": 0, "acceptance_rate": None, "too_few_members": True}])
        self.assertEqual([(r["at"][:10], r["task"], r["login"], r["commit"]) for r in data["recent"]],
                         [("2026-11-12", "toy-0004", "carol", sha(5012)), ("2026-11-10", "toy-0002", "alice-new", sha(5007)),
                          ("2026-11-01", "toy-0001", "alice-new", sha(5001))])
        # The page says the same.
        self.assertEqual(seen.rows[seen.rows.index(seen.row("alice-new")) - 1], ["Member", "Accepted contributions", "To show"])
        self.assertEqual(seen.row("alice-new"), ["alice-new", "2", "card · badge"])
        self.assertEqual(seen.row("carol"), ["carol", "1", "card · badge"])
        self.assertEqual(seen.row("claude-fable-5-2"), ["claude-fable-5-2", page.TOO_FEW, "1", page.TOO_FEW])
        self.assertEqual(seen.row("gpt-x"), ["gpt-x", page.TOO_FEW, "0", page.TOO_FEW])
        self.assertEqual(seen.row("undeclared"), ["undeclared", page.TOO_FEW, "2", page.TOO_FEW])
        for reason in ("conflict", "judge_refused", "path_outside_task"):
            self.assertEqual(seen.row(reason), [reason, "1", hive.REASONS[reason]])
        self.assertEqual(seen.row("2026-11-12"), ["2026-11-12", "toy-0004 Title of toy-0004", "no figure", "carol", sha(5012)[:10]])
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
        self.assertEqual([(m["id"], m["login"]) for m in self.summary(files)["members"]], [(105, "Alice"), (101, None)],
                         "an account without a login is listed after those that have one")
        seen = self.harmless(files)
        self.assertEqual(seen.hrefs.count("https://github.com/Alice"), 3, "the first screen, the integrations and the members' table, for account 105 only")
        self.assertIsNotNone(seen.row("account 101"))

    def test_this_week_moves_with_the_instant(self):
        self.assertEqual(self.summary(self.make("--now", "2026-11-19T10:00:00Z"))["week"]["integrations"], 1)
        self.assertEqual(self.summary(self.make("--now", "2026-12-25T00:00:00Z"))["week"],
                         {"since": "2026-12-18T00:00:00Z", "integrations": 0, "members": 0, "judged": 0, "accepted": 0, "acceptance_rate": None})
        with mock.patch.dict(os.environ, {"HIVE_NOW": "2026-11-08T09:00:00Z"}):
            self.assertEqual(self.summary(self.make())["week"]["integrations"], 0, "HIVE_NOW is the clock, as for the hive")

    def test_every_member_with_an_integration_is_listed_by_login_and_the_latest_thirty_integrations_are(self):
        lines, number = [], 0
        login = lambda member: f"m{member * 37 % 60:02d}"  # noqa: E731  (the logins' order is not the order of the counts)
        for member in range(59, -1, -1):  # account 1000 has 60 integrations, account 1059 has one; the most active come last in time
            for _ in range(60 - member):
                number += 1
                lines.append(verdict(number, f"2026-10-{1 + number % 28:02d}T00:00:00Z" if member else f"2026-11-{1 + number % 9:02d}T00:00:00Z",
                                     login(member), 1000 + member, "toy-0001"))
        self.ledger(lines)
        files = self.make()
        data, seen = self.summary(files), self.harmless(files)
        listed = sorted(range(60), key=login)  # the sixty accounts, as a dictionary lists their logins
        self.assertEqual([m["login"] for m in data["members"]], [f"m{position:02d}" for position in range(60)], "all of them, by login")
        self.assertEqual([m["integrations"] for m in data["members"]], [60 - member for member in listed])
        self.assertNotIn([m["integrations"] for m in data["members"]], (sorted(range(1, 61)), sorted(range(1, 61), reverse=True)),
                         "the order is not the order of the counts, either way")
        shown = [row for row in seen.rows if len(row) == 3 and row[0].startswith("m")]
        self.assertEqual(shown, [[login(member), str(60 - member), "card · badge"] for member in listed], "the table lists every one of them: no cut")
        self.assertEqual([i for i in seen.ids if i.startswith("member-")], [f"member-{1000 + member}" for member in listed],
                         "each row has its anchor, made from the account's number")
        self.assertEqual([h for h in seen.hrefs if h.startswith("members/")],
                         [f"members/{1000 + member}{end}.svg" for member in listed for end in ("", "-badge")], "and says where its card and badge are")
        self.assertEqual([(m["card"], m["badge"]) for m in data["members"]],
                         [(f"members/{1000 + member}.svg", f"members/{1000 + member}-badge.svg") for member in listed])
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


class TestRefusals(Case):
    """What was refused of candidates, and, apart from it, what the hive's own side ended at no cost to the member."""

    def refused(self, *reasons):
        self.ledger([verdict(n, f"2026-10-{n:02d}T09:00:00Z", "bob", 102, "toy-0001", "refused", judged=reason == "judge_refused", reason=reason)
                     for n, reason in enumerate(reasons, 1)])
        files = self.make()
        return self.summary(files), self.harmless(files)

    def test_what_the_hive_itself_ended_is_not_listed_as_a_refusal_of_a_candidate(self):
        data, seen = self.refused("not_answered", "task_closed", "task_closed", "conflict", "judge_refused")
        self.assertEqual(data["refusals"], [{"reason": "conflict", "count": 1}, {"reason": "judge_refused", "count": 1}])
        self.assertEqual(data["ended_by_hive"], [{"reason": "not_answered", "count": 1}, {"reason": "task_closed", "count": 2}])
        self.assertEqual({key: data["totals"][key] for key in ("verdicts", "refused", "ended_by_hive")}, {"verdicts": 5, "refused": 2, "ended_by_hive": 3})
        head = seen.rows.index(["Reason", "Candidates", "What it means"])
        self.assertEqual(seen.rows[head + 1:], [[reason, "1", hive.REASONS[reason]] for reason in ("conflict", "judge_refused")],
                         "the table of what was refused holds the candidates' refusals and no other")
        self.assertIn("A refusal says something about the candidate, not about its member."
                      "Ended by the hive, at no cost to the member: 3. These candidates were not refused: "
                      f"not_answered (1), {hive.REASONS['not_answered']}; task_closed (2), {hive.REASONS['task_closed']}.Three measures", seen.said)

    def test_with_nothing_refused_the_page_says_so_and_still_says_what_the_hive_ended(self):
        data, seen = self.refused("task_closed")
        self.assertEqual((data["refusals"], data["totals"]["refused"], data["totals"]["ended_by_hive"]), ([], 0, 1))
        self.assertIn(f"No candidate has been refused yet.Ended by the hive, at no cost to the member: 1. These candidates were not refused: "
                      f"task_closed (1), {hive.REASONS['task_closed']}.Three measures", seen.said)
        data, seen = self.refused("conflict")
        self.assertEqual((data["ended_by_hive"], data["totals"]["ended_by_hive"]), ([], 0))
        self.assertNotIn("Ended by the hive", seen.said)

    def test_the_hive_s_side_is_two_reasons_and_every_other_reason_is_a_refusal_of_the_candidate(self):
        self.assertEqual(page.HIVE_SIDE, ("not_answered", "task_closed"))
        self.assertEqual(page.HIVE_SIDE, hive.HIVE_SIDE_REASONS)
        self.assertRegex(hive.REASONS["not_answered"], r"the hive spent .* for no fault it can pin on them")
        self.assertRegex(hive.REASONS["task_closed"], r"the task was closed while the candidate waited")
        data, seen = self.refused(*hive.REASONS, "a reason of tomorrow")
        self.assertEqual({r["reason"] for r in data["refusals"]}, {*hive.REASONS, None} - {"not_answered", "task_closed"})
        self.assertEqual({r["reason"] for r in data["ended_by_hive"]}, {"not_answered", "task_closed"})
        self.assertEqual((data["totals"]["refused"], data["totals"]["ended_by_hive"]), (len(hive.REASONS) - 1, 2), "a reason the page does not know is a refusal")


def told(text):
    """What a file tells a reader: its text and its labels, without the markup, the styles and the drawing's numbers."""
    text = re.sub(r"(?s)<style>.*?</style>", " ", text)
    labels = re.findall(r'(?:aria-label|content|data-label)="([^"]*)"', text)
    return html.unescape(" ".join([re.sub(r"<[^>]+>", " ", text), *labels]))


def people(value):
    """Every object of a JSON value that speaks of one person: it holds a login or an account's number."""
    if isinstance(value, dict):
        if {"login", "member", "member_id", "id"} & set(value):
            yield value
        for inner in value.values():
            yield from people(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from people(inner)


class TestNobodyIsRanked(Case):
    """The page ranks nobody: every member with an accepted contribution is listed, by login, with the number of its
    accepted contributions; what was refused is counted for the project, and for a model once enough members stand
    behind it, never for a person, in any file."""

    def several(self):
        """Six accounts whose counts follow neither the logins' order nor its reverse; three of them had candidates
        refused, in numbers (41, 67, 23; with their accepted ones 42, 69, 23 judged) that nothing else on the site is."""
        lines, number = [], 0

        def some(count, login, member_id, day, result="accepted"):
            nonlocal number
            for _ in range(count):
                number += 1
                lines.append(verdict(number, f"2026-11-{day:02d}T09:00:00Z", login, member_id, "toy-0001", result,
                                     reason=None if result == "accepted" else "judge_refused"))
        for count, login, member_id in ((5, "Zoe", 201), (1, "bob", 202), (3, "alice", 203), (2, "Carol", 204), (4, "no login", 206)):
            some(count, login, member_id, 6 + member_id % 3)
        for count, login, member_id in ((41, "bob", 202), (67, "Carol", 204), (23, "dave", 205)):
            some(count, login, member_id, 1, "refused")
        self.ledger(lines)

    def test_members_are_listed_by_login_with_what_was_accepted_and_no_file_says_what_was_refused_of_a_person(self):
        self.several()
        files = self.make("--repo-url", REPO, "--site-url", SITE)
        data, seen = self.summary(files), self.harmless(files, site=SITE)
        self.assertEqual([(m["login"], m["id"], m["integrations"]) for m in data["members"]],
                         [("alice", 203, 3), ("bob", 202, 1), ("Carol", 204, 2), ("Zoe", 201, 5), (None, 206, 4)],
                         "as a dictionary lists the logins, case ignored; an account without a login comes after")
        self.assertEqual({key for member in data["members"] for key in member},
                         {"id", "login", "integrations", "first_integration", "last_integration", "card", "badge"})
        head = seen.rows.index(["Member", "Accepted contributions", "To show"])
        self.assertEqual(seen.rows[head + 1:head + 6], [[who, count, "card · badge"] for who, count in (
            ("alice", "3"), ("bob", "1"), ("Carol", "2"), ("Zoe", "5"), ("account 206", "4"))], "the table says the same, and nothing more")
        self.assertEqual(data["members_without_integration"], 1, "counted, not named")
        self.assertEqual((data["totals"]["judged"], data["totals"]["refused"], data["totals"]["integrations"]), (146, 131, 15), "the project's own figures")
        # No file says how many candidates of one person were judged or refused, nor a rate of theirs.
        self.assertGreater(len(files), 40)
        for name, text in files.items():
            said = told(text)
            self.assertNotRegex(said, r"\b(41|42|67|69|23)\b", name)
            self.assertNotRegex(said, r"(?i)\btop\b|leader|\bbest\b|most active|\b1st\b|\bfirst place\b|\bscore", name)
            if name.startswith("members/"):
                self.assertNotRegex(said, r"(?i)refus|judged|\brate\b|%|\brank", name)
            if name.startswith("wins/"):
                self.assertNotRegex(said, r"(?i)refus|\brate\b", name)
        for person in people(data):
            self.assertEqual([key for key in person if re.search(r"judged|refus|rate|rank|accepted|score|position|yield", key)], [], person)
        self.assertNotIn("dave", "".join(files.values()), "an account with no accepted contribution is named nowhere")
        self.assertIn("nobody is ranked", seen.said)

    def test_members_with_the_same_login_in_another_case_or_no_login_at_all_are_listed_by_account_number(self):
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "b", 9, "toy-0001"), verdict(2, "2026-11-02T09:00:00Z", "", 8, "toy-0001"),
                     verdict(3, "2026-11-03T09:00:00Z", "A", 7, "toy-0001"), verdict(4, "2026-11-04T09:00:00Z", "-", 6, "toy-0001"),
                     verdict(5, "2026-11-05T09:00:00Z", "a-", 5, "toy-0001"), verdict(6, "2026-11-06T09:00:00Z", "a-b", 4, "toy-0001")])
        self.assertEqual([(m["login"], m["id"]) for m in self.summary(self.make())["members"]],
                         [("A", 7), ("a-b", 4), ("b", 9), (None, 5), (None, 6), (None, 8)])

    def rows(self, **models):
        """page.model_rows() for {model: (judged, accepted, the accounts behind it)}, as (model, judged, accepted, rate, kept back)."""
        rows = page.model_rows({None if model == "undeclared" else model.replace("_", "-"): {"judged": judged, "accepted": accepted, "ids": set(ids)}
                                for model, (judged, accepted, ids) in models.items()})
        self.assertEqual([set(row) for row in rows], [{"model", "judged", "accepted", "acceptance_rate", "too_few_members"}] * len(rows))
        return [tuple(row.values()) for row in rows]

    def test_a_model_s_judged_count_and_rate_are_shown_once_enough_members_stand_behind_it(self):
        self.assertEqual(page.MODEL_MEMBERS_MIN, 5)
        five, four, others = range(1, 6), range(11, 15), range(21, 27)
        # Five accounts: shown. Four: kept back, with the number accepted. Those kept back have five accounts between them.
        self.assertEqual(self.rows(model_a=(7, 3, five), model_b=(50, 2, four), model_c=(9, 1, [15])),
                         [("model-a", 7, 3, 0.4286, False), ("model-b", None, 2, None, True), ("model-c", None, 1, None, True)])
        # The rows shown are in the order of their judged counts; those kept back in the order of their names, whatever
        # their figures; « undeclared » is a row like another.
        self.assertEqual(self.rows(model_a=(7, 3, five), model_d=(8, 8, others), model_z=(90, 1, [15, 16]), model_y=(1, 1, [17, 18, 19]),
                                   undeclared=(40, 0, [20])),
                         [("model-d", 8, 8, 1.0, False), ("model-a", 7, 3, 0.4286, False), (None, None, 0, None, True),
                          ("model-y", None, 1, None, True), ("model-z", None, 1, None, True)])
        self.assertEqual(self.rows(undeclared=(40, 4, five))[0], (None, 40, 4, 0.1, False))
        # The project's totals are on the page: one row kept back alone is the totals minus the rows shown. So rows are
        # kept back, the one with the fewest accounts first, until those kept back have enough accounts between them.
        self.assertEqual(self.rows(model_a=(7, 3, five), model_b=(50, 2, four)),
                         [("model-a", None, 3, None, True), ("model-b", None, 2, None, True)], "four accounts kept back alone: the other row too")
        self.assertEqual(self.rows(model_a=(7, 3, five), model_b=(50, 2, four), model_d=(8, 8, others)),
                         [("model-d", 8, 8, 1.0, False), ("model-a", None, 3, None, True), ("model-b", None, 2, None, True)],
                         "the row with the fewest accounts joins it, and that is enough")
        self.assertEqual(self.rows(model_a=(7, 3, five), model_b=(50, 2, four), model_c=(9, 1, [11])),
                         [("model-a", None, 3, None, True), ("model-b", None, 2, None, True), ("model-c", None, 1, None, True)],
                         "an account behind two rows kept back is one account")
        self.assertEqual(self.rows(model_b=(50, 2, four)), [("model-b", None, 2, None, True)])
        self.assertEqual(self.rows(), [])

    def test_the_page_keeps_back_the_judged_count_of_a_model_few_members_declared(self):
        lines = [verdict(n, "2026-11-01T09:00:00Z", f"m{n}", 300 + n, "toy-0001", "accepted" if n < 4 else "refused", model="model-a",
                         reason=None if n < 4 else "judge_refused") for n in range(1, 8)]  # seven accounts, three accepted
        lines += [verdict(10 + n, "2026-11-02T09:00:00Z", "solo", 400, "toy-0002", "accepted" if n == 0 else "refused", model="model-b",
                          reason=None if n == 0 else "judge_refused") for n in range(42)]  # one account: 42 judged, 41 refused
        lines += [verdict(60 + n, "2026-11-03T09:00:00Z", None, None, "toy-0003", "refused", model="model-b", reason="judge_refused")
                  for n in range(4)]  # lines without an account add no account
        lines += [verdict(70 + n, "2026-11-04T09:00:00Z", f"n{n}", 500 + n, "toy-0004", "refused", reason="judge_refused") for n in range(4)]
        self.ledger(lines)
        files = self.make()
        data, seen = self.summary(files), self.harmless(files)
        self.assertEqual(data["models"], [
            {"model": "model-a", "judged": 7, "accepted": 3, "acceptance_rate": 0.4286, "too_few_members": False},
            {"model": None, "judged": None, "accepted": 0, "acceptance_rate": None, "too_few_members": True},
            {"model": "model-b", "judged": None, "accepted": 1, "acceptance_rate": None, "too_few_members": True}])
        self.assertEqual([seen.row(name) for name in ("model-a", "undeclared", "model-b")],
                         [["model-a", "7", "3", "43 %"], ["undeclared", page.TOO_FEW, "0", page.TOO_FEW], ["model-b", page.TOO_FEW, "1", page.TOO_FEW]])
        self.assertIn("Declared by each worker: a statistic, not a proof. " + page.MODELS_NOTE, seen.said)
        self.assertIn("at least 5 members", page.MODELS_NOTE)
        own = Seen(files[f"wins/{sha(5010)}.html"]).said
        self.assertIn("@solo", own)
        self.assertIn("declared model: model-b", own, "the page of an accepted contribution names its member and the model it declared")
        for name, text in files.items():
            self.assertNotRegex(told(text), r"\b(41|42|45|46)\b", (name, "how many of that member's candidates were judged or refused"))

    def test_an_acceptance_without_a_judgement_is_an_integration_and_not_a_judged_candidate(self):
        """The hive writes no such line. If the ledger holds one, it is an integration like another for its member, its
        card and the badges, which all count the same lines; it is not in what the judge judged and accepted."""
        self.ledger([verdict(1, "2026-11-10T09:00:00Z", "alice", 101, "toy-0001", judged=False), verdict(2, "2026-11-11T09:00:00Z", "alice", 101, "toy-0002"),
                     verdict(3, "2026-11-11T10:00:00Z", "bob", 102, "toy-0003", "refused", reason="judge_refused")])
        files = self.make()
        data = self.summary(files)
        self.assertEqual([(m["login"], m["integrations"]) for m in data["members"]], [("alice", 2)])
        self.assertIn(">2 accepted by the judge<", files["members/101-badge.svg"])
        self.assertIn("2 verified contributions", files["badge.svg"])
        self.assertEqual(sorted(name for name in files if name.startswith("wins/") and name.endswith(".svg")), [f"wins/{sha(5000 + n)}.svg" for n in (1, 2)])
        self.assertEqual(data["totals"], {**data["totals"], "verdicts": 3, "judged": 2, "accepted": 1, "integrations": 2})
        self.assertEqual({key: data["week"][key] for key in ("integrations", "judged", "accepted", "acceptance_rate")},
                         {"integrations": 2, "judged": 2, "accepted": 1, "acceptance_rate": 0.5})
        self.assertEqual(data["measures"]["yield"], 0.5)
        self.assertEqual([(m["model"], m["accepted"]) for m in data["models"]], [(None, 1)], "a model's row counts what was judged")


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
                                                *(f"members/{i}-badge.svg" for i in valid), *wins, *(name[:-4] + ".html" for name in wins)]))
        self.assertEqual(sorted(after), sorted(["bystander.txt", "state", "state/toy", *(f"state/toy/{n}" for n in ("ledger.jsonl", "feed.json", "stats.json")),
                                                "site", "site/members", "site/wins", *(f"site/{name}" for name in files)]), "no temporary file is left")
        for name, text in files.items():
            for needle in NEEDLES:
                self.assertNotIn(needle, text.lower(), (name, needle))
        seen = self.harmless(files)
        self.assertIn("Written by the AI coding assistant of GitHub account 201, measured", Seen(files[f"wins/{sha(5020)}.html"]).said,
                      "a login that spells markup is no login: its integration's page names the account by its number")
        # What was dropped, and what was kept.
        data = self.summary(files)
        self.assertEqual({m["id"]: m["login"] for m in data["members"]},
                         {**{201 + i: None for i in range(len(LOGINS))}, 300: "mallory", 398: None, 399: None, 500: "honest"})
        self.assertEqual(seen.hrefs.count("https://github.com/honest"), 4, "the first screen, two integrations, the members' table")
        self.assertEqual([m["model"] for m in data["models"]], [None, "claude-fable-5-2"], "a model that is not an identifier is undeclared")
        self.assertEqual({r["task"] for r in data["recent"]}, {"toy-0001", "toy-0002", None}, "a task id that is not one is unknown")
        self.assertEqual(data["tasks"], {"done": 2, "dealt": 0, "open": 0, "closed": 0, "total": 2}, "a task counts once, under a real id and status")
        self.assertEqual(data["totals"], {"verdicts": 38, "judged": 35, "accepted": 32, "integrations": 35, "refused": 3, "ended_by_hive": 0,
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
        own = files[f"wins/{sha(5020)}.html"]  # the page of the first hostile login's integration
        self.assertIn("<strong><a href=\"https://github.com/%22%3E%3Cscript%3Ealert%281%29%3C%2Fscript%3E\" rel=\"nofollow noopener\">"
                      "@&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;</a></strong>", own, "and the builder of its page: quoted in the link, escaped in the text")
        self.assertIn("&lt;img src=x&gt;", files[f"wins/{sha(5040)}.html"], "a hostile model, in the story of its page")
        for name, content in files.items():
            if not name.endswith(".html"):
                continue
            self.assertNotIn("<script", content.lower(), name)
            self.assertNotIn("<img", content.lower(), name)
            seen = Seen(content)
            for tag in NO_TAGS:
                self.assertNotIn(tag, seen.tags, name)
            self.assertEqual([attribute for attribute in seen.attributes if attribute.startswith("on") or attribute in ("src", "style")], [], name)
            self.assertEqual(seen.styles, [str(page.CSS)] + [str(page.CARD_CSS)] * name.startswith("wins/"), name)
            for href in seen.hrefs:
                self.assertTrue(href in (JOIN, "#join", "../index.html") or re.match(r"https://github\.com/[A-Za-z0-9%._~-]*\Z", href)
                                or (LOCAL_HREF.match(href) and href in files) or (BESIDE_HREF.match(href) and f"wins/{href}" in files), (name, href))
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
            self.assertEqual((page.repo_link(address), page.repo_name(address)), (None, None), address)
        self.assertEqual((page.repo_link(repo), page.repo_name(repo), type(page.repo_link(repo))), (repo, "Bee-ruche/toy", page.Link))

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
        for end in ("svg", "html"):
            for name in (f"wins/x.{end}", f"wins/{sha(10).upper()}.{end}", f"wins/{sha(1)}.{end}/../../x", f"wins/../x.{end}", f"wins/{sha(1)[:-1]}.{end}",
                         f"wins/{sha(1)}.{end}\n", f"wins/a/{sha(1)}.{end}", f"wins/{sha(1)}.{end.upper()}", f"wins/{sha(1)}.svg.{end}", f"{sha(1)}.{end}",
                         f"wins/{sha(1)}", f"wins/{sha(1)}.htm", f"wins/{sha(1)}.{end}.tmp", f"wins/.{sha(1)}.{end}", f"index.{end}\n", "members/101.html"):
                with self.assertRaises(page.PageError):
                    page.write(self.out, {name: "x"})
        self.assertEqual((page.win_name(sha(1)), page.win_page_name(sha(1)), page.win_page_link(sha(1)), page.beside(sha(1))),
                         (f"wins/{sha(1)}.svg", f"wins/{sha(1)}.html", f"wins/{sha(1)}.html", f"{sha(1)}.svg"))
        for commit in ("", "abc", sha(1) + "0", sha(1)[:-1] + "G", sha(1) + "\n", "../" + sha(1)[3:], sha(10).upper(), None, 5, ["a"], sha(1) + "/../x"):
            self.assertEqual((page.win_name(commit), page.win_page_name(commit), page.win_page_link(commit), page.beside(commit)), (None,) * 4, commit)
        self.assertEqual(tree(self.root), {"state": None, "state/toy": None}, "a refused name writes nothing, anywhere")

    def test_an_address_given_on_the_command_line_must_be_on_github(self):
        self.ledger([verdict(1, "2026-11-10T00:00:00Z", "alice", 101, "toy-0001")])
        for address in ("javascript:alert(1)", "http://github.com/a/b", "https://github.com.evil.example/a/b", "https://evil.example/a/b",
                        "https://github.com/a/b/c", "https://github.com/a/..", "https://github.com/a/b\"onload=\"x", "https://github.com/a/b\n", "//github.com/a/b"):
            self.assertEqual(self.make("--repo-url", address, code=2), {}, address)
        for address in ("javascript:alert(1)", "https://evil.example/join", "https://github.com", "https://github.com/a/b/../../c",
                        "https://github.com/a/b?x=<script>", "data:text/html,x", "join.html"):
            self.assertEqual(self.make("--join-url", address, code=2), {}, address)
        # The site's own address is shown whole in the Markdown that embeds a card: https, a plain host, plain segments.
        refused = ("javascript:alert(1)", "http://example.org", "https://example.org/", "https://example.org/a/../b", "https://example.org/./a",
                   "https://example.org/a/..", "https://user@example.org", "https://user:pw@example.org/x", "https://example.org:8080/x",
                   "https://example.org/x?y=1", "https://example.org/x#y", "https://EXAMPLE.org", "https://example.org/a b", 'https://example.org/"onload="x',
                   "https://example.org/x)](javascript:alert(1)", "https://example.org/x](y", "https://example.org/<script>", "//example.org",
                   "https://localhost", "https://example.org/" + "a" * 101, "data:text/html,x", "https://example.org\n", " https://example.org",
                   "https://-example.org", "https://example-.org", "https://example..org", "https://example.org/a//b", "https://exa_mple.org",
                   "https://example.org/%2e%2e/x", "https://example.org/a\\b", "ftp://example.org", "https://example.org/" + "/".join(["abcdefghij" * 5] * 8),
                   "https://example.org/'x", "https://example.org/a&b", "https://éxample.org", "")
        for address in refused:
            self.assertEqual(self.make("--site-url", address, code=2), {}, address)
        self.assertEqual([page.site_address(address) for address in (*refused, None, 5, ["https://example.org"])], [None] * (len(refused) + 3))
        accepted = (SITE, "https://ruche.example.org", "https://example.org/a.b/c_d/e~f-g", "https://a.b.c.example.org/x")
        self.assertEqual([page.site_address(address) for address in accepted], list(accepted))
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
        """The cards of the integrations."""
        return {name: text for name, text in files.items() if name.startswith("wins/") and name.endswith(".svg")}

    def pages(self, files):
        """The pages of the integrations."""
        return {name: text for name, text in files.items() if name.startswith("wins/") and name.endswith(".html")}

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
        files = self.make("--repo-url", "https://github.com/Bee-ruche/toy", "--now", "2026-11-30T00:00:00Z")  # after the last of these lines
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
        self.assertEqual(len(self.pages(files)), len(reports) + 1)
        rows = {}
        for name, text in self.pages(files).items():
            seen = Seen(text)
            self.assertRegex(seen.said, r"^La Ruche · toy · accepted by the judgeAcceptedby the judgeTask toy-0001\. Written by ", "no figure leads")
            self.assertNotRegex(seen.said, r"outputs compared|Suspect constructs|gain_|sure_|(?i:nan|inf)", name)
            if seen.rows:
                rows[name] = seen.rows[1:]
            else:
                self.assertIn("The ledger keeps no measured gain for this contribution.", seen.said)
                self.assertNotRegex(seen.said, r"[0-9] %|A gain is", name)
        # A row of « what the judge measured » is made of a number under an identifier, and of nothing else: the four
        # reports whose gain is a real number and whose flag is not one have that gain, read as having no flag.
        self.assertEqual(rows, {**{f"wins/{sha(5000 + n)}.html": [["a", "50.0 %", "no noise flag in the ledger"]] for n in (2, 4, 16)},
                                f"wins/{sha(5027)}.html": [["e", "50.0 %", "no noise flag in the ledger"]]})

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
        self.assertEqual([(r["card"], r["page"], r["headline"]) for r in data["recent"]],
                         [(None, None, None), (f"wins/{sha(5002)}.svg", f"wins/{sha(5002)}.html", None),
                          (f"wins/{sha(5001)}.svg", f"wins/{sha(5001)}.html", {"metric": "a", "gain": 0.25})])
        self.assertEqual(sorted({h for h in seen.hrefs if h.startswith("wins/")}), [f"wins/{sha(5001)}.html", f"wins/{sha(5002)}.html"],
                         "a date links to the integration's own page, and to nothing where there is none")
        self.assertEqual(sorted(name for name in files if name.startswith("wins/")),
                         sorted(f"wins/{sha(n)}.{end}" for n in (5001, 5002) for end in ("svg", "html")), "a card and a page, or neither")
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
        self.assertEqual(sorted(self.pages(files)), sorted(f"wins/{line['commit']}.html" for line in lines), "and 250 pages")
        self.assertEqual(len(self.summary(files)["recent"]), page.RECENT_SHOWN, "the page's table shows the latest thirty")
        left = f"wins/{sha(9999)}.svg"
        (self.out / left).write_text("a card of an earlier run that this ledger no longer explains")
        more = [verdict(n, f"2027-01-{n - 250:02d}T09:00:00Z", "bob" if n % 2 else "alice", 102 if n % 2 else 101, "toy-0002") for n in range(251, 261)]
        self.ledger(lines + more)
        later = self.make("--now", "2027-02-01T00:00:00Z")
        self.assertEqual(set(files) - set(later), set(), "every file of the first run is written by the second")
        self.assertEqual((len(self.wins(later)), len(self.pages(later))), (260 + 1, 260))
        self.assertEqual(later[left], "a card of an earlier run that this ledger no longer explains", "nothing is deleted")
        self.assertEqual([name for name in {**wins, **self.pages(files)} if later[name] != files[name]], [],
                         "a card or a page whose integration did not change keeps its bytes: neither carries the date it was made")
        self.assertEqual(sorted(name for name in later if name.startswith("members/")),
                         ["members/101-badge.svg", "members/101.svg", "members/102-badge.svg", "members/102.svg"])

    def test_a_commit_recorded_twice_is_one_integration_and_its_first_line_speaks(self):
        self.ledger([report_verdict(1, {}), {**report_verdict(2, {"gain_a": 0.1, "sure_a": 1}), "commit": sha(5001)}])
        files = self.make()
        self.assertEqual(sorted(self.wins(files)), [f"wins/{sha(5001)}.svg"])
        self.assertNotIn("10.0 %", files[f"wins/{sha(5001)}.svg"], "the first line speaks, as the hive reads its own ledger")
        self.assertIn("first integration · 1 Nov 2026", files[f"wins/{sha(5001)}.svg"])
        self.assertEqual((self.summary(files)["totals"]["integrations"], len(self.summary(files)["recent"])), (1, 1), "and it is counted once")


class TestOnce(Case):
    """One accepted contribution is counted once, wherever it is counted, and the latest one is never from the future."""

    def counts(self, files):
        """Every place that counts integrations: the totals, the members, the badges, the table, the cards, the pages."""
        data = self.summary(files)
        return {"totals": data["totals"]["integrations"], "members": sum(m["integrations"] for m in data["members"]),
                "badge": int(re.search(r">([0-9]+) verified contribution", files["badge.svg"]).group(1)),
                "member badges": sum(int(re.search(r">([0-9,]+) accepted by the judge<", text).group(1))
                                     for name, text in files.items() if name.endswith("-badge.svg")),
                "member cards": sum(int(re.search(r"· ([0-9,]+) contributions? accepted by the judge ·", text).group(1))
                                    for name, text in files.items() if re.fullmatch(r"members/[0-9]+\.svg", name)),
                "recent": len(data["recent"]), "week": data["week"]["integrations"],
                "cards": sum(1 for name in files if re.fullmatch(r"wins/[0-9a-f]{40}\.svg", name)),
                "pages": sum(1 for name in files if re.fullmatch(r"wins/[0-9a-f]{40}\.html", name))}

    def test_a_line_the_ledger_holds_twice_counts_once_everywhere(self):
        first = verdict(1, "2026-11-10T09:00:00Z", "bob", 102, "toy-0001", report={"gain_a": 0.1, "sure_a": 1})
        refused = verdict(2, "2026-11-10T10:00:00Z", "bob", 102, "toy-0002", "refused", reason="judge_refused")
        error = {**failure(3, "2026-11-10T11:00:00Z", "bob", 102, "judge"), "run": "a" * 32}
        self.ledger([first, refused, error, first, refused, error, first])
        files = self.make()
        self.harmless(files)
        self.assertEqual(self.counts(files), dict.fromkeys(("totals", "members", "badge", "member badges", "member cards", "recent", "week", "cards", "pages"), 1))
        data = self.summary(files)
        self.assertEqual(data["totals"], {**data["totals"], "verdicts": 2, "judged": 2, "accepted": 1, "integrations": 1, "refused": 1, "judge_failures": 1})
        self.assertEqual(data["ledger"], {"lines": 7, "unreadable_lines": 0, "events_left_out": 0, "lines_after_now": 0, "repeated_lines": 4})
        self.assertIn("page: 4 ledger line(s) that repeat an answer the ledger already holds: left out\n", self.errors)
        self.assertIn("Ledger lines that repeat an answer already recorded, counted once: 4.", files["index.html"])

    def test_one_candidate_is_answered_once_and_one_commit_is_integrated_once(self):
        self.ledger([
            verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001"),
            {**verdict(1, "2026-11-02T09:00:00Z", "bob", 102, "toy-0002"), "commit": sha(6000)},  # the candidate of the first line, answered again
            {**verdict(3, "2026-11-03T09:00:00Z", "carol", 103, "toy-0003"), "commit": sha(5001)},  # the commit of the first line, under another candidate
            {**verdict(1, "2026-11-04T09:00:00Z", "dave", 104, "toy-0004", "refused", reason="conflict")},  # the same candidate, refused after it was accepted
            verdict(5, "2026-11-05T09:00:00Z", "erin", 105, "toy-0005", "refused", reason="conflict"),
            {**verdict(6, "2026-11-06T09:00:00Z", "erin", 105, "toy-0005"), "sha": sha(5)},  # refused first: the first answer stands
            {**failure(7, "2026-11-07T09:00:00Z", "erin", 105, "judge"), "run": "a" * 32},
            {**failure(7, "2026-11-07T10:00:00Z", "erin", 105, "judge"), "run": "b" * 32},  # another run on the same candidate: another line
            {**failure(7, "2026-11-07T11:00:00Z", "erin", 105, "none"), "run": "b" * 32},  # another kind in the same run: another line
        ])
        files = self.make()
        data = self.summary(files)
        self.assertEqual(self.counts(files), {**dict.fromkeys(("totals", "members", "badge", "member badges", "member cards", "recent", "week", "cards", "pages"), 1),
                                              "week": 0})
        self.assertEqual([(m["login"], m["integrations"]) for m in data["members"]], [("alice", 1)], "the first line speaks: its member, its date")
        self.assertEqual((data["recent"][0]["at"], data["recent"][0]["commit"]), ("2026-11-01T09:00:00Z", sha(5001)))
        self.assertEqual((data["totals"]["verdicts"], data["totals"]["refused"], data["totals"]["judge_failures"]), (2, 1, 2))
        self.assertEqual(data["ledger"]["repeated_lines"], 4)
        for login in ("bob", "carol", "dave", "erin"):
            self.assertNotIn(login, "".join(files.values()), "a line that repeats an answer names nobody")

    def test_a_line_without_a_whole_id_counts_for_itself(self):
        bare = {"type": "verdict", "at": "2026-11-10T09:00:00Z", "result": "accepted", "member": "alice", "member_id": 101, "judged": True}
        self.ledger([bare, bare, {**bare, "sha": "abc", "commit": "abc"}, {**bare, "sha": ["x"], "commit": sha(5001)[:-1]},
                     {**failure(3, "2026-11-10T11:00:00Z", "bob", 102, "judge"), "run": "not a key"}, {**failure(3, "2026-11-10T11:00:00Z", "bob", 102, "judge"), "run": "not a key"},
                     {**failure(4, "2026-11-10T11:00:00Z", "bob", 102, "judge"), "sha": "x"}, {**failure(4, "2026-11-10T11:00:00Z", "bob", 102, "judge"), "sha": "x"}])
        data = self.summary(self.make())
        self.assertEqual((data["totals"]["integrations"], data["totals"]["judge_failures"], data["ledger"]["repeated_lines"]), (4, 4, 0),
                         "only whole ids are compared: nothing is merged on a guess")

    def test_a_line_dated_after_the_instant_of_the_page_is_left_out_until_then(self):
        self.ledger([verdict(1, "2026-11-11T09:00:00Z", "alice", 101, "toy-0001"), verdict(2, NOW, "carol", 103, "toy-0002"),
                     verdict(3, "2026-11-12T12:00:01Z", "bob", 102, "toy-0003"),  # one second after the instant
                     verdict(4, "2999-12-31T23:59:59Z", "bob", 102, "toy-0004"),
                     verdict(5, "2026-11-20T09:00:00Z", "dave", 104, "toy-0005", "refused", reason="judge_refused"),
                     failure(6, "2026-11-20T10:00:00Z", "dave", 104, "judge")])
        files = self.make()
        data, seen = self.summary(files), self.harmless(files)
        self.assertEqual((data["recent"][0]["login"], data["recent"][0]["at"]), ("carol", NOW), "the latest is the latest at that instant, not after it")
        self.assertIn("Latest accepted contributionAccepted by the judgetoy-0002 by carol · 12 Nov 2026", seen.said)
        self.assertEqual(self.counts(files), dict.fromkeys(("totals", "members", "badge", "member badges", "member cards", "recent", "week", "cards", "pages"), 2))
        self.assertEqual(data["totals"], {**data["totals"], "verdicts": 2, "refused": 0, "judge_failures": 0})
        self.assertNotIn("bob", "".join(files.values()))
        self.assertEqual(data["ledger"], {"lines": 6, "unreadable_lines": 0, "events_left_out": 0, "lines_after_now": 4, "repeated_lines": 0})
        self.assertIn(f"page: 4 ledger line(s) dated after {NOW}, the instant the page is made for: left out\n", self.errors)
        self.assertIn("Ledger lines dated after that instant, left out until then: 4.", files["index.html"])
        later = self.make("--now", "2026-11-20T09:30:00Z")
        self.assertEqual((self.summary(later)["recent"][0]["login"], self.summary(later)["totals"]["refused"], self.summary(later)["ledger"]["lines_after_now"]),
                         ("bob", 1, 2), "at a later instant, the lines dated before it are read")
        self.assertEqual(self.make("--now", "2026-11-11T08:59:59Z")["index.html"].count("Nothing has been integrated yet."), 2)
        self.assertEqual(self.errors.count("\n"), 1, "one line on the standard error says how many lines were left out")


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


class TestFirstScreen(Case):
    """index.html opens on what this is, in one sentence, the latest contribution the judge accepted, with the figure
    it measured and who it is credited to, and how to take part. The counters and the tables come after."""

    def opening(self, *options):
        files = self.make(*options)
        seen = self.harmless(files)
        return seen, seen.said[:seen.said.index("Progress")]

    def test_the_page_opens_on_what_was_gained_by_whom_and_how_to_take_part(self):
        self.ledger([report_verdict(1, {"gain_a": 0.5, "sure_a": 1}), verdict(2, "2026-11-10T09:00:00Z", "bob", 102, "toy-0002", report=MINIZ),
                     verdict(3, "2026-11-11T09:00:00Z", "carol", 103, "toy-0003", "refused", reason="judge_refused")])
        self.put("feed.json", feed({"toy-0001": "done", "toy-0002": "done", "toy-0003": "open"}))
        goals = self.tasks([task("toy-0002", gain_goal("gain_instructions_n6"))])
        seen, opening = self.opening("--title", "A toy, made faster.", "--tasks", goals)
        self.assertEqual(opening, "La Ruchetoy" "A toy, made faster." + page.WHAT + "Latest accepted contribution" "4.3 %better · instructions n6"
                         "toy-0002 Title of toy-0002" "by bob · 10 Nov 2026 · what the judge measured" "How to take part")
        self.assertEqual(seen.hrefs[:3], ["https://github.com/bob", f"wins/{sha(5002)}.html", "#join"])
        self.assertNotIn("carol", opening, "a refusal is not what the page opens on")
        # After it, the counters and the tables, in this order; the block on how to take part closes the page.
        self.assertEqual(seen.heads, ["toy", "Progress", "This week", "Recent integrations", "Members", "Models", "What was refused, and why",
                                      "Three measures", "How to take part"])
        self.assertTrue(seen.said.endswith("How to take part" + page.JOIN_WORDS + "How to joinMade from the project's public ledger, as of "
                                           f"{NOW}. No script, no tracker, nothing loaded from elsewhere."), seen.said)
        self.assertEqual(seen.ids.count("join"), 1)
        self.assertEqual(seen.row("2026-11-10"), ["2026-11-10", "toy-0002 Title of toy-0002", "4.3 % better · instructions n6", "bob", sha(5002)[:10]],
                         "the measured gain is on the page, in the table too")
        self.assertEqual(seen.row("2026-11-01"), ["2026-11-01", "toy-0001 Title of toy-0001", "50.0 % better · a", "alice", sha(5001)[:10]])
        # Without a title and without the task file: the sentence that says what this is, and the largest sure gain.
        _, opening = self.opening()
        self.assertEqual(opening, "La Ruchetoy" + page.WHAT + "Latest accepted contribution" "5.2 %better · compression throughput n9"
                         "toy-0002 Title of toy-0002" "by bob · 10 Nov 2026 · what the judge measured" "How to take part")
        self.assertNotRegex(page.WHAT, r"[0-9<>&]")

    def test_the_opening_says_only_what_the_ledger_holds(self):
        self.ledger([verdict(1, "2026-11-03T09:00:00Z", "alice", 101, "nothing", commit="not one"), verdict(2, "2026-11-02T09:00:00Z", "Alice", 105, "toy-0002")])
        seen, opening = self.opening()
        self.assertEqual(opening, "La Ruchetoy" + page.WHAT + "Latest accepted contributionAccepted by the judgeby account 101 · 3 Nov 2026How to take part",
                         "no figure, no task that is one, a login that is another account's, no commit to link: none is invented")
        self.assertEqual(seen.hrefs[0], "#join")
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "bob", 102, "toy-0001", "refused", reason="judge_refused")])
        seen, opening = self.opening()
        self.assertEqual(opening, "La Ruchetoy" + page.WHAT + "Nothing has been integrated yet. The first contribution the judge accepts will appear here."
                         "How to take part")
        self.assertNotIn("bob", seen.said)


class TestWinPage(Case):
    """The permanent page of one integration (wins/<commit>.html): what its card links to."""

    def setUp(self):
        super().setUp()
        self.ledger([
            verdict(1, "2026-10-21T19:12:00Z", "ada", 101, "toy-0001", model="claude-fable-5-2", figures={"files": 1, "lines": 17}, report=MINIZ),
            verdict(2, "2026-11-09T20:30:00Z", "ada", 101, "toy-0002", figures={"files": 2, "lines": 1}, report={
                "gain_instructions_n9": 0.032, "gain_time": -0.03, "sure_time": 0, "worse_time": 1, "gain_memory": -0.002, "sure_memory": 0,
                "worse_memory": 0, "gain_instructions_n1": -0.004, "gain_size": 0.029, "sure_size": 1, "worse_size": 0, "gain_tiny": -0.0004, "sure_tiny": 0}),
        ])
        self.put("feed.json", feed({"toy-0001": "done", "toy-0002": "done"},
                                   titles={"toy-0001": "Compare matches 16 bits at a time", "toy-0002": "Fewer instructions per probe."}))
        self.goals = self.tasks([task("toy-0001", gain_goal("gain_instructions_n6")), task("toy-0002", gain_goal("gain_instructions_n9"))])
        self.first, self.second = f"wins/{sha(5001)}.html", f"wins/{sha(5002)}.html"

    def test_the_page_tells_one_integration_from_checked_fields(self):
        files = self.make("--tasks", self.goals, "--repo-url", REPO, "--site-url", SITE)
        self.harmless(files, site=SITE)
        text, seen = files[self.first], Seen(files[self.first])
        self.assertTrue(seen.said.startswith(
            "La Ruche · toy · accepted by the judge4.3 %better · instructions n6Task toy-0001: Compare matches 16 bits at a time. Written by the AI "
            "coding assistant of @ada (declared model: claude-fable-5-2), measured and accepted by the project's judge in a sandbox, and integrated "
            "on 21 Oct 2026 as commit 0000000000, credited to that account.This is the first integration of this account in toy."
            "What the judge measured"), seen.said)
        self.assertEqual(seen.rows, [["Measure", "Gain", "Reading"],
                                     ["instructions n6", "4.3 %", "the figure the task asked for"],
                                     ["compression throughput n9", "5.2 %", "beyond the noise"],
                                     ["compression throughput n6", "3.7 %", "beyond the noise"],
                                     ["instructions n9", "6.1 %", "no noise flag in the ledger"],
                                     ["ratio n6", "0.1 %", "within the noise"]], "everything the judge measured, each row read from its flags")
        self.assertEqual(re.findall(r"<tr(?: class=\"([a-z]+)\")?><th scope=\"row\">", text), ["asked", "", "", "soft", "soft"])
        self.assertIn("9,289 outputs compared with the base: identical. Suspect constructs: 0. Changed: 1 file, 17 lines. A gain is measured on the "
                      "judge's own inputs and machine; it is not a promise for another workload.", seen.said)
        # Check it yourself: the commit's id, whole; the repository and the commit, linked; the task.
        self.assertIn(f"The integrated commit, in Bee-ruche/toy:{sha(5001)}This commit on GitHubThe task: toy-0001 (Compare matches 16 bits at a time).",
                      seen.said)
        for href in (REPO, f"{REPO}/commit/{sha(5001)}", "https://github.com/ada", f"{sha(5001)}.svg", "../index.html", JOIN):
            self.assertIn(href, seen.hrefs)
        # Show it: the card as its file holds it, and the Markdown that embeds it, which takes the site's address.
        self.assertIn(files[f"wins/{sha(5001)}.svg"].rstrip("\n"), text, "the card inlined in the page is the card's file, byte for byte")
        markdown = f"[![La Ruche · toy · toy-0001 · accepted by the judge]({SITE}/wins/{sha(5001)}.svg)]({SITE}/wins/{sha(5001)}.html)"
        self.assertIn(f'<code class="copy">{markdown}</code>', text)
        self.assertEqual((seen.metas["og:url"], seen.metas["og:title"], seen.metas["og:description"]),
                         (f"{SITE}/wins/{sha(5001)}.html", "4.3 % better · instructions n6 · toy · La Ruche",
                          "4.3 % better · instructions n6 in toy. Task toy-0001, accepted by the judge, integrated on 21 Oct 2026."))
        self.assertIn("<title>4.3 % better · instructions n6 · toy-0001 · La Ruche</title>", text)
        self.assertEqual(seen.metas["Content-Security-Policy"], page.CSP)
        # How to take part: the same words as on index.html, one link, the way back. No counter, no deadline.
        self.assertTrue(seen.said.endswith("How to take part" + page.JOIN_WORDS + "How to joinAll of toy's integrations"
                                           "Made from the project's public ledger. No script, no tracker, nothing loaded from elsewhere."), seen.said)
        self.assertIn(page.JOIN_WORDS, Seen(files["index.html"]).said)
        self.assertNotRegex(page.JOIN_WORDS.lower(), r"[0-9]|now|today|hurry|left|only|last|soon|rank", "what happens, and nothing that presses")
        self.assertNotIn(NOW[:10], text, "the page carries no date of making: it changes only when what it says does")
        # The second integration of the same account: losses read as losses, and no « first ».
        other = Seen(files[self.second])
        self.assertTrue(other.said.startswith(
            "La Ruche · toy · accepted by the judge3.2 %better · instructions n9Task toy-0002: Fewer instructions per probe. Written by the AI coding "
            "assistant of @ada, measured and accepted by the project's judge in a sandbox, and integrated on 9 Nov 2026 as commit 0000000000, credited "
            "to that account.What the judge measured"), other.said)
        self.assertEqual(other.rows[1:], [["instructions n9", "3.2 %", "the figure the task asked for"],
                                          ["size", "2.9 %", "beyond the noise"],
                                          ["time", "−3.0 %", "worse, beyond the noise"],
                                          ["tiny", "0.0 %", "within the noise"],
                                          ["memory", "−0.2 %", "worse, within the noise"],
                                          ["instructions n1", "−0.4 %", "worse, no noise flag in the ledger"]])
        self.assertIn("for that figure.Changed: 2 files, 1 line. A gain is measured", other.said)
        self.assertNotRegex(other.said, r"outputs compared|Suspect constructs|first integration|declared")

    def test_without_the_site_s_address_the_repository_s_or_the_task_file_the_page_says_less(self):
        files = self.make()
        self.harmless(files)
        seen = Seen(files[self.first])
        self.assertIn("5.2 %better · compression throughput n9", seen.said, "no task file: the largest gain beyond the noise leads")
        self.assertEqual(seen.rows[1], ["compression throughput n9", "5.2 %", "beyond the noise"])
        self.assertNotIn("the figure the task asked for", seen.said)
        self.assertIn(f"The integrated commit:{sha(5001)}The task: toy-0001", seen.said, "no repository: the commit's id, and no link")
        self.assertNotRegex(seen.said, r"Markdown|on GitHub|README")
        self.assertNotIn("og:url", seen.metas)
        self.assertEqual([href for href in seen.hrefs if href.startswith("http")], ["https://github.com/ada", JOIN])
        self.assertIn(f"The card is the file {sha(5001)[:10]}….svg beside this page.", seen.said)

    def test_the_join_link_of_a_page_under_wins(self):
        self.assertIn("../join.html", Seen(self.make("--join")[self.first]).hrefs, "join.html is beside index.html: one folder up")
        self.assertIn("join.html", self.harmless(self.make("--join")).hrefs)
        other = "https://github.com/Bee-ruche/registre/blob/hive/docs/join.md"
        files = self.make("--join-url", other)
        self.harmless(files, join=other)
        self.assertIn(other, Seen(files[self.first]).hrefs)

    def test_the_page_says_only_what_the_ledger_is_sure_of(self):
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001", model="gpt-x<b>"),
                     verdict(2, "2026-11-02T09:00:00Z", "Alice", 105, "toy-0009"),
                     verdict(3, "2026-11-03T09:00:00Z", "eve", None, "not a task", judged=False, figures="<script>alert(1)</script>"),
                     verdict(4, "2026-11-04T09:00:00Z", "Alice", 105, "toy-0002", judged="yes")])
        self.put("feed.json", {"project": "Not an <id>", "tasks": [{"id": "toy-0001", "title": "A title!", "status": "done"}]})
        self.state.rename(self.root / "state" / "Not an id")
        self.state = self.root / "state" / "Not an id"
        files = self.make("--repo-url", REPO, "--site-url", SITE)
        self.harmless(files, site=SITE)
        said = {n: Seen(files[f"wins/{sha(5000 + n)}.html"]).said for n in (1, 2, 3, 4)}
        self.assertTrue(said[1].startswith(
            "La Ruche · a hive project · accepted by the judgeAcceptedby the judgeTask toy-0001: A title! Written by the AI coding assistant of GitHub "
            "account 101, measured and accepted by the project's judge in a sandbox, and integrated on 1 Nov 2026 as commit 0000000000, credited to that "
            "account.This is the first integration of this account in this project.What the judge measuredThe ledger keeps no measured gain for this "
            "contribution.Changed: 1 file, 3 lines.Check it yourself"), said[1])
        self.assertNotRegex(said[1], r"(?i)alice|gpt-x|declared", "a login that passed to another account, a model that is not an identifier: not shown")
        self.assertIn("Task toy-0009. Written by the AI coding assistant of @Alice, measured", said[2], "a task the feed does not know: its id alone")
        self.assertIn("accepted by the judgeAcceptedby the judgeWritten by a member's AI coding assistant, accepted, and integrated on 3 Nov 2026 as commit "
                      "0000000000.What the judge measuredThe ledger keeps no measured gain for this contribution.Check it yourself", said[3],
                      "no task, no account, not judged, no size of the change: none is invented")
        self.assertNotRegex(said[3], r"credited to that|first integration|The task|Changed|measured and accepted")
        self.assertIn("of @Alice, accepted, and integrated on 4 Nov 2026", said[4], "« judged » is true or it is not")
        self.assertIn("All the integrations", said[4])
        self.assertIn(f"[![La Ruche · accepted by the judge]({SITE}/wins/{sha(5003)}.svg)]({SITE}/wins/{sha(5003)}.html)", files[f"wins/{sha(5003)}.html"])

    def test_each_measure_is_read_from_its_flags(self):
        def read(gain, sure=None, worse=None, goal=False):
            return page.reading({"metric": "m", "gain": gain, "sure": sure, "worse": worse, "goal": goal})
        self.assertEqual([read(0.05, 1, 0), read(0.05, 0, 0), read(0.05), read(-0.05, 0, 1), read(-0.05, 0, 0), read(-0.05),
                          read(-0.0004, 0), read(0.0), read(-0.05, None, 1), read(0.0, 1, 0), read(0.0, 0, 1)],
                         ["beyond the noise", "within the noise", "no noise flag in the ledger", "worse, beyond the noise", "worse, within the noise",
                          "worse, no noise flag in the ledger", "within the noise", "no noise flag in the ledger", "worse, beyond the noise",
                          "beyond the noise", "worse, beyond the noise"])
        asked = "the figure the task asked for"
        self.assertEqual([read(0.05, goal=True), read(0.05, 1, 0, True), read(0.05, 0, 0, True), read(-0.05, goal=True), read(-0.05, None, 1, True)],
                         [asked, f"{asked} · beyond the noise", f"{asked} · within the noise", f"{asked} · worse, no noise flag in the ledger",
                          f"{asked} · worse, beyond the noise"])
        # A figure and a flag that point opposite ways, or two flags that do: no direction is stated, whatever the size.
        none = page.NO_READING
        self.assertEqual([read(-0.05, 1), read(-0.05, 1, 0), read(0.05, 0, 1), read(0.05, None, 1), read(0.05, 1, 1), read(-0.05, 1, 1), read(0.0, 1, 1),
                          read(-0.0004, 1, 0), read(0.0004, 0, 1)], [none] * 9)
        self.assertEqual([read(0.05, None, 1, True), read(-0.05, 1, 0, True), read(0.05, 1, 1, True)], [f"{asked} · {none}"] * 3)
        self.assertNotRegex(none, r"better|worse|beyond|within")
        self.assertEqual([page.direction(*row) for row in ((0.05, 1, 0), (0.05, None, None), (0.05, 0, 0), (-0.05, 0, 1), (-0.05, None, None), (0.0, 1, 0),
                                                            (0, 0, 1), (-0.05, 1, 0), (0.05, 0, 1), (0.05, 1, 1), (-0.05, 1, 1), (0.0, 1, 1))],
                         ["better", "better", "better", "worse", "worse", "", "", None, None, None, None, None])
        self.assertEqual([page.gain_text(value) for value in (0.043, 10, 0, -0.0004, 0.0004, -0.03, -1.5, 0.0005)],
                         ["4.3 %", "1000.0 %", "0.0 %", "0.0 %", "0.0 %", "−3.0 %", "−150.0 %", "0.1 %"], "a loss wears a real minus sign")

    def test_no_direction_is_stated_when_the_judge_s_figure_and_its_noise_flag_disagree(self):
        """The registry's judge compares medians for the figure and paired runs for the flags: nine runs of ten faster
        and a slower median give sure_ 1 with a gain below zero. The page prints the figure and states no direction."""
        report = {"gain_compression_throughput_n1": -0.03, "sure_compression_throughput_n1": 1, "worse_compression_throughput_n1": 0,
                  "gain_decompression_throughput": 0.04, "sure_decompression_throughput": 0, "worse_decompression_throughput": 1,
                  "gain_both": 0.07, "sure_both": 1, "worse_both": 1, "gain_ratio": 0.001, "sure_ratio": 0, "worse_ratio": 0}
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "ada", 101, "toy-0001", report=report),
                     verdict(2, "2026-11-02T09:00:00Z", "ada", 101, "toy-0002", report={"gain_both": 0.07, "sure_both": 1, "worse_both": 1})])
        for options in ((), ("--tasks", self.tasks([task("toy-0001", gain_goal("gain_decompression_throughput")), task("toy-0002", gain_goal("gain_both"))]))):
            files = self.make(*options)
            self.harmless(files)
            seen = Seen(files[self.first])
            asked = "the figure the task asked for · " if options else ""
            self.assertEqual(sorted(seen.rows[1:]), sorted([["both", "7.0 %", page.NO_READING], ["decompression throughput", "4.0 %", asked + page.NO_READING],
                                                            ["compression throughput n1", "−3.0 %", page.NO_READING], ["ratio", "0.1 %", "within the noise"]]))
            self.assertIn("« No reading »: the judge's figure and its noise flag do not say the same; this page prints the figure and calls it neither "
                          "better nor worse.", seen.said)
            for name in (self.first, self.second, f"wins/{sha(5001)}.svg", f"wins/{sha(5002)}.svg", "index.html"):
                # A page: what it opens on, before its tables (their rows are held here, and the notes under them explain
                # the words); a card: everything.
                said = told(files[name]).split("What the judge measured")[0].split("Progress")[0]
                self.assertNotRegex(said, r"(?i)better|worse|beyond the noise", (name, "no direction the judge did not state"))
                self.assertNotRegex(said, r"[0-9] %", (name, "and a figure without a direction leads nothing"))
            self.assertEqual([row[2] for row in Seen(files["index.html"]).rows if row[0].startswith("2026-11-0")], ["no figure"] * 2)
            self.assertEqual([(r["figure"], r["headline"]) for r in self.summary(files)["recent"]], [(None, None)] * 2)
            self.assertTrue(Seen(files[self.second]).said.startswith("La Ruche · toy · accepted by the judgeAcceptedby the judgeTask toy-0002"))
        self.ledger([verdict(1, "2026-11-01T09:00:00Z", "ada", 101, "toy-0001", report={"gain_ratio": 0.001, "sure_ratio": 0, "worse_ratio": 0})])
        self.assertNotRegex(Seen(self.make()[self.first]).said, r"(?i)no reading", "the note comes only with such a row")

    def test_a_verdict_of_an_unexpected_shape_gives_a_page_that_shows_none_of_it(self):
        odd = {"gain_a": {"<script>alert(1)</script>": 1}, "gain_b": "<img src=x onerror=alert(1)>", "gain_<script>": 0.5, "sure_c": "<script>",
               "gain_c": 0.25, "worse_c": ["<script>"], "outputs_compared": "<script>alert(1)</script>", "suspects": {"a": "<script>"},
               "<script>alert(1)</script>": 1, "gain_d": 0.5, "sure_d": 1, "worse_d": "javascript:alert(1)"}
        self.ledger([
            verdict(1, "2026-11-01T09:00:00Z", "alice", 101, "toy-0001", report=odd, figures={"files": "<script>", "lines": [3]},
                    extra={"<script>alert(1)</script>": ["<img src=x>"]}, deal="<script>alert(1)</script>", repo_id="javascript:alert(1)"),
            verdict(2, "2026-11-02T09:00:00Z", "alice", 101, "toy-0001", report=["<script>alert(1)</script>"], figures=["<img src=x>"]),
            verdict(3, "2026-11-03T09:00:00Z", "alice", 101, "toy-0001", report="<script>alert(1)</script>", figures=None, commit=sha(5003) + "\n"),
            {"type": "mystery", "at": "2026-11-04T09:00:00Z", "member": "alice", "member_id": 101, "payload": "<script>alert(1)</script>"},
            {"type": "verdict", "at": "2026-11-05T09:00:00Z", "result": "accepted", "commit": sha(5005)},
            {"type": "verdict", "at": "2026-11-06T09:00:00Z", "result": "accepted", "commit": sha(5006), "report": {"gain_a": 0.1, "sure_a": 1},
             "member": {"login": "<script>"}, "member_id": [101], "task": {"id": "<script>"}, "model": 5, "judged": 1, "figures": 7},
            '{"type":"verdict","at":"2026-11-07T09:00:00Z","result":"accepted","commit":"' + sha(5007) + '","report":{"gain_a":1e999,"gain_b":NaN,'
            '"outputs_compared":1e999,"suspects":-Infinity},"figures":{"files":NaN,"lines":1e999}}',
        ])
        files = self.make("--repo-url", REPO, "--site-url", SITE)
        self.harmless(files, site=SITE)
        for name, text in files.items():
            for needle in NEEDLES:
                self.assertNotIn(needle, text.lower(), (name, needle))
        self.assertEqual(sorted(name for name in files if name.endswith(".html")),
                         ["index.html", *(f"wins/{sha(5000 + n)}.html" for n in (1, 2, 5, 6, 7))], "a commit id with a line feed is not one: no page")
        first = Seen(files[f"wins/{sha(5001)}.html"])
        self.assertEqual(first.rows[1:], [["d", "50.0 %", "beyond the noise"], ["c", "25.0 %", "no noise flag in the ledger"]],
                         "the two gains that are numbers under identifiers, each read from the flags that are numbers")
        self.assertNotRegex(first.said, r"outputs compared|Suspect constructs|Changed")
        for n in (2, 5, 7):
            seen = Seen(files[f"wins/{sha(5000 + n)}.html"])
            self.assertEqual(seen.rows, [], n)
            self.assertNotRegex(seen.said, r"[0-9] %|outputs compared|Suspect constructs|Changed|inf|nan", n)
        bare = Seen(files[f"wins/{sha(5006)}.html"])
        self.assertIn("10.0 %better · aWritten by a member's AI coding assistant, accepted, and integrated on 6 Nov 2026 as commit 0000000000.", bare.said)
        self.assertEqual(self.summary(files)["totals"]["integrations"], 6, "the line of a kind this page does not know counts for nothing")


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
        self.assertEqual(self.summary(files)["ledger"], {"lines": 2, "unreadable_lines": 1, "events_left_out": 0, "lines_after_now": 0, "repeated_lines": 0})
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
        self.assertEqual(seen.row("alice"), ["alice", "1", "card · badge"])
        self.assertIsNone(seen.row("bob"))
        self.assertEqual(seen.row("2026-11-12"), ["2026-11-12", "toy-0001 Make f0 faster", "no figure", "alice", self.w.tip()[:10]])
        self.assertTrue(seen.said.startswith(
            "La Ruchetoy" + "A toy project" + page.WHAT + "Latest accepted contributionAccepted by the judgetoy-0001 Make f0 faster"
            "by alice · 12 Nov 2026 · what the judge measuredHow to take partProgress"), seen.said)
        self.assertIn("https://github.com/alice", seen.hrefs)
        self.assertIn(f"https://github.com/Bee-ruche/toy/commit/{self.w.tip()}", seen.hrefs)
        self.assertEqual(seen.row("judge_refused"), ["judge_refused", "1", hive.REASONS["judge_refused"]])
        self.assertEqual(seen.row("claude-fable-5-2"), ["claude-fable-5-2", page.TOO_FEW, "1", page.TOO_FEW])
        self.assertEqual(seen.row("undeclared"), ["undeclared", page.TOO_FEW, "0", page.TOO_FEW], "two accounts: too few for a model's judged count")
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
        self.assertEqual(sorted(path.name for path in (out / "wins").iterdir()), [f"{self.w.tip()}.html", f"{self.w.tip()}.svg"])
        own = Seen((out / "wins" / f"{self.w.tip()}.html").read_text(encoding="utf-8"))
        self.assertIn("Task toy-0001: Make f0 faster. Written by the AI coding assistant of @alice (declared model: claude-fable-5-2), measured and "
                      f"accepted by the project's judge in a sandbox, and integrated on 12 Nov 2026 as commit {self.w.tip()[:10]}, credited to that "
                      "account.This is the first integration of this account in toy.", own.said)
        self.assertIn(f"https://github.com/Bee-ruche/toy/commit/{self.w.tip()}", own.hrefs)
        self.assertIn(f"wins/{self.w.tip()}.html", seen.hrefs, "the date of the integration links to its page")
        self.assertNotIn("<script", text)


class TestPatterns(unittest.TestCase):
    def test_the_patterns_written_again_here_are_the_hives(self):
        for name in ("LOGIN", "TASK_ID", "MODEL", "SHA", "ISO"):
            self.assertEqual(getattr(page, name).pattern, getattr(hive, name).pattern, name)
        self.assertEqual(page.RUN.pattern, hive.RUN_KEY.pattern)

    def test_every_reason_of_the_hive_has_a_text_the_page_can_show(self):
        self.assertTrue(all(isinstance(text, str) and text for text in hive.REASONS.values()))


if __name__ == "__main__":
    unittest.main()
