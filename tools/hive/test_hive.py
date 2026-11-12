#!/usr/bin/env python3
"""Tests of the hive protocol (tools/hive/hive.py), on real git repositories in a temporary folder: a project, forks,
the hive's clone. No network, no GitHub: the API is a fake, and the judge is a function of the candidate's files.

  python3 tools/hive/test_hive.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hive  # noqa: E402

NOW = "2026-11-12T12:00:00Z"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_AUTHOR_DATE": "2026-11-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-11-01T00:00:00Z", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
LIB = "".join(f"int f{i}(void) {{ return {i}; }}\n" for i in range(8))
CONFIG = {"protocol": 1, "project": "toy", "repo": "Bee-ruche/toy", "branch": "main", "protected": ["tests/**"],
          "tasks": "hive/tasks/toy.jsonl", "limits": {"changed_lines": 50, "files": 3, "file_bytes": 2000, "commits": 5}}
TASKS = [
    {"id": "toy-0001", "title": "Make f0 faster", "files": ["lib.c"]},
    {"id": "toy-0002", "title": "Work in src", "files": ["src/"]},
    {"id": "toy-0003", "title": "Closed", "files": ["lib.c"], "closed": True},
    {"id": "toy-0004", "title": "Gain of 2 %", "files": ["lib.c"], "goal": {"kind": "metric", "name": "gain", "min": 0.02}},
    {"id": "toy-0005", "title": "Everything allowed by the task",
     "files": [".github/", "AGENTS.md", "hive/", "tests/", "run.sh", "link", "sub", "lib.c", ".GitHub/", "CLAUDE.md"]},
]


def sh(*command, cwd, check=True, stdin=None):
    return subprocess.run(command, cwd=cwd, env={**os.environ, **GIT_ENV}, check=check, capture_output=True, text=True, input=stdin)


def judge_by_content(base, candidate, task, tip, commit):
    """The fake judge: refuses a candidate whose lib.c says REFUSE, fails on ENVERR, measures a gain on FAST."""
    judge_by_content.seen.append((candidate / "lib.c").read_bytes() if (candidate / "lib.c").exists() else None)
    text = (candidate / "lib.c").read_text() if (candidate / "lib.c").exists() else ""
    if "REFUSE" in text:
        return {"code": 1}
    if "ENVERR" in text:
        return {"code": 2}
    return {"code": 0, "report": {"gain": 0.05 if "FAST" in text else 0.0, "outputs_compared": 12, "note": "x y"}}


judge_by_content.seen = []


class FakeApi:
    def __init__(self, world):
        self.world, self.users, self.repos = world, {}, {}

    def forks(self, repo):
        return [{"full_name": f.full_name, "login": f.login, "id": f.id, "type": f.type, "pushed_at": NOW}
                for f in self.world.forks.values()]

    def user(self, login):
        f = self.world.forks[login]
        return self.users.get(login, {"id": f.id, "created_at": f.created, "type": f.type})

    def repo(self, full_name):
        f = next(f for f in self.world.forks.values() if f.full_name == full_name)
        return self.repos.get(full_name, {"full_name": full_name, "fork": True, "parent": "Bee-ruche/toy", "login": f.login,
                                          "id": f.id, "type": f.type})

    def local_url(self, full_name):
        return str(next(f for f in self.world.forks.values() if f.full_name == full_name).bare)


class Fork:
    def __init__(self, world, login, id, created="2020-01-01T00:00:00Z", type="User"):
        self.world, self.login, self.id, self.created, self.type = world, login, id, created, type
        self.full_name = f"{login}/toy"
        self.bare, self.work = world.root / "forks" / f"{login}.git", world.root / "forks" / login
        sh("git", "clone", "--quiet", "--bare", str(world.upstream), str(self.bare), cwd=world.root)
        sh("git", "clone", "--quiet", str(self.bare), str(self.work), cwd=world.root)
        self.branch = "claude/work"
        sh("git", "checkout", "--quiet", "-b", self.branch, cwd=self.work)

    def write(self, path, content, mode=None):
        target = self.work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
        if mode:
            os.chmod(target, mode)
        return self

    def commit(self, message="work"):
        sh("git", "add", "-A", cwd=self.work)
        sh("git", "commit", "--quiet", "--allow-empty", "-m", message, cwd=self.work)
        return self

    def marker(self, task, action="submit", model=None, extra=""):
        lines = [f"Hive {action}", "", f"Hive-Task: {task}", f"Hive-Action: {action}"] + ([f"Hive-Model: {model}"] if model else [])
        sh("git", "commit", "--quiet", "--allow-empty", "-m", "\n".join(lines) + extra, cwd=self.work)
        return self

    def fresh(self, branch):
        """A new branch from the project's tip as the fork knows it: an independent piece of work."""
        self.branch = branch
        sh("git", "checkout", "--quiet", "-B", branch, "origin/main", cwd=self.work)
        return self

    def push(self, branch=None):
        sh("git", "push", "--quiet", "origin", f"HEAD:refs/heads/{branch or self.branch}", cwd=self.work)
        return sh("git", "rev-parse", "HEAD", cwd=self.work).stdout.strip()

    def submit(self, task, path="lib.c", content=None, model=None):
        """One change, the submit marker, pushed: returns the candidate's commit."""
        self.write(path, content if content is not None else LIB.replace("return 0;", "return 0; /* tuned */"))
        return self.commit().marker(task, model=model).push()


class World:
    def __init__(self, root, config=None):
        self.root = Path(root)
        self.upstream, self.seed = self.root / "upstream.git", self.root / "seed"
        (self.root / "forks").mkdir()
        sh("git", "init", "--quiet", "--bare", "-b", "main", str(self.upstream), cwd=self.root)
        sh("git", "init", "--quiet", "-b", "main", str(self.seed), cwd=self.root)
        files = {"lib.c": LIB, "src/a.c": "int a;\n", "tests/t.c": "int t;\n", "hive/readme": "hive\n", "AGENTS.md": "agents\n",
                 ".github/workflows/ci.yml": "on: push\n", ".gitattributes": "*.c text eol=crlf\n", "run.sh": "#!/bin/sh\n"}
        for path, content in files.items():
            (self.seed / path).parent.mkdir(parents=True, exist_ok=True)
            (self.seed / path).write_text(content)
        os.chmod(self.seed / "run.sh", 0o755)
        sh("git", "add", "-A", cwd=self.seed)
        sh("git", "commit", "--quiet", "-m", "seed", cwd=self.seed)
        sh("git", "remote", "add", "origin", str(self.upstream), cwd=self.seed)
        sh("git", "push", "--quiet", "origin", "main", cwd=self.seed)
        self.harvest = self.root / "harvest"
        sh("git", "clone", "--quiet", str(self.upstream), str(self.harvest), cwd=self.root)
        self.registry = self.root / "registry"
        (self.registry / "hive/projects").mkdir(parents=True)
        (self.registry / "hive/tasks").mkdir(parents=True)
        self.set_config(config or {})
        (self.registry / "hive/tasks/toy.jsonl").write_text("".join(json.dumps(t) + "\n" for t in TASKS))
        self.state, self.work = self.root / "state" / "toy", self.root / "work"
        self.work.mkdir()
        self.forks, self.api = {}, FakeApi(self)

    def set_config(self, changes):
        config = {**CONFIG, **{k: v for k, v in changes.items() if k not in ("limits", "members")}}
        config["limits"] = {**CONFIG["limits"], **changes.get("limits", {})}
        if "members" in changes:
            config["members"] = changes["members"]
        (self.registry / "hive/projects/toy.json").write_text(json.dumps(config))

    def fork(self, login, id, **options):
        self.forks[login] = Fork(self, login, id, **options)
        return self.forks[login]

    def upstream_commit(self, path, content):
        sh("git", "pull", "--quiet", "origin", "main", cwd=self.seed)
        (self.seed / path).write_text(content)
        sh("git", "add", "-A", cwd=self.seed)
        sh("git", "commit", "--quiet", "-m", "upstream moves", cwd=self.seed)
        sh("git", "push", "--quiet", "origin", "main", cwd=self.seed)

    def tip(self):
        return sh("git", "rev-parse", "refs/heads/main", cwd=self.upstream).stdout.strip()

    def load(self):
        config = hive.load_config(self.registry / "hive/projects/toy.json")
        return config, hive.load_tasks(self.registry / config["tasks"]), hive.Ledger(self.state)

    def sweep(self, judge=judge_by_content):
        sh("git", "fetch", "--quiet", "origin", cwd=self.harvest)
        config, tasks, ledger = self.load()
        tip = hive.tip_of(self.harvest, config)
        claims, candidates = hive.collect(self.harvest, config, tasks, ledger, self.api, self.state, allow_local=True)
        results = hive.judge_all(self.harvest, tip, candidates, config, tasks, ledger, self.api, judge, self.work)
        return tip, claims, results

    def apply(self, tip, claims, results):
        config, tasks, ledger = self.load()
        return hive.apply(self.harvest, "origin", tip, results, claims, config, tasks, ledger, self.api, allow_local=True)

    def run(self, judge=judge_by_content):
        tip, claims, results = self.sweep(judge)
        self.apply(tip, claims, results)
        return results

    def events(self):
        return self.load()[2].events


class Base(unittest.TestCase):
    config = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.dict(os.environ, {"HIVE_NOW": NOW, **GIT_ENV})
        patch.start()
        self.addCleanup(patch.stop)
        judge_by_content.seen = []
        self.w = World(self.tmp.name, self.config)
        self.alice = self.w.fork("alice", 101)

    def one(self, results):
        self.assertEqual(len(results), 1, results)
        return results[0]

    def refused(self, reason, results=None):
        result = self.one(results if results is not None else self.w.run())
        self.assertEqual((result["result"], result.get("reason")), ("refused", reason), result)
        self.assertEqual(self.w.tip(), self.start, "a refused candidate never moves the project")
        return result

    @property
    def start(self):
        return sh("git", "rev-parse", "HEAD", cwd=self.w.seed).stdout.strip()


class TestIntegration(Base):
    def test_a_candidate_that_passes_is_integrated_as_one_commit_credited_to_the_forks_owner(self):
        before = self.w.tip()
        candidate = self.alice.submit("toy-0001", model="claude-fable-5-2")
        result = self.one(self.w.run())
        self.assertEqual(result["result"], "accepted")
        tip = self.w.tip()
        self.assertEqual(tip, result["commit"])
        show = sh("git", "show", "-s", "--format=%P|%an|%ae|%cn|%ce|%B", tip, cwd=self.w.upstream).stdout
        parents, author, email, committer, committer_email, body = show.split("|", 5)
        self.assertEqual(parents, before, "one commit on the former tip: the candidate's own commits stay in the fork")
        self.assertEqual((author, email), ("alice", "101+alice@users.noreply.github.com"))
        self.assertEqual((committer, committer_email), hive.ROBOT)
        self.assertIn("toy-0001: Make f0 faster", body)
        self.assertIn(f"Hive-Candidate: {candidate}", body)
        self.assertIn("Hive-Member: alice", body)
        self.assertNotIn("Hive-Action", body)
        self.assertIn("tuned", sh("git", "show", f"{tip}:lib.c", cwd=self.w.upstream).stdout)
        verdict = [e for e in self.w.events() if e["type"] == "verdict"]
        self.assertEqual(len(verdict), 1)
        self.assertEqual((verdict[0]["result"], verdict[0]["member"], verdict[0]["member_id"], verdict[0]["sha"], verdict[0]["commit"],
                          verdict[0]["model"]), ("accepted", "alice", 101, candidate, tip, "claude-fable-5-2"))
        self.assertEqual(verdict[0]["report"], {"gain": 0.0, "outputs_compared": 12}, "only plain figures are kept")

    def test_a_candidate_is_answered_once(self):
        self.alice.submit("toy-0001", content=LIB + "/* REFUSE */\n")
        self.assertEqual(self.one(self.w.run())["reason"], "judge_refused")
        self.assertEqual(self.w.run(), [], "the same commit is never judged twice")
        self.assertEqual(len(judge_by_content.seen), 1)

    def test_two_candidates_are_judged_on_a_tip_that_moves(self):
        bob = self.w.fork("bob", 102)
        self.alice.submit("toy-0001")
        bob.write("src/b.c", "int b;\n").commit().marker("toy-0002").push()
        before = self.w.tip()
        results = self.w.run()
        self.assertEqual(sorted(r["result"] for r in results), ["accepted", "accepted"])
        log = sh("git", "rev-list", f"{before}..main", cwd=self.w.upstream).stdout.split()
        self.assertEqual(len(log), 2)
        second, first = log
        self.assertEqual(sh("git", "rev-parse", f"{second}^", cwd=self.w.upstream).stdout.strip(), first)
        files = sh("git", "ls-tree", "-r", "--name-only", "main", cwd=self.w.upstream).stdout
        self.assertIn("src/b.c", files)
        self.assertIn("tuned", sh("git", "show", "main:lib.c", cwd=self.w.upstream).stdout)

    def test_the_second_candidate_for_a_task_is_superseded(self):
        bob = self.w.fork("bob", 102)
        self.alice.submit("toy-0001")
        bob.submit("toy-0001", content=LIB.replace("return 1;", "return 1; /* other */"))
        results = self.w.run()
        self.assertEqual(sorted((r["result"], r.get("reason")) for r in results), [("accepted", None), ("refused", "superseded")])
        self.assertEqual(len(judge_by_content.seen), 1, "the superseded candidate costs no judgement")

    def test_the_judge_sees_the_trees_bytes_whatever_gitattributes_says(self):
        self.alice.submit("toy-0001", content=LIB + "int last;\n")
        self.w.run()
        self.assertEqual(judge_by_content.seen, [(LIB + "int last;\n").encode()], "no end-of-line conversion (the tree says eol=crlf)")

    def test_an_error_of_the_judges_machine_judges_nothing(self):
        self.alice.submit("toy-0001", content=LIB + "/* ENVERR */\n")
        result = self.one(self.w.run())
        self.assertEqual((result["result"], result["judged"]), ("skipped", False))
        self.assertEqual([e for e in self.w.events() if e["type"] == "verdict"], [])
        self.assertEqual(self.one(self.w.run(lambda *a: {"code": 0}))["result"], "accepted", "judged again at the next sweep")

    def test_a_task_the_judge_keeps_refusing_rises_in_tier(self):
        for i in range(3):
            self.alice.fresh(f"claude/try{i}").submit("toy-0001", content=LIB + f"/* REFUSE {i} */\n")
            self.assertEqual(self.one(self.w.run())["reason"], "judge_refused")
        config, tasks, ledger = self.w.load()
        task = next(t for t in hive.build_feed(config, tasks, ledger, self.start)["tasks"] if t["id"] == "toy-0001")
        self.assertEqual((task["tier"], task["refusals"], task["refused_for"]), (2, 3, {"judge_refused": 3}))
        feed = {"tasks": [task]}
        self.assertIsNone(hive.pick(feed, "alice", "h", max_tier=1), "a light model leaves it to a stronger one")
        self.assertEqual(hive.pick(feed, "alice", "h", max_tier=2)["id"], "toy-0001")

    def test_the_stop_button_and_the_statistics(self):
        self.alice.submit("toy-0001", model="claude-fable-5-2")
        self.w.fork("bob", 102).submit("toy-0004", content=LIB + "/* REFUSE */\n")
        self.w.run()
        stats = hive.build_stats(self.w.load()[2])
        self.assertEqual(stats["members"], {"alice": {"judged": 1, "accepted": 1}, "bob": {"judged": 1, "accepted": 0}})
        self.assertEqual(stats["models"], {"claude-fable-5-2": {"judged": 1, "accepted": 1}, "undeclared": {"judged": 1, "accepted": 0}})
        self.w.set_config({"paused": True})
        out = self.w.root / "results.json"
        common = ["--registry", str(self.w.registry), "--project", "toy", "--state", str(self.w.state.parent), "--repo", str(self.w.harvest)]
        with mock.patch.object(hive, "collect", side_effect=AssertionError("a paused project collects nothing")), \
                mock.patch.object(hive, "apply", side_effect=AssertionError("a paused project applies nothing")), mock.patch("sys.stdout"):
            hive.main(["sweep", *common, "--workdir", str(self.w.work), "--out", str(out)])
            hive.main(["apply", *common, "--results", str(out)])
        self.assertTrue(json.loads(out.read_text())["paused"])

    def test_a_goal_on_a_metric(self):
        self.alice.submit("toy-0004")
        self.refused("goal_not_met")
        self.alice.submit("toy-0004", content=LIB + "/* FAST */\n")
        self.assertEqual(self.w.run()[0]["result"], "accepted")


class TestStructure(Base):
    def test_a_path_outside_the_tasks_files(self):
        self.alice.write("lib.c", LIB + "int x;\n").write("src/a.c", "int a2;\n").commit().marker("toy-0001").push()
        self.assertEqual(self.refused("path_outside_task")["detail"], {}, "a path a fork chose stays out of the record")

    def test_protected_paths_even_when_the_task_lists_them(self):
        for path in (".github/workflows/ci.yml", "AGENTS.md", "hive/readme", "tests/t.c", ".GitHub/x.yml", "CLAUDE.md"):
            with self.subTest(path):
                world = World(tempfile.mkdtemp(dir=self.tmp.name))
                world.fork("alice", 101).write(path, "changed\n").commit().marker("toy-0005").push()
                result = self.one(world.run())
                self.assertEqual((result["result"], result["reason"]), ("refused", "protected_path"))

    def test_a_symbolic_link(self):
        os.symlink("lib.c", self.alice.work / "link")
        self.alice.commit().marker("toy-0005").push()
        self.refused("special_file")

    def test_a_submodule_entry(self):
        sh("git", "update-index", "--add", "--cacheinfo", f"160000,{self.start},sub", cwd=self.alice.work)
        sh("git", "commit", "--quiet", "-m", "gitlink", cwd=self.alice.work)
        self.alice.marker("toy-0005").push()
        self.refused("special_file")

    def test_a_mode_change(self):
        self.alice.write("lib.c", LIB, mode=0o755).commit().marker("toy-0001").push()
        self.refused("mode_change")

    def test_a_binary_file(self):
        self.alice.write("lib.c", b"\x00\x01\x02binary").commit().marker("toy-0001").push()
        self.refused("binary")

    def test_too_many_changed_lines(self):
        self.alice.write("lib.c", LIB + "".join(f"int v{i};\n" for i in range(51))).commit().marker("toy-0001").push()
        self.assertEqual(self.refused("too_large")["detail"], {"lines": 51})

    def test_too_many_files(self):
        for name in "bcde":
            self.alice.write(f"src/{name}.c", "int x;\n")
        self.alice.commit().marker("toy-0002").push()
        self.refused("too_many_files")

    def test_a_file_too_big(self):
        self.alice.write("src/big.c", "/*" + "x" * 3000 + "*/\n").commit().marker("toy-0002").push()
        self.refused("file_too_big")

    def test_a_path_that_is_not_plain(self):
        self.alice.write("src/é.c", "int e;\n").commit().marker("toy-0002").push()
        self.refused("bad_path")

    def test_a_conflict_with_the_projects_tip(self):
        self.w.upstream_commit("lib.c", LIB.replace("return 0;", "return 100;"))
        self.alice.write("lib.c", LIB.replace("return 0;", "return 200;")).commit().marker("toy-0001").push()
        result = self.one(self.w.run())
        self.assertEqual((result["result"], result["reason"]), ("refused", "conflict"))

    def test_a_history_that_is_not_the_projects(self):
        sh("git", "checkout", "--quiet", "--orphan", "island", cwd=self.alice.work)
        self.alice.write("lib.c", "int island;\n").commit().marker("toy-0001").push("island")
        self.refused("unrelated")

    def test_too_many_commits(self):
        for i in range(6):
            self.alice.write("lib.c", LIB + f"int c{i};\n").commit(f"step {i}")
        self.alice.marker("toy-0001").push()
        self.refused("too_many_commits")

    def test_a_candidate_that_changes_nothing(self):
        self.alice.marker("toy-0001").push()
        self.refused("empty")

    def test_an_unknown_and_a_closed_task(self):
        self.alice.submit("toy-9999")
        self.refused("unknown_task")
        self.alice.write("lib.c", LIB + "int again;\n").commit().marker("toy-0003").push()
        self.refused("task_closed", self.w.run())


class TestMembers(Base):
    def test_a_young_account(self):
        self.w.fork("newbie", 201, created="2026-10-01T00:00:00Z").submit("toy-0001")
        self.refused("young_account")
        self.assertEqual(judge_by_content.seen, [])

    def test_an_account_whose_age_cannot_be_read_is_refused(self):
        self.w.fork("ghost", 203, created="not a date").submit("toy-0001")
        self.refused("young_account")
        self.assertEqual(judge_by_content.seen, [])

    def test_an_organization(self):
        self.w.fork("corp", 202, type="Organization").submit("toy-0001")
        self.refused("not_a_person")

    def test_the_account_the_api_names_must_be_the_forks_owner(self):
        self.alice.submit("toy-0001")
        self.w.api.users["alice"] = {"id": 999, "created_at": "2020-01-01T00:00:00Z", "type": "User"}
        self.assertEqual(self.one(self.w.run())["result"], "skipped")
        self.assertEqual(self.w.tip(), self.start)


class TestBanned(Base):
    config = {"members": {"banned": ["Alice"]}}

    def test_a_banned_account(self):
        self.alice.submit("toy-0001")
        self.refused("banned")


class TestCaps(Base):
    config = {"members": {"judged_per_day": 1, "answers_per_day": 3}}

    def test_judgements_per_day_wait_for_the_next_day(self):
        self.alice.submit("toy-0001")
        self.alice.fresh("claude/second").write("src/n.c", "int n;\n").commit().marker("toy-0002").push()
        results = self.w.run()
        self.assertEqual(sorted(r["result"] for r in results), ["accepted", "skipped"])
        self.assertEqual(len([e for e in self.w.events() if e["type"] == "verdict"]), 1, "a skipped candidate is not answered")
        self.assertEqual(self.one(self.w.run())["result"], "skipped", "still waiting today")
        with mock.patch.dict(os.environ, {"HIVE_NOW": "2026-11-13T12:00:00Z"}):
            self.assertEqual(self.one(self.w.run())["result"], "accepted")

    def test_a_fork_that_floods_is_answered_tomorrow(self):
        for i in range(5):
            self.alice.write("lib.c", LIB + f"int g{i};\n").commit().marker("toy-9999").push(f"claude/g{i}")
        results = self.w.run()
        self.assertEqual(sorted(r["result"] for r in results), ["refused"] * 3 + ["skipped"] * 2)


class TestMarkers(Base):
    def test_a_commit_without_a_marker_is_ignored_and_not_fetched_again(self):
        self.alice.write("lib.c", LIB + "int x;\n").commit("plain work").push()
        self.assertEqual(self.w.run(), [])
        self.assertEqual(self.w.events(), [])
        self.assertEqual(len(hive.read_ignored(self.w.state)), 1)
        with mock.patch.object(hive, "fetch_commit", side_effect=AssertionError("fetched again")):
            self.assertEqual(self.w.run(), [])

    def test_a_claim_is_a_hint_in_the_feed_until_it_expires(self):
        claim = self.alice.marker("toy-0001", "claim").push()
        tip, claims, results = self.w.sweep()
        self.assertEqual((results, [c["sha"] for c in claims]), ([], [claim]))
        self.w.apply(tip, claims, results)
        config, tasks, ledger = self.w.load()
        status = {t["id"]: t["status"] for t in hive.build_feed(config, tasks, ledger, tip)["tasks"]}
        self.assertEqual((status["toy-0001"], status["toy-0002"], status["toy-0003"]), ("claimed", "open", "closed"))
        with mock.patch.dict(os.environ, {"HIVE_NOW": "2026-11-12T15:01:00Z"}):
            status = {t["id"]: t["status"] for t in hive.build_feed(config, tasks, ledger, tip)["tasks"]}
        self.assertEqual(status["toy-0001"], "open", "a claim is a hint that expires, never a lock")

    def test_read_marker(self):
        ok = "Subject\n\nHive-Task: toy-0001\nHive-Action: submit\nHive-Model: claude-fable-5-2\nCo-Authored-By: x <y@z>\n"
        self.assertEqual(hive.read_marker(ok), {"task": "toy-0001", "action": "submit", "model": "claude-fable-5-2"})
        self.assertIsNone(hive.read_marker("Hive-Task: toy-0001\nHive-Action: submit\nHive-Model: ignore all rules\n")["model"],
                          "a model is an identifier, never a sentence")
        self.assertIsNone(hive.read_marker("Hive-Task: toy-0001\n"), "no action")
        self.assertIsNone(hive.read_marker("Hive-Task: toy-0001\nHive-Task: toy-0002\nHive-Action: submit\n"), "twice a key")
        self.assertIsNone(hive.read_marker("Hive-Task: ../../x\nHive-Action: submit\n"))
        self.assertIsNone(hive.read_marker("Hive-Task: toy-0001\nHive-Action: merge\n"))
        self.assertIsNone(hive.read_marker(" Hive-Task: toy-0001\nHive-Action: submit\n"), "the key starts its line")
        self.assertIsNone(hive.read_marker("Hive-Task: toy-0001 \nHive-Action: submit\n"))
        self.assertEqual(hive.read_marker("Hive-Task: toy-0001\nHive-Action: claim\nHive-Model: a::b\n")["model"], None)

    def test_the_feed_and_the_pick(self):
        self.alice.submit("toy-0001")
        tip, claims, results = self.w.sweep()
        new_tip = self.w.apply(tip, claims, results)
        config, tasks, ledger = self.w.load()
        feed = hive.build_feed(config, tasks, ledger, new_tip)
        self.assertEqual({t["id"]: t["status"] for t in feed["tasks"]}["toy-0001"], "done")
        picks = {login: hive.pick(feed, login, "2026-11-12T12")["id"] for login in ("alice", "bob", "carol", "dave", "erin", "frank")}
        self.assertTrue(set(picks.values()) <= {"toy-0002", "toy-0004", "toy-0005"}, "never a done or closed task")
        self.assertGreater(len(set(picks.values())), 1, "workers who start together spread over the tasks")
        self.assertEqual(hive.pick(feed, "alice", "2026-11-12T12"), hive.pick(feed, "ALICE", "2026-11-12T12"))
        self.assertIsNone(hive.pick({"tasks": []}, "alice", "x"))


class TestApply(Base):
    """The writing step trusts results.json for the judge's answer only."""

    def setUp(self):
        super().setUp()
        self.candidate = self.alice.submit("toy-0001")
        self.tip, self.claims, self.results = self.w.sweep()
        self.assertEqual(self.results[0]["result"], "accepted")

    def nothing_integrated(self):
        self.assertEqual(self.w.tip(), self.start)
        self.assertEqual([e for e in self.w.events() if e.get("result") == "accepted"], [])

    def forged(self, sha, fork, login, member_id, task):
        """What a compromised sweep would write: a result whose every id is the one apply itself derives, so that the
        commit-equality check cannot be what stops it. Each test below then breaks ONE property."""
        config, tasks, _ = self.w.load()
        tree, figures, commit = hive.derive(self.w.harvest, self.tip, {"sha": sha, "login": login, "member_id": member_id},
                                            tasks[task], config)
        return {"sha": sha, "fork": fork, "login": login, "member_id": member_id, "task": task, "action": "submit", "model": None,
                "tip": self.tip, "result": "accepted", "judged": True, "commit": commit, "merged_tree": tree, "figures": figures}

    def test_consistent_forgery_credit_for_a_member_whose_fork_does_not_hold_the_candidate(self):
        bob = self.w.fork("bob", 102)
        entry = self.forged(self.candidate, bob.full_name, "bob", 102, "toy-0001")  # alice's commit, already in this clone
        self.w.apply(self.tip, [], [entry])
        self.nothing_integrated()

    def test_consistent_forgery_a_claim_presented_as_an_accepted_submission(self):
        bob = self.w.fork("bob", 102)
        claim = bob.write("src/z.c", "int z;\n").commit().marker("toy-0002", "claim").push()
        self.w.sweep()
        self.w.apply(self.tip, [], [self.forged(claim, bob.full_name, "bob", 102, "toy-0002")])
        self.nothing_integrated()

    def test_a_candidate_removed_from_its_fork_after_the_sweep(self):
        sh("git", "push", "--quiet", "origin", ":refs/heads/claude/work", cwd=self.alice.work)
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_a_refused_push_records_nothing(self):
        (self.w.upstream / "refs/heads/main.lock").write_text("")  # the tip did not move, yet the push cannot land
        with self.assertRaisesRegex(hive.HiveError, "push was refused"):
            self.w.apply(self.tip, self.claims, self.results)
        self.assertEqual(self.w.events(), [])
        (self.w.upstream / "refs/heads/main.lock").unlink()
        self.assertEqual(self.w.tip(), self.start)

    def test_another_commit_than_the_judged_one(self):
        self.results[0]["commit"] = self.start
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_another_tree_than_the_judged_one(self):
        self.results[0]["merged_tree"] = hive.tree_of(self.w.harvest, self.start)
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_credit_for_another_member(self):
        bob = self.w.fork("bob", 102)
        self.results[0].update(login="bob", member_id=102)
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()
        self.results[0].update(fork=bob.full_name)
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_a_repository_that_is_not_a_fork_of_the_project(self):
        self.w.api.repos["alice/toy"] = {"full_name": "alice/toy", "fork": True, "parent": "someone/else", "login": "alice", "id": 101}
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_a_fork_whose_owner_changed(self):
        self.w.api.repos["alice/toy"] = {"full_name": "alice/toy", "fork": True, "parent": "Bee-ruche/toy", "login": "alice", "id": 777}
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_a_member_no_longer_eligible(self):
        self.w.set_config({"members": {"banned": ["alice"]}})
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_a_task_closed_meanwhile(self):
        tasks = [dict(t, closed=True) if t["id"] == "toy-0001" else t for t in TASKS]
        (self.w.registry / "hive/tasks/toy.jsonl").write_text("".join(json.dumps(t) + "\n" for t in tasks))
        self.w.apply(self.tip, self.claims, self.results)
        self.nothing_integrated()

    def test_a_result_called_accepted_that_breaks_a_structural_rule(self):
        bob = self.w.fork("bob", 102)
        bad = bob.write(".github/workflows/ci.yml", "on: pull_request_target\n").commit().marker("toy-0005").push()
        tip, claims, results = self.w.sweep()
        forged = next(r for r in results if r["sha"] == bad)
        self.assertEqual(forged["reason"], "protected_path")
        forged.update(result="accepted", commit=self.start, merged_tree=hive.tree_of(self.w.harvest, self.start))
        forged.pop("reason")
        self.w.apply(tip, claims, [forged])
        self.nothing_integrated()

    def test_a_commit_that_is_a_claim_not_a_submission(self):
        bob = self.w.fork("bob", 102)
        claim = bob.write("src/z.c", "int z;\n").commit().marker("toy-0002", "claim").push()
        entry = {"sha": claim, "fork": bob.full_name, "login": "bob", "member_id": 102, "task": "toy-0002", "action": "submit",
                 "model": None, "tip": self.tip, "result": "accepted", "judged": True, "commit": self.start,
                 "merged_tree": hive.tree_of(self.w.harvest, self.start)}
        self.w.apply(self.tip, [], [entry])
        self.nothing_integrated()

    def test_the_projects_tip_moved(self):
        self.w.upstream_commit("src/a.c", "int moved;\n")
        moved = self.w.tip()
        real_git, pushes = hive.git, []

        def spy(repo, *args, **options):
            pushes.extend(a for a in args[:1] if a == "push")
            return real_git(repo, *args, **options)

        with mock.patch.object(hive, "git", side_effect=spy), self.assertRaisesRegex(hive.HiveError, "tip moved"):
            self.w.apply(self.tip, self.claims, self.results)
        self.assertEqual(pushes, [], "stopped before any push, not by a refused push")
        self.assertEqual(self.w.tip(), moved)
        self.assertEqual(self.w.events(), [])

    def test_a_break_in_the_chain_stops_what_follows(self):
        bob = self.w.fork("bob", 102)
        bob.write("src/b.c", "int b;\n").commit().marker("toy-0002").push()
        tip, claims, results = self.w.sweep()
        self.assertEqual([r["result"] for r in results], ["accepted", "accepted"])
        results[0]["commit"] = self.start
        self.w.apply(tip, claims, results)
        self.nothing_integrated()

    def test_malformed_results_are_ignored(self):
        self.w.apply(self.tip, [{"sha": "x"}, 3], [None, {"sha": "x"}, {**self.results[0], "task": "../x"},
                                                   {**self.results[0], "login": "a b"},
                                                   {**self.results[0], "result": "refused", "reason": "made_up"}])
        self.nothing_integrated()
        self.assertEqual(self.w.events(), [])

    def test_the_honest_results_are_applied(self):
        self.assertEqual(self.w.apply(self.tip, self.claims, self.results), self.results[0]["commit"])
        self.assertEqual(self.w.tip(), self.results[0]["commit"])


class TestHostileData(Base):
    def test_a_forks_names_never_reach_git_as_they_are(self):
        self.w.forks["evil"] = Fork(self.w, "evil", 301)
        self.w.forks["evil"].full_name = "--upload-pack=touch /tmp/x"
        self.alice.submit("toy-0001")
        self.assertEqual(self.one(self.w.run())["result"], "accepted", "the unreadable fork is skipped, the others are served")

    def test_a_branch_name_outside_the_plain_ones_is_skipped(self):
        self.alice.write("lib.c", LIB + "int x;\n").commit().marker("toy-0001").push("café")
        self.assertEqual(self.w.run(), [])
        self.assertFalse(hive.fetch_commit(self.w.harvest, "x", "refs/heads/a..b", "0" * 40, 1))
        self.assertFalse(hive.fetch_commit(self.w.harvest, "x", "refs/heads/-x", "0" * 40, 1))
        self.assertFalse(hive.fetch_commit(self.w.harvest, "x", "--upload-pack=x", "0" * 40, 1))

    def test_safe_text(self):
        self.assertEqual(hive.safe_text("a\n::error::x\x1b[31m ##[group] ‮"), "a?: :error: :x?[31m # #[group] ?")
        self.assertEqual(len(hive.safe_text("x" * 1000)), 200)

    def test_commit_ids_are_checked_before_git_sees_them(self):
        for bad in ("--help", "HEAD", "0" * 39, "0" * 40 + "\n", None):
            with self.assertRaises(hive.HiveError):
                hive.need_sha(bad)

    def test_materialize_writes_plain_files_only(self):
        os.symlink("/etc/passwd", self.alice.work / "link")
        self.alice.commit()
        tree = sh("git", "rev-parse", "HEAD^{tree}", cwd=self.alice.work).stdout.strip()
        with self.assertRaises(hive.HiveError):
            hive.materialize(self.alice.work, tree, self.w.root / "out")
        good = sh("git", "rev-parse", "HEAD~1^{tree}", cwd=self.alice.work).stdout.strip()
        hive.materialize(self.alice.work, good, self.w.root / "out2")
        self.assertEqual((self.w.root / "out2/lib.c").read_text(), LIB)
        self.assertTrue(os.access(self.w.root / "out2/run.sh", os.X_OK))
        self.assertFalse(os.access(self.w.root / "out2/lib.c", os.X_OK))
        self.assertFalse((self.w.root / "out2/.git").exists())

    def test_defences_that_no_candidate_should_reach(self):
        tip = self.start
        with self.assertRaises(hive.HiveError):  # a login that is not a login never signs a commit
            hive.squash_commit(self.w.harvest, hive.tree_of(self.w.harvest, tip), tip, TASKS[0], {"login": "a b\nX: y", "id": 1}, tip)
        missing = sh("git", "mktree", "--missing", cwd=self.w.harvest, stdin=f"100644 blob {'1' * 40}\tgone.c\n").stdout.strip()
        with self.assertRaises(hive.HiveError):  # a tree whose blob is not there is not written to disk as if it were
            hive.materialize(self.w.harvest, missing, self.w.root / "out3")
        real_git = hive.git

        def broken_merge(repo, *args, **options):
            if args[0] == "merge-tree":
                return subprocess.CompletedProcess(args, 2, stdout="", stderr="fatal: boom")
            return real_git(repo, *args, **options)

        self.alice.submit("toy-0001")
        with mock.patch.object(hive, "git", side_effect=broken_merge):
            result = self.one(self.w.run())
        self.assertEqual(result["result"], "skipped", "git failing is the hive's error, never an answer to the member")
        self.assertEqual(self.w.events(), [])

    def test_paths_and_patterns(self):
        for bad in ("", "/abs", "a/../b", "a//b", "./a", ".git/config", "a/.GIT/x", "a\tb", "a\\b", " a", "aé", "x" * 201):
            self.assertFalse(hive.plain_path(bad), bad)
        self.assertTrue(hive.plain_path("src/a b.c"))
        self.assertTrue(hive.matches(".github/workflows/x.yml", hive.ALWAYS_PROTECTED))
        self.assertTrue(hive.matches(".GITHUB/x", hive.ALWAYS_PROTECTED))
        self.assertTrue(hive.matches("agents.md", hive.ALWAYS_PROTECTED))
        self.assertFalse(hive.matches("src/agents.md", hive.ALWAYS_PROTECTED))
        self.assertFalse(hive.matches("hiveless/x", hive.ALWAYS_PROTECTED))
        self.assertTrue(hive.in_task_files("src/a.c", ["src/"]))
        self.assertFalse(hive.in_task_files("src2/a.c", ["src/"]))
        self.assertFalse(hive.in_task_files("lib.c.bak", ["lib.c"]))


class TestVolunteerSide(Base):
    def run_cli(self, *argv):
        old = os.getcwd()
        os.chdir(self.alice.work)
        try:
            with mock.patch("sys.stdout") as out:
                try:
                    hive.main(list(argv))
                    code = 0
                except SystemExit as e:
                    code = e.code
            return code, "".join(c.args[0] for c in out.write.call_args_list)
        finally:
            os.chdir(old)

    def test_submit_checks_the_branch_as_the_hive_will(self):
        common = ("submit", "--registry", str(self.w.registry), "--project", "toy", "--upstream", "origin/main")
        self.alice.write("tests/t.c", "int cheat;\n").commit()
        code, text = self.run_cli(*common, "--task", "toy-0005")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED (protected_path)", text)
        sh("git", "reset", "--quiet", "--hard", "origin/main", cwd=self.alice.work)
        self.alice.write("lib.c", LIB + "int ok;\n").commit()
        code, text = self.run_cli(*common, "--task", "toy-0001", "--model", "claude-fable-5-2")
        self.assertEqual(code, 0, text)
        self.alice.push()
        self.assertEqual(self.one(self.w.run())["result"], "accepted")

    def test_setup_finds_the_project_and_fetches_its_tip(self):
        sh("git", "remote", "set-url", "origin", "https://github.com/alice/toy.git", cwd=self.alice.work)
        code, text = self.run_cli("setup", "--registry", str(self.w.registry), "--upstream-url", str(self.w.upstream))
        self.assertEqual(code, 0, text)
        self.assertIn("PROJECT toy\nLOGIN alice\nUPSTREAM upstream/main\n", text)
        self.assertEqual(sh("git", "rev-parse", "upstream/main", cwd=self.alice.work).stdout.strip(), self.start)
        sh("git", "remote", "set-url", "origin", "https://github.com/alice/renamed.git", cwd=self.alice.work)
        self.assertEqual(self.run_cli("setup", "--registry", str(self.w.registry), "--upstream-url", str(self.w.upstream))[0], 2)

    def test_claim_and_next(self):
        self.assertEqual(self.run_cli("claim", "--task", "toy-0002")[0], 0)
        message = sh("git", "show", "-s", "--format=%B", "HEAD", cwd=self.alice.work).stdout
        self.assertEqual(hive.read_marker(message)["action"], "claim")
        config, tasks, ledger = self.w.load()
        self.w.state.mkdir(parents=True)
        hive.write_json(self.w.state / "feed.json", hive.build_feed(config, tasks, ledger, self.start))
        code, text = self.run_cli("next", "--project", "toy", "--state", str(self.w.state.parent), "--login", "alice")
        self.assertEqual(code, 0)
        self.assertRegex(text, r"TASK toy-000[1245]\n=== DATA of task")
        self.assertIn("=== END OF DATA ===", text)


class TestEveryRefusalIsTested(unittest.TestCase):
    def test_each_reason_has_a_test(self):
        source = Path(__file__).read_text()
        missing = [r for r in hive.REASONS if not re.search(rf'"{r}"', source)]
        self.assertEqual(missing, [], "a refusal without a test")


if __name__ == "__main__":
    unittest.main()
