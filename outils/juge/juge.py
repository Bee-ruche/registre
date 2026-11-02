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
  d'un autre côté ;
- la graine des entrées tirées au hasard est choisie ici, APRÈS la compilation ; le greffon perturbe les
  entrées des mesures à chaque répétition ;
- le temps processeur et la mémoire sont mesurés par le noyau (wait4) dans le lanceur chrono du juge
  commun, compilé à part ; le décompte d'instructions couvre tout le processus du harnais et se lit sur
  la dernière ligne de Valgrind ;
- les sorties ne sont lues qu'à travers lecture.py (sans lien, sans fichier spécial, taille bornée) ;
- une analyse des objets compilés (analyse.py) liste les constructions suspectes.

Usage :
  python3 outils/juge/juge.py --outillage BASE --image-seulement
  python3 outils/juge/juge.py --outillage BASE --source-a DOSSIER --source-b DOSSIER [--option CLE=VALEUR]…
                              [--repetitions 10] [--chauffe 1] [--sans-instructions] [--prefixe-instructions 131072]
                              [--json juge.json] [--graine HEX]
                              [--reseau-construction host]
  --outillage : copie de la BASE de la PR (son bee/juge/projet.py est le greffon)
  --source-a / --source-b : dépôts de la référence (A, la base) et de la candidate (B, la PR)
Sortie : rapport JSON au format d'ab.py (mesures, metriques, instructions) plus une section « juge ».
Code de sortie : 0 si toutes les sorties de B sont justes, 1 si le juge refuse B, 2 si l'environnement
ne convient pas (Docker absent, base qui ne compile pas, greffon invalide, juge mal monté).
"""

import argparse
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

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import analyse  # noqa: E402
import conteneur  # noqa: E402
import entrees as module_entrees  # noqa: E402
import stats  # noqa: E402
from lecture import Erreur, Refus, Sorties, exiger, journal, lire_sortie, propre  # noqa: E402,F401

VERSION_COMMUNE = 2   # étiquette juge-v2 du registre
VERSION_JUGE = 3      # numérotation de verdict.json : 2 = juge de minizBee (miniz-0031), 3 = juge commun (its tag in « commun »)
CHEMIN_GREFFON = os.path.join("bee", "juge", "projet.py")
ATTRIBUTS_REQUIS = ("NOM", "SOURCES", "SOURCES_REQUISES", "OUTILLAGE", "EN_TETES_BASE", "CONSTRUIRE",
                    "PREFIXES", "COTES", "SCENARIOS", "INSTRUCTIONS", "METRIQUES")
METHODES_REQUISES = ("corpus", "verification", "verifier", "fixes", "repetition", "instructions", "scenario")
RELEVES = (("symboles", "symboles.txt"), ("sections", "sections.txt"), ("desassemblage", "desassemblage.txt"))
OBJET = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}\.o")
IDENTIFIANT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
PREFIXE = re.compile(r"[A-Za-z][A-Za-z0-9]{0,30}_")  # un mot suivi de « _ » : frontière d'identifiant
PERMIS_MAX = 64
JAMAIS_PERMIS = analyse.JAMAIS_PERMIS
UNITES = (".c", ".S", ".s", ".cc", ".cpp", ".cxx")  # unités de traduction : chacune doit laisser son objet
ARCHITECTURES_ANALYSEES = ("x86_64", "amd64")  # mnémoniques et préambule de Valgrind connus d'analyse.py
VALGRIND = ["/usr/bin/valgrind", "--tool=cachegrind", "--cache-sim=no", "--vgdb=no", "--cachegrind-out-file=/dev/null"]
COMMIT, HISTORIQUE_MAX, DEPOT = re.compile(r"[0-9a-f]{40}"), 16, re.compile(r"[A-Za-z0-9-]+/(?!\.\.?$)[A-Za-z0-9_.-]+")


# ------------------------------------------------------------------ greffon

def charger_greffon(outillage, options):
    """Charge bee/juge/projet.py de l'outillage (la BASE) et vérifie qu'il respecte le contrat."""
    chemin = os.path.join(outillage, CHEMIN_GREFFON)
    if not os.path.isfile(chemin) or os.path.islink(chemin):
        raise Erreur(f"greffon introuvable : {CHEMIN_GREFFON} dans {outillage}")
    with open(chemin, "rb") as f:
        empreinte = hashlib.sha256(f.read()).hexdigest()
    spec = importlib.util.spec_from_file_location("bee_greffon_projet", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "Projet"):
        raise Erreur("le greffon ne définit pas de classe Projet")
    projet = module.Projet(dict(options))
    manquants = [a for a in ATTRIBUTS_REQUIS if not hasattr(projet, a)] + \
                [m for m in METHODES_REQUISES if not callable(getattr(projet, m, None))]
    if manquants:
        raise Erreur("greffon incomplet : " + ", ".join(manquants))
    cotes = tuple(projet.COTES)
    if not cotes or any(not module_entrees.COTE_PERMIS.fullmatch(c) for c in cotes) or len(set(cotes)) != len(cotes):
        raise Erreur("COTES du greffon invalides")
    for s, c in projet.SCENARIOS.items():
        if c not in cotes or not module_entrees.NOM_PERMIS.fullmatch(s):
            raise Erreur(f"scénario invalide dans le greffon : {s}")
    if any(s not in projet.SCENARIOS for s in projet.INSTRUCTIONS):
        raise Erreur("INSTRUCTIONS du greffon : scénario inconnu")
    # Espace de noms et fonctions permises : un préfixe vide ou trop court éteindrait deux catégories de
    # l'analyse des objets (revue adverse du 28/10) ; les fonctions qui trompent la mesure ne sont jamais permises.
    prefixes, permis = tuple(projet.PREFIXES), tuple(getattr(projet, "PERMIS", ()))
    if not prefixes or any(not isinstance(p, str) or not PREFIXE.fullmatch(p) for p in prefixes):
        raise Erreur("PREFIXES du greffon invalides : au moins un préfixe, chacun un mot terminé par « _ » (mz_, yaml_…)")
    couvrants = sorted(n for n in JAMAIS_PERMIS if n.startswith(prefixes))
    if couvrants:
        raise Erreur("PREFIXES du greffon : couvriraient des fonctions jamais permises : " + ", ".join(couvrants))
    if len(permis) > PERMIS_MAX or any(not isinstance(n, str) or not IDENTIFIANT.fullmatch(n) for n in permis):
        raise Erreur(f"PERMIS du greffon invalide : au plus {PERMIS_MAX} noms de fonctions")
    interdits = sorted(set(permis) & JAMAIS_PERMIS)
    if interdits:
        raise Erreur("PERMIS du greffon : fonctions jamais permises : " + ", ".join(interdits))
    if hasattr(projet, "DIFF"):
        raise Erreur("DIFF n'existe plus : le diff analysé est celui de SOURCES (revue adverse du 28/10)")
    for chemin_relatif in list(projet.OUTILLAGE) + [projet.CONSTRUIRE]:
        if os.path.isabs(chemin_relatif) or ".." in chemin_relatif.split("/"):
            raise Erreur(f"chemin d'outillage invalide dans le greffon : {chemin_relatif}")
    return projet, empreinte


# ------------------------------------------------------------------ préparation et construction

def _sans_lien(depot, relatif):
    """Vrai si aucun composant de depot/relatif n'est un lien symbolique et si c'est un fichier ordinaire."""
    chemin = depot
    morceaux = relatif.split(os.sep)
    for i, m in enumerate(morceaux):
        chemin = os.path.join(chemin, m)
        st = os.lstat(chemin)
        if stat.S_ISLNK(st.st_mode):
            raise Refus(f"{relatif} : lien symbolique refusé")
        if i < len(morceaux) - 1 and not stat.S_ISDIR(st.st_mode):
            return False
    return stat.S_ISREG(os.lstat(chemin).st_mode)


def copier_sources(depot, destination, motifs, requis):
    """Copie les fichiers du projet (motifs glob relatifs à la racine) en refusant tout lien symbolique."""
    os.makedirs(destination, exist_ok=True)
    depot = os.path.abspath(depot)
    trouves = set()
    for motif in motifs:
        if os.path.isabs(motif) or ".." in motif.split("/"):
            raise Erreur(f"motif de sources invalide : {motif}")
        for chemin in sorted(glob.glob(os.path.join(glob.escape(depot), motif))):
            relatif = os.path.relpath(chemin, depot)
            if relatif in trouves or not _sans_lien(depot, relatif):
                continue
            cible = os.path.join(destination, relatif)
            os.makedirs(os.path.dirname(cible), exist_ok=True)
            shutil.copyfile(chemin, cible)
            trouves.add(relatif)
    for r in requis:
        if r not in trouves:
            raise Refus(f"{r} introuvable dans {depot}")
    return destination


def copier_outillage(outillage, source_a, destination, projet):
    """Ce que la BASE fournit au conteneur : ses dossiers d'outillage (OUTILLAGE) et ses en-têtes (EN_TETES_BASE).

    Les en-têtes de la base sont copiés dans /outillage/base/ : le harnais se compile avec eux, pas avec
    ceux de la PR (une macro glissée dans un en-tête de la PR ne peut pas réécrire le harnais)."""
    for relatif in projet.OUTILLAGE:
        source = os.path.join(outillage, relatif)
        if os.path.islink(source) or not os.path.isdir(source):
            raise Erreur(f"dossier d'outillage absent de la base : {relatif}")
        shutil.copytree(source, os.path.join(destination, relatif), symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    copier_sources(source_a, os.path.join(destination, "base"), projet.EN_TETES_BASE, ())
    return destination


def objets_attendus(sources):
    """Un objet obj/<nom>.o par unité de traduction (.c, .S, .cc…) copiée des SOURCES de la variante.

    Deux unités de même nom dans deux dossiers ne peuvent pas laisser chacune son objet : refusé (None)."""
    vus = {}
    for dossier, _, noms in os.walk(sources):
        for n in noms:
            racine, extension = os.path.splitext(n)
            if extension in UNITES:
                vus.setdefault(racine + ".o", []).append(os.path.relpath(os.path.join(dossier, n), sources))
    doublons = sorted(c for c, l in vus.items() if len(l) > 1)
    return set(vus), doublons


def construire(docker, projet, sources, outillage, sortie, etiquette, travail):
    """Compile une variante dans le conteneur (script CONSTRUIRE de la base), puis relève ses objets.

    Contrat du script : le harnais lié dans <sortie>/execution, et CHAQUE objet du projet dans
    <sortie>/obj/<nom>.o (un par fichier .c des SOURCES). Les relevés d'analyse (nm, objdump) sont produits
    ensuite par le juge commun lui-même, sur tous ces objets : un script de construction ne peut ni les
    omettre ni les vider (revue adverse du 28/10)."""
    conteneur.dossier_ouvert(sortie)
    commande = ["sh", "/outillage/" + projet.CONSTRUIRE, "/sources", "/outillage", "/sortie"]
    r = docker.lancer(commande, [(sources, "/sources", True), (outillage, "/outillage", True), (sortie, "/sortie", False)],
                      pids=64, delai=900)
    echec = Erreur if etiquette == "A" else Refus
    if r.returncode != 0:
        raise echec(f"la compilation de {etiquette} a échoué : " + propre(r.stderr))
    dossier_obj = os.path.join(sortie, "obj")
    if os.path.islink(dossier_obj) or not os.path.isdir(dossier_obj):
        raise echec(f"{etiquette} : pas de dossier obj/ après la construction")
    objets = []
    for n in sorted(os.listdir(dossier_obj)):
        st = os.lstat(os.path.join(dossier_obj, n))
        if not n.endswith(".o"):
            continue
        if not OBJET.fullmatch(n) or not stat.S_ISREG(st.st_mode):
            raise echec(f"{etiquette} : objet invalide dans obj/ : {propre(n, 80)}")
        objets.append(n)
    attendus, doublons = objets_attendus(sources)
    if doublons:
        raise echec(f"{etiquette} : unités de traduction homonymes (un seul objet possible dans obj/) : "
                    + ", ".join(propre(d, 80) for d in doublons[:10]))
    manquants = sorted(attendus - set(objets))
    if manquants:
        raise echec(f"{etiquette} : fichier(s) source(s) sans objet dans obj/ (non compilés ou non relevables) : "
                    + ", ".join(propre(m, 80) for m in manquants[:10]))
    if not objets:
        raise echec(f"{etiquette} : aucun objet dans obj/")
    releves_dossier = conteneur.dossier_ouvert(os.path.join(travail, f"releves-{etiquette}"))
    script = ('umask 000 && cd /construction/obj && nm -P -A "$@" > /releves/symboles.txt'
              ' && objdump -h "$@" > /releves/sections.txt && objdump -d --no-show-raw-insn "$@" > /releves/desassemblage.txt')
    r = docker.lancer(["sh", "-c", script, "releves"] + objets,
                      [(sortie, "/construction", True), (releves_dossier, "/releves", False)], pids=64, delai=900)
    if r.returncode != 0:
        raise echec(f"{etiquette} : relevés d'analyse impossibles : " + propre(r.stderr))
    releves = {cle: exiger(releves_dossier, nom, 256 << 20).decode("utf-8", "replace") for cle, nom in RELEVES}
    for o in objets:  # chaque objet figure dans chaque relevé (objdump : « <objet>:     file format … »)
        if not any(ligne.startswith(o + ":") for ligne in releves["desassemblage"].splitlines()) or \
           not any(ligne.startswith(o + ":") for ligne in releves["sections"].splitlines()):
            raise Erreur(f"{etiquette} : {o} absent des relevés d'analyse : juge mal monté")
    releves["objets"] = [(o, exiger(dossier_obj, o)) for o in objets]
    releves["programme"] = [("execution", exiger(sortie, "execution"))]
    return releves


def textes(dossier):
    """The judged files of a variant (those copied from SOURCES), whole: {relative path: text} (latin-1 keeps every byte)."""
    resultat = {}
    for racine, _, noms in os.walk(dossier):
        for n in noms:
            with open(os.path.join(racine, n), encoding="latin-1") as f:
                resultat[os.path.relpath(os.path.join(racine, n), dossier)] = f.read()
    return resultat


# ------------------------------------------------------------------ exécution

def preparer(travail, nom, entrees, cotes):
    """Écrit les entrées, un dossier par côté ; renvoie {côté: dossier}."""
    module_entrees.verifier_entrees(entrees, cotes)
    dossiers = {}
    for c in cotes:
        dossiers[c] = os.path.join(travail, secrets.token_hex(8))  # a neutral name, the same kind in every mode
        module_entrees.ecrire(dossiers[c], [e for e in entrees if e.cote == c], cotes)
    return dossiers


def sorties_de(travail, nom, cotes):
    return {c: conteneur.dossier_ouvert(os.path.join(travail, secrets.token_hex(8))) for c in cotes}


def lancer_par_cote(execution, variante, dossiers, sorties, plans, **options):
    """Un conteneur par scénario, ses sorties sur /sorties comme la vérification (dossier neutre, puis <côté>/<scénario>)."""
    mesures = {}
    for cote, plan in plans.items():
        for etiquette, commande in plan:
            dossier = conteneur.dossier_ouvert(os.path.join(os.path.dirname(sorties[cote]), secrets.token_hex(8)))
            mesures.update(execution.lancer(variante, dossiers[cote], dossier, [(etiquette, commande)], **options))
            os.rename(dossier, os.path.join(sorties[cote], etiquette))
    return mesures


def tour(rng, entrees):
    """The verification inputs in an order drawn from the judge's seed, round after round: each passes once per round."""
    while entrees:
        ordre = list(entrees)
        rng.shuffle(ordre)
        yield from ordre


def renommer(rng, entrees):
    """Inputs as written in every mode, shuffled and renamed (e0000…); also the new name of each input, in the given order."""
    ordre, neutres = list(range(len(entrees))), [""] * len(entrees)
    rng.shuffle(ordre)
    for rang, i in enumerate(ordre):
        neutres[i] = f"e{rang:04d}"
    return [entrees[i]._replace(nom=neutres[i]) for i in ordre], neutres


def meler(rng, mesurees, tours, combien, noms):
    """Measured inputs and `combien[c]` verification inputs per side from `tours[c]`, renamed together: neither name nor
    order tells them apart. Returns (inputs, {(side, name): the same input's name in verification, `noms`})."""
    ajout = [next(tours[c]) for c, k in combien.items() for _ in range(k)]
    entrees, neutres = renommer(rng, list(mesurees) + ajout)
    return entrees, {(e.cote, neutres[len(mesurees) + j]): noms[(e.cote, e.nom)] for j, e in enumerate(ajout)}


def sorties_par_entree(racines):
    """B's verification outputs: {(side, written name): [paths relative to the side's folder]}."""
    index = {}
    for c, racine in racines.items():
        for dossier, _, noms in os.walk(racine):
            for n in noms:
                m = re.fullmatch(r"(e\d{4,})(\..*)?", n)
                if m:
                    index.setdefault((c, m.group(1)), []).append(os.path.relpath(os.path.join(dossier, n), racine))
    return index


def memes_sorties(index, verification, sorties, melange, scenarios):
    """B's output of each verification input mixed into a measured run is, byte for byte, its own output in verification
    (same path); each such input has at least one. Returns the number of outputs compared."""
    total = 0
    for (cote, nom), nom_verification in melange.items():
        vues = 0
        for s in (s for s, c in scenarios if c == cote):
            for relatif in index.get((cote, nom_verification), []):
                tete, barre, dernier = relatif.rpartition("/")
                mesuree = lire_sortie(os.path.join(sorties[cote], s), tete + barre + nom + dernier[len(nom_verification):])
                if mesuree is not None:
                    vues += 1
                    if mesuree != exiger(verification[cote], relatif):
                        raise Refus(f"scénario {s} : sortie de B différente de sa sortie en vérification pour la même entrée")
        if not vues:
            raise Erreur(f"{cote}/{nom} : aucune sortie de B comparable à la vérification (mêmes sorties dans chaque mode attendues)")
        total += vues
    return total


def variante(construction, dossier):
    """/variante: the harness alone, copied (no link followed) into a folder of the judge, which sets its times."""
    os.makedirs(dossier)
    with open(os.path.join(dossier, "execution"), "wb") as f:
        f.write(exiger(construction, "execution"))
    os.chmod(os.path.join(dossier, "execution"), 0o755)
    os.chmod(dossier, 0o755)
    return dossier


def effacer(*groupes):
    for groupe in groupes:
        for dossier in (groupe.values() if isinstance(groupe, dict) else groupe):
            shutil.rmtree(dossier, ignore_errors=True)


def entier_compte(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise Erreur("le greffon doit renvoyer un nombre de sorties comparées (entier positif)")
    return n


def exiger_couverture(sorties_b, entrees, etape):
    """Chaque entrée doit avoir eu au moins une sortie de B lue par le greffon pendant l'étape."""
    oubliees = [e.nom for e in entrees if not sorties_b.couvre(e.cote, e.nom)]
    if oubliees:
        raise Erreur(f"{etape} : le greffon n'a lu aucune sortie de B pour {len(oubliees)} entrée(s) "
                     f"({', '.join(oubliees[:5])}) : juge mal monté")


# ------------------------------------------------------------------ declared history

def recuperer_historique(outillage, texte, jeton=None, budget=600):
    """Fetches into the base's repository the commits its plugin reads (juge.yml's `historique`), with their trees
    and blobs but no history. Each must be in the base's ancestry, as GitHub's compare API on the calling repository
    (GITHUB_REPOSITORY) says (identical or behind), all checked before any fetch; checks and fetches share one time
    budget. juge.yml runs it in its own step (--historique-seulement), the only call of juge.py given a token
    (GH_TOKEN, passed to gh alone), before anything loads the plugin and before the PR."""
    commits, depot = sorted(set(texte.split())), os.environ.get("GITHUB_REPOSITORY", "")
    if len(commits) > HISTORIQUE_MAX or not all(COMMIT.fullmatch(c) for c in commits):
        raise Erreur(f"historique : at most {HISTORIQUE_MAX} full commit SHAs (40 hexadecimal digits), separated by blanks")
    if not commits:
        return []
    fin = time.monotonic() + budget

    def lancer(commande, env=None):
        try:
            return subprocess.run(commande, capture_output=True, text=True, errors="replace", env=env,
                                  timeout=max(0.01, fin - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise Erreur(f"historique : checks and fetches exceeded their budget of {budget} s")
        except OSError as e:
            raise Erreur(f"historique : {commande[0]} unavailable ({propre(str(e), 200)})")
    base = lancer(["git", "-C", outillage, "rev-parse", "HEAD"]).stdout.strip()
    if not DEPOT.fullmatch(depot) or not COMMIT.fullmatch(base):
        raise Erreur("historique : the calling repository (GITHUB_REPOSITORY, owner/name) and the base's commit are required")
    for c in commits:
        r = lancer(["gh", "api", f"repos/{depot}/compare/{base}...{c}", "--jq", ".status"],
                   {**os.environ, "GH_TOKEN": jeton} if jeton else None)
        if r.returncode != 0 or r.stdout.strip() not in ("identical", "behind"):
            raise Erreur(f"historique : {c} is not in the ancestry of the base ({propre(r.stdout.strip() or r.stderr, 300)})")
    for c in commits:
        r = lancer(["git", "-C", outillage, "fetch", "--quiet", "--no-tags", "--depth=1", "origin", f"{c}:refs/bee/historique/{c}"])
        if r.returncode != 0:
            raise Erreur(f"historique : commit {c} not fetched from the base's origin : " + propre(r.stderr, 500))
    return commits


# ------------------------------------------------------------------ programme

def options_de(liste):
    options = {}
    for o in liste or []:
        if "=" not in o:
            raise Erreur(f"option invalide (CLE=VALEUR attendu) : {o}")
        cle, valeur = o.split("=", 1)
        options[cle.strip()] = valeur.strip()
    return options


def main(argv=None):
    analyseur = argparse.ArgumentParser(description="Juge commun Bee (voir l'aide du module).")
    analyseur.add_argument("--outillage", required=True, help="copie de la BASE de la PR (greffon bee/juge/projet.py)")
    analyseur.add_argument("--source-a")
    analyseur.add_argument("--source-b")
    analyseur.add_argument("--image-seulement", action="store_true",
                           help="construit l'image du conteneur (avec réseau, avant la PR) et affiche son étiquette")
    analyseur.add_argument("--historique-seulement", action="store_true",
                           help="checks and fetches the declared history (--historique) into the base, without loading the plugin")
    analyseur.add_argument("--historique", default="", help="with --historique-seulement: commits fetched into the base")
    analyseur.add_argument("--source-juge", help="DEPOT@COMMIT of this judge's code (juge.yml: the workflow's own commit)")
    analyseur.add_argument("--option", action="append", default=[], help="option du greffon, CLE=VALEUR (répétable)")
    analyseur.add_argument("--repetitions", type=int, default=10)
    analyseur.add_argument("--chauffe", type=int, default=1)
    analyseur.add_argument("--sans-instructions", action="store_true")
    analyseur.add_argument("--prefixe-instructions", type=int, default=131072)
    analyseur.add_argument("--seuil-instructions", type=float, default=0.002)
    analyseur.add_argument("--json")
    analyseur.add_argument("--graine", help="graine hexadécimale (reproduction locale) ; défaut : tirée au hasard")
    analyseur.add_argument("--reseau-construction", help="réseau de docker build (« host » sans pont Docker)")
    analyseur.add_argument("--memoire", default="4g")
    analyseur.add_argument("--garder", action="store_true")
    args = analyseur.parse_args(argv)
    if args.repetitions < 1 or args.chauffe < 0:
        analyseur.error("--repetitions : au moins 1 ; --chauffe : au moins 0")
    if args.historique and not args.historique_seulement:
        analyseur.error("--historique va avec --historique-seulement")
    # Defence in depth: the plugin, loaded later in this process, does not find GH_TOKEN in os.environ (the value
    # stays in /proc/<pid>/environ: juge.yml gives the token to the --historique-seulement call alone).
    jeton = os.environ.pop("GH_TOKEN", None)
    if args.historique_seulement:
        print(" ".join(recuperer_historique(os.path.abspath(args.outillage), args.historique, jeton)))
        return 0

    debut = time.time()
    if shutil.which("docker") is None:
        raise Erreur("docker introuvable")
    outillage = os.path.abspath(args.outillage)
    if not args.image_seulement:
        os.environ["GIT_ALLOW_PROTOCOL"] = "none"  # judging: no git transport at all, the declared history is already here
    projet, empreinte_greffon = charger_greffon(outillage, options_de(args.option))
    if args.image_seulement:
        print(conteneur.construire_image(getattr(projet, "PAQUETS", ()), args.reseau_construction))
        return 0
    if not (args.source_a and args.source_b):
        analyseur.error("--source-a et --source-b sont requis")
    cotes = tuple(projet.COTES)
    travail = tempfile.mkdtemp(prefix="bee-juge-")
    os.chmod(travail, 0o755)
    try:
        image = conteneur.construire_image(getattr(projet, "PAQUETS", ()), args.reseau_construction)
        docker = conteneur.Docker(image, args.memoire)
        source_a = copier_sources(args.source_a, os.path.join(travail, "sources-A"), projet.SOURCES, projet.SOURCES_REQUISES)
        source_b = copier_sources(args.source_b, os.path.join(travail, "sources-B"), projet.SOURCES, projet.SOURCES_REQUISES)
        outils = copier_outillage(outillage, source_a, os.path.join(travail, "outillage"), projet)
        chrono = conteneur.compiler_chrono(docker, travail)
        constructions = {v: os.path.join(travail, f"construction-{v}") for v in "AB"}
        releves = {"A": construire(docker, projet, source_a, outils, constructions["A"], "A", travail),
                   "B": construire(docker, projet, source_b, outils, constructions["B"], "B", travail)}
        journal("A et B compilés dans le conteneur")

        suspects = analyse.analyser(releves["A"], releves["B"], textes(source_a), textes(source_b),
                                    prefixes=projet.PREFIXES, permis=getattr(projet, "PERMIS", ()))
        architecture = platform.machine().lower()
        if architecture not in ARCHITECTURES_ANALYSEES:
            # analyse.py ne connaît que les instructions x86-64 : ailleurs, le désassemblage n'est pas analysé.
            suspects.append({"type": "architecture", "detail": f"{architecture} : instructions des objets non analysées "
                                                               "(analyse.py ne couvre que x86-64)"})
        for s in suspects:
            journal(f"construction suspecte : {propre(s['detail'], 300)}")

        # La graine est tirée maintenant, après la compilation : rien de ce qui a été compilé ne la connaît.
        graine = bytes.fromhex(args.graine) if args.graine else secrets.token_bytes(16)
        rng = random.Random(int.from_bytes(graine, "big"))
        corpus = projet.corpus(outillage)
        execution = conteneur.Execution(docker, chrono, {v: variante(constructions[v], os.path.join(travail, f"variante-{v}"))
                                                         for v in "AB"}, travail)
        comparees = 0

        # 1. Vérification : le greffon choisit les entrées (corpus, tirées au hasard, invalides) et la règle.
        entrees = projet.verification(rng, corpus)
        module_entrees.verifier_entrees(entrees, cotes)
        ecrites, neutres = renommer(rng, entrees)  # the plugin keeps its names, read through `noms`
        noms = {(e.cote, e.nom): n for e, n in zip(entrees, neutres)}
        dossiers = preparer(travail, "verification", ecrites, cotes)
        racines = {}
        commande = ["/variante/execution", "verifier", "/entrees", "/sorties"]
        for v in "AB":
            racines[v] = sorties_de(travail, f"sorties-verification-{v}", cotes)
            for cote in cotes:
                execution.lancer(v, dossiers[cote], racines[v][cote], [("verifier", commande)], delai=3600)
        vue_b = Sorties(racines["B"], noms)
        comparees += entier_compte(projet.verifier(Sorties(racines["A"], noms), vue_b, entrees))
        exiger_couverture(vue_b, entrees, "vérification")
        if comparees == 0:
            raise Erreur("vérification : aucune sortie comparée : juge mal monté")
        fixes = {v: dict(projet.fixes(Sorties(racines[v], noms), corpus)) for v in "AB"}
        effacer(racines["A"], dossiers)
        index = sorties_par_entree(racines["B"])
        journal(f"vérification : {comparees} sorties de B justes ({len(entrees)} entrées)")
        # Verification inputs mixed into every measurement (ruche-0037), spread over the repetitions.
        par_cote = {c: [e for e in entrees if e.cote == c] for c in set(projet.SCENARIOS.values())}
        if not all(par_cote.values()):
            raise Erreur("un côté mesuré n'a aucune entrée de vérification à mêler aux mesures : greffon invalide")
        tours = {c: tour(rng, l) for c, l in par_cote.items()}
        combien = {c: -(-len(l) // (args.chauffe + args.repetitions)) for c, l in par_cote.items()}
        legeres = {c: [e for e in l if max(len(e.donnees), e.taille) <= args.prefixe_instructions]
                   for c, l in par_cote.items() if c in {projet.SCENARIOS[s] for s in projet.INSTRUCTIONS}}
        sans_melange = sorted(s for s in projet.INSTRUCTIONS if not legeres.get(projet.SCENARIOS[s]))
        melees = 0

        # 2. Mesures au chronomètre (temps processeur du fils, lu par le noyau), A et B entrelacés.
        mesures = {"A": [], "B": []}
        for i in range(args.chauffe + args.repetitions):
            entrees, melange = meler(rng, projet.repetition(rng, corpus), tours, combien, noms)
            melees += len(melange)
            dossiers = preparer(travail, f"repetition-{i}", entrees, cotes)
            plans = {c: [(s, ["/variante/execution", s, "/entrees", "/sorties"]) for s, cs in projet.SCENARIOS.items() if cs == c]
                     for c in cotes}
            sorties, brut = {}, {}
            for v in (("A", "B") if i % 2 == 0 else ("B", "A")):
                sorties[v] = sorties_de(travail, f"sorties-{i}-{v}", cotes)
                brut[v] = lancer_par_cote(execution, v, dossiers, sorties[v], plans)
            for v in "AB":
                valeurs = dict(fixes[v])  # a scenario's value of a fixed metric, read on its timed outputs, replaces it
                for s, cote in projet.SCENARIOS.items():
                    vue = Sorties(sorties[v])
                    vals, n = projet.scenario(s, Sorties(sorties["A"]), vue, entrees, brut[v][s])
                    comparees += entier_compte(n)
                    exiger_couverture(vue, [e for e in entrees if e.cote == cote], f"scénario {s} ({v})")
                    valeurs.update(vals)
                if i >= args.chauffe:
                    mesures[v].append(valeurs)
            comparees += memes_sorties(index, racines["B"], sorties["B"], melange, projet.SCENARIOS.items())
            effacer(sorties["A"], sorties["B"], dossiers)
            journal(f"répétition {i + 1}/{args.chauffe + args.repetitions} ({'chauffe' if i < args.chauffe else 'mesurée'}) faite")

        rapport = {
            "repetitions": args.repetitions, "chauffe": args.chauffe, "ordre": "A, B puis B, A, en alternance",
            "machine": stats.description_machine(),
            "methode": {
                "valeur_retenue": "médiane des répétitions",
                "gain": "médiane(B)/médiane(A) - 1 (plus_haut) ; 1 - médiane(B)/médiane(A) (plus_bas) ; positif = mieux",
                "au_dela_du_bruit": f"test du signe sur les paires entrelacées, comme ab.py (k = {stats.seuil_signe(args.repetitions)} sur {args.repetitions})",
                "chronometre": ("temps processeur (utilisateur + système) du processus qui exécute un scénario, lu par le "
                                "lanceur chrono du juge commun avec wait4 ; une exécution par scénario et par répétition, "
                                "sur des entrées perturbées à chaque répétition"),
            },
            "metriques": {}, "mesures": {"A": {}, "B": {}},
        }
        rapport["methode"].update(getattr(projet, "METHODE", {}))
        for nom, sens, unite in projet.METRIQUES:
            valeurs_a = [m.get(nom) for m in mesures["A"]]
            valeurs_b = [m.get(nom) for m in mesures["B"]]
            a, b = stats.resume(valeurs_a), stats.resume(valeurs_b)
            signe = stats.test_du_signe(valeurs_a, valeurs_b, sens)
            rapport["metriques"][nom] = {
                "sens": sens, "unite": unite, "A": a, "B": b, "gain": stats.gain_relatif(a["mediane"], b["mediane"], sens),
                "au_dela_du_bruit": signe["au_dela_du_bruit"], "degradation_au_dela_du_bruit": signe["degradation_au_dela_du_bruit"],
                "test_du_signe": signe,
                "minmax_disjoints": (a["mediane"] is not None and b["mediane"] is not None and (a["max"] < b["min"] or b["max"] < a["min"])),
            }
            rapport["mesures"]["A"][nom] = a["mediane"]
            rapport["mesures"]["B"][nom] = b["mediane"]

        # 3. Décompte d'instructions : Valgrind dans le conteneur, tout le processus, résumé relevé par chrono.
        if not args.sans_instructions and projet.INSTRUCTIONS:
            entrees, melange = meler(rng, projet.instructions(rng, corpus, args.prefixe_instructions), {c: tour(rng, l) for c, l
                                     in legeres.items()}, {c: min(combien[c], len(l)) for c, l in legeres.items()}, noms)
            melees += len(melange)
            dossiers = preparer(travail, "instructions", entrees, cotes)
            plans = {c: [(s, VALGRIND + ["/variante/execution", s, "/entrees", "/sorties"])
                         for s in projet.INSTRUCTIONS if projet.SCENARIOS[s] == c] for c in cotes}
            comptes, sorties = {}, {}
            for v in "AB":
                sorties[v] = sorties_de(travail, f"sorties-instructions-{v}", cotes)
                comptes[v] = lancer_par_cote(execution, v, dossiers, sorties[v], plans, valgrind=True, delai=3600)
            for s in projet.INSTRUCTIONS:
                vue = Sorties(sorties["B"])
                _, n = projet.scenario(s, Sorties(sorties["A"]), vue, entrees, comptes["B"][s])
                comparees += entier_compte(n)
                exiger_couverture(vue, [e for e in entrees if e.cote == projet.SCENARIOS[s]], f"instructions {s}")
            comparees += memes_sorties(index, racines["B"], sorties["B"], melange, [(s, projet.SCENARIOS[s]) for s in projet.INSTRUCTIONS])
            effacer(sorties["A"], sorties["B"], dossiers)
            rapport["instructions"] = {}
            for s in projet.INSTRUCTIONS:
                a, b = comptes["A"][s]["instructions"], comptes["B"][s]["instructions"]
                gain = stats.gain_relatif(a, b, "plus_bas")
                rapport["instructions"]["instructions_" + s] = {
                    "sens": "plus_bas", "unite": "instructions", "A": a, "B": b, "gain": gain,
                    "au_dela_du_bruit": gain is not None and abs(gain) > args.seuil_instructions}
            rapport["methode"]["instructions"] = (
                f"valgrind --tool=cachegrind dans le conteneur, tout le processus du harnais (rien n'échappe au décompte), "
                f"entrées du greffon (préfixe de {args.prefixe_instructions} octets), perturbées ; résumé relevé par "
                f"chrono sur la dernière ligne de Valgrind ; au-delà du bruit si l'écart dépasse {100 * args.seuil_instructions:.2f} %")

        verification = {"sorties_comparees": comparees, "entrees_melees": melees, "melees_par_repetition": combien,
                        "instructions_sans_melange": sans_melange}
        verification.update(getattr(projet, "VERIFICATION", {}))
        rapport["juge"] = {
            "version": VERSION_JUGE,
            "commun": f"juge-v{VERSION_COMMUNE}",
            "source": args.source_juge,
            "projet": projet.NOM,
            "greffon": empreinte_greffon,
            "graine": graine.hex(),
            "image": image,
            "isolation": " ".join(conteneur.ISOLATION) + " --pids-limit 2 (exécution), 64 (compilation)",
            "verification": verification,
            "analyse": {"architecture": platform.machine().lower(), "prefixes": list(projet.PREFIXES),
                        "permis": list(getattr(projet, "PERMIS", ()))},
            "constructions_suspectes": suspects,
        }
        rapport["duree_s"] = round(time.time() - debut, 1)
    finally:
        if args.garder:
            journal(f"dossier de travail conservé : {travail}")
        else:
            shutil.rmtree(travail, ignore_errors=True)

    stats.afficher_tableau(rapport)
    texte = json.dumps(rapport, ensure_ascii=False, indent=2)
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(texte + "\n")
    print(texte)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refus as e:
        print(f"juge : REFUS : {propre(str(e), 3000)}", file=sys.stderr)
        sys.exit(1)
    except Erreur as e:
        print(f"juge : erreur : {propre(str(e), 3000)}", file=sys.stderr)
        sys.exit(2)
    except Exception:  # noqa: BLE001 — défaut du juge ou du greffon : jamais un succès, jamais une trace brute
        print("juge : erreur interne (juge ou greffon) : " + propre(traceback.format_exc(), 3000), file=sys.stderr)
        sys.exit(2)
