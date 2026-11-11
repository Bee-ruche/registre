#!/usr/bin/env python3
"""Juge commun Bee : exécuter le code d'une PR en conteneur et le juger de l'extérieur, pour tout projet.

Spécification : docs/juge-commun.md du registre. Le juge commun fait ce qui protège et ne dépend
d'aucun projet ; le GREFFON du projet (bee/juge/projet.py du fork, lu depuis la BASE de la PR, jamais
depuis la PR) dit comment construire, quelles entrées donner, comment vérifier et que mesurer.

Ce que garantit le juge commun, quel que soit le greffon :
- ce programme (l'hôte) n'exécute JAMAIS un fichier issu de la PR. Compilation, exécution et décompte
  d'instructions ont lieu dans des conteneurs sans réseau, en lecture seule, sans privilège, limités à
  deux processus pour l'exécution, qui ne voient que leurs entrées et un dossier de sorties ;
- chaque côté d'entrées (« f », « z »…) a son propre conteneur : un harnais ne voit jamais les entrées
  d'un autre côté ; chaque scénario a le sien, avec ses seules sorties, figées (SHA-256) dès la fin du
  conteneur : la comparaison ne lit que ce qui a été figé ; leur ordre est tiré à chaque répétition ;
- la graine des entrées tirées au hasard est choisie ici, APRÈS la compilation ; le greffon perturbe les
  entrées des mesures à chaque répétition ;
- le temps processeur et la mémoire sont mesurés par le noyau (wait4) dans le lanceur chrono du juge
  commun, compilé à part ; le décompte d'instructions couvre tout le processus du harnais et se lit sur
  la dernière ligne de Valgrind ;
- les sorties ne sont lues qu'à travers lecture.py (sans lien, sans fichier spécial, taille bornée) ;
- une analyse des objets compilés (analysis.py) liste les constructions suspectes.

Usage :
  python3 tools/judge/judge.py --tooling BASE --image-only
  python3 tools/judge/judge.py --tooling BASE --source-a DOSSIER --source-b DOSSIER [--option CLE=VALEUR]…
                              [--repetitions 10] [--warmup 1] [--no-instructions] [--instructions-prefix 131072]
                              [--json juge.json] [--seed HEX]
                              [--build-network host]
  --tooling : copie de la BASE de la PR (son bee/juge/projet.py est le greffon)
  --source-a / --source-b : dépôts de la référence (A, la base) et de la candidate (B, la PR)
Sortie : rapport JSON au format d'ab.py (mesures, metriques, instructions) plus une section « juge ».
Code de sortie : 0 si toutes les sorties de B sont justes, 1 si le juge refuse B, 2 si l'environnement
ne convient pas (Docker absent, base qui ne compile pas, greffon invalide, juge mal monté), une panne de la machine
(Docker, son runtime, l'image) comprise. With --json, juge.json says it in every case (juge.code, juge.issue: ISSUES).
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

COMMON_VERSION = 3   # étiquette juge-v3 du registre
JUDGE_VERSION = 3      # numérotation de verdict.json : 2 = juge de minizBee (miniz-0031), 3 = juge commun (its tag in « commun »)
ISSUES = {0: "juste", 1: "refus", 2: "erreur_environnement"}  # juge.json's juge.issue for each exit code (ruche-0136)
FAILURE = {}  # what juge.json says when the judge stops (code 1 or 2): its path and the judge's identity, set by main
PLUGIN_PATH = os.path.join("bee", "juge", "projet.py")
REQUIRED_ATTRIBUTES = ("NOM", "SOURCES", "SOURCES_REQUISES", "OUTILLAGE", "EN_TETES_BASE", "CONSTRUIRE",
                    "PREFIXES", "COTES", "SCENARIOS", "INSTRUCTIONS", "METRIQUES")
REQUIRED_METHODS = ("corpus", "verification", "verifier", "fixes", "repetition", "instructions", "scenario")
SURVEYS = (("symboles", "symboles.txt"), ("sections", "sections.txt"), ("desassemblage", "desassemblage.txt"))
OBJECT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}\.o")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
PREFIX = re.compile(r"[A-Za-z][A-Za-z0-9]{0,30}_")  # un mot suivi de « _ » : frontière d'identifiant
ALLOWED_MAX = 64
SUSPICIOUS_MAX = 100  # juge.json lists at most this many suspicious constructs and counts the rest (constructions_suspectes_omises)
# Kinds of suspicious construct, the most serious first: juge.json lists them in this order, and counts each kind (ruche-0117).
SEVERITY = ("analyse_incomplete", "architecture", "appel_interdit", "symbole_interdit", "instruction", "octets", "section", "symbole",
           "symbole_defini", "appel_externe", "source")
NEVER_ALLOWED = analysis.NEVER_ALLOWED
UNITS = (".c", ".S", ".s", ".cc", ".cpp", ".cxx")  # unités de traduction : chacune doit laisser son objet
ANALYSED_ARCHITECTURES = ("x86_64", "amd64")  # mnémoniques et préambule de Valgrind connus d'analyse.py
VALGRIND = ["/usr/bin/valgrind", "--tool=cachegrind", "--cache-sim=no", "--vgdb=no", "--cachegrind-out-file=/dev/null"]
COMMIT, HISTORY_MAX, REPO = re.compile(r"[0-9a-f]{40}"), 16, re.compile(r"[A-Za-z0-9-]+/(?!\.\.?$)[A-Za-z0-9_.-]+")


# ------------------------------------------------------------------ greffon

def load_plugin(tooling, options):
    """Charge bee/juge/projet.py de l'outillage (la BASE) et vérifie qu'il respecte le contrat."""
    path = os.path.join(tooling, PLUGIN_PATH)
    if not os.path.isfile(path) or os.path.islink(path):
        raise Erreur(f"greffon introuvable : {PLUGIN_PATH} dans {tooling}")
    with open(path, "rb") as f:
        fingerprint = hashlib.sha256(f.read()).hexdigest()
    spec = importlib.util.spec_from_file_location("bee_greffon_projet", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "Projet"):
        raise Erreur("le greffon ne définit pas de classe Projet")
    projet = module.Projet(dict(options))
    missing_items = [a for a in REQUIRED_ATTRIBUTES if not hasattr(projet, a)] + \
                [m for m in REQUIRED_METHODS if not callable(getattr(projet, m, None))]
    if missing_items:
        raise Erreur("greffon incomplet : " + ", ".join(missing_items))
    sides_of = tuple(projet.COTES)
    if not sides_of or any(not inputs_module.COTE_PERMIS.fullmatch(c) for c in sides_of) or len(set(sides_of)) != len(sides_of):
        raise Erreur("COTES du greffon invalides")
    for s, c in projet.SCENARIOS.items():
        if c not in sides_of or not inputs_module.NOM_PERMIS.fullmatch(s):
            raise Erreur(f"scénario invalide dans le greffon : {s}")
    if any(s not in projet.SCENARIOS for s in projet.INSTRUCTIONS):
        raise Erreur("INSTRUCTIONS du greffon : scénario inconnu")
    # Espace de noms et fonctions permises : un préfixe vide ou trop court éteindrait deux catégories de
    # l'analyse des objets (revue adverse du 28/10) ; les fonctions qui trompent la mesure ne sont jamais permises.
    prefixes, allowed_set = tuple(projet.PREFIXES), tuple(getattr(projet, "PERMIS", ()))
    if not prefixes or any(not isinstance(p, str) or not PREFIX.fullmatch(p) for p in prefixes):
        raise Erreur("PREFIXES du greffon invalides : au moins un préfixe, chacun un mot terminé par « _ » (mz_, yaml_…)")
    covering = sorted(n for n in NEVER_ALLOWED if n.startswith(prefixes))
    if covering:
        raise Erreur("PREFIXES du greffon : couvriraient des fonctions jamais permises : " + ", ".join(covering))
    if len(allowed_set) > ALLOWED_MAX or any(not isinstance(n, str) or not IDENTIFIER.fullmatch(n) for n in allowed_set):
        raise Erreur(f"PERMIS du greffon invalide : au plus {ALLOWED_MAX} noms de fonctions")
    forbidden_items = sorted(set(allowed_set) & NEVER_ALLOWED)
    if forbidden_items:
        raise Erreur("PERMIS du greffon : fonctions jamais permises : " + ", ".join(forbidden_items))
    if hasattr(projet, "DIFF"):
        raise Erreur("DIFF n'existe plus : le diff analysé est celui de SOURCES (revue adverse du 28/10)")
    for relative_path in list(projet.OUTILLAGE) + [projet.CONSTRUIRE]:
        if os.path.isabs(relative_path) or ".." in relative_path.split("/"):
            raise Erreur(f"chemin d'outillage invalide dans le greffon : {relative_path}")
    return projet, fingerprint


# ------------------------------------------------------------------ préparation et construction

def _no_link(repo, relative_one):
    """Vrai si aucun composant de depot/relatif n'est un lien symbolique et si c'est un fichier ordinaire."""
    path = repo
    chunks = relative_one.split(os.sep)
    for i, m in enumerate(chunks):
        path = os.path.join(path, m)
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            raise Refus(f"{relative_one} : lien symbolique refusé")
        if i < len(chunks) - 1 and not stat.S_ISDIR(st.st_mode):
            return False
    return stat.S_ISREG(os.lstat(path).st_mode)


def copy_sources(repo, destination, reasons, required_items):
    """Copie les fichiers du projet (motifs glob relatifs à la racine) en refusant tout lien symbolique."""
    os.makedirs(destination, exist_ok=True)
    repo = os.path.abspath(repo)
    found_items = set()
    for reason in reasons:
        if os.path.isabs(reason) or ".." in reason.split("/"):
            raise Erreur(f"motif de sources invalide : {reason}")
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
            raise Refus(f"{r} introuvable dans {repo}")
    return destination


def copy_tooling(tooling, source_a, destination, projet):
    """Ce que la BASE fournit au conteneur : ses dossiers d'outillage (OUTILLAGE) et ses en-têtes (EN_TETES_BASE).

    Les en-têtes de la base sont copiés dans /outillage/base/ : le harnais se compile avec eux, pas avec
    ceux de la PR (une macro glissée dans un en-tête de la PR ne peut pas réécrire le harnais)."""
    for relative_one in projet.OUTILLAGE:
        source = os.path.join(tooling, relative_one)
        if os.path.islink(source) or not os.path.isdir(source):
            raise Erreur(f"dossier d'outillage absent de la base : {relative_one}")
        shutil.copytree(source, os.path.join(destination, relative_one), symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    copy_sources(source_a, os.path.join(destination, "base"), projet.EN_TETES_BASE, ())
    return destination


def expected_objects(sources):
    """Un objet obj/<nom>.o par unité de traduction (.c, .S, .cc…) copiée des SOURCES de la variante.

    Deux unités de même nom dans deux dossiers ne peuvent pas laisser chacune son objet : refusé (None)."""
    seen_items = {}
    for folder, _, names in os.walk(sources):
        for n in names:
            root, extension = os.path.splitext(n)
            if extension in UNITS:
                seen_items.setdefault(root + ".o", []).append(os.path.relpath(os.path.join(folder, n), sources))
    duplicate_items = sorted(c for c, l in seen_items.items() if len(l) > 1)
    return set(seen_items), duplicate_items


def build(docker, projet, sources, tooling, output_text, label, travail):
    """Compile une variante dans le conteneur (script CONSTRUIRE de la base), puis relève ses objets.

    Contrat du script : le harnais lié dans <sortie>/execution, et CHAQUE objet du projet dans
    <sortie>/obj/<nom>.o (un par fichier .c des SOURCES). Les relevés d'analyse (nm, objdump) sont produits
    ensuite par le juge commun lui-même, sur tous ces objets : un script de construction ne peut ni les
    omettre ni les vider (revue adverse du 28/10)."""
    container.open_folder(output_text)
    command = ["sh", "/outillage/" + projet.CONSTRUIRE, "/sources", "/outillage", "/sortie"]
    r = docker.launch(command, [(sources, "/sources", True), (tooling, "/outillage", True), (output_text, "/sortie", False)],
                      pids=64, timeout_seconds=900)
    failure = Erreur if label == "A" else Refus
    if r.returncode != 0:
        raise failure(f"la compilation de {label} a échoué : " + propre(r.stderr))
    obj_folder = os.path.join(output_text, "obj")
    if os.path.islink(obj_folder) or not os.path.isdir(obj_folder):
        raise failure(f"{label} : pas de dossier obj/ après la construction")
    objects_found = []
    for n in sorted(os.listdir(obj_folder)):
        st = os.lstat(os.path.join(obj_folder, n))
        if not n.endswith(".o"):
            continue
        if not OBJECT.fullmatch(n) or not stat.S_ISREG(st.st_mode):
            raise failure(f"{label} : objet invalide dans obj/ : {propre(n, 80)}")
        objects_found.append(n)
    expected_items, duplicate_items = expected_objects(sources)
    if duplicate_items:
        raise failure(f"{label} : unités de traduction homonymes (un seul objet possible dans obj/) : "
                    + ", ".join(propre(d, 80) for d in duplicate_items[:10]))
    missing_items = sorted(expected_items - set(objects_found))
    if missing_items:
        raise failure(f"{label} : fichier(s) source(s) sans objet dans obj/ (non compilés ou non relevables) : "
                    + ", ".join(propre(m, 80) for m in missing_items[:10]))
    if not objects_found:
        raise failure(f"{label} : aucun objet dans obj/")
    surveys_folder = container.open_folder(os.path.join(travail, f"releves-{label}"))
    script = ('umask 000 && cd /construction/obj && nm -P -A "$@" > /releves/symboles.txt'
              ' && objdump -h "$@" > /releves/sections.txt && objdump -d --no-show-raw-insn "$@" > /releves/desassemblage.txt')
    r = docker.launch(["sh", "-c", script, "releves"] + objects_found,
                      [(output_text, "/construction", True), (surveys_folder, "/releves", False)], pids=64, timeout_seconds=900)
    if r.returncode != 0:
        raise failure(f"{label} : relevés d'analyse impossibles : " + propre(r.stderr))
    surveys = {key: exiger(surveys_folder, nom, 256 << 20).decode("utf-8", "replace") for key, nom in SURVEYS}
    for o in objects_found:  # chaque objet figure dans chaque relevé (objdump : « <objet>:     file format … »)
        if not any(line_text.startswith(o + ":") for line_text in surveys["desassemblage"].splitlines()) or \
           not any(line_text.startswith(o + ":") for line_text in surveys["sections"].splitlines()):
            raise Erreur(f"{label} : {o} absent des relevés d'analyse : juge mal monté")
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


# ------------------------------------------------------------------ exécution

def prepare(travail, nom, entrees, sides_of):
    """Écrit les entrées, un dossier par côté ; renvoie {côté: dossier}."""
    inputs_module.verifier_entrees(entrees, sides_of)
    folders = {}
    for c in sides_of:
        folders[c] = os.path.join(travail, secrets.token_hex(8))  # a neutral name, the same kind in every mode
        inputs_module.ecrire(folders[c], [e for e in entrees if e.cote == c], sides_of)
    return folders


def outputs_of(travail, nom, sides_of):
    return {c: container.open_folder(os.path.join(travail, secrets.token_hex(8))) for c in sides_of}


def launch_by_side(run, variant, folders, outputs, plans, order, **options):
    """Un conteneur par scénario, dans l'ordre tiré (ruche-0036), ses sorties sur /sorties comme la vérification (dossier
    neutre, puis <côté>/<scénario>), figées dès la fin du conteneur. Renvoie (mesures, Sorties qui ne lit que le figé)."""
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
    """Une étape de juge.json : ordre des variantes et des scénarios, temps processeur de chaque scénario (wait4, chrono)."""
    return {"etape": nom, "variantes": "".join(variants_of), "ordre": list(order), "temps_processeur_s": {
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
                        raise Refus(f"scénario {s} : sortie de B différente de sa sortie en vérification pour la même entrée")
            if not views:
                raise Erreur(f"{quoted_side}/{nom}, scénario {s} : aucune sortie de B comparable à la vérification (mêmes sorties attendues)")
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
        raise Erreur("le greffon doit renvoyer un nombre de sorties comparées (entier positif)")
    return n


def require_coverage(outputs_b, entrees, step):
    """Chaque entrée doit avoir eu au moins une sortie de B lue par le greffon pendant l'étape."""
    forgotten_ones = [e.nom for e in entrees if not outputs_b.couvre(e.cote, e.nom)]
    if forgotten_ones:
        raise Erreur(f"{step} : le greffon n'a lu aucune sortie de B pour {len(forgotten_ones)} entrée(s) "
                     f"({', '.join(forgotten_ones[:5])}) : juge mal monté")


# ------------------------------------------------------------------ declared history

def fetch_history(tooling, text, token=None, budget=600):
    """Fetches into the base's repository the commits its plugin reads (juge.yml's `historique`), with their trees
    and blobs but no history. Each must be in the base's ancestry, as GitHub's compare API on the calling repository
    (GITHUB_REPOSITORY) says (identical or behind), all checked before any fetch; checks and fetches share one time
    budget. juge.yml runs it in its own step (--history-only), the only call of judge.py given a token
    (GH_TOKEN, passed to gh alone), before anything loads the plugin and before the PR."""
    commits, repo = sorted(set(text.split())), os.environ.get("GITHUB_REPOSITORY", "")
    if len(commits) > HISTORY_MAX or not all(COMMIT.fullmatch(c) for c in commits):
        raise Erreur(f"historique : at most {HISTORY_MAX} full commit SHAs (40 hexadecimal digits), separated by blanks")
    if not commits:
        return []
    end = time.monotonic() + budget

    def launch(command, env=None):
        try:
            return subprocess.run(command, capture_output=True, text=True, errors="replace", env=env,
                                  timeout=max(0.01, end - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise Erreur(f"historique : checks and fetches exceeded their budget of {budget} s")
        except OSError as e:
            raise Erreur(f"historique : {command[0]} unavailable ({propre(str(e), 200)})")
    base = launch(["git", "-C", tooling, "rev-parse", "HEAD"]).stdout.strip()
    if not REPO.fullmatch(repo) or not COMMIT.fullmatch(base):
        raise Erreur("historique : the calling repository (GITHUB_REPOSITORY, owner/name) and the base's commit are required")
    for c in commits:
        r = launch(["gh", "api", f"repos/{repo}/compare/{base}...{c}", "--jq", ".status"],
                   {**os.environ, "GH_TOKEN": token} if token else None)
        if r.returncode != 0 or r.stdout.strip() not in ("identical", "behind"):
            raise Erreur(f"historique : {c} is not in the ancestry of the base ({propre(r.stdout.strip() or r.stderr, 300)})")
    for c in commits:
        r = launch(["git", "-C", tooling, "fetch", "--quiet", "--no-tags", "--depth=1", "origin", f"{c}:refs/bee/historique/{c}"])
        if r.returncode != 0:
            raise Erreur(f"historique : commit {c} not fetched from the base's origin : " + propre(r.stderr, 500))
    return commits


# ------------------------------------------------------------------ programme

def options_of(list_of):
    options = {}
    for o in list_of or []:
        if "=" not in o:
            raise Erreur(f"option invalide (CLE=VALEUR attendu) : {o}")
        key, value = o.split("=", 1)
        options[key.strip()] = value.strip()
    return options


def main(argv=None):
    parser = argparse.ArgumentParser(description="Juge commun Bee (voir l'aide du module).")
    parser.add_argument("--tooling", required=True, help="copie de la BASE de la PR (greffon bee/juge/projet.py)")
    parser.add_argument("--source-a")
    parser.add_argument("--source-b")
    parser.add_argument("--image-only", action="store_true",
                           help="construit l'image du conteneur (avec réseau, avant la PR) et affiche son étiquette")
    parser.add_argument("--history-only", action="store_true",
                           help="checks and fetches the declared history (--history) into the base, without loading the plugin")
    parser.add_argument("--history", default="", help="with --history-only: commits fetched into the base")
    parser.add_argument("--judge-source", help="DEPOT@COMMIT of this judge's code (juge.yml: the workflow's own commit)")
    parser.add_argument("--base", help="commit of A, recorded in juge.json (juge.yml: checked against the event)")
    parser.add_argument("--head", help="commit of B, recorded in juge.json (juge.yml: checked against the event)")
    parser.add_argument("--workdir", help="folder of the work directory (juge.yml: a size-bounded tmpfs)")
    parser.add_argument("--option", action="append", default=[], help="option du greffon, CLE=VALEUR (répétable)")
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--no-instructions", action="store_true")
    parser.add_argument("--instructions-prefix", type=int, default=131072)
    parser.add_argument("--instructions-threshold", type=float, default=0.002)
    parser.add_argument("--json")
    parser.add_argument("--seed", help="graine hexadécimale (reproduction locale) ; défaut : tirée au hasard")
    parser.add_argument("--order-seed", help="graine hexadécimale de l'ordre des scénarios (reproduction locale) ; défaut : tirée au hasard, à part")
    parser.add_argument("--build-network", help="réseau de docker build (« host » sans pont Docker)")
    parser.add_argument("--memory", default="4g")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)
    if args.repetitions < 1 or args.warmup < 0:
        parser.error("--repetitions : au moins 1 ; --warmup : au moins 0")
    if args.history and not args.history_only:
        parser.error("--history va avec --history-only")
    if any(c is not None and not COMMIT.fullmatch(c) for c in (args.base, args.head)):
        parser.error("--base, --head : full commits (40 hexadecimal digits)")
    # Defence in depth: the plugin, loaded later in this process, does not find GH_TOKEN in os.environ (the value
    # stays in /proc/<pid>/environ: juge.yml gives the token to the --historique-seulement call alone).
    token = os.environ.pop("GH_TOKEN", None)
    FAILURE.update(json=args.json, juge={"version": JUDGE_VERSION, "commun": f"juge-v{COMMON_VERSION}", "source": args.judge_source,
                                       "base": args.base, "tete": args.head})
    if args.history_only:
        print(" ".join(fetch_history(os.path.abspath(args.tooling), args.history, token)))
        return 0

    beginning = time.time()
    if shutil.which("docker") is None:
        raise Erreur("docker introuvable")
    tooling = os.path.abspath(args.tooling)
    if not args.image_only:
        os.environ["GIT_ALLOW_PROTOCOL"] = "none"  # judging: no git transport at all, the declared history is already here
    projet, plugin_fingerprint = load_plugin(tooling, options_of(args.option))
    if args.image_only:
        print(container.build_image(getattr(projet, "PAQUETS", ()), args.build_network))
        return 0
    if not (args.source_a and args.source_b):
        parser.error("--source-a et --source-b sont requis")
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
        journal("A et B compilés dans le conteneur")

        suspects = analysis.analyse(surveys["A"], surveys["B"], texts_of(source_a), texts_of(source_b),
                                    prefixes=projet.PREFIXES, allowed_set=getattr(projet, "PERMIS", ()))
        architecture = platform.machine().lower()
        if architecture not in ANALYSED_ARCHITECTURES:
            # analyse.py ne connaît que les instructions x86-64 : ailleurs, le désassemblage n'est pas analysé.
            suspects.append({"type": "architecture", "detail": f"{architecture} : instructions des objets non analysées "
                                                               "(analysis.py ne couvre que x86-64)"})
        by_type = dict(sorted(collections.Counter(s["type"] for s in suspects).items()))
        suspects.sort(key=lambda s: SEVERITY.index(s["type"]) if s["type"] in SEVERITY else len(SEVERITY))
        omitted_ones, suspects = max(0, len(suspects) - SUSPICIOUS_MAX), suspects[:SUSPICIOUS_MAX]
        for s in suspects:
            journal(f"construction suspecte : {propre(s['detail'], 300)}")

        # La graine est tirée maintenant, après la compilation : rien de ce qui a été compilé ne la connaît.
        seed = bytes.fromhex(args.seed) if args.seed else secrets.token_bytes(16)
        rng = random.Random(int.from_bytes(seed, "big"))
        corpus = projet.corpus(tooling)
        run = container.Execution(docker, stopwatch, {v: variant(constructs[v], os.path.join(travail, f"variante-{v}"))
                                                         for v in "AB"}, travail)
        compared_ones = 0

        # 1. Vérification : le greffon choisit les entrées (corpus, tirées au hasard, invalides) et la règle.
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
                figees[quoted_side] = figer(roots[v][quoted_side])  # dès la fin du conteneur : seul le figé sera lu
            roots[v] = Sorties(roots[v], names, figees)
        view_b = Sorties(roots["B"], names)
        compared_ones += counted_integer(projet.verifier(Sorties(roots["A"], names), view_b, entrees))
        require_coverage(view_b, entrees, "vérification")
        if compared_ones == 0:
            raise Erreur("vérification : aucune sortie comparée : juge mal monté")
        fixes = {v: dict(projet.fixes(Sorties(roots[v], names), corpus)) for v in "AB"}
        for v in "AB":
            roots[v].controler()
        erase(roots["A"], folders)
        index = outputs_by_input(roots["B"].figees)
        journal(f"vérification : {compared_ones} sorties de B justes ({len(entrees)} entrées)")
        # Verification inputs mixed into every measurement (ruche-0037), spread over the repetitions.
        by_side = {c: [e for e in entrees if e.cote == c] for c in set(projet.SCENARIOS.values())}
        if not all(by_side.values()):
            raise Erreur("un côté mesuré n'a aucune entrée de vérification à mêler aux mesures : greffon invalide")
        rounds = {c: round_number(rng, l) for c, l in by_side.items()}
        how_many = {c: -(-len(l) // (args.warmup + args.repetitions)) for c, l in by_side.items()}
        light_ones = {c: [e for e in l if max(len(e.donnees), e.taille) <= args.instructions_prefix]
                   for c, l in by_side.items() if c in {projet.SCENARIOS[s] for s in projet.INSTRUCTIONS}}
        without_shuffle = sorted(s for s in projet.INSTRUCTIONS if not light_ones.get(projet.SCENARIOS[s]))
        interleaved = 0

        # 2. Mesures au chronomètre (temps processeur du fils, lu par le noyau), A et B entrelacés ; l'ordre des
        #    scénarios est tiré à chaque répétition, le même pour A et B, d'un générateur à part dont la graine (secrets,
        #    consignée dans juge.scenarios.graine_ordre) ne dépend pas de celle des entrées.
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
                    require_coverage(view, [e for e in entrees if e.cote == quoted_side], f"scénario {s} ({v})")
                    values_of.update(vals)
                    timed |= set(vals)
                if i >= args.warmup:
                    measurements[v].append(values_of)
                outputs[v].controler()
            compared_ones += same_outputs(index, roots["B"], outputs["B"], shuffled, projet.SCENARIOS.items())
            unfolding.append(step("chauffe" if i < args.warmup else "mesure", variants_of, order, raw))
            erase(outputs["A"], outputs["B"], folders)
            journal(f"répétition {i + 1}/{args.warmup + args.repetitions} ({'chauffe' if i < args.warmup else 'mesurée'}) faite")

        report = {
            "repetitions": args.repetitions, "chauffe": args.warmup, "ordre": "A, B puis B, A, en alternance ; scénarios : juge.scenarios",
            "machine": stats.description_machine(),
            "methode": {
                "valeur_retenue": "médiane des répétitions",
                "gain": "médiane(B)/médiane(A) - 1 (plus_haut) ; 1 - médiane(B)/médiane(A) (plus_bas) ; positif = mieux",
                "au_dela_du_bruit": f"test du signe sur les paires entrelacées, comme ab.py (k = {stats.sign_threshold(args.repetitions)} sur {args.repetitions})",
                "chronometre": ("temps processeur (utilisateur + système) du processus qui exécute un scénario, lu par le "
                                "lanceur chrono du juge commun avec wait4 ; une exécution par scénario et par répétition, "
                                "sur des entrées perturbées à chaque répétition"),
            },
            "metriques": {}, "mesures": {"A": {}, "B": {}},
        }
        report["methode"].update(getattr(projet, "METHODE", {}))
        # A fixed metric that no scenario computes from its timed outputs is read on verification alone (ruche-0117): flagged, and
        # never beyond the noise (its value is the same at every repetition, which the sign test would take for a sure gain).
        without_measurement = sorted((set(fixes["A"]) | set(fixes["B"])) - timed)
        for nom, direction, unit in projet.METRIQUES:
            values_a = [m.get(nom) for m in measurements["A"]]
            values_b = [m.get(nom) for m in measurements["B"]]
            a, b = stats.summary(values_a), stats.summary(values_b)
            sign_char = stats.sign_test(values_a, values_b, direction)
            report["metriques"][nom] = {
                "sens": direction, "unite": unit, "A": a, "B": b, "gain": stats.relative_gain(a["mediane"], b["mediane"], direction),
                "au_dela_du_bruit": sign_char["au_dela_du_bruit"] and nom not in without_measurement,
                "degradation_au_dela_du_bruit": sign_char["degradation_au_dela_du_bruit"], "verification_seulement": nom in without_measurement,
                "test_du_signe": sign_char,
                "minmax_disjoints": (a["mediane"] is not None and b["mediane"] is not None and (a["max"] < b["min"] or b["max"] < a["min"])),
            }
            report["mesures"]["A"][nom] = a["mediane"]
            report["mesures"]["B"][nom] = b["mediane"]

        # 3. Décompte d'instructions : Valgrind dans le conteneur, tout le processus, résumé relevé par chrono.
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
                    "sens": "plus_bas", "unite": "instructions", "A": a, "B": b, "gain": gain,
                    "au_dela_du_bruit": gain is not None and abs(gain) > args.instructions_threshold}
            report["methode"]["instructions"] = (
                f"valgrind --tool=cachegrind dans le conteneur, tout le processus du harnais (rien n'échappe au décompte), "
                f"entrées du greffon (préfixe de {args.instructions_prefix} octets), perturbées ; résumé relevé par "
                f"chrono sur la dernière ligne de Valgrind ; au-delà du bruit si l'écart dépasse {100 * args.instructions_threshold:.2f} %")

        verification = {"sorties_comparees": compared_ones, "entrees_melees": interleaved, "melees_par_repetition": how_many,
                        "instructions_sans_melange": without_shuffle, "fixes_sans_mesure": without_measurement}
        verification.update(getattr(projet, "VERIFICATION", {}))
        report["juge"] = {
            "version": JUDGE_VERSION,
            "commun": f"juge-v{COMMON_VERSION}",
            "source": args.judge_source,
            "base": args.base, "tete": args.head,
            "projet": projet.NOM,
            "greffon": plugin_fingerprint,
            "code": 0, "issue": ISSUES[0],
            "graine": seed.hex(),
            # A seed given on the command line is a local reproduction, never a judgement: rapport.py --verifier refuses it.
            "origine_des_graines": {"graine": "donnee" if args.seed else "tiree", "graine_ordre": "donnee" if args.order_seed else "tiree"},
            "image": image,
            "image_id": docker.image,
            "constructions_suspectes_omises": omitted_ones, "constructions_suspectes_par_type": by_type,
            "isolation": " ".join(container.ISOLATION + container.Docker.BOUNDS) + " --pids-limit 2 (exécution), 64 (compilation) ; "
                         f"chaque exécution sur son tmpfs ({container.TMPFS}), rempli à neuf",
            "verification": verification,
            "analyse": {"architecture": platform.machine().lower(), "prefixes": list(projet.PREFIXES),
                        "permis": list(getattr(projet, "PERMIS", ()))},
            "constructions_suspectes": suspects,
            "scenarios": {"isolement": "un conteneur par scénario (vérification : un par côté) ; ses sorties figées (SHA-256 de chaque "
                          "fichier et liste) à la fin du conteneur, seules lues : un écart ensuite est un refus",
                          "ordre": "tiré à chaque répétition, le même pour A et B", "graine_ordre": graine_ordre.hex(),
                          "temps_processeur": "utilisateur + système, wait4 dans chrono (pas le cgroup) ; sous Valgrind en « instructions »",
                          "deroulement": unfolding},
        }
        report["duree_s"] = round(time.time() - beginning, 1)
    finally:
        if args.keep:
            journal(f"dossier de travail conservé : {travail}")
        else:
            shutil.rmtree(travail, ignore_errors=True)

    stats.show_table(report)
    text = write_report(args.json, report)
    print(text)
    return 0


def write_report(path, report):
    """juge.json, whole or not at all (a temporary file renamed onto it); its text, every lone surrogate replaced."""
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
    """The judge stops (1 refusal, 2 error): the message on standard error and, with --json, in juge.json (ruche-0136)."""
    print(message, file=sys.stderr)
    try:
        write_report(FAILURE.get("json"), {"juge": dict(FAILURE.get("juge", {}), code=code, issue=ISSUES[code], panne_machine=fault,
                                                        motif=message)})
    except (OSError, ValueError):  # no report, never a stale or partial one: rapport.py --code keeps the exit code
        with contextlib.suppress(OSError, TypeError):
            os.unlink(FAILURE.get("json"))
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refus as e:
        sys.exit(stop_it(1, f"juge : REFUS : {propre(str(e), 3000)}"))
    except Erreur as e:
        sys.exit(stop_it(2, f"juge : erreur : {propre(str(e), 3000)}", isinstance(e, Panne)))
    except Exception:  # noqa: BLE001 — défaut du juge ou du greffon : jamais un succès, jamais une trace brute
        sys.exit(stop_it(2, "juge : erreur interne (juge ou greffon) : " + propre(traceback.format_exc(), 3000)))
