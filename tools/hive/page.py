#!/usr/bin/env python3
"""The public page of one hive project, made from its state folder (docs/protocol.md, "The ledger and the feed").

    python3 tools/hive/page.py --state <state folder of one project> --out <folder>
                               [--title "..."] [--repo-url https://github.com/owner/name]
                               [--tasks <the registry's hive/tasks/<project>.jsonl>]
                               [--join | --join-url https://github.com/...] [--now 2026-11-13T00:00:00Z]

It reads ledger.jsonl, feed.json and stats.json and writes static files that a GitHub Pages site or a README can
show. The hive deals each open task to one member at a time; the page shows how the tasks stand, what the judge
accepted, and how many dealt candidates wait for the judge (from the feed's deals):

  index.html              one page: progress, this week, members, models, integrations, refusals, measures
  members/<id>.svg        a card for each member with at least one integration, named by the account's numeric id
  wins/<commit>.svg       a card for each of the latest integrations, named by the integrated commit's 40-hex id: the
                          task, the member, the date and one figure the judge measured: the one the task asked for
                          when --tasks says which and the report holds it, else the largest gain beyond the noise
  badge.svg               the project's badge
  summary.json            the same figures, for other tools

Trust: the ledger holds strings that strangers chose (logins, model identifiers), within patterns the hive checks.
This file trusts none of that. Every value read is checked again against its pattern, and dropped or replaced when
it does not match; everything placed in HTML or SVG goes through one builder that escapes it; a link is built from
a checked login or a 40-hex commit id and from nothing else; a file's name is one of three constants or an integer.
The page has no script, loads nothing, and names a member only for work the judge accepted.

Standard library only. The figures come from the ledger; stats.json is only compared with them.
"""

import argparse
import datetime as dt
import html
import json
import math
import os
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hive  # noqa: E402  (REASONS, now, safe_text: the hive's own words and clock)

# The patterns, written again here on purpose: this file does not rely on what wrote the ledger.
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
TASK_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{4}\Z")
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}\Z")
MARK = re.compile(r"[0-9a-f]{16}\Z")  # a hash of a login, in the feed's deals; never shown
SHA = re.compile(r"[0-9a-f]{40}\Z")
ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
PROJECT = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
REPO_URL = re.compile(r"https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9._-]{1,100}\Z")
JOIN_URL = re.compile(r"https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:/[A-Za-z0-9._-]{1,100}){1,12}\Z")
CARD_NAME = re.compile(r"members/[1-9][0-9]{0,18}\.svg\Z")
BADGE_NAME = re.compile(r"members/[1-9][0-9]{0,18}-badge\.svg\Z")
WIN_NAME = re.compile(r"wins/[0-9a-f]{40}\.svg\Z")
METRIC = re.compile(r"[A-Za-z0-9_]{1,60}\Z")  # the <name> of a report's gain_<name> and sure_<name>
FIXED_NAMES = ("index.html", "badge.svg", "summary.json")
NAMES = (CARD_NAME, BADGE_NAME, WIN_NAME)  # with FIXED_NAMES, every name this tool writes a file under
DEFAULT_JOIN_URL = "https://github.com/Bee-ruche/registre/blob/main/docs/join.md"
ID_MAX = 2 ** 63 - 1  # an account's numeric id: a whole number in this range, never a string
TASK_ID_MAX, PROJECT_MAX, LINE_MAX = 64, 40, 1_000_000
STATUSES = ("done", "dealt", "open", "closed")  # the bar's order
STATUS_WORDS = {"done": "done", "dealt": "being worked on", "open": "open", "closed": "closed"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEK = dt.timedelta(days=7)
YEARS = (2000, 2999)  # an instant outside these years is not one
MEMBERS_SHOWN, MODELS_SHOWN, RECENT_SHOWN = 50, 30, 30  # rows of index.html's tables; the cards are not capped (render())
GAIN_MAX = 10  # a gain is a fraction: 10 is 1000 %, and nothing above is shown
MEASURES_MAX = 40  # rows of « what the judge measured » kept for one integration
COUNT_MAX = 10 ** 16 - 1  # a count in a report (outputs compared, files, lines): sixteen digits, as the hive reads them


class PageError(Exception):
    """The page cannot be made (an argument, an unreadable ledger): nothing is written."""


# ---------------------------------------------------------------------------------------------------------------
# Checking what is read


def account_id(value):
    """An account's numeric id, or None. A whole number in range and nothing else: not a string of digits, not a
    float, not a boolean. It is the only thing a card's file name is ever made of."""
    return value if type(value) is int and 0 < value <= ID_MAX else None


def matching(value, pattern, longest=None):
    """The string, if it is one and matches its pattern whole; else None."""
    if isinstance(value, str) and (longest is None or len(value) <= longest) and pattern.match(value):
        return value
    return None


def instant_of(value):
    """The instant an event carries, or None. The pattern alone lets a thirteenth month through, and a year that
    no ledger will ever hold (the year 1, the year 9999) breaks the arithmetic on dates and how they are printed."""
    if not matching(value, ISO):
        return None
    try:
        instant = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return instant if YEARS[0] <= instant.year <= YEARS[1] else None


def iso(instant):
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def plain(value, limit):
    """A line of text from a trusted file or from the command line, made fit to print: no control, format, surrogate
    or unassigned character (some cannot be written at all, some reorder what is shown), one line, bounded."""
    if not isinstance(value, str):
        return ""
    kept = "".join(" " if c.isspace() else c for c in value if c.isspace() or unicodedata.category(c)[0] != "C")
    text = " ".join(kept.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def headline(report):
    """{"metric": name, "gain": fraction} from a verdict's report, or None. Among the keys gain_<name> whose value is
    a number (not a boolean, not a string) above zero and at most GAIN_MAX, and whose sibling sure_<name> is the number
    1, the largest gain wins (a tie goes to the first name in alphabetical order). A gain that would show as 0.0 %
    is no figure. Nothing is computed from a string; <name> must be an identifier."""
    if not isinstance(report, dict):
        return None
    best = None
    for key, value in report.items():
        if not isinstance(key, str) or not key.startswith("gain_") or not matching(key[5:], METRIC):
            continue
        sure = report.get("sure_" + key[5:])
        if type(value) not in (int, float) or type(sure) not in (int, float) or sure != 1:
            continue
        if type(value) is float and not math.isfinite(value):
            continue
        if not 0 < value <= GAIN_MAX:
            continue
        gain = round(float(value), 6)
        if round(100 * gain, 1) <= 0:
            continue
        if best is None or gain > best[1] or (gain == best[1] and key[5:] < best[0]):
            best = (key[5:], gain)
    return None if best is None else {"metric": best[0], "gain": best[1]}


def shows(gain):
    """True for a gain that is one and would not print as 0.0 %: above zero, at most GAIN_MAX."""
    return 0 < gain <= GAIN_MAX and round(100 * gain, 1) > 0


def whole(value):
    """A count: a whole number from 0 to COUNT_MAX, never a boolean, a float or a string of digits; else None."""
    return value if type(value) is int and 0 <= value <= COUNT_MAX else None


def flag(value):
    """A report's yes or no: 1 or 0 when the value is that number (not a boolean, not a string), else None."""
    return int(value) if type(value) in (int, float) and value in (0, 1) else None


def read_report(report, goal=None):
    """What the page keeps of an accepted verdict's report; every value is a number checked here, every name an
    identifier, and nothing else of the report goes further.

      headline   headline(report): the largest gain whose sure_ flag is 1
      measures   a row {"metric", "gain", "sure", "worse", "goal"} for each gain_<metric> that is a finite number
                 between -GAIN_MAX and GAIN_MAX; sure and worse are the report's sure_<metric> and worse_<metric>
                 (1, 0, or None when the report has no such number); goal marks the task's own figure. The goal's row
                 comes first, then the rows beyond the noise, then the others; at most MEASURES_MAX are kept
      figure     the figure a card leads with, {"metric", "gain", "goal"}: the task's own (`goal`, the <metric> its
                 goal names) when the report holds it, it shows above 0.0 %, it is not marked worse, and its sure_
                 flag is 1 or the report keeps none for it (a project lists the flags it keeps: miniz keeps none for
                 its instruction counts); otherwise the headline, with goal False; None when there is neither
      outputs    outputs_compared when it is a whole number above zero; suspects, when it is a whole number
    """
    report = report if isinstance(report, dict) else {}
    best, rows = headline(report), []
    for key, value in report.items():
        if not isinstance(key, str) or not key.startswith("gain_") or not matching(key[5:], METRIC):
            continue
        if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or not -GAIN_MAX <= value <= GAIN_MAX:
            continue
        rows.append({"metric": key[5:], "gain": round(float(value), 6), "sure": flag(report.get("sure_" + key[5:])),
                     "worse": flag(report.get("worse_" + key[5:])), "goal": goal is not None and key[5:] == goal})
    rows.sort(key=lambda row: (not row["goal"], row["sure"] != 1 and row["worse"] != 1, -row["gain"], row["metric"]))
    asked = rows[0] if rows and rows[0]["goal"] else None
    if asked is not None and shows(asked["gain"]) and asked["worse"] != 1 and (asked["sure"] == 1 or "sure_" + asked["metric"] not in report):
        figure = {"metric": asked["metric"], "gain": asked["gain"], "goal": True}
    else:
        figure = None if best is None else {**best, "goal": False}
    return {"headline": best, "figure": figure, "measures": rows[:MEASURES_MAX], "measures_left_out": max(0, len(rows) - MEASURES_MAX),
            "outputs": whole(report.get("outputs_compared")) or None, "suspects": whole(report.get("suspects"))}


def read_changed(figures):
    """{"files": n, "lines": n} from a verdict's figures (what the hive counted of the change), or None."""
    if not isinstance(figures, dict) or whole(figures.get("files")) is None or whole(figures.get("lines")) is None:
        return None
    return {"files": figures["files"], "lines": figures["lines"]}


def goal_metric(task):
    """The <metric> of the figure gain_<metric> that a task's goal asks for, or None: a goal of another kind (« correct »,
    the default), on a figure that is not a gain, or under a name that is not an identifier gives no figure to lead with."""
    goal = task.get("goal")
    name = goal.get("name") if isinstance(goal, dict) and isinstance(goal.get("kind"), str) and goal["kind"] == "metric" else None
    return matching(name[5:], METRIC) if isinstance(name, str) and name.startswith("gain_") else None


def read_goals(path):
    """{task id: metric} from the registry's task file of the project (hive/tasks/<project>.jsonl), for the tasks
    whose goal is a gain (goal_metric). It is the hive's own file, trusted as the feed is, and read with the same care:
    a line that is not a task says nothing, a task listed twice is read once, and only an identifier is kept of it.
    The feed does not carry a task's goal; without this file a card leads with headline()'s figure. Raises PageError
    when the file cannot be read at all: it was named on the command line."""
    goals, seen = {}, set()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    task = json.loads(line) if line.strip() and len(line) <= LINE_MAX else None
                except (ValueError, RecursionError):
                    task = None
                identifier = matching(task.get("id"), TASK_ID, TASK_ID_MAX) if isinstance(task, dict) else None
                if identifier is None or identifier in seen:
                    continue
                seen.add(identifier)
                metric = goal_metric(task)
                if metric is not None:
                    goals[identifier] = metric
    except OSError:
        raise PageError("--tasks: the project's task file in the registry (hive/tasks/<project>.jsonl)") from None
    return goals


def read_json(folder, name):
    """A state file's content, or None when it is absent or unreadable: the page says less, and is still made."""
    try:
        with open(Path(folder) / name, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RecursionError):
        print(hive.safe_text(f"page: {name} is unreadable and is left out"), file=sys.stderr)
        return None


def read_ledger(folder):
    """(the ledger's lines that are JSON objects, in order; how many lines were left out). Unlike the hive, the
    page goes on when a line is broken: it shows what it can read, and says how many lines it could not."""
    path, objects, skipped = Path(folder) / "ledger.jsonl", [], 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line) if len(line) <= LINE_MAX else None
                except (ValueError, RecursionError):
                    value = None
                if isinstance(value, dict):
                    objects.append(value)
                else:
                    skipped += 1
    except FileNotFoundError:
        return [], 0
    except OSError:
        raise PageError("the ledger cannot be read") from None
    return objects, skipped


def clean_event(raw, goals=None):
    """One ledger line as the page uses it, every field checked again, or None if the line says nothing usable.
    A field that does not match its pattern becomes None (shown as « unknown », never linked). `goals` is
    read_goals()'s: the figure each task asked for, when the page was told."""
    kind, at = raw.get("type"), instant_of(raw.get("at"))
    if not isinstance(kind, str) or at is None:
        return None
    event = {"type": kind, "at": at, "member_id": account_id(raw.get("member_id")), "login": matching(raw.get("member"), LOGIN)}
    if kind == "error":
        event["judge"] = raw.get("kind", "judge") == "judge"  # as the hive reads it: no kind means the judge failed
    elif kind == "verdict":
        result = raw.get("result")
        if not isinstance(result, str) or result not in ("accepted", "refused"):
            return None
        reason, task = raw.get("reason"), matching(raw.get("task"), TASK_ID, TASK_ID_MAX)
        event.update(accepted=result == "accepted", judged=raw.get("judged") is True, task=task, model=matching(raw.get("model"), MODEL),
                     commit=matching(raw.get("commit"), SHA), headline=None,
                     reason=reason if isinstance(reason, str) and reason in hive.REASONS else None)
        if result == "accepted":
            event.update(read_report(raw.get("report"), (goals or {}).get(task)), changed=read_changed(raw.get("figures")))
    return event


def read_feed(folder):
    """(project id or None, {status: number of tasks} or None, {task id: title}) from feed.json. The titles come
    from the project's own task file (trusted); they are still cleaned here and escaped where they are shown."""
    feed = read_json(folder, "feed.json")
    if not isinstance(feed, dict):
        return None, None, {}
    project = matching(feed.get("project"), PROJECT, PROJECT_MAX)
    if not isinstance(feed.get("tasks"), list):
        return project, None, {}
    counts, titles = dict.fromkeys(STATUSES, 0), {}
    for task in feed["tasks"]:
        if not isinstance(task, dict):
            continue
        identifier, status = matching(task.get("id"), TASK_ID, TASK_ID_MAX), task.get("status")
        if identifier is None or identifier in titles or not isinstance(status, str) or status not in STATUSES:
            continue
        counts[status] += 1
        titles[identifier] = plain(task.get("title"), 100)
    return project, counts, titles


def read_waiting(folder, now):
    """{count, oldest_seconds} for the dealt candidates the judge has not answered yet (the feed's deals whose
    candidate is true; the age is measured from the deal's `at`), or None when there is none."""
    feed = read_json(folder, "feed.json")
    deals = feed.get("deals") if isinstance(feed, dict) else None
    if not isinstance(deals, dict):
        return None
    ages = []
    for mark, deal in deals.items():
        if not matching(mark, MARK) or not isinstance(deal, dict) or deal.get("candidate") is not True:
            continue
        since = instant_of(deal.get("at"))
        if since is not None and matching(deal.get("task"), TASK_ID, TASK_ID_MAX) and instant_of(deal.get("until")) is not None:
            ages.append(max(0, int((now - since).total_seconds())))
    return {"count": len(ages), "oldest_seconds": max(ages)} if ages else None


# ---------------------------------------------------------------------------------------------------------------
# The figures


def rate(part, whole):
    return round(part / whole, 4) if whole else None


def collect(state, now, tasks=None):
    """Everything the page shows, as plain data (it is also summary.json). Members are counted by account id and
    named by the login of their latest event; only members with an integration are named at all. `tasks` is the path
    of the registry's task file of the project, or None: it says which figure each task asked for (read_goals)."""
    goals = read_goals(tasks) if tasks is not None else {}
    objects, skipped = read_ledger(state)
    events = [event for event in (clean_event(raw, goals) for raw in objects) if event is not None]
    verdicts = [event for event in events if event["type"] == "verdict"]
    project, tasks, titles = read_feed(state)
    project = project or matching(Path(state).resolve().name, PROJECT, PROJECT_MAX)

    # Who is who: the login of an account's latest event; a login that a later event gives to another account is no
    # longer this one's (GitHub lets a freed login be taken), so it is not shown for it.
    latest, holder = {}, {}
    for position, event in enumerate(events):
        if event["member_id"] is not None and event["login"] is not None:
            latest[event["member_id"]] = event["login"]
            holder[event["login"].lower()] = (position, event["member_id"])

    def login_of(member_id):
        login = latest.get(member_id)
        return login if login is not None and holder[login.lower()][1] == member_id else None

    since = now - WEEK
    members, models, refusals, recent, firsts = {}, {}, {}, [], {}
    totals = dict.fromkeys(("verdicts", "judged", "accepted", "integrations", "refused", "judge_failures"), 0)
    week = {"integrations": 0, "judged": 0, "accepted": 0, "ids": set()}
    for position, event in enumerate(verdicts):
        accepted, judged, member_id = event["accepted"], event["judged"], event["member_id"]
        in_week = since < event["at"] <= now
        totals["verdicts"] += 1
        totals["judged"] += judged
        totals["accepted"] += accepted and judged
        totals["integrations"] += accepted
        totals["refused"] += not accepted
        if not accepted:
            refusals[event["reason"]] = refusals.get(event["reason"], 0) + 1
        if judged:
            row = models.setdefault(event["model"], {"judged": 0, "accepted": 0})
            row["judged"] += 1
            row["accepted"] += accepted
        if in_week:
            week["judged"] += judged
            week["accepted"] += accepted and judged
            week["integrations"] += accepted
            if accepted and member_id is not None:
                week["ids"].add(member_id)
        if member_id is not None:
            row = members.setdefault(member_id, {"integrations": 0, "judged": 0, "accepted": 0, "first": None, "last": None})
            row["judged"] += judged
            row["accepted"] += accepted and judged
            if accepted:
                row["integrations"] += 1
                row["first"] = min(row["first"] or event["at"], event["at"])
                row["last"] = max(row["last"] or event["at"], event["at"])
        if accepted:
            recent.append((event["at"], position, event))
            if member_id is not None and (member_id not in firsts or event["at"] < firsts[member_id]["at"]):
                firsts[member_id] = event  # the account's first integration: the earliest instant, then the ledger's order
    totals["judge_failures"] = sum(1 for event in events if event["type"] == "error" and event["judge"])

    named = sorted(((member_id, row) for member_id, row in members.items() if row["integrations"]),
                   key=lambda item: (-item[1]["integrations"], -item[1]["judged"], item[0]))
    recent.sort(key=lambda item: (item[0], item[1]), reverse=True)
    model_rows = sorted(models.items(), key=lambda item: (-item[1]["judged"], -item[1]["accepted"], item[0] or ""))
    integrations = totals["integrations"]

    def first(event):
        """True for the first integration of its account in this project, over the whole ledger (never for an
        account the ledger does not number)."""
        return firsts.get(event["member_id"]) is event

    wins, written = [], set()
    for at, _, event in recent:  # every integration, the latest first; a commit has one card, and its latest line speaks
        name = win_name(event["commit"])
        if name is None or name in written:
            continue
        written.add(name)
        wins.append({"commit": event["commit"], "at": iso(at), "task": event["task"], "title": titles.get(event["task"], ""),
                     "member_id": event["member_id"], "login": login_of(event["member_id"]), "model": event["model"],
                     "first": first(event), "judged": event["judged"], "changed": event["changed"],
                     **{key: event[key] for key in ("headline", "figure", "measures", "measures_left_out", "outputs", "suspects")}})
    data = {
        "protocol": hive.PROTOCOL,
        "project": project,
        "generated_at": iso(now),
        "tasks": None if tasks is None else {**tasks, "total": sum(tasks.values())},
        "totals": totals,
        "week": {"since": iso(since), "integrations": week["integrations"], "members": len(week["ids"]),
                 "judged": week["judged"], "accepted": week["accepted"], "acceptance_rate": rate(week["accepted"], week["judged"])},
        "members": [{"id": member_id, "login": login_of(member_id), "integrations": row["integrations"], "judged": row["judged"],
                     "accepted": row["accepted"], "acceptance_rate": rate(row["accepted"], row["judged"]),
                     "first_integration": iso(row["first"]), "last_integration": iso(row["last"])} for member_id, row in named],
        "members_without_integration": len(members) - len(named),
        "models": [{"model": model, "judged": row["judged"], "accepted": row["accepted"],
                    "acceptance_rate": rate(row["accepted"], row["judged"])} for model, row in model_rows],
        "recent": [{"at": iso(at), "task": event["task"], "title": titles.get(event["task"], ""), "member_id": event["member_id"],
                    "login": login_of(event["member_id"]), "commit": event["commit"], "headline": event["headline"],
                    "figure": event["figure"], "first": first(event),
                    "card": win_name(event["commit"])} for at, _, event in recent[:RECENT_SHOWN]],
        "refusals": [{"reason": reason, "count": count}
                     for reason, count in sorted(refusals.items(), key=lambda item: (-item[1], item[0] or "~"))],
        "measures": {
            "yield": rate(totals["accepted"], totals["judged"]),
            "time_to_answer_seconds": None,  # the ledger says when a candidate was answered, not when it was pushed
            "judge_runs_per_integration": round((totals["judged"] + totals["judge_failures"]) / integrations, 2) if integrations else None,
            "waiting": read_waiting(state, now),
        },
        "ledger": {"lines": len(objects) + skipped, "unreadable_lines": skipped, "events_left_out": len(objects) - len(events)},
    }
    data["stats_json"] = compare_stats(read_json(state, "stats.json"), models)
    data["_wins"] = wins  # for the cards; not part of summary.json
    return data


def win_name(commit):
    """wins/<commit>.svg for a 40-hex commit id, else None: a card exists only under a name made of nothing else."""
    name = f"wins/{commit}.svg" if isinstance(commit, str) else None
    return name if name is not None and WIN_NAME.match(name) else None


def compare_stats(stats, models):
    """« agrees », « differs » or « absent »: whether stats.json, which the hive writes from the same ledger, gives
    the models' figures this page counted. The page shows its own count either way; a difference is a stale file."""
    if not isinstance(stats, dict) or not isinstance(stats.get("models"), dict):
        return "absent"
    return "agrees" if stats["models"] == {model or "undeclared": row for model, row in models.items()} else "differs"


# ---------------------------------------------------------------------------------------------------------------
# One builder for HTML and SVG: whatever it is given is escaped, unless the builder made it itself


class Markup(str):
    """Text that is already safe in HTML and in SVG. Only el() and the constants of this file make one."""


class Link(str):
    """An address this file built itself: el() accepts no other value for href."""


TAGS = frozenset("html head meta title style body header main footer section div span p a h1 h2 table thead tbody tr th td "
                 "code strong svg rect path text".split())
VOID = frozenset(("meta",))
ATTRIBUTE = re.compile(r"[A-Za-z][A-Za-z0-9-]*\Z")
FORBIDDEN_ATTRIBUTES = frozenset(("style", "src", "srcdoc", "srcset", "action", "formaction", "data", "poster", "ping", "background"))


def escaped(value):
    """Any value as text that is safe between tags and inside a quoted attribute, in HTML and in XML: the five
    characters escaped, and no character that XML cannot hold or that cannot be written (controls, surrogates)."""
    return html.escape("".join(c for c in str(value) if c in "\n\t" or unicodedata.category(c)[0] != "C"), quote=True)


def el(name, /, *children, **attributes):
    """One element. Children that are not Markup are escaped; attribute values always are. No element that runs or
    loads anything can be made: the names are listed, « on… » attributes are refused, href takes a Link only, and a
    style holds one of this file's two constants (the pages' CSS, the cards' CARD_CSS) and nothing else."""
    if name not in TAGS:
        raise ValueError(f"element not allowed: {name}")
    if name == "style" and not (len(children) == 1 and not attributes and (children[0] is CSS or children[0] is CARD_CSS)):
        raise ValueError("a style is one of this file's two constants")
    written = []
    for key, value in attributes.items():
        if value is None:
            continue
        key = key.rstrip("_").replace("_", "-")
        if not ATTRIBUTE.match(key) or key.lower().startswith("on") or key.lower() in FORBIDDEN_ATTRIBUTES:
            raise ValueError(f"attribute not allowed: {key}")
        if key.lower() == "href" and not isinstance(value, Link):
            raise ValueError("href takes an address this file built")
        written.append(f' {key}="{escaped(value)}"')
    if name in VOID:
        return Markup(f"<{name}{''.join(written)} />")
    return Markup(f"<{name}{''.join(written)}>{inner(children)}</{name}>")


def inner(children):
    parts = []
    for child in children:
        if isinstance(child, (list, tuple)):
            parts.append(inner(child))
        elif child is not None:
            parts.append(child if isinstance(child, Markup) else escaped(child))
    return "".join(parts)


def member_link(login):
    """https://github.com/<login>, for a login that matches GitHub's pattern; None for anything else."""
    return Link("https://github.com/" + urllib.parse.quote(login, safe="", errors="replace")) if matching(login, LOGIN) else None


def commit_link(repo_url, commit):
    """<repository>/commit/<40 hex>, when the repository's address was given and checked; else None."""
    if matching(repo_url, REPO_URL) and matching(commit, SHA):
        return Link(f"{repo_url}/commit/{urllib.parse.quote(commit, safe='', errors='replace')}")
    return None


# ---------------------------------------------------------------------------------------------------------------
# The page

# Colours: the four parts of the bar are four hues in a fixed order, checked for both surfaces (light #fcfcfb, dark
# #1a1a19) for colour-blind and normal vision; two of them are faint on the light surface, which is why each part's
# number is written beside its swatch. Text never wears a data colour.
CSS = Markup("""
:root{color-scheme:light dark;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e1e0d9;--honey:#a86d00;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100}
@media (prefers-color-scheme:dark){:root{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--line:#2c2c2a;
--honey:#e9ab22;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main,header,footer{max-width:60rem;margin:0 auto;padding:0 1rem}
header{padding-top:2rem}
footer{padding:1.5rem 1rem 3rem;color:var(--ink2);font-size:.85rem}
.hive{margin:0;color:var(--ink2);font-size:.85rem;letter-spacing:.08em;text-transform:uppercase}
h1{margin:.1rem 0 .3rem;font-size:2rem;line-height:1.2;overflow-wrap:anywhere}
h2{margin:0 0 .8rem;font-size:1.15rem}
p{margin:.4rem 0}
.lead{margin:0;color:var(--ink2);font-size:1.05rem;overflow-wrap:anywhere}
.none{margin:1rem 0 0;padding:.7rem 1rem;border:1px solid var(--line);border-left:4px solid var(--honey);border-radius:6px;background:var(--surface)}
section{margin:1.5rem 0;padding:1.1rem 1.1rem 1.2rem;background:var(--surface);border:1px solid var(--line);border-radius:10px}
a{color:inherit;text-decoration:underline;text-decoration-color:var(--honey);text-decoration-thickness:2px;text-underline-offset:3px}
a:hover{text-decoration-color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:.9rem 1.2rem}
.label{color:var(--ink2);font-size:.85rem}
.value{font-size:1.7rem;font-weight:600;line-height:1.25}
.note{color:var(--ink2);font-size:.8rem}
.sw{display:inline-block;width:.65rem;height:.65rem;margin-right:.4rem;border-radius:2px}
.s1{fill:var(--s1);background:var(--s1)}.s2{fill:var(--s2);background:var(--s2)}
.s3{fill:var(--s3);background:var(--s3)}.s4{fill:var(--s4);background:var(--s4)}
.bar{display:block;width:100%;height:8px;margin:1rem 0 .2rem;border-radius:4px;overflow:hidden;background:var(--line)}
.gap{fill:var(--surface)}
.scroll{overflow-x:auto}
table{width:100%;min-width:27rem;border-collapse:collapse;font-size:.92rem}
th,td{padding:.4rem .7rem .4rem 0;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
thead th{color:var(--ink2);font-size:.8rem;font-weight:600;white-space:nowrap}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
tbody th{font-weight:600;white-space:nowrap}
td a,td code{white-space:nowrap}
.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.soft{color:var(--ink2);font-weight:400}
code{font:.88em ui-monospace,SFMono-Regular,Consolas,monospace}
.join{border-left:4px solid var(--honey)}
.go{display:inline-block;margin-top:.5rem;padding:.45rem .9rem;border:2px solid var(--honey);border-radius:6px;font-weight:600;text-decoration:none}
.go:hover{border-color:var(--ink)}
""")
CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"


def percent(value):
    return "n/a" if value is None else f"{100 * value:.0f} %"


def out_of(part, whole):
    return "n/a" if not whole else f"{100 * part / whole:.0f} % ({part} of {whole})"


def day(stamp):
    return stamp[:10]


def duration(seconds):
    hours = seconds // 3600
    return "under an hour" if hours < 1 else f"{hours} h" if hours < 48 else f"{hours // 24} d"


def tile(label, value, note=None, swatch=None):
    return el("div", el("div", swatch and el("span", class_=f"sw {swatch}"), label, class_="label"),
              el("div", value, class_="value"), note and el("div", note, class_="note"), class_="tile")


def table(head, rows):
    """A table; `head` is [(title, is a number)], and a row's first cell is its header."""
    def cell(position, content):
        css = "n" if head[position][1] else None
        return el("th", content, scope="row", class_=css) if position == 0 else el("td", content, class_=css)
    return el("div", el("table", el("thead", el("tr", [el("th", title, scope="col", class_="n" if number else None) for title, number in head])),
                        el("tbody", [el("tr", [cell(i, c) for i, c in enumerate(row)]) for row in rows])), class_="scroll")


def member_cell(login, member_id):
    """A member, linked to their GitHub profile when the login is a checked one; the account's number when the
    login is not known (or no longer theirs); « unknown » when the account itself is not."""
    link = member_link(login) if login is not None else None
    if link is not None:
        return el("a", login, href=link, rel="nofollow noopener")
    return el("span", "unknown" if member_id is None else f"account {member_id}", class_="soft")


def progress_bar(tasks):
    """One thin bar, split into the four states, with the same surface gap between touching parts."""
    total, parts, offset = tasks["total"], [], 0
    for position, status in enumerate(STATUSES, 1):
        count = tasks[status]
        if not count:
            continue
        parts.append(el("rect", el("title", f"{count} {STATUS_WORDS[status]}"), class_=f"s{position}",
                        x=f"{100 * offset / total:.3f}%", y="0", width=f"{100 * count / total:.3f}%", height="8"))
        if offset:  # drawn after the part, so that it shows: two pixels of surface between touching parts
            parts.append(el("rect", class_="gap", x=f"{100 * offset / total:.3f}%", y="0", width="2", height="8"))
        offset += count
    label = ", ".join(f"{tasks[status]} {STATUS_WORDS[status]}" for status in STATUSES)
    return el("svg", parts, class_="bar", role="img", aria_label=f"Tasks: {label}")


def render_html(data, title, repo_url, join):
    project = data["project"] or "A hive project"
    totals, week, measures, tasks = data["totals"], data["week"], data["measures"], data["tasks"]
    integrations = totals["integrations"]
    sections = []

    if tasks is None:
        progress = el("p", "The project's task list is not published yet.", class_="soft")
    else:
        progress = [el("div", [tile(STATUS_WORDS[status].capitalize(), tasks[status], swatch=f"s{position}")
                               for position, status in enumerate(STATUSES, 1)], class_="tiles"),
                    progress_bar(tasks) if tasks["total"] else None,
                    el("p", f"Tasks in all: {tasks['total']}. A task is done when the judge accepted a candidate for it.", class_="note")]
    sections.append(el("section", el("h2", "Progress"), progress))

    sections.append(el("section", el("h2", "This week"), el("div", [
        tile("Integrations", week["integrations"], "in the last 7 days"),
        tile("Members with an integration", week["members"]),
        tile("Candidates judged", week["judged"]),
        tile("Acceptance rate", percent(week["acceptance_rate"]), f"{week['accepted']} accepted of {week['judged']} judged"),
    ], class_="tiles")))

    if data["members"]:
        shown = data["members"][:MEMBERS_SHOWN]
        rows = [[member_cell(m["login"], m["id"]), m["integrations"], m["judged"], out_of(m["accepted"], m["judged"]),
                 day(m["last_integration"])] for m in shown]
        note = f"{len(data['members'])} members have an integration" + (f"; the first {len(shown)} are shown" if len(shown) < len(data["members"]) else "")
        members = [table([("Member", False), ("Integrations", True), ("Judged", True), ("Accepted", True), ("Last integration", True)], rows),
                   el("p", f"{note}. A member is a GitHub account, counted by its numeric id and shown under its latest login; "
                           "a name appears here only with work the judge accepted.", class_="note"),
                   el("p", "Every integration has its own card at wins/<commit>.svg, and every member here a card at members/<account id>.svg "
                           "and a badge at members/<account id>-badge.svg. A card that exists stays.", class_="note")]
    else:
        members = el("p", "No member has an integration yet.", class_="soft")
    sections.append(el("section", el("h2", "Members"), members))

    if data["models"]:
        shown, rest = data["models"][:MODELS_SHOWN], data["models"][MODELS_SHOWN:]
        rows = [[el("code", m["model"]) if m["model"] is not None else el("span", "undeclared", class_="soft"),
                 m["judged"], m["accepted"], percent(m["acceptance_rate"])] for m in shown]
        if rest:
            judged, accepted = sum(m["judged"] for m in rest), sum(m["accepted"] for m in rest)
            rows.append([el("span", f"{len(rest)} others", class_="soft"), judged, accepted, percent(rate(accepted, judged))])
        models = table([("Model", False), ("Judged", True), ("Accepted", True), ("Rate", True)], rows)
    else:
        models = el("p", "No candidate has been judged yet.", class_="soft")
    sections.append(el("section", el("h2", "Models"), models, el("p", "Declared by each worker: a statistic, not a proof.", class_="note")))

    if data["recent"]:
        rows = []
        for item in data["recent"]:
            task = [el("code", item["task"]), " ", el("span", item["title"], class_="soft")] if item["task"] else el("span", "unknown", class_="soft")
            link = commit_link(repo_url, item["commit"])
            short = el("code", item["commit"][:10]) if item["commit"] else el("span", "n/a", class_="soft")
            card = Link(item["card"]) if item["card"] is not None else None
            when = el("a", day(item["at"]), href=card) if card is not None else day(item["at"])
            rows.append([when, task, member_cell(item["login"], item["member_id"]),
                         el("a", short, href=link, rel="nofollow noopener") if link is not None else short])
        recent = [table([("Date", False), ("Task", False), ("Member", False), ("Commit", False)], rows),
                  el("p", "A date links to the integration's card: the task, the member and the largest gain the judge measured beyond the noise, if any.", class_="note")]
    else:
        recent = el("p", "Nothing has been integrated yet.", class_="soft")
    sections.append(el("section", el("h2", "Recent integrations"), recent))

    if data["refusals"]:
        rows = [[el("code", r["reason"]) if r["reason"] else el("span", "unknown", class_="soft"), r["count"],
                 hive.REASONS[r["reason"]] if r["reason"] else "a reason this page does not know"] for r in data["refusals"]]
        refusals = [table([("Reason", False), ("Candidates", True), ("What it means", False)], rows),
                    el("p", "Every refused candidate has its reason code in the ledger. A refusal says something about the candidate, "
                            "not about its member.", class_="note")]
    else:
        refusals = el("p", "No candidate has been refused yet.", class_="soft")
    sections.append(el("section", el("h2", "What was refused, and why"), refusals))

    waiting = measures["waiting"]
    runs = measures["judge_runs_per_integration"]
    sections.append(el("section", el("h2", "Three measures"), el("div", [
        tile("Yield", percent(measures["yield"]), f"{totals['accepted']} accepted of {totals['judged']} judged"),
        tile("Time to an answer", "n/a", "the ledger records when a candidate was answered, not when it was pushed"
             + (f"; {waiting['count']} waiting now, the oldest for {duration(waiting['oldest_seconds'])}" if waiting else "")),
        tile("Judge runs per integration", "n/a" if runs is None else f"{runs:.1f}",
             f"candidates judged: {totals['judged']}; runs the judge failed on: {totals['judge_failures']}; integrations: {integrations}"),
    ], class_="tiles")))

    sections.append(el("section", el("h2", "Give your AI's spare hours"),
                       el("p", "Point your own AI coding assistant at your own fork of this project. The hive deals it one task at a time; "
                               "it pushes the result to your fork and the judge decides. What it accepts is integrated as a commit authored by you."),
                       el("a", "How to join", href=join, class_="go"), class_="join"))

    left_out = data["ledger"]["unreadable_lines"] + data["ledger"]["events_left_out"]
    head = el("head", el("meta", charset="utf-8"), el("meta", name="viewport", content="width=device-width, initial-scale=1"),
              el("meta", http_equiv="Content-Security-Policy", content=CSP), el("meta", name="referrer", content="no-referrer"),
              el("title", f"{project} · La Ruche"), el("style", CSS))
    body = el("body",
              el("header", el("p", "La Ruche", class_="hive"), el("h1", project),
                 el("p", title or "A project of La Ruche: volunteers' AI assistants do the tasks, a judge decides what is integrated.", class_="lead"),
                 None if integrations else el("p", "Nothing has been integrated yet. The first contribution the judge accepts will appear here.", class_="none")),
              el("main", sections),
              el("footer", el("p", f"Made from the project's public ledger, as of {data['generated_at']}. No script, no tracker, nothing loaded from elsewhere."
                              + (f" Ledger lines that could not be read and are left out: {left_out}." if left_out else ""))))
    return "<!DOCTYPE html>\n" + el("html", head, body, lang="en") + "\n"


# ---------------------------------------------------------------------------------------------------------------
# The cards and the badges (SVG, fixed width, nothing loaded, no script)

SVG_NS = "http://www.w3.org/2000/svg"
SANS = "Verdana,Geneva,DejaVu Sans,sans-serif"  # the badges' font: one every reader has, so a forced length is safe there
TAGLINE = "Work by a volunteer's AI assistant, judged in a sandbox."  # what a stranger who meets a card must be told
CELLS = 18  # hexagons drawn on a member's card, one per integration; beyond, the number says the rest
WIDE, NARROW = frozenset("MWmw@%"), frozenset("iljtfrI1.,:;·'|() -")

# The one style of every card, and the only <style> an SVG of this tool holds (el() refuses any other): the page's own
# tokens, light then dark, so that ONE file reads on a light and on a dark page. The surface is opaque in both: a card
# stays readable when the host page's theme is not the reader's system theme. Contrast of the text on the surface:
# .i 19:1 and .j 7.8:1 in light, 15:1 and 9.6:1 in dark. It holds no address, no import and none of the characters
# that HTML and XML write differently: the same bytes stand in a card's file and in the page that shows the card. Its
# class names are single letters and the pages' are longer: neither restyles the other.
CARD_CSS = Markup(
    ".s{fill:#fcfcfb;stroke:#d9b56a}.i{fill:#0b0b0b}.j{fill:#52514e}.h{fill:#eda100}.e{fill:#b87900}.c{fill:#fcfcfb}"
    ".l{stroke:#bdb9a6;fill:none}.k{stroke:#a86d00;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}"
    ".b{font-weight:600}text{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}"
    ".m{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
    "@media (prefers-color-scheme:dark){.s{fill:#1a1a19;stroke:#6b5a2c}.i{fill:#f0efec}.j{fill:#c3c2b7}.h{fill:#e9ab22}"
    ".e{fill:#e9ab22}.c{fill:#1a1a19}.l{stroke:#55524a}.k{stroke:#e9ab22}}")


def width(text, size, bold=False, mono=False):
    """A cautious estimate of a line's width in pixels: the font is the reader's."""
    if mono:
        return len(text) * size * 0.62
    units = sum(1.05 if unicodedata.east_asian_width(c) in "WF" else 0.95 if c in WIDE else 0.36 if c in NARROW
                else 0.72 if c.isupper() else 0.62 for c in text)
    return units * size * (1.07 if bold else 1.0)


def wrap(text, size, room, lines, bold=False):
    """The text on at most `lines` lines of `room` pixels, cut between words where it can (a word wider than the room
    is broken where the room ends), and ended by « … » when there is more of it than the lines hold."""
    out, words = [], text.split()
    while words and len(out) < lines:
        current = words.pop(0)
        while words and width(f"{current} {words[0]}", size, bold) <= room:
            current += " " + words.pop(0)
        if len(current) > 1 and width(current, size, bold) > room:
            fit = len(current) - 1
            while fit > 1 and width(current[:fit], size, bold) > room:
                fit -= 1
            words.insert(0, current[fit:])
            current = current[:fit]
        out.append(current)
    if words:
        last = out[-1].rstrip("….,;: ")
        while last and width(last + "…", size, bold) > room:
            last = last[:-1]
        out[-1] = last + "…"
    return out


def line(content, x, y, size, look="i", room=None, bold=False, mono=False, end=False, floor=0.78, whole=False):
    """One line of a card. Too wide for its room by the estimate: a smaller size first (never under `floor` of the
    size asked), then cut and ended by « … », unless `whole` (a login is never cut: a cut one could be another
    account's). No forced length: textLength stretches a line as readily as it squeezes one, and both show."""
    if room is not None and width(content, size, bold, mono) > room:
        size = max(int(10 * size * floor) / 10, int(10 * size * room / width(content, size, bold, mono)) / 10)
        while not whole and len(content) > 1 and width(content, size, bold, mono) > room:
            content = content[:-2].rstrip() + "…"
    return el("text", content, class_=look + (" b" if bold else "") + (" m" if mono else ""), x=f"{x:g}", y=f"{y:g}",
              font_size=f"{size:g}", text_anchor="end" if end else None)


def hexagon(x, y, r, look="h", hollow=True):
    """The hive's mark: a hexagon of radius r centred on (x, y), with its hollow."""
    def ring(radius):
        dx = radius * 0.866
        return (f"M{x:g} {y - radius:g}L{x + dx:.1f} {y - radius / 2:g}V{y + radius / 2:g}L{x:g} {y + radius:g}"
                f"L{x - dx:.1f} {y + radius / 2:g}V{y - radius / 2:g}Z")
    return [el("path", class_=look, d=ring(r)), el("path", class_="c", d=ring(r * 0.55)) if hollow else None]


def card(wide, high, label, body, pad):
    """A card's frame. The content sits in a nested svg that ends at the right padding: whatever font the reader has,
    a line that the estimate got wrong is clipped there and never leaves the card. The label says, in whole words,
    everything the lines show (a line may be cut; the label is not)."""
    return el("svg", el("title", label), el("style", CARD_CSS),
              el("rect", class_="s", x="0.5", y="0.5", width=f"{wide - 1}", height=f"{high - 1}", rx="10"),
              el("svg", body, width=f"{wide - pad}", height=f"{high}"),
              xmlns=SVG_NS, width=f"{wide}", height=f"{high}", viewBox=f"0 0 {wide} {high}", role="img", aria_label=label)


def date(stamp):
    """« 21 Oct 2026 » for 2026-10-21T19:12:00Z (a stamp this file wrote itself: iso())."""
    return f"{int(stamp[8:10])} {MONTHS[int(stamp[5:7]) - 1]} {stamp[:4]}"


def gain_text(gain):
    """A fraction as a percentage with one decimal. A loss wears a real minus sign; what rounds to nothing is 0.0 %."""
    return f"{round(100 * gain, 1) or 0.0:.1f} %".replace("-", "−")


def better(metric):
    """What follows a lead figure: a gain is above zero when the judge found the candidate better, and nothing more
    is said than the figure's own name (an identifier of the project's judge)."""
    return "better · " + metric.replace("_", " ")


def head_of(project):
    return "La Ruche" + (f" · {plain(project, 24)}" if project else "")


def repo_name(repo_url):
    """owner/name out of a checked repository address; None for anything else."""
    return repo_url[len("https://github.com/"):] if matching(repo_url, REPO_URL) else None


def render_win(project, win, repo_url=None):
    """The card of one integration (wins/<commit>.svg): the figure the judge measured (read_report()'s lead figure),
    what was compared, the task, who, when, the commit, and one line that says what La Ruche is. Every value is a
    checked field or a constant of this file; the title is the task's, from the hive's feed."""
    wide, pad = 440, 24
    room, figure, tag, name = wide - 2 * pad, win["figure"], "accepted by the judge", plain(project, 24) if project else ""
    head = head_of(project)
    said = [head, tag]
    parts = [hexagon(pad + 10, 32, 11), line(head, pad + 28, 37, 14, room=room - 28 - width(tag, 12) - 32, bold=True),
             line(tag, wide - pad - 18, 37, 12, "j", end=True), el("path", class_="k", d=f"M{wide - pad - 13} 33l3.5 3.5 7.5-8.5")]
    if figure:
        what, y = better(figure["metric"]), 128
        parts += [line(gain_text(figure["gain"]), pad - 2, 102, 58, room=room, bold=True), line(what, pad, y, 15.5, room=room, bold=True)]
        said.append(f"measured {gain_text(figure['gain'])} {what}")
    else:
        y = 84
        parts.append(line("Accepted by the judge", pad, y, 26, room=room, bold=True))
    where = " · ".join(filter(None, [f"in {name}" if name else "", f"{win['outputs']:,} outputs identical to the base" if win["outputs"] else ""]))
    if where:
        y += 21
        parts.append(line(where, pad, y, 13, "j", room=room))
        said.append(where)
    if win["task"]:
        y += 29
        parts.append(line(win["task"], pad, y, 12, "j", room=room, mono=True))
        title = plain(win["title"], 100)
        for text in wrap(title, 13.5, room, 2):
            y += 19
            parts.append(line(text, pad, y, 13.5, room=room))
        said.append(f"{win['task']} · {title}" if title else win["task"])
    y += 18
    parts.append(el("path", class_="l", stroke_dasharray="2 4", d=f"M{pad} {y}H{wide - pad}"))
    when = ("first integration · " if win["first"] else "integrated ") + date(win["at"])
    y += 26
    # Who: the login, whole (it shrinks, and takes the line for itself when it is long). When the login is no longer
    # this account's, the account's number, which is what the ledger is sure of.
    who = "@" + win["login"] if win["login"] else f"GitHub account {win['member_id']}" if win["member_id"] else ""
    if who:
        alone = width(who, 15, True) > room - width(when, 12) - 16
        parts.append(line(who, pad, y, 15, room=room, bold=True, floor=0.55, whole=True))
        y += 19 if alone else 0
        parts.append(line(when, pad, y, 12, "j") if alone else line(when, wide - pad, y, 12, "j", end=True))
        said.append(who)
    else:
        parts.append(line(when, pad, y, 12, "j"))
    said.append(when)
    more = [(f"declared model: {win['model']}", False)] if win["model"] else []
    repo = repo_name(repo_url)  # the commit first: if the line must be cut, the repository's name is, not the commit's id
    more += [(f"commit {win['commit'][:10]}" + (f" · {repo}" if repo else ""), True), (TAGLINE, False)]
    for text, mono in more:
        y += 19
        parts.append(line(text, pad, y, 12, "j", room=room, mono=mono))
        said.append(text)
    return card(wide, y + 19, " · ".join(said), parts, pad)


def accepted_words(count):
    return ("contribution" if count == 1 else "contributions") + " accepted by the judge"


def render_card(project, member):
    """A member's card (members/<id>.svg): the number of contributions the judge accepted, the month of the first and
    the day of the latest, one hexagon per integration (CELLS at most are drawn; the number says the rest), and the
    account's number. It carries no login: the file is named by the account's id and stays right when the account is
    renamed. No rank, no streak, no rate."""
    wide, pad, count = 400, 22, member["integrations"]
    head, first = head_of(project), instant_of(member["first_integration"])
    since = f"first {MONTHS[first.month - 1]} {first.year} · latest {date(member['last_integration'])}"
    number, account = f"{count:,}", f"GitHub account {member['id']}"
    size = 44 if len(number) < 4 else 34 if len(number) < 6 else 26
    x = pad + width(number, size, True) + 12
    parts = [hexagon(pad + 10, 30, 11), line(head, pad + 28, 35, 14, room=wide - 2 * pad - 28 - width(account, 11.5) - 14, bold=True),
             line(account, wide - pad, 35, 11.5, "j", end=True),
             line(number, pad - 1, 86, size, bold=True), line(accepted_words(count), x, 68, 14, room=wide - pad - x, bold=True),
             line(since, x, 87, 12.5, "j", room=wide - pad - x)]
    shown = min(count, CELLS)
    parts += [hexagon(pad + 8 + i * 17, 112, 8, "e", hollow=False) for i in range(shown)]
    if count > shown:
        parts.append(line(f"+{count - shown:,}", pad + 8 + shown * 17, 116, 11.5, "j"))
    return card(wide, 132, f"{head} · {number} {accepted_words(count)} · {since} · {account}", parts, pad)


def badge(left, right):
    """A badge the size of a README's other badges, with the hive's mark. The badges' own way: fixed colours that read
    on any page (white on #33322f is 12.6:1, on #855600 6.3:1) and a forced length, in a font every reader has."""
    left_width, right_width = round(len(left) * 6.6) + 30, round(len(right) * 6.6) + 14
    total = left_width + right_width

    def part(text, start, room):
        return el("text", text, x=f"{start}", y="14", fill="#ffffff", font_family=SANS, font_size="11",
                  textLength=f"{room}", lengthAdjust="spacingAndGlyphs")
    return el("svg", el("title", f"{left}: {right}"),
              el("rect", width=f"{total}", height="20", rx="3", fill="#33322f"),
              el("path", d=f"M{left_width} 0H{total - 3}A3 3 0 0 1 {total} 3V17A3 3 0 0 1 {total - 3} 20H{left_width}Z", fill="#855600"),
              el("path", d="M12 4L17.2 7V13L12 16L6.8 13V7Z", fill="#eda100"),
              el("path", d="M12 7L14.6 8.5V11.5L12 13L9.4 11.5V8.5Z", fill="#33322f"),
              part(left, 23, left_width - 30), part(right, left_width + 7, right_width - 14),
              xmlns=SVG_NS, width=f"{total}", height="20", viewBox=f"0 0 {total} 20", role="img", aria_label=f"{left}: {right}")


def contributions(count):
    return f"{count} verified contribution" + ("" if count == 1 else "s")


def render_badge(count):
    """The project's badge (badge.svg)."""
    return badge("La Ruche", contributions(count))


def render_member_badge(project, member):
    """A member's badge (members/<id>-badge.svg): the member card's first fact, the size of the other badges. No login."""
    return badge(head_of(project), f"{member['integrations']:,} accepted by the judge")


# ---------------------------------------------------------------------------------------------------------------
# Files


def card_name(member_id):
    """members/<id>.svg. With badge_name(), the only file names that depend on a member: made from a whole number,
    never from a string."""
    if account_id(member_id) is None:
        raise ValueError("a card is named by an account's numeric id")
    return f"members/{member_id:d}.svg"


def badge_name(member_id):
    """members/<id>-badge.svg, from the same whole number as the card's name."""
    if account_id(member_id) is None:
        raise ValueError("a badge is named by an account's numeric id")
    return f"members/{member_id:d}-badge.svg"


def summary_json(data):
    """summary.json: plain ASCII, and no « < », « > » or « & » even inside a string, so that it stays harmless if a
    tool pastes it into a page."""
    data = {key: value for key, value in data.items() if key != "_wins"}
    text = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=True, allow_nan=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "\n"


def render(data, title="", repo_url=None, join=None):
    """{file name: text} for one project's page. The same data gives the same bytes.

    Every integration has its card and every member with an integration has a card and a badge, at every run: a card
    that someone embedded once is still there later, whatever came after it. Nothing is capped and nothing relies on
    what an earlier run left in the folder: each file is derived again from the whole ledger, so a card also follows
    what changed since (a login that passed to another account is no longer shown; a task's title is the feed's).
    The cost is linear: about 3.5 kB per integration and 3 kB per member."""
    files = {"index.html": render_html(data, title, repo_url, join or Link(DEFAULT_JOIN_URL)),
             "badge.svg": render_badge(data["totals"]["integrations"]) + "\n", "summary.json": summary_json(data)}
    for member in data["members"]:
        files[card_name(member["id"])] = render_card(data["project"], member) + "\n"
        files[badge_name(member["id"])] = render_member_badge(data["project"], member) + "\n"
    for win in data["_wins"]:
        name = win_name(win["commit"])
        if name is not None:
            files[name] = render_win(data["project"], win, repo_url) + "\n"
    return files


def write(out, files):
    """Writes each file whole or not at all, under `out` and nowhere else: a name is one of the three constants,
    members/<digits>.svg, members/<digits>-badge.svg or wins/<40 hex>.svg, whatever asked for it. Nothing is ever
    deleted: a file of an earlier run that this run does not write stays as it was."""
    out = Path(out)
    if any(name not in FIXED_NAMES and not any(pattern.match(name) for pattern in NAMES) for name in files):
        raise PageError("a file name this tool does not write")
    for name in sorted(files):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        with open(temporary, "w", encoding="utf-8", newline="\n") as f:
            f.write(files[name])
        os.replace(temporary, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description="The public page of one hive project, from its state folder.")
    parser.add_argument("--state", required=True, help="the project's folder of the state repository (ledger.jsonl, feed.json, stats.json)")
    parser.add_argument("--out", required=True, help="where index.html, badge.svg, summary.json, members/ and wins/ are written")
    parser.add_argument("--title", default="", help="one line saying what the project is, shown under its name")
    parser.add_argument("--repo-url", help="https://github.com/owner/name: integrations then link to their commit")
    parser.add_argument("--tasks", help="the project's task file in the registry (hive/tasks/<project>.jsonl): a card then leads with "
                                        "the figure its task asked for")
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--join", action="store_true", help="the join page is join.html, beside index.html")
    where.add_argument("--join-url", help=f"the join page's address on github.com (default: {DEFAULT_JOIN_URL})")
    parser.add_argument("--now", help="the instant the page is made for, as 2026-11-13T00:00:00Z (default: HIVE_NOW, or the clock)")
    args = parser.parse_args(argv)
    try:
        if args.repo_url is not None and (not REPO_URL.match(args.repo_url) or args.repo_url.rsplit("/", 1)[1] in (".", "..")):
            raise PageError("--repo-url: https://github.com/owner/name")
        if args.join_url is not None and (not JOIN_URL.match(args.join_url) or {".", ".."} & set(args.join_url.split("/"))):
            raise PageError("--join-url: an address under https://github.com/")
        try:
            now = instant_of(args.now) if args.now is not None else instant_of(iso(hive.now()))
        except ValueError:
            now = None
        if now is None:
            raise PageError("--now, or HIVE_NOW: an instant like 2026-11-13T00:00:00Z")
        if not Path(args.state).is_dir():
            raise PageError("--state: the folder of one project's state")
        join = Link("join.html") if args.join else Link(args.join_url or DEFAULT_JOIN_URL)
        files = render(collect(args.state, now, args.tasks), plain(args.title, 160), args.repo_url, join)
        write(args.out, files)
    except PageError as error:
        print(f"page: {hive.safe_text(error, 400)}", file=sys.stderr)
        sys.exit(2)
    print(f"{len(files)} file(s) written")


if __name__ == "__main__":
    main()
