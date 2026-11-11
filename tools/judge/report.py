#!/usr/bin/env python3
"""judge.json's SHA-256 and key figures (FORMATS), juge.yml's job outputs; the verdict job checks the report against them.
  python3 report.py juge.json                    the figures, « key=value » lines (empty values: no report)
  python3 report.py juge.json --code CODE        juge.yml's outputs: code=CODE then the figures, once the report is checked;
                                                  code=2 if it fails its check (none or malformed for code 0, another
                                                  code stated) (ruche-0117); a refusal (1) needs no report (ruche-0136)
  python3 report.py juge.json --verify S.json --base BASE --head TETE
      S.json: toJSON(needs.<judging job>.outputs), BASE and TETE the pull request's commits; 0 the same report, its code 0,
      the PR's commits and both seeds drawn by the judge (ruche-0136); 1 not; 2 error. Any non-zero exit blocks the verdict.
Standard library only: a verdict job can run this file alone (docs/juge-commun.md)."""

import datetime
import hashlib
import json
import os
import re
import stat
import sys

REPORT_MAX = 32 << 20  # bytes; juge.json is far smaller (juge.py caps its list of suspicious constructs)
FORMATS = {"fingerprint": r"[0-9a-f]{64}", "suspects": r"0|[1-9][0-9]{0,8}", "outputs_compared": r"0|[1-9][0-9]{0,15}",
           "plugin": r"[0-9a-f]{64}", "seed": r"[0-9a-f]{2,64}", "base": r"[0-9a-f]{40}|", "head": r"[0-9a-f]{40}|"}


ISSUES = {"0": "correct", "1": "refusal", "2": "environment_error"}  # judge.py's exit code and judge.json's judge.outcome (ruche-0136)
# ruche-0148 (J2b): judge.json is English from judge-v4 on; juge.json, French, is read until DATE_D (bee's). A report that mixes the
# vocabularies among the keys report.py reads (the top level, the judge section, verification's judge-owned keys, the seed origin) is
# refused. FRENCH: those French keys that have another English name, verification's aside (VERIFICATION_KEYS: a plugin adds its own
# keys there, which stay as written); FRENCH_VALUES: the values report.py reads (names.yaml, judge_report).
DATE_D = "2027-01-01"
FRENCH = {"chauffe": "warmup", "ordre": "order", "methode": "method", "metriques": "metrics", "mesures": "measurements",
          "duree_s": "duration_s", "juge": "judge", "commun": "common", "tete": "head", "projet": "project", "greffon": "plugin",
          "issue": "outcome", "graine": "seed", "origine_des_graines": "seed_origin", "graine_ordre": "order_seed",
          "constructions_suspectes_omises": "suspicious_constructs_omitted", "constructions_suspectes_par_type": "suspicious_constructs_by_type",
          "analyse": "analysis", "constructions_suspectes": "suspicious_constructs", "panne_machine": "machine_failure", "motif": "reason"}
VERIFICATION_KEYS = {"sorties_comparees": "outputs_compared", "entrees_melees": "inputs_mixed", "melees_par_repetition": "mixed_per_repetition",
                     "instructions_sans_melange": "instructions_without_mixing", "fixes_sans_mesure": "fixed_without_measurement"}
FRENCH_VALUES = {"juste": "correct", "refus": "refusal", "erreur_environnement": "environment_error", "donnee": "given", "tiree": "drawn"}


def today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def judge_of(data):
    """The report's judge section, in English: judge.json's as it is; juge.json's (juge-v1 to juge-v3) with the keys and values
    report.py reads put in English, until DATE_D. ValueError for French from DATE_D on, or for both vocabularies among the keys
    report.py reads (the top level, the judge section, verification's judge-owned keys, the seed origin)."""
    report = json.loads(data)
    if not isinstance(report, dict):
        raise ValueError("report without its judge section (not a mapping)")
    judge = report.get("judge", report.get("juge"))
    section = judge if isinstance(judge, dict) else {}
    nested = [section.get(k) for k in ("verification", "seed_origin", "origine_des_graines")]
    verification, origins = (d if isinstance(d, dict) else {} for d in (nested[0], nested[1] or nested[2]))
    keys = set(report) | set(section) | set(origins) | set(verification) & (set(VERIFICATION_KEYS) | set(VERIFICATION_KEYS.values()))
    pairs = {**FRENCH, **VERIFICATION_KEYS}
    french, english = sorted(keys & set(pairs)), sorted(keys & set(pairs.values()))
    if french and english:
        raise ValueError(f"French keys ({', '.join(french[:3])}) and English keys ({', '.join(english[:3])}): one vocabulary per report "
                         "(among the keys report.py reads)")
    if french and today() >= DATE_D:
        raise ValueError(f"French keys ({', '.join(french[:3])}): juge.json is read until {DATE_D} only (judge.json from judge-v4 on)")
    if not french or not isinstance(judge, dict):
        return judge

    def english_of(d, table, values=()):
        return {table.get(k, k): FRENCH_VALUES.get(v, v) if k in values and isinstance(v, str) else v for k, v in d.items()}
    english = english_of(judge, FRENCH, ("issue",))
    if isinstance(english.get("verification"), dict):
        english["verification"] = english_of(english["verification"], VERIFICATION_KEYS)
    if isinstance(english.get("seed_origin"), dict):
        english["seed_origin"] = english_of(english["seed_origin"], FRENCH, ("graine", "graine_ordre"))
    return english


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
        judge = judge_of(data)
        suspects, omitted_ones = judge["suspicious_constructs"], judge.get("suspicious_constructs_omitted", 0)
        values_of = {"fingerprint": hashlib.sha256(data).hexdigest(), "outputs_compared": judge["verification"]["outputs_compared"],
                   "plugin": judge["plugin"], "seed": judge["seed"], "base": judge.get("base") or "", "head": judge.get("head") or ""}
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"report without its judge section ({e!r})")
    if type(suspects) is not list or type(omitted_ones) is not int or omitted_ones < 0 or type(values_of["outputs_compared"]) is not int \
            or any(type(values_of[k]) is not str for k in ("plugin", "seed", "base", "head")):
        raise ValueError("malformed figure in the report")
    values_of = {k: str(len(suspects) + omitted_ones if k == "suspects" else values_of[k]) for k in FORMATS}
    if [k for k, reason in FORMATS.items() if not re.fullmatch(reason, values_of[k])]:
        raise ValueError("malformed figure in the report")
    return values_of


def outcome(data):
    """The report's own code (judge.code, with its judge.outcome); ValueError unless it is one of ISSUES."""
    try:
        judge = judge_of(data)
        code, nom = judge["code"], judge["outcome"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"report without its code ({e!r})")
    if type(code) is not int or ISSUES.get(str(code)) != nom:
        raise ValueError("malformed code in the report")
    return str(code)


def contradicts(path):
    """True if the report, read and parsed, states a code or an issue other than a refusal's."""
    try:
        judge = judge_of(lire(path) or b"{}")
        code = judge.get("code", 1) if isinstance(judge, dict) else 1
        return type(code) is not int or code != 1 or isinstance(judge, dict) and judge.get("outcome", ISSUES["1"]) != ISSUES["1"]
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
    not 0, or whose commits are not the pull request's (base, head); returns it."""
    if not isinstance(published_ones, dict) or str(published_ones.get("code")) != "0":
        raise Gap("the judging job's code is not 0")
    if not all(isinstance(c, str) and re.fullmatch(r"[0-9a-f]{40}", c) for c in (base, head)):
        raise Gap("the pull request's base and head are required (40 hexadecimal digits)")
    data = lire(path)
    if data is None or not isinstance(published_ones, dict) or not re.fullmatch(FORMATS["fingerprint"], str(published_ones.get("fingerprint"))):
        raise Gap("no report, or no SHA-256 among the judging job's outputs")
    if hashlib.sha256(data).hexdigest() != published_ones["fingerprint"]:
        raise Gap("its SHA-256 is not the one the judging job published")
    values_of = digits(data)
    gaps = [k for k, v in values_of.items() if str(published_ones.get(k, "")) != v]
    if gaps:
        raise Gap("figure(s) other than the judging job's: " + ", ".join(gaps))
    if (values_of["base"], values_of["head"]) != (base, head):
        raise Gap("base or head other than the pull request's")
    if outcome(data) != "0":
        raise Gap("the report is not a judgement's (its own code is not 0)")
    if judge_of(data).get("seed_origin") != {"seed": "drawn", "order_seed": "drawn"}:
        raise Gap("a seed given on the command line, or its origin unsaid: a local reproduction, never a judgement")
    return json.loads(data)


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
