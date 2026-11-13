#!/usr/bin/env python3
"""The hive over many runs (docs/protocol.md, « What holds over time »): schedules drawn at random, in which honest
workers do what `hive next` says (ask, work on the task they were dealt, submit), other accounts ask and leave their
task, send what fails, what never ends, what the project's repository declines, many candidates at once, candidates
for tasks they do not hold and copies of someone else's work, and in which the hive's own machines break (the judge
down, its answers lost, a push that lands and is not confirmed, the write step killed after its promise, the
recording step skipped, a plan made on a ledger another run wrote to, a fork that cannot be read).

Whatever the schedule, at the end:

  R1  every correct candidate an honest worker pushed for its deal, in time, is integrated in its name; and in a
      run where nothing breaks, an honest worker that asks while tasks are plenty is dealt one;
  R2  only the member the hive dealt a task to has credit for it: a candidate for a task its member does not hold
      is never judged and leaves no line;
  R3  every run of the judge on a candidate left a line in the ledger (in the runs the write step completed);
  R4  the project's branch only ever moved forward, each task was integrated once, the ledger is plain JSON, a task
      is never dealt while its previous deal is live, and an account never holds two live deals nor more deals in
      a day than the project allows;
  R5  no candidate is judged more than six times, and accounts that take tasks and waste them do not stop the work.

Local git repositories only, standard library only. HIVE_SEEDS (default "1 2 3 4") chooses the schedules."""

import datetime as dt
import hashlib
import json
import os
import random
import subprocess
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
LIMITS = {"limits": {"changed_lines": 50, "files": 3, "file_bytes": 2000, "commits": 30}}


def pool_world(root, hook=False):
    world = th.World(root, LIMITS)
    (world.registry / "hive/tasks/toy.jsonl").write_text("".join(json.dumps(t) + "\n" for t in TASKS))
    if hook:
        path = world.upstream / "hooks/pre-receive"
        path.write_text(HOOK)
        os.chmod(path, 0o755)
    return world


def feed_of(world):
    path = world.state / "feed.json"
    return json.loads(path.read_text()) if path.exists() else None


def replay(test, events, per_day):
    """R4 on the ledger alone: a task is dealt only when its previous deal is not live; an account is dealt a task
    only when it holds no live deal; and never more deals in a day than allowed (those accepted left out)."""
    live, holder, day = {}, {}, {}
    for e in events:
        if e["type"] == "deal":
            test.assertNotIn(e["task"], live, f"R4: {e['task']} dealt while its deal to {live.get(e['task'])} is live")
            test.assertNotIn(e["member_id"], holder, f"R4: {e['member']} dealt {e['task']} while it holds {holder.get(e['member_id'])}")
            live[e["task"]], holder[e["member_id"]] = (e["member_id"], e["at"]), e["task"]
            day.setdefault((e["member_id"], e["at"][:10]), set()).add(e["at"])
            test.assertLessEqual(len(day[(e["member_id"], e["at"][:10])]), per_day, f"R4: {e['member']} has more deals than a day allows")
        elif e["type"] in ("expired", "verdict") and live.get(e.get("task")) == (e.get("member_id"), e.get("deal")):
            del live[e["task"]], holder[e["member_id"]]
        if e["type"] == "verdict" and e["result"] == "accepted":
            day.get((e["member_id"], e["deal"][:10]), set()).discard(e["deal"])


class Schedule:
    def __init__(self, test, seed, root):
        self.test, self.rng, self.hour, self.elapsed = test, random.Random(seed), 0, 0.0
        self.w = pool_world(root, hook=True)
        self.honest = [self.w.fork(f"honest{i}", 100 + i) for i in range(3)]
        self.others = [self.w.fork(f"other{i}", 600 + i) for i in range(3)]
        self.tokens, self.branches = {}, 0  # token -> {"sha", "login", "task", "kind", ...}
        self.calls, self.recorded_runs, self.down, self.heavy, self.tips = {}, set(), False, set(), [self.w.tip()]
        self.faulty, self.answered_deals, self.last_deal, self.slow = set(), {}, {}, []

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

    def now(self, minutes=0.0):
        return hive.iso(START + dt.timedelta(hours=self.hour, minutes=minutes))

    # -- what members push ----------------------------------------------------------------------------------------
    def push(self, fork, task, kind, deal, body="", copy_of=None):
        token = f"t{len(self.tokens):03d}"
        self.branches += 1
        content = (f"int v; /* id:{copy_of} */\n" if copy_of else f"int v; /* id:{token} {body} */\n")
        sha = fork.fresh(f"b{self.branches}").write(f"pool/p{int(task[-4:]):02d}.c", content).commit(f"work {token}") \
            .marker(task, deal=deal).push()
        self.tokens[token] = {"sha": sha, "login": fork.login, "task": task, "kind": kind, "at": self.hour, "copy_of": copy_of,
                              "fork": fork, "branch": fork.branch, "deal": deal}
        return token

    def members_act(self, others=True):
        """Each worker's firing, some minutes before the hive's run."""
        rng, feed = self.rng, feed_of(self.w)
        with mock.patch.dict(os.environ, {"HIVE_NOW": self.now(-10)}):
            for fork in self.honest:
                lazy = fork is self.honest[2]
                deal, wait = hive.my_deal(feed, fork.login) if feed else (None, None)
                done = self.answered_deals.setdefault(fork.login, set())
                if lazy and rng.random() < 0.3:
                    continue  # it misses a firing
                if deal is None:
                    former = self.last_deal.get(fork.login)
                    if lazy and wait and former and former["at"] not in done and rng.random() < 0.5:
                        done.add(former["at"])  # its time was up: it pushes its work all the same
                        self.push(fork, former["task"], "late", former["at"])
                    elif not wait:
                        fork.ready()
                    continue
                self.last_deal[fork.login] = deal
                left = (hive.parse_iso(deal["until"]) - hive.now()).total_seconds() / 3600
                if deal["candidate"] or deal["at"] in done or left < hive.WORK_MARGIN_HOURS:
                    continue  # `hive next` says to wait
                done.add(deal["at"])
                self.push(fork, deal["task"], "honest", deal["at"])
                fork.ready()  # and asks for the next one
            if not others:
                return
            waiting = [t for t, c in self.tokens.items() if c["kind"] == "honest" and c["sha"] not in self.answered()]
            holders = self.w.load()[2].deals()
            for fork in self.others:
                deal, _ = hive.my_deal(feed, fork.login) if feed else (None, None)
                action = rng.choice(["ask", "ask", "ask", "junk", "junk", "junk", "flood", "stray", "copy", "none"])
                if action == "ask" or (action in ("junk", "flood") and not deal):
                    fork.ready(tier=rng.choice([None, 1, 3]))  # most of these deals are left to expire
                elif action == "junk":
                    body = rng.choice(["ENVERR", "TIMEOUT", "REFUSE", 'key "AKIAABCDEFGHIJKLMNOP"', "heavy"])
                    token = self.push(fork, deal["task"], body.split()[0], deal["at"], body)
                    if body == "heavy":
                        self.heavy.add(self.tokens[token]["sha"])
                    if rng.random() < 0.5:
                        fork.ready()
                elif action == "flood":
                    for _ in range(6):
                        self.push(fork, deal["task"], "REFUSE", deal["at"], "REFUSE again")
                elif action == "stray":  # for a task it does not hold: under an instant of its own, or under the holder's
                    task = rng.choice(TASKS)["id"]
                    if not (task in holders and holders[task]["member_id"] == fork.id and holders[task]["state"] != "closed"):
                        named = holders[task]["at"] if task in holders and rng.random() < 0.5 else False
                        self.push(fork, task, "stray", named, "stray")
                elif action == "copy" and waiting:
                    original = self.tokens[rng.choice(waiting)]
                    self.push(fork, original["task"], "stray", original["deal"], copy_of=[t for t, c in self.tokens.items() if c is original][0])

    def answered(self):
        return {e["sha"] for e in self.w.events() if e["type"] == "verdict"}

    def unreadable(self, fork):
        real = hive.git

        def git(repo, *args, **options):
            if args[:2] == ("ls-remote", "--heads") and str(fork.bare) in args:
                return subprocess.CompletedProcess(args, 128, "", "fatal: unable to access")
            return real(repo, *args, **options)
        return mock.patch.object(hive, "git", side_effect=git)

    def promptly_dealt(self, before):
        """R1, second half, after a run in which nothing broke: an honest worker that was asking, held nothing, was
        not waiting and had deals left today, while tasks were plenty, now holds a task."""
        config, _, ledger = self.w.load()
        plenty = before is None or sum(1 for t in before["tasks"] if t["status"] == "open") >= len(self.honest) + 2 * len(self.others)
        held = {d["member_id"] for d in ledger.deals().values() if d["state"] == "live"}
        for fork in self.honest:
            asked = th.sh("git", "ls-remote", str(fork.bare), "refs/heads/hive/ready", cwd=self.w.root).stdout.strip()
            deal, wait = hive.my_deal(before, fork.login) if before else (None, None)
            _, _, today = ledger.standing(fork.id, hive.parse_iso(self.now()), config)
            if plenty and asked and deal is None and not wait and today < config["members"]["deals_per_day"]:
                self.slow.append((self.hour, fork.login)) if fork.id not in held else None

    # -- one run of the hive, with what may go wrong in it ---------------------------------------------------------
    def one_run(self, quiet=False):
        rng, self.run, self.elapsed = self.rng, self.hour, 0.0
        fault = "none" if quiet else rng.choice(["none"] * 5 + ["down", "lost", "unconfirmed", "killed", "withdrawn", "late", "norecord",
                                                                "stale", "unread"])
        self.down = fault == "down"
        real_merge, real_push, before = hive.merge_tree, hive.guarded_push, feed_of(self.w)

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
                if fault == "stale":  # a plan made now, used after another run went through
                    stale = self.w.plan()
                if fault == "unread":
                    with self.unreadable(rng.choice(self.honest + self.others)):
                        self.w.plan()
                else:
                    self.w.plan()
                if fault != "norecord":
                    self.w.record()
                pushed = [c for c in self.tokens.values() if c["kind"] not in ("honest", "late")]
                if fault == "withdrawn" and pushed:  # an honest member leaves its branch where it is
                    gone = rng.choice(pushed)
                    th.sh("git", "push", "--quiet", "origin", f":refs/heads/{gone['branch']}", cwd=gone["fork"].work, check=False)
                if fault == "late":
                    other = rng.choice(self.others)
                    self.push(other, rng.choice(TASKS)["id"], "stray", False, "REFUSE late")
                verdicts, _ = self.w.judge(self.judge)
            completed = True
            with mock.patch.dict(os.environ, {"HIVE_NOW": self.now(self.elapsed / 60)}):
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
                if fault == "stale":
                    current, self.w.made = self.w.made, stale
                    try:
                        self.w.record()  # refused, unless the run in between wrote nothing to the ledger
                    except hive.HiveError:
                        pass
                    self.w.made = current
        if completed and fault != "lost":
            self.recorded_runs.add(self.run)
        if fault in ("unconfirmed", "killed", "lost", "down"):
            self.faulty.add(self.run)  # a judgement lost to the hive's own breakdown is not the candidate's doing
        if fault == "none":
            self.promptly_dealt(before)
        self.tips.append(self.w.tip())
        self.hour += 1

    # -- what must hold at the end ----------------------------------------------------------------------------------
    def check(self):
        t, events, everything = self.test, self.w.events(), self.w.load()[2].events
        for line in (self.w.state / "ledger.jsonl").read_text().splitlines():
            json.loads(line, parse_constant=lambda name: t.fail(f"{name} in the ledger"))
        accepted = {e["sha"]: e for e in events if e["type"] == "verdict" and e["result"] == "accepted"}
        dealt = {(e["task"], e["member"], e["at"]) for e in everything if e["type"] == "deal"}
        by_sha = {c["sha"]: (token, c) for token, c in self.tokens.items()}
        for token, c in self.tokens.items():
            history = [(e["type"], e.get("kind") or e.get("reason") or e.get("result"), e["at"][5:16]) for e in everything
                       if e.get("sha") == c["sha"]]
            if c["kind"] == "honest":  # R1
                t.assertTrue(c["sha"] in accepted, f"R1: honest candidate {token} ({c['login']}, {c['task']}, pushed before run "
                                                   f"{c['at']}) was never integrated; its lines: {history}")
            if c["kind"] == "stray":  # R2
                t.assertEqual(history, [], f"R2: {token}, pushed by {c['login']} for a task it does not hold, left a line")
                t.assertNotIn(token, self.calls, f"R2: {token} was judged")
        for sha, verdict in accepted.items():  # R2
            t.assertIn((verdict["task"], verdict["member"], verdict["deal"]), dealt, "R2: credit without a deal")
            t.assertEqual(by_sha[sha][1]["login"], verdict["member"], "R2: credit to another account than the one that pushed")
        t.assertEqual(self.slow, [], "R1: honest workers that asked, in a run where nothing broke and tasks were plenty, and got none")
        for token, runs in self.calls.items():  # R3
            sha = self.tokens[token]["sha"] if token in self.tokens else None
            counted = [r for r in runs if r in self.recorded_runs]
            lines = [e for e in everything if e.get("sha") == sha and (
                e["type"] in ("error", "unused", "intent") or (e["type"] == "verdict" and e.get("judged") and e["result"] == "refused"))]
            t.assertLessEqual(len(counted), len(lines), f"R3: {token} ({self.tokens[token]['kind']}) was judged in runs {counted} "
                                                        f"and the ledger has {len(lines)} line(s) for it")
        tasks = [e["task"] for e in accepted.values()]  # R4
        t.assertEqual(len(tasks), len(set(tasks)), "R4: a task integrated twice")
        for before, after in zip(self.tips, self.tips[1:]):
            moved = th.sh("git", "merge-base", "--is-ancestor", before, after, cwd=self.w.upstream, check=False).returncode
            t.assertEqual(moved, 0, "R4: the project's branch went back")
        t.assertNotIn("AKIA", th.sh("git", "log", "-p", "main", cwd=self.w.upstream).stdout)
        replay(t, everything, hive.DEFAULTS["members"]["deals_per_day"])
        for sha, (token, c) in by_sha.items():  # R5
            judged = len([run for run in self.calls.get(token, []) if run in self.recorded_runs and run not in self.faulty])
            story = [(e["type"], e.get("kind") or e.get("reason") or e.get("result"), e.get("unproven"), e["at"][8:13])
                     for e in everything if e.get("sha") == sha]
            t.assertLessEqual(judged, 6, f"{token} ({c['kind']}, {c['login']}) was judged {judged} times in runs where nothing of the "
                                         f"hive's broke, in runs {self.calls.get(token)}: {story}")
        mine = {login: sum(1 for e in accepted.values() if e["member"] == login) for login in (f.login for f in self.honest)}
        t.assertGreaterEqual(sum(mine.values()), POOL - 2 * len(self.others), f"R5: the honest workers integrated {mine}")


class TestSchedule(unittest.TestCase):
    def test_what_holds_over_many_runs(self):
        for seed in (int(s) for s in os.environ.get("HIVE_SEEDS", "1 2 3 4").split()):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as root:
                drawn = iter(range(10 ** 6))
                keys = mock.patch.object(hive.secrets, "token_hex",
                                         side_effect=lambda size: hashlib.sha256(f"{seed}:{next(drawn)}".encode()).hexdigest()[:2 * size])
                with keys, mock.patch.dict(os.environ, th.GIT_ENV):
                    schedule = Schedule(self, seed, root)
                    for _ in range(12):
                        schedule.members_act()
                        schedule.one_run()
                    for _ in range(int(os.environ.get("HIVE_QUIET", "10"))):  # then runs in which nothing of the hive's breaks
                        schedule.members_act()
                        schedule.one_run(quiet=True)
                    for _ in range(2):  # the others stop; the honest workers finish
                        schedule.members_act(others=False)
                        schedule.one_run(quiet=True)
                    for _ in range(4):  # and runs in which nobody pushes anything more
                        schedule.one_run(quiet=True)
                    schedule.check()


def at(hours, minutes=0):
    return hive.iso(START.replace(hour=0) + dt.timedelta(hours=hours, minutes=minutes))


class Sim:
    """A world driven run by run: deals and pushes at chosen instants, a judge on a clock of its own (TIMEOUT costs
    an hour)."""

    def __init__(self, root, hook=False):
        self.w = pool_world(root, hook)
        self.elapsed, self.count, self.calls = 0.0, 0, {}

    def judge(self, base, candidate, task, tip, commit):
        path = candidate / task["files"][0]
        text = path.read_text() if path.exists() else ""
        token = text.split("id:")[1].split()[0] if "id:" in text else None
        if tip != commit and token:
            self.calls[token] = self.calls.get(token, 0) + 1
        self.elapsed += 3600 if "TIMEOUT" in text else 60
        return {"code": 2 if "TIMEOUT" in text else 1 if "REFUSE" in text else 0, "report": {"gain": 0.0, "outputs_compared": 12}}

    def push(self, fork, task, token, body, deal=None):
        """A candidate of `fork` for `task`; by default for a deal the hive made to it an hour or so before."""
        self.count += 1
        sha = fork.fresh(f"b{self.count}").write(f"pool/p{int(task[-4:]):02d}.c", f"int v; /* id:{token} {body} */\n") \
            .commit(f"work {token}").marker(task, deal=deal).push()
        return sha, fork.branch

    def run(self, when, lost=False, applies=1):
        self.elapsed = 0.0
        with mock.patch.object(hive.time, "monotonic", side_effect=lambda: self.elapsed), mock.patch.dict(os.environ, {"HIVE_NOW": when}):
            self.w.plan()
            self.w.record()
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
    """Schedules built on purpose against one member's work, with what must come out of them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        drawn = iter(range(10 ** 6))
        for patch in (mock.patch.dict(os.environ, {**th.GIT_ENV, "HIVE_NOW": at(12)}),
                      mock.patch.object(hive.secrets, "token_hex",
                                        side_effect=lambda size: hashlib.sha256(f"t:{next(drawn)}".encode()).hexdigest()[:2 * size])):
            patch.start()
            self.addCleanup(patch.stop)

    def test_candidates_that_never_end_cost_a_candidate_behind_them_one_run_and_no_mark(self):
        """Three accounts, dealt their tasks before the victim, each send a candidate that never ends: the time
        allowed for judging is used up before the victim's turn. It is not marked for it, and it goes first at the
        next run, because a candidate a run failed on goes after the others."""
        s = Sim(self.tmp.name)
        for i in range(3):
            s.push(s.w.fork(f"atk{i}", 601 + i), f"pool-{1 + i:04d}", f"x{i}", "TIMEOUT")
        honest, _ = s.push(s.w.fork("victim", 101), "pool-0000", "V", "honest")
        for hour in (13, 14, 15):
            s.run(at(hour))
            if honest in s.accepted():
                break
        self.assertEqual(s.accepted().get(honest), "victim", s.lines(honest))
        self.assertLessEqual(hour, 14, "within two runs")
        self.assertEqual([kind for kind, _ in s.lines(honest) if kind == "error"], [], "never marked for the others' time")

    def test_candidates_the_project_declines_cost_the_others_one_run_per_account(self):
        s = Sim(self.tmp.name, hook=True)
        victim = s.w.fork("victim", 101)
        first, _ = s.push(victim, "pool-0013", "W", "honest")
        s.run(at(13))  # the hive has pushed to this project before
        self.assertEqual(s.accepted().get(first), "victim")
        declined = [s.push(s.w.fork(f"atk{i}", 601 + i), f"pool-{1 + i:04d}", f"k{i}", 'key "AKIAABCDEFGHIJKLMNOP"')[0] for i in range(2)]
        honest, _ = s.push(victim, "pool-0000", "V", "honest")
        runs = 0
        while honest not in s.accepted() and runs < 12:
            runs += 1
            s.run(at(13 + runs))
        self.assertEqual(s.accepted().get(honest), "victim", s.lines(honest))
        self.assertLessEqual((runs, s.calls["V"]), (3, 3), "one run for each account whose candidate the project declines")
        for _ in range(2 * hive.UNANSWERED_RUNS):
            runs += 1
            s.run(at(13 + runs))
        self.assertEqual([s.lines(sha)[-1] for sha in declined], [("verdict", "not_answered")] * 2,
                         "and each of those ends in an answer: declined when no other push of the run had landed, it proves nothing "
                         "against its member, and is given up after six runs")
        self.assertNotIn("AKIA", th.sh("git", "log", "-p", "main", cwd=s.w.upstream).stdout)

    def test_a_write_step_run_again_marks_nobody_twice(self):
        s = Sim(self.tmp.name)
        honest, _ = s.push(s.w.fork("victim", 101), "pool-0000", "V", "honest")
        slow, _ = s.push(s.w.fork("other", 102), "pool-0001", "T", "TIMEOUT")
        for hour in (13, 14, 15, 16):
            s.run(at(hour), applies=3)
        self.assertEqual(s.accepted().get(honest), "victim")
        self.assertEqual(s.lines(slow), [("error", "judge")] * 3 + [("verdict", "judge_failed")],
                         "three runs, three failures, however often each write step ran")
        self.assertEqual(len(s.lines(honest)), 2, "one promise and one verdict")

    def test_accounts_that_take_tasks_and_leave_them_hold_little_and_stop_nobody(self):
        """Three accounts ask at every run and never do anything; one honest worker does what `hive next` says. Each
        idle account holds one task at a time, for four hours, then waits two hours, four, eight: the honest worker
        gets a task at every run and all its work is integrated."""
        s = Sim(self.tmp.name)
        idle, victim, pushed, done = [s.w.fork(f"idle{i}", 601 + i) for i in range(3)], s.w.fork("victim", 101), [], set()
        for hour in range(12, 30):
            with mock.patch.dict(os.environ, {"HIVE_NOW": at(hour, -10)}):
                feed = feed_of(s.w)
                for fork in idle:
                    fork.ready()
                deal, wait = hive.my_deal(feed, "victim") if feed else (None, None)
                self.assertIsNone(wait, "the honest worker is never made to wait")
                if deal and not deal["candidate"] and deal["at"] not in done:
                    done.add(deal["at"])
                    pushed.append(s.push(victim, deal["task"], f"V{hour}", "honest", deal["at"])[0])
                victim.ready()
            s.run(at(hour))
        events = s.w.load()[2].events
        replay(self, events, hive.DEFAULTS["members"]["deals_per_day"])
        deals = {login: [e["at"][8:13] for e in events if e["type"] == "deal" and e["member"] == login] for login in ("idle0", "idle1", "idle2")}
        for login, given in deals.items():
            self.assertLessEqual(len(given), 3, f"{login} was dealt at {given}: two hours of wait, then four, then eight")
        accepted = s.accepted()
        self.assertEqual([sha for sha in pushed[:-1] if sha not in accepted], [], "every candidate but the last one pushed is integrated")
        self.assertGreaterEqual(len(accepted), POOL - 3, f"the pool is done but what the idle accounts hold: {len(accepted)} of {POOL}")
        self.assertTrue(all(member == "victim" for member in accepted.values()))


if __name__ == "__main__":
    unittest.main()
