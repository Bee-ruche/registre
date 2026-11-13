#!/usr/bin/env python3
"""The hive over many runs (docs/protocol.md, « What holds over time »): schedules drawn at random, in which other
accounts push what fails, what never ends, what the project's repository declines, copies and duplicates, take
branches away and push between the steps, and in which the hive's own machines break (the judge down, its answers
lost, a push that lands and is not confirmed, the write step killed after its promise).

Whatever the schedule, at the end:

  R1  every honest candidate, alone of its member on an open task, is integrated, in its member's name;
  R2  no account has credit for a task on which someone else's same work was pushed before its own;
  R3  every run of the judge on a candidate left a line in the ledger (in the runs the write step completed);
  R4  the project's branch only ever moved forward, each task was integrated once, and the ledger is plain JSON.

Local git repositories only, standard library only. HIVE_SEEDS (default "1 2 3 4") chooses the schedules."""

import datetime as dt
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.environ.get("HIVE_DIR") or str(Path(__file__).resolve().parent))
import hive  # noqa: E402
import test_hive as th  # noqa: E402

POOL = 14
TASKS = [{"id": f"pool-{i:04d}", "title": f"Fill p{i:02d}", "files": [f"pool/p{i:02d}.c"]} for i in range(POOL)]
START = dt.datetime(2026, 11, 12, 12, 0, 0, tzinfo=dt.timezone.utc)
HOOK = ("#!/bin/sh\nwhile read old new ref; do\n  if git log -p \"$old..$new\" | grep -q 'AKIA[0-9A-Z]\\{16\\}'; then\n"
        "    echo 'push protection' >&2; exit 1\n  fi\ndone\nexit 0\n")


class Schedule:
    def __init__(self, test, seed, root):
        self.test, self.rng, self.hour, self.elapsed = test, random.Random(seed), 0, 0.0
        self.w = th.World(root, {"limits": {"changed_lines": 50, "files": 3, "file_bytes": 2000, "commits": 30}})
        (self.w.registry / "hive/tasks/toy.jsonl").write_text("".join(json.dumps(t) + "\n" for t in TASKS))
        hook = self.w.upstream / "hooks/pre-receive"
        hook.write_text(HOOK)
        os.chmod(hook, 0o755)
        self.honest = [self.w.fork(f"honest{i}", 100 + i) for i in range(3)]
        self.others = [self.w.fork(f"other{i}", 600 + i) for i in range(3)]
        self.tokens, self.branches = {}, 0   # token -> {"sha", "login", "task", "kind", "at"}
        self.calls, self.recorded_runs, self.down, self.heavy, self.tips = {}, set(), False, set(), [self.w.tip()]
        self.faulty = set()
        self.free = [t["id"] for t in TASKS]

    # -- the judge, on a clock of its own -----------------------------------------------------------------------
    def judge(self, base, candidate, task, tip, commit):
        if self.down:
            raise OSError("no container runtime")
        path = candidate / task["files"][0]
        text = path.read_text() if path.exists() else ""
        token = text.split("id:")[1].split()[0] if "id:" in text else None
        if tip != commit and token:  # not the check of the machine (the tip against itself)
            self.calls.setdefault(token, []).append(self.run)
        if "TIMEOUT" in text:
            self.elapsed += 3600
            return {"code": 2}
        self.elapsed += 60
        return {"code": 2 if "ENVERR" in text else 1 if "REFUSE" in text else 0, "report": {"gain": 0.0, "outputs_compared": 12}}

    def now(self, extra=0.0):
        return hive.iso(START + dt.timedelta(hours=self.hour, seconds=extra))

    # -- what members push ----------------------------------------------------------------------------------------
    def push(self, fork, task, kind, body="", copy_of=None):
        token = f"t{len(self.tokens):03d}"
        self.branches += 1
        content = (f"int v; /* id:{copy_of} */\n" if copy_of else f"int v; /* id:{token} {body} */\n")
        number = int(task[-4:])
        with mock.patch.dict(os.environ, {"HIVE_NOW": self.now(60 if copy_of else 0)}):  # a copy comes after what it copies
            sha = fork.fresh(f"b{self.branches}").write(f"pool/p{number:02d}.c", content).commit(f"work {token}").marker(task).push()
        self.tokens[token] = {"sha": sha, "login": fork.login, "task": task, "kind": kind, "at": self.hour, "copy_of": copy_of,
                              "fork": fork, "branch": fork.branch}
        return token

    def members_act(self):
        rng = self.rng
        answered, ledger = self.answered(), self.w.load()[2]
        for fork in self.honest:
            # An honest worker follows `hive next`: one candidate at a time, and none once the day's judgements are used.
            in_flight = any(c["login"] == fork.login and c["sha"] not in answered for c in self.tokens.values())
            used = ledger.judged_today(fork.id, self.now()[:10]) >= hive.DEFAULTS["members"]["judged_per_day"]
            if self.free and not in_flight and not used and rng.random() < 0.8:
                self.push(fork, self.free.pop(rng.randrange(len(self.free))), "honest")
        waiting = [t for t, c in self.tokens.items() if c["kind"] == "honest" and c["sha"] not in self.answered()]
        for fork in self.others:
            action = rng.choice(["ENVERR", "TIMEOUT", "REFUSE", "AKIA", "HEAVY", "copy", "twenty", "none", "none"])
            task = rng.choice(TASKS)["id"]
            if action in ("ENVERR", "TIMEOUT", "REFUSE"):
                self.push(fork, task, action, action)
            elif action == "AKIA":
                self.push(fork, task, action, 'key "AKIAABCDEFGHIJKLMNOP"')
            elif action == "HEAVY":
                self.heavy.add(self.tokens[self.push(fork, task, action, "heavy")]["sha"])
            elif action == "copy" and waiting:
                original = rng.choice(waiting)
                self.push(fork, self.tokens[original]["task"], "copy", copy_of=original)
            elif action == "twenty":
                for _ in range(6):
                    self.push(fork, task, "REFUSE", "REFUSE again")

    def answered(self):
        return {e["sha"] for e in self.w.events() if e["type"] == "verdict"}

    # -- one run of the hive, with what may go wrong in it ---------------------------------------------------------
    def one_run(self, quiet=False):
        rng, self.run, self.elapsed = self.rng, self.hour, 0.0
        fault = "none" if quiet else rng.choice(["none"] * 5 + ["down", "lost", "unconfirmed", "killed", "withdrawn", "late"])
        self.down = fault == "down"
        real_merge, real_push = hive.merge_tree, hive.guarded_push

        def merge(repo, tip, candidate, limits):
            if candidate in self.heavy:
                raise hive.HiveError("git merge-tree: timeout after 300 s")
            return real_merge(repo, tip, candidate, limits)

        def push_then_fail(*a, **k):
            landed = real_push(*a, **k)
            if landed:
                raise hive.HiveError("git push: timeout after 180 s")
            return landed

        clock = mock.patch.object(hive.time, "monotonic", side_effect=lambda: self.elapsed)
        with mock.patch.object(hive, "merge_tree", side_effect=merge), clock:
            with mock.patch.dict(os.environ, {"HIVE_NOW": self.now()}):
                self.w.plan()
                others = [c for c in self.tokens.values() if c["kind"] != "honest"]
                if fault == "withdrawn" and others:  # an honest member leaves its branch where it is
                    gone = rng.choice(others)
                    th.sh("git", "push", "--quiet", "origin", f":refs/heads/{gone['branch']}", cwd=gone["fork"].work, check=False)
                if fault == "late":
                    self.push(rng.choice(self.others), rng.choice(TASKS)["id"], "REFUSE", "REFUSE late")
                verdicts, _ = self.w.judge(self.judge)
            completed = True
            with mock.patch.dict(os.environ, {"HIVE_NOW": self.now(self.elapsed)}):
                try:
                    if fault == "lost":
                        self.w.apply({}, started=[])
                    elif fault == "unconfirmed":
                        with mock.patch.object(hive, "guarded_push", side_effect=push_then_fail):
                            self.w.apply(verdicts)
                    elif fault == "killed":
                        def killed():
                            raise hive.HiveError("the write step was stopped")
                        self.w.apply(verdicts, checkpoint=killed)
                    else:
                        self.w.apply(verdicts)
                except hive.HiveError:
                    completed = fault not in ("killed",)
        if completed and fault != "lost":
            self.recorded_runs.add(self.run)
        if fault in ("unconfirmed", "killed", "lost", "down"):
            self.faulty.add(self.run)  # a judgement lost to the hive's own breakdown is not the candidate's doing
        self.tips.append(self.w.tip())
        self.hour += 1

    # -- what must hold at the end ----------------------------------------------------------------------------------
    def check(self):
        t, events = self.test, self.w.events()
        for line in (self.w.state / "ledger.jsonl").read_text().splitlines():
            json.loads(line, parse_constant=lambda name: t.fail(f"{name} in the ledger"))
        accepted = {e["sha"]: e for e in events if e["type"] == "verdict" and e["result"] == "accepted"}
        by_sha = {c["sha"]: (token, c) for token, c in self.tokens.items()}
        for token, c in self.tokens.items():
            if c["kind"] == "honest":  # R1
                history = [(e["type"], e.get("kind") or e.get("reason") or e.get("result"), e["at"][5:16])
                           for e in self.w.load()[2].events if e.get("sha") == c["sha"]]
                rivals = [(k, x["kind"], x["login"], x["at"], x["sha"][:7], x["sha"] in accepted) for k, x in self.tokens.items()
                          if x["task"] == c["task"] and k != token]
                t.assertTrue(c["sha"] in accepted, f"R1: honest candidate {token} ({c['login']}, {c['task']}, pushed at run "
                                                   f"{c['at']}) was never integrated; its lines: {history}; others on the task: {rivals}")
                t.assertEqual(accepted[c["sha"]]["member"], c["login"])
            if c["kind"] == "copy":  # R2
                t.assertNotIn(c["sha"], accepted, f"R2: {c['login']} has the credit for a copy of {c['copy_of']}")
        for token, runs in self.calls.items():  # R3
            sha = self.tokens[token]["sha"] if token in self.tokens else None
            counted = [r for r in runs if r in self.recorded_runs]
            lines = [e for e in self.w.load()[2].events if e.get("sha") == sha and (
                e["type"] in ("error", "unused", "intent") or (e["type"] == "verdict" and e.get("judged") and e["result"] == "refused"))]
            t.assertLessEqual(len(counted), len(lines), f"R3: {token} ({self.tokens[token]['kind']}) was judged in runs {counted} "
                                                        f"and the ledger has {len(lines)} line(s) for it")
        tasks = [e["task"] for e in accepted.values()]  # R4
        t.assertEqual(len(tasks), len(set(tasks)), "R4: a task integrated twice")
        for before, after in zip(self.tips, self.tips[1:]):
            moved = th.sh("git", "merge-base", "--is-ancestor", before, after, cwd=self.w.upstream, check=False).returncode
            t.assertEqual(moved, 0, "R4: the project's branch went back")
        t.assertNotIn("AKIA", th.sh("git", "log", "-p", "main", cwd=self.w.upstream).stdout)
        for sha, (token, c) in by_sha.items():
            judged = len([run for run in self.calls.get(token, []) if run in self.recorded_runs and run not in self.faulty])
            story = [(e["type"], e.get("kind") or e.get("reason") or e.get("result"), e.get("unproven"), e["at"][8:13])
                     for e in self.w.load()[2].events if e.get("sha") == sha]
            t.assertLessEqual(judged, 6, f"{token} ({c['kind']}, {c['login']}) was judged {judged} times in runs where nothing of the "
                                         f"hive's broke, in runs {self.calls.get(token)}: {story}")


class TestSchedule(unittest.TestCase):
    def test_what_holds_over_many_runs(self):
        for seed in (int(s) for s in os.environ.get("HIVE_SEEDS", "1 2 3 4").split()):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as root:
                drawn = iter(range(10 ** 6))
                import hashlib
                keys = mock.patch.object(hive.secrets, "token_hex",
                                         side_effect=lambda size: hashlib.sha256(f"{seed}:{next(drawn)}".encode()).hexdigest()[:2 * size])
                with keys, mock.patch.dict(os.environ, th.GIT_ENV):
                    schedule = Schedule(self, seed, root)
                    for _ in range(12):
                        schedule.members_act()
                        schedule.one_run()
                    for _ in range(int(os.environ.get("HIVE_QUIET", "14"))):  # then runs in which nothing more goes wrong
                        schedule.one_run(quiet=True)
                    schedule.check()


def at(hours, minutes=0):
    return hive.iso(START.replace(hour=0) + dt.timedelta(hours=hours, minutes=minutes))


class Sim:
    """A world driven run by run: pushes at chosen instants, a judge on a clock of its own (TIMEOUT costs an hour)."""

    def __init__(self, root, hook=False):
        self.w = th.World(root, {"limits": {"changed_lines": 50, "files": 3, "file_bytes": 2000, "commits": 30}})
        (self.w.registry / "hive/tasks/toy.jsonl").write_text("".join(json.dumps(t) + "\n" for t in TASKS))
        if hook:
            path = self.w.upstream / "hooks/pre-receive"
            path.write_text(HOOK)
            os.chmod(path, 0o755)
        self.elapsed, self.count, self.calls = 0.0, 0, {}

    def judge(self, base, candidate, task, tip, commit):
        path = candidate / task["files"][0]
        text = path.read_text() if path.exists() else ""
        token = text.split("id:")[1].split()[0] if "id:" in text else None
        if tip != commit and token:
            self.calls[token] = self.calls.get(token, 0) + 1
        self.elapsed += 3600 if "TIMEOUT" in text else 60
        return {"code": 2 if "TIMEOUT" in text else 1 if "REFUSE" in text else 0, "report": {"gain": 0.0, "outputs_compared": 12}}

    def push(self, fork, task, token, body, when):
        self.count += 1
        with mock.patch.dict(os.environ, {"HIVE_NOW": when}):
            sha = fork.fresh(f"b{self.count}").write(f"pool/p{int(task[-4:]):02d}.c", f"int v; /* id:{token} {body} */\n") \
                .commit(f"work {token}").marker(task).push()
        return sha, fork.branch

    def delete(self, fork, branch):
        th.sh("git", "push", "--quiet", "origin", f":refs/heads/{branch}", cwd=fork.work)

    def push_again(self, fork, sha, branch, when):
        th.sh("git", "push", "--quiet", "origin", f"{sha}:refs/heads/{branch}", cwd=fork.work)
        fork.pushes.append((sha, when))

    def run(self, when, lost=False, applies=1):
        self.elapsed = 0.0
        with mock.patch.object(hive.time, "monotonic", side_effect=lambda: self.elapsed), mock.patch.dict(os.environ, {"HIVE_NOW": when}):
            self.w.plan()
            verdicts, _ = self.w.judge(self.judge)
            for _ in range(applies):
                try:
                    self.w.apply({} if lost else verdicts, started=[] if lost else None)
                except hive.HiveError:
                    pass

    def lines(self, sha):
        return [(e["type"], e.get("kind") or e.get("reason") or e.get("result")) for e in self.w.load()[2].events if e.get("sha") == sha]

    def accepted(self):
        return {e["sha"]: e["member"] for e in self.w.load()[2].events if e["type"] == "verdict" and e["result"] == "accepted"}


class TestTargetedSchedules(unittest.TestCase):
    """Schedules built on purpose against one member's candidate (found by an adversarial review of an earlier
    version), with what must come out of them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        import hashlib
        drawn = iter(range(10 ** 6))
        for patch in (mock.patch.dict(os.environ, th.GIT_ENV),
                      mock.patch.object(hive.secrets, "token_hex",
                                        side_effect=lambda size: hashlib.sha256(f"t:{next(drawn)}".encode()).hexdigest()[:2 * size])):
            patch.start()
            self.addCleanup(patch.stop)

    def test_candidates_that_never_end_cost_a_candidate_behind_them_neither_its_place_nor_its_credit(self):
        """Two accounts put three never-ending candidates before the victim's at each run, and one of them copies
        the victim's work. The victim is not marked for the time they use up, is integrated, and keeps the credit."""
        s = Sim(self.tmp.name)
        victim, a, b = s.w.fork("victim", 101), s.w.fork("atk1", 601), s.w.fork("atk2", 602)
        live, number = [], 0

        def arm(hour):
            nonlocal number
            for fork, branch in live:
                s.delete(fork, branch)
            live.clear()
            for fork in (a, a, b):
                number += 1
                live.append((fork, s.push(fork, f"pool-{1 + number % 12:04d}", f"x{number:03d}", "TIMEOUT", at(hour, 5))[1]))

        arm(20)
        honest, _ = s.push(victim, "pool-0000", "V", "honest", at(20, 30))
        copy, _ = s.push(b, "pool-0000", "V", "honest", at(20, 31))
        for hour in range(21, 27):
            s.run(at(hour))
            if honest in s.accepted():
                break
            arm(hour)
        self.assertEqual((s.accepted().get(honest), copy in s.accepted()), ("victim", False), s.lines(honest))
        self.assertLessEqual(hour, 22, "within two runs")
        self.assertEqual([kind for kind, _ in s.lines(honest) if kind == "error"], [], "never marked for the others' time")

    def test_commits_kept_in_reserve_and_declined_by_the_project_do_not_hold_a_candidate_back(self):
        for reserve in (True, False):
            with self.subTest(taken_away_and_pushed_again=reserve), tempfile.TemporaryDirectory() as root:
                s = Sim(root, hook=True)
                victim, a, b = s.w.fork("victim", 101), s.w.fork("atk1", 601), s.w.fork("atk2", 602)
                first, _ = s.push(victim, "pool-0013", "W", "honest", at(9, 0))
                s.run(at(10))  # the hive has pushed to this project before
                self.assertEqual(s.accepted().get(first), "victim")
                stock = []
                for i in range(5):
                    for fork in (a, b):
                        sha, branch = s.push(fork, f"pool-{1 + len(stock):04d}", f"k{len(stock):02d}", 'key "AKIAABCDEFGHIJKLMNOP"', at(10, 10))
                        stock.append((fork, sha, branch))
                        if reserve:
                            s.delete(fork, branch)
                honest, _ = s.push(victim, "pool-0000", "V", "honest", at(14, 30))
                if reserve:
                    for fork, sha, branch in stock:
                        s.push_again(fork, sha, branch, at(14, 31))
                runs = 0
                while honest not in s.accepted() and runs < 12:
                    runs += 1
                    s.run(at(14 + runs))
                self.assertEqual(s.accepted().get(honest), "victim", s.lines(honest))
                self.assertLessEqual((runs, s.calls["V"]), (1, 1) if reserve else (3, 3),
                                     "each account that sends what the project declines costs the others one run, not one per commit")

    def test_a_write_step_run_again_marks_nobody_twice(self):
        s = Sim(self.tmp.name)
        victim, other = s.w.fork("victim", 101), s.w.fork("other", 102)
        honest, _ = s.push(victim, "pool-0000", "V", "honest", at(20, 30))
        slow, _ = s.push(other, "pool-0001", "T", "TIMEOUT", at(20, 31))
        for hour in (21, 22, 23):
            s.run(at(hour), applies=3)
        self.assertEqual(s.accepted().get(honest), "victim")
        self.assertEqual(s.lines(slow)[:3], [("error", "judge")] * 3)
        self.assertEqual(s.lines(slow)[3:], [("verdict", "judge_failed")], "three runs, three failures, however often each write step ran")
        self.assertEqual(len(s.lines(honest)), 2, "one promise and one verdict")


if __name__ == "__main__":
    unittest.main()
