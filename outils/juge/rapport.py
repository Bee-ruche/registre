#!/usr/bin/env python3
"""juge.json's SHA-256 and key figures (FORMATS), juge.yml's job outputs; the verdict job checks the report against them.
  python3 rapport.py juge.json                    the figures, « key=value » lines (empty values: no report)
  python3 rapport.py juge.json --code CODE        juge.yml's outputs: code=CODE then the figures, once the report is checked;
                                                  code=2 if it fails its check (malformed, or none for code 0) (ruche-0117)
  python3 rapport.py juge.json --verifier S.json --base BASE --tete TETE
      S.json: toJSON(needs.<judging job>.outputs), BASE and TETE the pull request's commits; 0 the same report, its code 0 and
      the PR's commits; 1 not; 2 error. Any non-zero exit blocks the verdict.
Standard library only: a verdict job can run this file alone (docs/juge-commun.md)."""

import hashlib
import json
import os
import re
import stat
import sys

RAPPORT_MAX = 32 << 20  # bytes; juge.json is far smaller (juge.py caps its list of suspicious constructs)
FORMATS = {"empreinte": r"[0-9a-f]{64}", "suspectes": r"0|[1-9][0-9]{0,8}", "sorties_comparees": r"0|[1-9][0-9]{0,15}",
           "greffon": r"[0-9a-f]{64}", "graine": r"[0-9a-f]{2,64}", "base": r"[0-9a-f]{40}|", "tete": r"[0-9a-f]{40}|"}


class Ecart(Exception):  # the report read is not the one the judging job published
    pass


def lire(chemin):
    """The report's bytes: a regular file, never through a link, at most RAPPORT_MAX; None if there is none."""
    try:
        fd = os.open(chemin, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as f:
        donnees = f.read(RAPPORT_MAX + 1) if stat.S_ISREG(os.fstat(fd).st_mode) else b""
    if not 0 < len(donnees) <= RAPPORT_MAX:
        raise ValueError(f"the report is not a regular file of 1 to {RAPPORT_MAX} bytes")
    return donnees


def chiffres(donnees):
    """{output: text} of a report's bytes; ValueError if it or any figure is malformed."""
    try:
        juge = json.loads(donnees)["juge"]
        suspects, omises = juge["constructions_suspectes"], juge.get("constructions_suspectes_omises", 0)
        valeurs = {"empreinte": hashlib.sha256(donnees).hexdigest(), "sorties_comparees": juge["verification"]["sorties_comparees"],
                   "greffon": juge["greffon"], "graine": juge["graine"], "base": juge.get("base") or "", "tete": juge.get("tete") or ""}
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"report without its judge section ({e!r})")
    if type(suspects) is not list or type(omises) is not int or omises < 0 or type(valeurs["sorties_comparees"]) is not int \
            or any(type(valeurs[k]) is not str for k in ("greffon", "graine", "base", "tete")):
        raise ValueError("malformed figure in the report")
    valeurs = {k: str(len(suspects) + omises if k == "suspectes" else valeurs[k]) for k in FORMATS}
    if [k for k, motif in FORMATS.items() if not re.fullmatch(motif, valeurs[k])]:
        raise ValueError("malformed figure in the report")
    return valeurs


def publier(chemin, code):
    """juge.yml's job outputs: {"code": ..., figures}; code 2 and no figures if the report fails its check."""
    try:
        donnees = lire(chemin)
        if code not in ("0", "1", "2") or (code == "0" and donnees is None):
            raise ValueError("no report for code 0, or a code other than 0, 1 and 2")
        return {"code": code, **(chiffres(donnees) if donnees else dict.fromkeys(FORMATS, ""))}
    except (OSError, ValueError) as e:
        print(f"rapport : erreur : {e}; code 2 published", file=sys.stderr)
        return {"code": "2", **dict.fromkeys(FORMATS, "")}


def verifier(chemin, publiees, base, tete):
    """Refuses (Ecart) a report whose SHA-256 or any figure differs from the judging job's outputs, whose published code is
    not 0, or whose commits are not the pull request's (base, tete); returns it."""
    if not isinstance(publiees, dict) or str(publiees.get("code")) != "0":
        raise Ecart("the judging job's code is not 0")
    if not all(isinstance(c, str) and re.fullmatch(r"[0-9a-f]{40}", c) for c in (base, tete)):
        raise Ecart("the pull request's base and head are required (40 hexadecimal digits)")
    donnees = lire(chemin)
    if donnees is None or not isinstance(publiees, dict) or not re.fullmatch(FORMATS["empreinte"], str(publiees.get("empreinte"))):
        raise Ecart("no report, or no SHA-256 among the judging job's outputs")
    if hashlib.sha256(donnees).hexdigest() != publiees["empreinte"]:
        raise Ecart("its SHA-256 is not the one the judging job published")
    valeurs = chiffres(donnees)
    ecarts = [k for k, v in valeurs.items() if str(publiees.get(k, "")) != v]
    if ecarts:
        raise Ecart("figure(s) other than the judging job's: " + ", ".join(ecarts))
    if (valeurs["base"], valeurs["tete"]) != (base, tete):
        raise Ecart("base or head other than the pull request's")
    return json.loads(donnees)


def main(argv):
    try:
        if len(argv) == 1:
            donnees = lire(argv[0])
            print("\n".join(f"{k}={v}" for k, v in (chiffres(donnees) if donnees else dict.fromkeys(FORMATS, "")).items()))
            return 0
        if len(argv) == 3 and argv[1] == "--code":
            print("\n".join(f"{k}={v}" for k, v in publier(argv[0], argv[2]).items()))
            return 0
        if len(argv) == 7 and argv[1::2] == ["--verifier", "--base", "--tete"]:
            with open(argv[2], encoding="utf-8") as f:
                verifier(argv[0], json.loads(f.read(1 << 20)), argv[4], argv[6])
            return 0
    except (Ecart, OSError, ValueError) as e:
        print(f"rapport : {'REFUS' if isinstance(e, Ecart) else 'erreur'} : {e}", file=sys.stderr)
        return 1 if isinstance(e, Ecart) else 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
