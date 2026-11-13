#!/usr/bin/env python3
"""The public page of one hive project, made from its state folder (docs/protocol.md, "The ledger and the feed").

    python3 tools/hive/page.py --state <state folder of one project> --out <folder>
                               [--title "..."] [--repo-url https://github.com/owner/name]
                               [--join | --join-url https://github.com/...] [--now 2026-11-13T00:00:00Z]

It reads ledger.jsonl, feed.json and stats.json and writes static files that a GitHub Pages site or a README can
show. The hive deals each open task to one member at a time; the page shows how the tasks stand, what the judge
accepted, and how many dealt candidates wait for the judge (from the feed's deals):

  index.html              one page: progress, this week, members, models, integrations, refusals, measures
  members/<id>.svg        a card for each member with at least one integration, named by the account's numeric id
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
FIXED_NAMES = ("index.html", "badge.svg", "summary.json")
DEFAULT_JOIN_URL = "https://github.com/Bee-ruche/registre/blob/main/docs/join.md"
ID_MAX = 2 ** 63 - 1  # an account's numeric id: a whole number in this range, never a string
TASK_ID_MAX, PROJECT_MAX, LINE_MAX = 64, 40, 1_000_000
STATUSES = ("done", "dealt", "open", "closed")  # the bar's order
STATUS_WORDS = {"done": "done", "dealt": "being worked on", "open": "open", "closed": "closed"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEK = dt.timedelta(days=7)
YEARS = (2000, 2999)  # an instant outside these years is not one
MEMBERS_SHOWN, MODELS_SHOWN, RECENT_SHOWN = 50, 30, 30


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


def clean_event(raw):
    """One ledger line as the page uses it, every field checked again, or None if the line says nothing usable.
    A field that does not match its pattern becomes None (shown as « unknown », never linked)."""
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
        reason = raw.get("reason")
        event.update(accepted=result == "accepted", judged=raw.get("judged") is True,
                     task=matching(raw.get("task"), TASK_ID, TASK_ID_MAX), model=matching(raw.get("model"), MODEL),
                     commit=matching(raw.get("commit"), SHA),
                     reason=reason if isinstance(reason, str) and reason in hive.REASONS else None)
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


def collect(state, now):
    """Everything the page shows, as plain data (it is also summary.json). Members are counted by account id and
    named by the login of their latest event; only members with an integration are named at all."""
    objects, skipped = read_ledger(state)
    events = [event for event in map(clean_event, objects) if event is not None]
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
    members, models, refusals, recent = {}, {}, {}, []
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
    totals["judge_failures"] = sum(1 for event in events if event["type"] == "error" and event["judge"])

    named = sorted(((member_id, row) for member_id, row in members.items() if row["integrations"]),
                   key=lambda item: (-item[1]["integrations"], -item[1]["judged"], item[0]))
    recent.sort(key=lambda item: (item[0], item[1]), reverse=True)
    model_rows = sorted(models.items(), key=lambda item: (-item[1]["judged"], -item[1]["accepted"], item[0] or ""))
    integrations = totals["integrations"]
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
                    "login": login_of(event["member_id"]), "commit": event["commit"]} for at, _, event in recent[:RECENT_SHOWN]],
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
    return data


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
    loads anything can be made: the names are listed, « on… » attributes are refused, and href takes a Link only."""
    if name not in TAGS:
        raise ValueError(f"element not allowed: {name}")
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
                           "a name appears here only with work the judge accepted.", class_="note")]
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
            rows.append([day(item["at"]), task, member_cell(item["login"], item["member_id"]),
                         el("a", short, href=link, rel="nofollow noopener") if link is not None else short])
        recent = table([("Date", False), ("Task", False), ("Member", False), ("Commit", False)], rows)
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
# The card and the badge (SVG, fixed width, nothing loaded, no script)

SVG_NS = "http://www.w3.org/2000/svg"
SANS = "Verdana,Geneva,DejaVu Sans,sans-serif"


def fitted(text, size, room, bold=False):
    """textLength for a line that would not fit `room` pixels by a cautious estimate: the font is the reader's, so
    the width is forced rather than guessed."""
    estimate = len(text) * size * (0.68 if bold else 0.62)
    return {"textLength": f"{room:.0f}", "lengthAdjust": "spacingAndGlyphs"} if estimate > room else {}


def contributions(count):
    return f"{count} verified contribution" + ("" if count == 1 else "s")


def render_card(project, member):
    """A member's card: the hive, the project, the number of integrations, the month of the first one. It carries
    no login: the file is named by the account's id and stays right when the account is renamed."""
    first = instant_of(member["first_integration"])
    top = "La Ruche" + (f" · {plain(project, 24)}" if project else "")
    bottom = f"{contributions(member['integrations'])} · since {MONTHS[first.month - 1]} {first.year}"
    return el("svg", el("title", f"{top} · {bottom}"),
              el("rect", x="0.5", y="0.5", width="399", height="71", rx="8", fill="#fffaf0", stroke="#d9b56a"),
              el("path", d="M34 16L51.3 26V46L34 56L16.7 46V26Z", fill="#eda100"),
              el("path", d="M34 25L43.5 30.5V41.5L34 47L24.5 41.5V30.5Z", fill="#fffaf0"),
              el("text", top, x="66", y="31", fill="#0b0b0b", font_family=SANS, font_size="15", font_weight="bold", **fitted(top, 15, 318, True)),
              el("text", bottom, x="66", y="52", fill="#52514e", font_family=SANS, font_size="12.5", **fitted(bottom, 12.5, 318)),
              xmlns=SVG_NS, width="400", height="72", viewBox="0 0 400 72", role="img", aria_label=f"{top} · {bottom}") + "\n"


def render_badge(count):
    left, right = "La Ruche", contributions(count)
    left_width, right_width = round(len(left) * 6.6) + 12, round(len(right) * 6.6) + 12
    width = left_width + right_width

    def label(text, start, room):
        return el("text", text, x=f"{start + 6}", y="14", fill="#ffffff", font_family=SANS, font_size="11",
                  textLength=f"{room - 12}", lengthAdjust="spacingAndGlyphs")
    return el("svg", el("title", f"{left}: {right}"),
              el("rect", width=f"{width}", height="20", rx="3", fill="#3b3b3b"),
              el("path", d=f"M{left_width} 0H{width - 3}A3 3 0 0 1 {width} 3V17A3 3 0 0 1 {width - 3} 20H{left_width}Z", fill="#8a5a00"),
              label(left, 0, left_width), label(right, left_width, right_width),
              xmlns=SVG_NS, width=f"{width}", height="20", viewBox=f"0 0 {width} 20", role="img", aria_label=f"{left}: {right}") + "\n"


# ---------------------------------------------------------------------------------------------------------------
# Files


def card_name(member_id):
    """The only file name that depends on the ledger: made from a whole number, never from a string."""
    if account_id(member_id) is None:
        raise ValueError("a card is named by an account's numeric id")
    return f"members/{member_id:d}.svg"


def summary_json(data):
    """summary.json: plain ASCII, and no « < », « > » or « & » even inside a string, so that it stays harmless if a
    tool pastes it into a page."""
    text = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=True, allow_nan=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") + "\n"


def render(data, title="", repo_url=None, join=None):
    """{file name: text} for one project's page. The same data gives the same bytes."""
    files = {"index.html": render_html(data, title, repo_url, join or Link(DEFAULT_JOIN_URL)),
             "badge.svg": render_badge(data["totals"]["integrations"]), "summary.json": summary_json(data)}
    for member in data["members"]:
        files[card_name(member["id"])] = render_card(data["project"], member)
    return files


def write(out, files):
    """Writes each file whole or not at all, under `out` and nowhere else: a name is one of the three constants or
    members/<digits>.svg, whatever asked for it."""
    out = Path(out)
    if any(name not in FIXED_NAMES and not CARD_NAME.match(name) for name in files):
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
    parser.add_argument("--state", required=True, help="the project's folder of the state branch (ledger.jsonl, feed.json, stats.json)")
    parser.add_argument("--out", required=True, help="where index.html, badge.svg, summary.json and members/ are written")
    parser.add_argument("--title", default="", help="one line saying what the project is, shown under its name")
    parser.add_argument("--repo-url", help="https://github.com/owner/name: integrations then link to their commit")
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
        files = render(collect(args.state, now), plain(args.title, 160), args.repo_url, join)
        write(args.out, files)
    except PageError as error:
        print(f"page: {hive.safe_text(error, 400)}", file=sys.stderr)
        sys.exit(2)
    print(f"{len(files)} file(s) written")


if __name__ == "__main__":
    main()
