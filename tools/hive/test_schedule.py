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
                        self.w.apply({})
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
            judged = len(self.calls.get(token, []))
            t.assertLessEqual(judged, 8, f"{token} ({c['kind']}) was judged {judged} times")


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


if __name__ == "__main__":
    unittest.main()
