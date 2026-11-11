#!/usr/bin/env python3
"""Bee's common judge: run a PR's code in containers and judge it from outside, for any project.

Specification: the registry's docs/common-judge.md. The common judge does what protects and depends on no
project; the project's PLUGIN (the fork's bee/judge/project.py or bee/juge/projet.py, read from the PR's BASE, never
from the PR) says how to build, which inputs to give, how to verify and what to measure.

What the common judge guarantees, whatever the plugin:
- this program (the host) NEVER executes a file from the PR. Compilation, execution and instruction
  counting take place in containers without network, read-only, without privilege, limited to
  two processes for execution, which see only their inputs and an outputs folder;
- each side of inputs (« f », « z »…) has its own container: a harness never sees the inputs
  of another side; each scenario has its own, with its own outputs only, frozen (SHA-256) as soon as the
  container ends: the comparison reads only what was frozen; their order is drawn at each repetition;
- the seed of the inputs drawn at random is chosen here, AFTER compilation; the plugin perturbs the
  measurements' inputs at each repetition;
- processor time and memory are measured by the kernel (wait4) in the common judge's chrono launcher,
  compiled separately; the instruction count covers the harness's whole process and is read on
  Valgrind's last line;
- the outputs are read only through lecture.py (no link, no special file, bounded size);
- an analysis of the compiled objects (analysis.py) lists the suspicious constructs.

Usage:
  python3 tools/judge/judge.py --tooling BASE --image-only
  python3 tools/judge/judge.py --tooling BASE --source-a FOLDER --source-b FOLDER [--option KEY=VALUE]…
                              [--repetitions 10] [--warmup 1] [--no-instructions] [--instructions-prefix 131072]
                              [--json judge.json] [--seed HEX]
                              [--build-network host]
  --tooling: copy of the PR's BASE (its bee/judge/project.py or bee/juge/projet.py is the plugin)
  --source-a / --source-b: repositories of the reference (A, the base) and of the candidate (B, the PR)
Output: a JSON report in ab.py's format (measurements, metrics, instructions) plus a « judge » section.
Exit code: 0 if all of B's outputs are correct, 1 if the judge refuses B, 2 if the environment
is not suitable (Docker missing, a base that does not compile, an invalid plugin, a badly set-up judge), a failure of the machine
(Docker, its runtime, the image) included. With --json, judge.json says it in every case (judge.code, judge.outcome: ISSUES); its keys
and values are English from judge-v4 on (ruche-0148: names.yaml, judge_report), juge.json's French before.
"""

import argparse
import collections
import contextlib
import glob
import hashlib
import importlib.util
import json
import os
import platform
import random
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analysis  # noqa: E402
import container  # noqa: E402
import entrees as inputs_module  # noqa: E402
import stats  # noqa: E402
from lecture import Erreur, Panne, Refus, Sorties, exiger, figer, journal, propre  # noqa: E402,F401

COMMON_VERSION = 4   # the registry's tag judge-v4
JUDGE_VERSION = 3      # verdict.json's numbering: 2 = minizBee's judge (miniz-0031), 3 = the common judge (its tag in « common »)
ISSUES = {0: "correct", 1: "refusal", 2: "environment_error"}  # judge.json's judge.outcome for each exit code (ruche-0136)
FAILURE = {}  # what judge.json says when the judge stops (code 1 or 2): its path and the judge's identity, set by main
# ruche-0148 (J2): a base holds one plugin, in English (bee/judge/project.py, judge-v4 on) or in French (bee/juge/projet.py, read
# until judge-v5). PLUGIN_NAMES gives the English name of each name of the French contract that has another one (identifiers.yaml,
# judge: plugin); the judge reads an English plugin under the French names (EnglishPlugin), its directions as DIRECTIONS says.
PLUGIN_PATH, FRENCH_PLUGIN_PATH = os.path.join("bee", "judge", "project.py"), os.path.join("bee", "juge", "projet.py")
PLUGIN_NAMES = {"Projet": "Project", "NOM": "NAME", "SOURCES_REQUISES": "REQUIRED_SOURCES", "OUTILLAGE": "TOOLING",
                "EN_TETES_BASE": "BASE_HEADERS", "CONSTRUIRE": "BUILD", "COTES": "SIDES", "METRIQUES": "METRICS", "PAQUETS": "PACKAGES",
                "PERMIS": "ALLOWED", "METHODE": "METHOD", "verifier": "verify", "fixes": "fixed"}
DIRECTIONS = {"plus_haut": "higher", "plus_bas": "lower"}  # a metric's direction, French (the judge's) -> English
REQUIRED_ATTRIBUTES = ("NOM", "SOURCES", "SOURCES_REQUISES", "OUTILLAGE", "EN_TETES_BASE", "CONSTRUIRE",
                    "PREFIXES", "COTES", "SCENARIOS", "INSTRUCTIONS", "METRIQUES")
REQUIRED_METHODS = ("corpus", "verification", "verifier", "fixes", "repetition", "instructions", "scenario")
SURVEYS = (("symboles", "symboles.txt"), ("sections", "sections.txt"), ("desassemblage", "desassemblage.txt"))
OBJECT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}\.o")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
PREFIX = re.compile(r"[A-Za-z][A-Za-z0-9]{0,30}_")  # a word followed by « _ »: an identifier boundary
ALLOWED_MAX = 64
SUSPICIOUS_MAX = 100  # judge.json lists at most this many suspicious constructs and counts the rest (suspicious_constructs_omitted)
# Kinds of suspicious construct, the most serious first: judge.json lists them in this order, and counts each kind (ruche-0117).
SEVERITY = ("analyse_incomplete", "architecture", "appel_interdit", "symbole_interdit", "instruction", "octets", "section", "symbole",
           "symbole_defini", "appel_externe", "source")
NEVER_ALLOWED = analysis.NEVER_ALLOWED
UNITS = (".c", ".S", ".s", ".cc", ".cpp", ".cxx")  # translation units: each must leave its object
ANALYSED_ARCHITECTURES = ("x86_64", "amd64")  # mnemonics and Valgrind preamble known to analysis.py
VALGRIND = ["/usr/bin/valgrind", "--tool=cachegrind", "--cache-sim=no", "--vgdb=no", "--cachegrind-out-file=/dev/null"]
COMMIT, HISTORY_MAX, REPO = re.compile(r"[0-9a-f]{40}"), 16, re.compile(r"[A-Za-z0-9-]+/(?!\.\.?$)[A-Za-z0-9_.-]+")


def common_tag(version=COMMON_VERSION):
    """The registry's tag of this judge: juge-v1 to juge-v3, then judge-v4 on (ruche-0148); bee reads no other name of a number."""
    return f"{'juge' if version <= 3 else 'judge'}-v{version}"


# ------------------------------------------------------------------ plugin

class EnglishPlugin:
    """ruche-0148 (J2): an English plugin read under the French contract's names (PLUGIN_NAMES), its METRICS with the French
    directions (higher -> plus_haut, lower -> plus_bas; any other: None, which load_plugin refuses)."""

    def __init__(self, plugin):
        self._plugin = plugin

    def __getattr__(self, name):
        value = getattr(self._plugin, PLUGIN_NAMES.get(name, name))
        french = {e: f for f, e in DIRECTIONS.items()}
        return [(m[0], french.get(m[1]) if isinstance(m[1], str) else None, m[2]) if isinstance(m, (tuple, list)) and len(m) == 3 else m
                for m in value] if name == "METRIQUES" else value


def load_plugin(tooling, options):
    """Loads the tooling's plugin (the BASE) and checks that it keeps the contract: bee/judge/project.py, in English, or
    bee/juge/projet.py, in French (ruche-0148), never both."""
    found = [p for p in (PLUGIN_PATH, FRENCH_PLUGIN_PATH) if os.path.lexists(os.path.join(tooling, p))]
    if len(found) == 2:
        raise Erreur(f"two plugins in {tooling}, {PLUGIN_PATH} (English) and {FRENCH_PLUGIN_PATH} (French): a base holds one")
    relative = (found or [PLUGIN_PATH])[0]
    english, path, parts = relative == PLUGIN_PATH, os.path.join(tooling, relative), relative.split(os.sep)
    if not os.path.isfile(path):
        raise Erreur(f"plugin not found: {' or '.join(found or (PLUGIN_PATH, FRENCH_PLUGIN_PATH))} in {tooling}")
    if any(os.path.islink(os.path.join(tooling, *parts[:i + 1])) for i in range(len(parts))):
        raise Erreur(f"plugin {relative}: every component of its path must be a real folder or file, not a link")
    with open(path, "rb") as f:
        fingerprint = hashlib.sha256(f.read()).hexdigest()
    spec = importlib.util.spec_from_file_location("bee_greffon_projet", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = PLUGIN_NAMES if english else {}
    if not hasattr(module, names.get("Projet", "Projet")):
        raise Erreur(f"the plugin defines no class {names.get('Projet', 'Projet')}")
    cls = getattr(module, names.get("Projet", "Projet"))
    plugin = cls(dict(options))
    # Names of the other contract defined in the module, in the class body or in a base class's (not those an instance or a
    # __getattr__ answers).
    defined = {n for c in type(plugin).__mro__ if c is not object for n in vars(c)}
    other = [n for n in (PLUGIN_NAMES if english else PLUGIN_NAMES.values())
             if n in (vars(module) if n in ("Projet", "Project") else defined)]
    if other:
        raise Erreur(f"plugin {relative}: names of the {'French' if english else 'English'} contract "
                     f"({', '.join(other)}): one contract per plugin")
    projet = EnglishPlugin(plugin) if english else plugin
    missing_items = [names.get(a, a) for a in REQUIRED_ATTRIBUTES if not hasattr(projet, a)] + \
                [names.get(m, m) for m in REQUIRED_METHODS if not callable(getattr(projet, m, None))]
    if missing_items:
        raise Erreur("incomplete plugin: " + ", ".join(missing_items))
    if any(not (isinstance(m, (tuple, list)) and len(m) == 3 and m[1] in tuple(DIRECTIONS)) for m in projet.METRIQUES):
        raise Erreur(f"plugin's {names.get('METRIQUES', 'METRIQUES')}: (name, direction, unit) each, the direction "
                     + ("higher or lower" if english else "plus_haut or plus_bas"))
    sides_of = tuple(projet.COTES)
    if not sides_of or any(not inputs_module.COTE_PERMIS.fullmatch(c) for c in sides_of) or len(set(sides_of)) != len(sides_of):
        raise Erreur("plugin's COTES invalid")
    for s, c in projet.SCENARIOS.items():
        if c not in sides_of or not inputs_module.NOM_PERMIS.fullmatch(s):
            raise Erreur(f"invalid scenario in the plugin: {s}")
    if any(s not in projet.SCENARIOS for s in projet.INSTRUCTIONS):
        raise Erreur("plugin's INSTRUCTIONS: unknown scenario")
    # Namespace and allowed functions: an empty or too short prefix would switch off two categories of
    # the objects' analysis (adversarial review of 28 October); the functions that deceive the measurement are never allowed.
    prefixes, allowed_set = tuple(projet.PREFIXES), tuple(getattr(projet, "PERMIS", ()))
    if not prefixes or any(not isinstance(p, str) or not PREFIX.fullmatch(p) for p in prefixes):
        raise Erreur("plugin's PREFIXES invalid: at least one prefix, each a word ending in « _ » (mz_, yaml_…)")
    covering = sorted(n for n in NEVER_ALLOWED if n.startswith(prefixes))
    if covering:
        raise Erreur("plugin's PREFIXES: they would cover functions never allowed: " + ", ".join(covering))
    if len(allowed_set) > ALLOWED_MAX or any(not isinstance(n, str) or not IDENTIFIER.fullmatch(n) for n in allowed_set):
        raise Erreur(f"plugin's PERMIS invalid: at most {ALLOWED_MAX} function names")
    forbidden_items = sorted(set(allowed_set) & NEVER_ALLOWED)
    if forbidden_items:
        raise Erreur("plugin's PERMIS: functions never allowed: " + ", ".join(forbidden_items))
    if hasattr(projet, "DIFF"):
        raise Erreur("DIFF no longer exists: the diff analyzed is SOURCES' (adversarial review of 28 October)")
    for relative_path in list(projet.OUTILLAGE) + [projet.CONSTRUIRE]:
        if os.path.isabs(relative_path) or ".." in relative_path.split("/"):
            raise Erreur(f"invalid tooling path in the plugin: {relative_path}")
    return projet, fingerprint


# ------------------------------------------------------------------ preparation and build

def _no_link(repo, relative_one):
    """True if no component of repo/relative is a symbolic link and it is a regular file."""
    path = repo
    chunks = relative_one.split(os.sep)
    for i, m in enumerate(chunks):
        path = os.path.join(path, m)
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            raise Refus(f"{relative_one}: symbolic link refused")
        if i < len(chunks) - 1 and not stat.S_ISDIR(st.st_mode):
            return False
    return stat.S_ISREG(os.lstat(path).st_mode)


def copy_sources(repo, destination, reasons, required_items):
    """Copies the project's files (glob patterns relative to the root), refusing any symbolic link."""
    os.makedirs(destination, exist_ok=True)
    repo = os.path.abspath(repo)
    found_items = set()
    for reason in reasons:
        if os.path.isabs(reason) or ".." in reason.split("/"):
            raise Erreur(f"invalid sources pattern: {reason}")
        for path in sorted(glob.glob(os.path.join(glob.escape(repo), reason))):
            relative_one = os.path.relpath(path, repo)
            if relative_one in found_items or not _no_link(repo, relative_one):
                continue
            target = os.path.join(destination, relative_one)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(path, target)
            found_items.add(relative_one)
    for r in required_items:
        if r not in found_items:
            raise Refus(f"{r} not found in {repo}")
    return destination


def copy_tooling(tooling, source_a, destination, projet):
    """What the BASE gives the container: its tooling folders (OUTILLAGE) and its headers (EN_TETES_BASE).

    The base's headers are copied into /outillage/base/: the harness is compiled with them, not with
    the PR's (a macro slipped into a header of the PR cannot rewrite the harness)."""
    for relative_one in projet.OUTILLAGE:
        source = os.path.join(tooling, relative_one)
        if os.path.islink(source) or not os.path.isdir(source):
            raise Erreur(f"tooling folder missing from the base: {relative_one}")
        shutil.copytree(source, os.path.join(destination, relative_one), symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    copy_sources(source_a, os.path.join(destination, "base"), projet.EN_TETES_BASE, ())
    return destination


def expected_objects(sources):
    """One object obj/<name>.o per translation unit (.c, .S, .cc…) copied from the variant's SOURCES.

    Two units of the same name in two folders cannot each leave its object: refused (None)."""
    seen_items = {}
    for folder, _, names in os.walk(sources):
        for n in names:
            root, extension = os.path.splitext(n)
            if extension in UNITS:
                seen_items.setdefault(root + ".o", []).append(os.path.relpath(os.path.join(folder, n), sources))
    duplicate_items = sorted(c for c, l in seen_items.items() if len(l) > 1)
    return set(seen_items), duplicate_items


def build(docker, projet, sources, tooling, output_text, label, travail):
    """Compiles a variant in the container (the base's CONSTRUIRE script), then surveys its objects.

    The script's contract: the linked harness in <sortie>/execution, and EACH object of the project in
    <sortie>/obj/<name>.o (one per .c file of SOURCES). The analysis surveys (nm, objdump) are then produced
    by the common judge itself, on all these objects: a build script can neither omit
    nor empty them (adversarial review of 28 October)."""
    container.open_folder(output_text)
    command = ["sh", "/outillage/" + projet.CONSTRUIRE, "/sources", "/outillage", "/sortie"]
    r = docker.launch(command, [(sources, "/sources", True), (tooling, "/outillage", True), (output_text, "/sortie", False)],
                      pids=64, timeout_seconds=900)
    failure = Erreur if label == "A" else Refus
    if r.returncode != 0:
        raise failure(f"the compilation of {label} failed: " + propre(r.stderr))
    obj_folder = os.path.join(output_text, "obj")
    if os.path.islink(obj_folder) or not os.path.isdir(obj_folder):
        raise failure(f"{label}: no obj/ folder after the build")
    objects_found = []
    for n in sorted(os.listdir(obj_folder)):
        st = os.lstat(os.path.join(obj_folder, n))
        if not n.endswith(".o"):
            continue
        if not OBJECT.fullmatch(n) or not stat.S_ISREG(st.st_mode):
            raise failure(f"{label}: invalid object in obj/: {propre(n, 80)}")
        objects_found.append(n)
    expected_items, duplicate_items = expected_objects(sources)
    if duplicate_items:
        raise failure(f"{label}: translation units of the same name (only one object possible in obj/): "
                    + ", ".join(propre(d, 80) for d in duplicate_items[:10]))
    missing_items = sorted(expected_items - set(objects_found))
    if missing_items:
        raise failure(f"{label}: source file(s) without an object in obj/ (not compiled or not surveyable): "
                    + ", ".join(propre(m, 80) for m in missing_items[:10]))
    if not objects_found:
        raise failure(f"{label}: no object in obj/")
    surveys_folder = container.open_folder(os.path.join(travail, f"releves-{label}"))
    script = ('umask 000 && cd /construction/obj && nm -P -A "$@" > /releves/symboles.txt'
              ' && objdump -h "$@" > /releves/sections.txt && objdump -d --no-show-raw-insn "$@" > /releves/desassemblage.txt')
    r = docker.launch(["sh", "-c", script, "releves"] + objects_found,
                      [(output_text, "/construction", True), (surveys_folder, "/releves", False)], pids=64, timeout_seconds=900)
    if r.returncode != 0:
        raise failure(f"{label}: analysis surveys failed: " + propre(r.stderr))
    surveys = {key: exiger(surveys_folder, nom, 256 << 20).decode("utf-8", "replace") for key, nom in SURVEYS}
    for o in objects_found:  # each object is in each survey (objdump: « <object>:     file format … »)
        if not any(line_text.startswith(o + ":") for line_text in surveys["desassemblage"].splitlines()) or \
           not any(line_text.startswith(o + ":") for line_text in surveys["sections"].splitlines()):
            raise Erreur(f"{label}: {o} missing from the analysis surveys: judge badly set up")
    surveys["objets"] = [(o, exiger(obj_folder, o)) for o in objects_found]
    surveys["programme"] = [("execution", exiger(output_text, "execution"))]
    return surveys


def texts_of(folder):
    """The judged files of a variant (those copied from SOURCES), whole: {relative path: text} (latin-1 keeps every byte)."""
    result = {}
    for root, _, names in os.walk(folder):
        for n in names:
            with open(os.path.join(root, n), encoding="latin-1") as f:
                result[os.path.relpath(os.path.join(root, n), folder)] = f.read()
    return result


# ------------------------------------------------------------------ execution

def prepare(travail, nom, entrees, sides_of):
    """Writes the inputs, one folder per side; returns {side: folder}."""
    inputs_module.verifier_entrees(entrees, sides_of)
    folders = {}
    for c in sides_of:
        folders[c] = os.path.join(travail, secrets.token_hex(8))  # a neutral name, the same kind in every mode
        inputs_module.ecrire(folders[c], [e for e in entrees if e.cote == c], sides_of)
    return folders


def outputs_of(travail, nom, sides_of):
    return {c: container.open_folder(os.path.join(travail, secrets.token_hex(8))) for c in sides_of}


def launch_by_side(run, variant, folders, outputs, plans, order, **options):
    """One container per scenario, in the drawn order (ruche-0036), its outputs on /sorties as in verification (a neutral
    folder, then <side>/<scenario>), frozen as soon as the container ends. Returns (measurements, a Sorties that reads only the frozen)."""
    measurements, commands, figees = {}, {s: (c, command) for c, plan in plans.items() for s, command in plan}, {c: {} for c in outputs}
    for label in order:
        quoted_side, command = commands[label]
        folder = container.open_folder(os.path.join(os.path.dirname(outputs[quoted_side]), secrets.token_hex(8)))
        measurements.update(run.launch(variant, folders[quoted_side], folder, [(label, command)], **options))
        figees[quoted_side][label] = "dossier"
        figees[quoted_side].update((f"{label}/{k}", e) for k, e in figer(folder).items())
        os.rename(folder, os.path.join(outputs[quoted_side], label))
    return measurements, Sorties(outputs, figees=figees)


def step(nom, variants_of, order, measurements):
    """A step of judge.json: order of the variants and of the scenarios, processor time of each scenario (wait4, chrono)."""
    return {"step": nom, "variants": "".join(variants_of), "order": list(order), "cpu_time_s": {
        v: {s: round(m[s]["utilisateur_s"] + m[s]["systeme_s"], 6) for s in order} for v, m in sorted(measurements.items())}}


def round_number(rng, entrees):
    """The verification inputs in an order drawn from the judge's seed, round after round: each passes once per round."""
    while entrees:
        order = list(entrees)
        rng.shuffle(order)
        yield from order


def rename(rng, entrees):
    """Inputs as written in every mode, shuffled and renamed (e0000…); also the new name of each input, in the given order."""
    order, neutral_ones = list(range(len(entrees))), [""] * len(entrees)
    rng.shuffle(order)
    for rank, i in enumerate(order):
        neutral_ones[i] = f"e{rank:04d}"
    return [entrees[i]._replace(nom=neutral_ones[i]) for i in order], neutral_ones


def interleave(rng, measured_ones, rounds, how_many, names):
    """Measured inputs and `combien[c]` verification inputs per side from `tours[c]`, renamed together: neither name nor
    order tells them apart. Returns (inputs, {(side, name): the same input's name in verification, `noms`})."""
    addition = [next(rounds[c]) for c, k in how_many.items() for _ in range(k)]
    entrees, neutral_ones = rename(rng, list(measured_ones) + addition)
    return entrees, {(e.cote, neutral_ones[len(measured_ones) + j]): names[(e.cote, e.nom)] for j, e in enumerate(addition)}


def outputs_by_input(figees):
    """B's verification outputs, as frozen: {(side, written name): [paths relative to the side's folder]}."""
    index = {}
    for c, fingerprint in figees.items():
        for path, e in fingerprint.items():
            m = re.fullmatch(r"(e\d{4,})(\..*)?", path.rpartition("/")[2])
            if m and e != "dossier":
                index.setdefault((c, m.group(1)), []).append(path)
    return index


def same_outputs(index, verification, outputs, shuffled, scenarios):
    """B's output of each verification input mixed into a measured run is, byte for byte, its own output in verification
    (same path); each such input has at least one in each scenario of its side (ruche-0117). Returns the number compared."""
    total = 0
    for (quoted_side, nom), verification_name in shuffled.items():
        for s in (s for s, c in scenarios if c == quoted_side):
            views = 0
            for relative_one in index.get((quoted_side, verification_name), []):
                head, bar_line, last = relative_one.rpartition("/")
                measured = outputs.ecrite(quoted_side, f"{s}/{head}{bar_line}{nom}{last[len(verification_name):]}")
                if measured is not None:
                    views += 1
                    if measured != verification.ecrite(quoted_side, relative_one):
                        raise Refus(f"scenario {s}: B's output differs from its output in verification for the same input")
            if not views:
                raise Erreur(f"{quoted_side}/{nom}, scenario {s}: no output of B comparable with verification (the same outputs expected)")
            total += views
    return total


def variant(build_step, folder):
    """/variante: the harness alone, copied (no link followed) into a folder of the judge, which sets its times."""
    os.makedirs(folder)
    with open(os.path.join(folder, "execution"), "wb") as f:
        f.write(exiger(build_step, "execution"))
    os.chmod(os.path.join(folder, "execution"), 0o755)
    os.chmod(folder, 0o755)
    return folder


def erase(*groups):
    for group_of in groups:
        for folder in (group_of.values() if isinstance(group_of, dict) else group_of):
            shutil.rmtree(folder, ignore_errors=True)


def counted_integer(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise Erreur("the plugin must return a number of outputs compared (a positive integer)")
    return n


def require_coverage(outputs_b, entrees, step):
    """Each input must have had at least one output of B read by the plugin during the step."""
    forgotten_ones = [e.nom for e in entrees if not outputs_b.couvre(e.cote, e.nom)]
    if forgotten_ones:
        raise Erreur(f"{step}: the plugin read no output of B for {len(forgotten_ones)} input(s) "
                     f"({', '.join(forgotten_ones[:5])}): judge badly set up")


# ------------------------------------------------------------------ declared history

def fetch_history(tooling, text, token=None, budget=600):
    """Fetches into the base's repository the commits its plugin reads (judge.yml's `history`), with their trees
    and blobs but no history. Each must be in the base's ancestry, as GitHub's compare API on the calling repository
    (GITHUB_REPOSITORY) says (identical or behind), all checked before any fetch; checks and fetches share one time
    budget. judge.yml runs it in its own step (--history-only), the only call of judge.py given a token
    (GH_TOKEN, passed to gh alone), before anything loads the plugin and before the PR."""
    commits, repo = sorted(set(text.split())), os.environ.get("GITHUB_REPOSITORY", "")
    if len(commits) > HISTORY_MAX or not all(COMMIT.fullmatch(c) for c in commits):
        raise Erreur(f"history: at most {HISTORY_MAX} full commit SHAs (40 hexadecimal digits), separated by blanks")
    if not commits:
        return []
    end = time.monotonic() + budget

    def launch(command, env=None):
        try:
            return subprocess.run(command, capture_output=True, text=True, errors="replace", env=env,
                                  timeout=max(0.01, end - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise Erreur(f"history: checks and fetches exceeded their budget of {budget} s")
        except OSError as e:
            raise Erreur(f"history: {command[0]} unavailable ({propre(str(e), 200)})")
    base = launch(["git", "-C", tooling, "rev-parse", "HEAD"]).stdout.strip()
    if not REPO.fullmatch(repo) or not COMMIT.fullmatch(base):
        raise Erreur("history: the calling repository (GITHUB_REPOSITORY, owner/name) and the base's commit are required")
    for c in commits:
        r = launch(["gh", "api", f"repos/{repo}/compare/{base}...{c}", "--jq", ".status"],
                   {**os.environ, "GH_TOKEN": token} if token else None)
        if r.returncode != 0 or r.stdout.strip() not in ("identical", "behind"):
            raise Erreur(f"history: {c} is not in the ancestry of the base ({propre(r.stdout.strip() or r.stderr, 300)})")
    for c in commits:
        r = launch(["git", "-C", tooling, "fetch", "--quiet", "--no-tags", "--depth=1", "origin", f"{c}:refs/bee/historique/{c}"])
        if r.returncode != 0:
            raise Erreur(f"history: commit {c} not fetched from the base's origin: " + propre(r.stderr, 500))
    return commits


# ------------------------------------------------------------------ program

def options_of(list_of):
    options = {}
    for o in list_of or []:
        if "=" not in o:
            raise Erreur(f"invalid option (KEY=VALUE expected): {o}")
        key, value = o.split("=", 1)
        options[key.strip()] = value.strip()
    return options


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bee's common judge (see the module's help).")
    parser.add_argument("--tooling", required=True, help="copy of the PR's BASE (plugin bee/judge/project.py or bee/juge/projet.py)")
    parser.add_argument("--source-a")
    parser.add_argument("--source-b")
    parser.add_argument("--image-only", action="store_true",
                           help="builds the container's image (with network, before the PR) and prints its label")
    parser.add_argument("--history-only", action="store_true",
                           help="checks and fetches the declared history (--history) into the base, without loading the plugin")
    parser.add_argument("--history", default="", help="with --history-only: commits fetched into the base")
    parser.add_argument("--judge-source", help="REPO@COMMIT of this judge's code (judge.yml: the workflow's own commit)")
    parser.add_argument("--base", help="commit of A, recorded in judge.json (judge.yml: checked against the event)")
    parser.add_argument("--head", help="commit of B, recorded in judge.json (judge.yml: checked against the event)")
    parser.add_argument("--workdir", help="folder of the work directory (judge.yml: a size-bounded tmpfs)")
    parser.add_argument("--option", action="append", default=[], help="plugin option, KEY=VALUE (repeatable)")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--no-instructions", action="store_true")
    parser.add_argument("--instructions-prefix", type=int, default=131072)
    parser.add_argument("--instructions-threshold", type=float, default=0.002)
    parser.add_argument("--json")
    parser.add_argument("--seed", help="hexadecimal seed (local reproduction); default: drawn at random")
    parser.add_argument("--order-seed", help="hexadecimal seed of the scenarios' order (local reproduction); default: drawn at random, separately")
    parser.add_argument("--build-network", help="docker build's network ('host' without Docker's bridge)")
    parser.add_argument("--memory", default="4g")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    if args.repetitions < 1 or args.warmup < 0:
        parser.error("--repetitions: at least 1; --warmup: at least 0")
    if args.history and not args.history_only:
        parser.error("--history requires --history-only")
    if any(c is not None and not COMMIT.fullmatch(c) for c in (args.base, args.head)):
        parser.error("--base, --head: full commits (40 hexadecimal digits)")
    # Defence in depth: the plugin, loaded later in this process, does not find GH_TOKEN in os.environ (the value
    # stays in /proc/<pid>/environ: judge.yml gives the token to the --history-only call alone).
    token = os.environ.pop("GH_TOKEN", None)
    FAILURE.update(json=args.json, judge={"version": JUDGE_VERSION, "common": common_tag(), "source": args.judge_source,
                                        "base": args.base, "head": args.head})
    if args.history_only:
        print(" ".join(fetch_history(os.path.abspath(args.tooling), args.history, token)))
        return 0

    beginning = time.time()
    if shutil.which("docker") is None:
        raise Erreur("docker not found")
    tooling = os.path.abspath(args.tooling)
    if not args.image_only:
        os.environ["GIT_ALLOW_PROTOCOL"] = "none"  # judging: no git transport at all, the declared history is already here
    projet, plugin_fingerprint = load_plugin(tooling, options_of(args.option))
    if args.image_only:
        print(container.build_image(getattr(projet, "PAQUETS", ()), args.build_network))
        return 0
    if not (args.source_a and args.source_b):
        parser.error("--source-a and --source-b are required")
    sides_of = tuple(projet.COTES)
    travail = tempfile.mkdtemp(prefix="bee-juge-", dir=args.workdir)
    os.chmod(travail, 0o755)
    try:
        image = container.build_image(getattr(projet, "PAQUETS", ()), args.build_network)
        docker = container.Docker(container.image_id(image), args.memory)  # every container runs the image by its id
        source_a = copy_sources(args.source_a, os.path.join(travail, "sources-A"), projet.SOURCES, projet.SOURCES_REQUISES)
        source_b = copy_sources(args.source_b, os.path.join(travail, "sources-B"), projet.SOURCES, projet.SOURCES_REQUISES)
        tools = copy_tooling(tooling, source_a, os.path.join(travail, "outillage"), projet)
        stopwatch = container.compile_stopwatch(docker, travail)
        constructs = {v: os.path.join(travail, f"construction-{v}") for v in "AB"}
        surveys = {"A": build(docker, projet, source_a, tools, constructs["A"], "A", travail),
                   "B": build(docker, projet, source_b, tools, constructs["B"], "B", travail)}
        journal("A and B compiled in the container")

        suspects = analysis.analyse(surveys["A"], surveys["B"], texts_of(source_a), texts_of(source_b),
                                    prefixes=projet.PREFIXES, allowed_set=getattr(projet, "PERMIS", ()))
        architecture = platform.machine().lower()
        if architecture not in ANALYSED_ARCHITECTURES:
            # analysis.py knows only x86-64 instructions: elsewhere, the disassembly is not analyzed.
            suspects.append({"type": "architecture", "detail": f"{architecture}: the objects' instructions not analyzed "
                                                               "(analysis.py covers only x86-64)"})
        by_type = dict(sorted(collections.Counter(s["type"] for s in suspects).items()))
        suspects.sort(key=lambda s: SEVERITY.index(s["type"]) if s["type"] in SEVERITY else len(SEVERITY))
        omitted_ones, suspects = max(0, len(suspects) - SUSPICIOUS_MAX), suspects[:SUSPICIOUS_MAX]
        for s in suspects:
            journal(f"suspicious construct: {propre(s['detail'], 300)}")

        # The seed is drawn now, after compilation: nothing that was compiled knows it.
        seed = bytes.fromhex(args.seed) if args.seed else secrets.token_bytes(16)
        rng = random.Random(int.from_bytes(seed, "big"))
        corpus = projet.corpus(tooling)
        run = container.Execution(docker, stopwatch, {v: variant(constructs[v], os.path.join(travail, f"variante-{v}"))
                                                         for v in "AB"}, travail)
        compared_ones = 0

        # 1. Verification: the plugin chooses the inputs (corpus, drawn at random, invalid) and the rule.
        entrees = projet.verification(rng, corpus)
        inputs_module.verifier_entrees(entrees, sides_of)
        written_ones, neutral_ones = rename(rng, entrees)  # the plugin keeps its names, read through `noms`
        names = {(e.cote, e.nom): n for e, n in zip(entrees, neutral_ones)}
        folders = prepare(travail, "verification", written_ones, sides_of)
        roots = {}
        command = ["/variante/execution", "verifier", "/entrees", "/sorties"]
        for v in "AB":
            roots[v], figees = outputs_of(travail, f"sorties-verification-{v}", sides_of), {}
            for quoted_side in sides_of:
                run.launch(v, folders[quoted_side], roots[v][quoted_side], [("verifier", command)], timeout_seconds=3600)
                figees[quoted_side] = figer(roots[v][quoted_side])  # as soon as the container ends: only the frozen will be read
            roots[v] = Sorties(roots[v], names, figees)
        view_b = Sorties(roots["B"], names)
        compared_ones += counted_integer(projet.verifier(Sorties(roots["A"], names), view_b, entrees))
        require_coverage(view_b, entrees, "verification")
        if compared_ones == 0:
            raise Erreur("verification: no output compared: judge badly set up")
        fixes = {v: dict(projet.fixes(Sorties(roots[v], names), corpus)) for v in "AB"}
        for v in "AB":
            roots[v].controler()
        erase(roots["A"], folders)
        index = outputs_by_input(roots["B"].figees)
        journal(f"verification: {compared_ones} outputs of B correct ({len(entrees)} inputs)")
        # Verification inputs mixed into every measurement (ruche-0037), spread over the repetitions.
        by_side = {c: [e for e in entrees if e.cote == c] for c in set(projet.SCENARIOS.values())}
        if not all(by_side.values()):
            raise Erreur("a measured side has no verification input to mix into the measurements: invalid plugin")
        rounds = {c: round_number(rng, l) for c, l in by_side.items()}
        how_many = {c: -(-len(l) // (args.warmup + args.repetitions)) for c, l in by_side.items()}
        light_ones = {c: [e for e in l if max(len(e.donnees), e.taille) <= args.instructions_prefix]
                   for c, l in by_side.items() if c in {projet.SCENARIOS[s] for s in projet.INSTRUCTIONS}}
        without_shuffle = sorted(s for s in projet.INSTRUCTIONS if not light_ones.get(projet.SCENARIOS[s]))
        interleaved = 0

        # 2. Stopwatch measurements (the child's processor time, read by the kernel), A and B interleaved; the order of the
        #    scenarios is drawn at each repetition, the same for A and B, from a generator of its own whose seed (secrets,
        #    recorded in judge.scenarios.order_seed) does not depend on the inputs' seed.
        graine_ordre = bytes.fromhex(args.order_seed) if args.order_seed else secrets.token_bytes(16)
        measurements, draw, unfolding, timed = {"A": [], "B": []}, random.Random(graine_ordre), [], set()
        for i in range(args.warmup + args.repetitions):
            entrees, shuffled = interleave(rng, projet.repetition(rng, corpus), rounds, how_many, names)
            interleaved += len(shuffled)
            folders = prepare(travail, f"repetition-{i}", entrees, sides_of)
            plans = {c: [(s, ["/variante/execution", s, "/entrees", "/sorties"]) for s, cs in projet.SCENARIOS.items() if cs == c]
                     for c in sides_of}
            outputs, raw, order = {}, {}, draw.sample(list(projet.SCENARIOS), len(projet.SCENARIOS))
            variants_of = ("A", "B") if i % 2 == 0 else ("B", "A")
            for v in variants_of:
                raw[v], outputs[v] = launch_by_side(run, v, folders, outputs_of(travail, f"sorties-{i}-{v}", sides_of), plans,
                                                       order)
            for v in "AB":
                values_of = dict(fixes[v])  # a scenario's value of a fixed metric, read on its timed outputs, replaces it
                for s, quoted_side in projet.SCENARIOS.items():
                    view = Sorties(outputs[v])
                    vals, n = projet.scenario(s, Sorties(outputs["A"]), view, entrees, raw[v][s])
                    compared_ones += counted_integer(n)
                    require_coverage(view, [e for e in entrees if e.cote == quoted_side], f"scenario {s} ({v})")
                    values_of.update(vals)
                    timed |= set(vals)
                if i >= args.warmup:
                    measurements[v].append(values_of)
                outputs[v].controler()
            compared_ones += same_outputs(index, roots["B"], outputs["B"], shuffled, projet.SCENARIOS.items())
            unfolding.append(step("warmup" if i < args.warmup else "measurement", variants_of, order, raw))
            erase(outputs["A"], outputs["B"], folders)
            journal(f"repetition {i + 1}/{args.warmup + args.repetitions} ({'warmup' if i < args.warmup else 'measured'}) done")

        report = {
            "repetitions": args.repetitions, "warmup": args.warmup, "order": "A, B then B, A, alternately; scenarios: judge.scenarios",
            "machine": stats.description_machine(),
            "method": {
                "retained_value": "median of the repetitions",
                "gain": "median(B)/median(A) - 1 (higher); 1 - median(B)/median(A) (lower); positive = better",
                "beyond_noise": f"sign test on the interleaved pairs, as in ab.py (k = {stats.sign_threshold(args.repetitions)} of {args.repetitions})",
                "stopwatch": ("processor time (user + system) of the process that runs a scenario, read by the "
                                "common judge's chrono launcher with wait4; one execution per scenario and per repetition, "
                                "on inputs perturbed at each repetition"),
            },
            "metrics": {}, "measurements": {"A": {}, "B": {}},
        }
        report["method"].update(getattr(projet, "METHODE", {}))
        # A fixed metric that no scenario computes from its timed outputs is read on verification alone (ruche-0117): flagged, and
        # never beyond the noise (its value is the same at every repetition, which the sign test would take for a sure gain).
        without_measurement = sorted((set(fixes["A"]) | set(fixes["B"])) - timed)
        for nom, direction, unit in projet.METRIQUES:
            values_a = [m.get(nom) for m in measurements["A"]]
            values_b = [m.get(nom) for m in measurements["B"]]
            a, b = stats.summary(values_a), stats.summary(values_b)
            sign_char = stats.sign_test(values_a, values_b, direction)
            report["metrics"][nom] = {
                "direction": DIRECTIONS[direction], "unit": unit, "A": a, "B": b, "gain": stats.relative_gain(a["median"], b["median"], direction),
                "beyond_noise": sign_char["beyond_noise"] and nom not in without_measurement,
                "degradation_beyond_noise": sign_char["degradation_beyond_noise"], "verification_only": nom in without_measurement,
                "sign_test": sign_char,
                "minmax_disjoint": (a["median"] is not None and b["median"] is not None and (a["max"] < b["min"] or b["max"] < a["min"])),
            }
            report["measurements"]["A"][nom] = a["median"]
            report["measurements"]["B"][nom] = b["median"]

        # 3. Instruction count: Valgrind in the container, the whole process, its summary read by chrono.
        if not args.no_instructions and projet.INSTRUCTIONS:
            entrees, shuffled = interleave(rng, projet.instructions(rng, corpus, args.instructions_prefix), {c: round_number(rng, l) for c, l
                                     in light_ones.items()}, {c: min(how_many[c], len(l)) for c, l in light_ones.items()}, names)
            interleaved += len(shuffled)
            folders = prepare(travail, "instructions", entrees, sides_of)
            plans = {c: [(s, VALGRIND + ["/variante/execution", s, "/entrees", "/sorties"])
                         for s in projet.INSTRUCTIONS if projet.SCENARIOS[s] == c] for c in sides_of}
            accounts, outputs, order = {}, {}, draw.sample(list(projet.INSTRUCTIONS), len(projet.INSTRUCTIONS))
            for v in "AB":
                accounts[v], outputs[v] = launch_by_side(run, v, folders, outputs_of(travail, f"sorties-instructions-{v}", sides_of),
                                                         plans, order, valgrind=True, timeout_seconds=3600)
            for s in projet.INSTRUCTIONS:
                view = Sorties(outputs["B"])
                _, n = projet.scenario(s, Sorties(outputs["A"]), view, entrees, accounts["B"][s])
                compared_ones += counted_integer(n)
                require_coverage(view, [e for e in entrees if e.cote == projet.SCENARIOS[s]], f"instructions {s}")
            for v in "AB":
                outputs[v].controler()
            compared_ones += same_outputs(index, roots["B"], outputs["B"], shuffled, [(s, projet.SCENARIOS[s]) for s in projet.INSTRUCTIONS])
            unfolding.append(step("instructions", "AB", order, accounts))
            erase(outputs["A"], outputs["B"], folders)
            report["instructions"] = {}
            for s in projet.INSTRUCTIONS:
                a, b = accounts["A"][s]["instructions"], accounts["B"][s]["instructions"]
                gain = stats.relative_gain(a, b, "plus_bas")
                report["instructions"]["instructions_" + s] = {
                    "direction": "lower", "unit": "instructions", "A": a, "B": b, "gain": gain,
                    "beyond_noise": gain is not None and abs(gain) > args.instructions_threshold}
            report["method"]["instructions"] = (
                f"valgrind --tool=cachegrind in the container, the harness's whole process (nothing escapes the count), "
                f"the plugin's inputs (a prefix of {args.instructions_prefix} bytes), perturbed; summary read by "
                f"chrono on Valgrind's last line; beyond the noise if the difference exceeds {100 * args.instructions_threshold:.2f}%")

        verification = {"outputs_compared": compared_ones, "inputs_mixed": interleaved, "mixed_per_repetition": how_many,
                        "instructions_without_mixing": without_shuffle, "fixed_without_measurement": without_measurement}
        verification.update(getattr(projet, "VERIFICATION", {}))
        report["judge"] = {
            "version": JUDGE_VERSION,
            "common": common_tag(),
            "source": args.judge_source,
            "base": args.base, "head": args.head,
            "project": projet.NOM,
            "plugin": plugin_fingerprint,
            "code": 0, "outcome": ISSUES[0],
            "seed": seed.hex(),
            # A seed given on the command line is a local reproduction, never a judgement: report.py --verify refuses it.
            "seed_origin": {"seed": "given" if args.seed else "drawn", "order_seed": "given" if args.order_seed else "drawn"},
            "image": image,
            "image_id": docker.image,
            "suspicious_constructs_omitted": omitted_ones, "suspicious_constructs_by_type": by_type,
            "isolation": " ".join(container.ISOLATION + container.Docker.BOUNDS) + " --pids-limit 2 (execution), 64 (compilation); "
                         f"each execution on its own tmpfs ({container.TMPFS}), filled anew",
            "verification": verification,
            "analysis": {"architecture": platform.machine().lower(), "prefixes": list(projet.PREFIXES),
                         "allowed": list(getattr(projet, "PERMIS", ()))},
            "suspicious_constructs": suspects,
            "scenarios": {"separation": "one container per scenario (verification: one per side); its outputs frozen (SHA-256 of each "
                          "file, and the listing) when the container ends, the only ones read: a difference afterwards is a refusal",
                          "order": "drawn at each repetition, the same for A and B", "order_seed": graine_ordre.hex(),
                          "cpu_time": "user + system, wait4 in chrono (not the cgroup); under Valgrind in « instructions »",
                          "steps": unfolding},
        }
        report["duration_s"] = round(time.time() - beginning, 1)
    finally:
        if args.keep:
            journal(f"work folder kept: {travail}")
        else:
            shutil.rmtree(travail, ignore_errors=True)

    stats.show_table(report)
    text = write_report(args.json, report)
    print(text)
    return 0


def write_report(path, report):
    """judge.json, whole or not at all (a temporary file renamed onto it); its text, every lone surrogate replaced."""
    text = re.sub("[\ud800-\udfff]", "\ufffd", json.dumps(report, ensure_ascii=False, indent=2))
    if path:
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        fd, temporary_dir = tempfile.mkstemp(dir=folder, prefix=".juge-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            os.replace(temporary_dir, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temporary_dir)
            raise
    return text


def stop_it(code, message, fault=False):
    """The judge stops (1 refusal, 2 error): the message on standard error and, with --json, in judge.json (ruche-0136)."""
    print(message, file=sys.stderr)
    try:
        write_report(FAILURE.get("json"), {"judge": dict(FAILURE.get("judge", {}), code=code, outcome=ISSUES[code], machine_failure=fault,
                                                         reason=message)})
    except (OSError, ValueError):  # no report, never a stale or partial one: report.py --code keeps the exit code
        with contextlib.suppress(OSError, TypeError):
            os.unlink(FAILURE.get("json"))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refus as e:
        sys.exit(stop_it(1, f"judge: REFUSAL: {propre(str(e), 3000)}"))
    except Erreur as e:
        sys.exit(stop_it(2, f"judge: error: {propre(str(e), 3000)}", isinstance(e, Panne)))
    except Exception:  # noqa: BLE001 — a defect of the judge or of the plugin: never a success, never a raw traceback
        sys.exit(stop_it(2, "judge: internal error (judge or plugin): " + propre(traceback.format_exc(), 3000)))
