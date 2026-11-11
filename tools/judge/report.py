#!/usr/bin/env python3
"""juge.json's SHA-256 and key figures (FORMATS), juge.yml's job outputs; the verdict job checks the report against them.
  python3 report.py juge.json                    the figures, « key=value » lines (empty values: no report)
  python3 report.py juge.json --code CODE        juge.yml's outputs: code=CODE then the figures, once the report is checked;
                                                  code=2 if it fails its check (none or malformed for code 0, another
                                                  code stated) (ruche-0117); a refusal (1) needs no report (ruche-0136)
  python3 report.py juge.json --verify S.json --base BASE --head TETE
      S.json: toJSON(needs.<judging job>.outputs), BASE and TETE the pull request's commits; 0 the same report, its code 0,
      the PR's commits and both seeds drawn by the judge (ruche-0136); 1 not; 2 error. Any non-zero exit blocks the verdict.
Standard library only: a verdict job can run this file alone (docs/juge-commun.md)."""

import hashlib
import json
import os
import re
import stat
import sys

REPORT_MAX = 32 << 20  # bytes; juge.json is far smaller (juge.py caps its list of suspicious constructs)
FORMATS = {"empreinte": r"[0-9a-f]{64}", "suspectes": r"0|[1-9][0-9]{0,8}", "sorties_comparees": r"0|[1-9][0-9]{0,15}",
           "greffon": r"[0-9a-f]{64}", "graine": r"[0-9a-f]{2,64}", "base": r"[0-9a-f]{40}|", "tete": r"[0-9a-f]{40}|"}


ISSUES = {"0": "juste", "1": "refus", "2": "erreur_environnement"}  # juge.py's exit code and juge.json's juge.issue (ruche-0136)


class Gap(Exception):  # the report read is not the one the judging job published
    pass


def lire(path):
    """The report's bytes: a regular file, never through a link, at most RAPPORT_MAX; None if there is none."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as f:
        data = f.read(REPORT_MAX + 1) if stat.S_ISREG(os.fstat(fd).st_mode) else b""
    if not 0 < len(data) <= REPORT_MAX:
        raise ValueError(f"the report is not a regular file of 1 to {REPORT_MAX} bytes")
    return data


def digits(data):
    """{output: text} of a report's bytes; ValueError if it or any figure is malformed."""
    try:
        judge = json.loads(data)["juge"]
        suspects, omitted_ones = judge["constructions_suspectes"], judge.get("constructions_suspectes_omises", 0)
        values_of = {"empreinte": hashlib.sha256(data).hexdigest(), "sorties_comparees": judge["verification"]["sorties_comparees"],
                   "greffon": judge["greffon"], "graine": judge["graine"], "base": judge.get("base") or "", "tete": judge.get("tete") or ""}
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"report without its judge section ({e!r})")
    if type(suspects) is not list or type(omitted_ones) is not int or omitted_ones < 0 or type(values_of["sorties_comparees"]) is not int \
            or any(type(values_of[k]) is not str for k in ("greffon", "graine", "base", "tete")):
        raise ValueError("malformed figure in the report")
    values_of = {k: str(len(suspects) + omitted_ones if k == "suspectes" else values_of[k]) for k in FORMATS}
    if [k for k, reason in FORMATS.items() if not re.fullmatch(reason, values_of[k])]:
        raise ValueError("malformed figure in the report")
    return values_of


def outcome(data):
    """The report's own code (juge.code, with its juge.issue); ValueError unless it is one of ISSUES."""
    try:
        judge = json.loads(data)["juge"]
        code, nom = judge["code"], judge["issue"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"report without its code ({e!r})")
    if type(code) is not int or ISSUES.get(str(code)) != nom:
        raise ValueError("malformed code in the report")
    return str(code)


def contradicts(path):
    """True if the report, read and parsed, states a code or an issue other than a refusal's."""
    try:
        judge = json.loads(lire(path) or b"{}").get("juge")
        code = judge.get("code", 1) if isinstance(judge, dict) else 1
        return type(code) is not int or code != 1 or isinstance(judge, dict) and judge.get("issue", ISSUES["1"]) != ISSUES["1"]
    except (OSError, ValueError, AttributeError, RecursionError):
        return False


def publish(path, code):
    """juge.yml's job outputs: {"code": ..., figures}; code 2 and no figures if the report fails its check. A refusal needs no
    report: code 1 stays 1 whatever state its report is in, unless the report states another code."""
    try:
        if code == "1" and contradicts(path):
            raise ValueError("the report's code is not the judge's exit code")
        if code == "1":
            return {"code": "1", **dict.fromkeys(FORMATS, "")}
        data = lire(path)
        if code not in ISSUES or (code == "0" and data is None):
            raise ValueError("no report for code 0, or a code other than 0, 1 and 2")
        if data is not None and outcome(data) != code:
            raise ValueError("the report's code is not the judge's exit code")
        return {"code": code, **(digits(data) if code == "0" else dict.fromkeys(FORMATS, ""))}
    except (OSError, ValueError) as e:
        print(f"rapport : erreur : {e}; code 2 published", file=sys.stderr)
        return {"code": "2", **dict.fromkeys(FORMATS, "")}


def verifier(path, published_ones, base, head):
    """Refuses (Ecart) a report whose SHA-256 or any figure differs from the judging job's outputs, whose published code is
    not 0, or whose commits are not the pull request's (base, tete); returns it."""
    if not isinstance(published_ones, dict) or str(published_ones.get("code")) != "0":
        raise Gap("the judging job's code is not 0")
    if not all(isinstance(c, str) and re.fullmatch(r"[0-9a-f]{40}", c) for c in (base, head)):
        raise Gap("the pull request's base and head are required (40 hexadecimal digits)")
    data = lire(path)
    if data is None or not isinstance(published_ones, dict) or not re.fullmatch(FORMATS["empreinte"], str(published_ones.get("empreinte"))):
        raise Gap("no report, or no SHA-256 among the judging job's outputs")
    if hashlib.sha256(data).hexdigest() != published_ones["empreinte"]:
        raise Gap("its SHA-256 is not the one the judging job published")
    values_of = digits(data)
    gaps = [k for k, v in values_of.items() if str(published_ones.get(k, "")) != v]
    if gaps:
        raise Gap("figure(s) other than the judging job's: " + ", ".join(gaps))
    if (values_of["base"], values_of["tete"]) != (base, head):
        raise Gap("base or head other than the pull request's")
    if outcome(data) != "0":
        raise Gap("the report is not a judgement's (its own code is not 0)")
    report = json.loads(data)
    if report["juge"].get("origine_des_graines") != {"graine": "tiree", "graine_ordre": "tiree"}:
        raise Gap("a seed given on the command line, or its origin unsaid: a local reproduction, never a judgement")
    return report


def main(argv):
    try:
        if len(argv) == 1:
            data = lire(argv[0])
            print("\n".join(f"{k}={v}" for k, v in (digits(data) if data else dict.fromkeys(FORMATS, "")).items()))
            return 0
        if len(argv) == 3 and argv[1] == "--code":
            print("\n".join(f"{k}={v}" for k, v in publish(argv[0], argv[2]).items()))
            return 0
        if len(argv) == 7 and argv[1::2] == ["--verify", "--base", "--head"]:
            with open(argv[2], encoding="utf-8") as f:
                verifier(argv[0], json.loads(f.read(1 << 20)), argv[4], argv[6])
            return 0
    except (Gap, OSError, ValueError) as e:
        print(f"rapport : {'REFUS' if isinstance(e, Gap) else 'erreur'} : {e}", file=sys.stderr)
        return 1 if isinstance(e, Gap) else 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
