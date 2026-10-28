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
                              [--json juge.json] [--depot-diff DOSSIER --base REV --tete REV] [--graine HEX]
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
import random
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import analyse  # noqa: E402
import conteneur  # noqa: E402
import entrees as module_entrees  # noqa: E402
import stats  # noqa: E402
from lecture import Erreur, Refus, Sorties, exiger, journal, propre  # noqa: E402,F401

VERSION_COMMUNE = 1   # étiquette juge-v1 du registre
VERSION_JUGE = 3      # numérotation de verdict.json : 2 = juge de minizBee (miniz-0031), 3 = juge commun v1
CHEMIN_GREFFON = os.path.join("bee", "juge", "projet.py")
ATTRIBUTS_REQUIS = ("NOM", "SOURCES", "SOURCES_REQUISES", "DIFF", "OUTILLAGE", "EN_TETES_BASE", "CONSTRUIRE",
                    "PREFIXES", "COTES", "SCENARIOS", "INSTRUCTIONS", "METRIQUES")
METHODES_REQUISES = ("corpus", "verification", "verifier", "fixes", "repetition", "instructions", "scenario")
RELEVES = (("symboles", "symboles.txt"), ("sections", "sections.txt"), ("desassemblage", "desassemblage.txt"))
VALGRIND = ["/usr/bin/valgrind", "--tool=cachegrind", "--cache-sim=no", "--vgdb=no", "--cachegrind-out-file=/dev/null"]


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


def construire(docker, projet, sources, outillage, sortie, etiquette):
    """Compile une variante dans le conteneur (script CONSTRUIRE de la base) ; renvoie les relevés d'analyse."""
    conteneur.dossier_ouvert(sortie)
    commande = ["sh", "/outillage/" + projet.CONSTRUIRE, "/sources", "/outillage", "/sortie"]
    r = docker.lancer(commande, [(sources, "/sources", True), (outillage, "/outillage", True), (sortie, "/sortie", False)],
                      pids=64, delai=900)
    if r.returncode != 0:
        message = f"la compilation de {etiquette} a échoué : " + propre(r.stderr)
        raise (Erreur(message) if etiquette == "A" else Refus(message))
    return {cle: exiger(sortie, nom, 64 << 20).decode("utf-8", "replace") for cle, nom in RELEVES}


# ------------------------------------------------------------------ exécution

def preparer(travail, nom, entrees, cotes):
    """Écrit les entrées, un dossier par côté ; renvoie {côté: dossier}."""
    module_entrees.verifier_entrees(entrees, cotes)
    dossiers = {}
    for c in cotes:
        dossiers[c] = os.path.join(travail, f"{nom}-{c}")
        module_entrees.ecrire(dossiers[c], [e for e in entrees if e.cote == c], cotes)
    return dossiers


def sorties_de(travail, nom, cotes):
    return {c: conteneur.dossier_ouvert(os.path.join(travail, f"{nom}-{c}")) for c in cotes}


def lancer_par_cote(execution, variante, dossiers, sorties, plans, **options):
    """Un conteneur par côté ; renvoie les mesures de tous les côtés, fusionnées."""
    mesures = {}
    for cote, plan in plans.items():
        if plan:
            for etiquette, _ in plan:
                conteneur.dossier_ouvert(os.path.join(sorties[cote], etiquette))
            mesures.update(execution.lancer(variante, dossiers[cote], sorties[cote], plan, **options))
    return mesures


def effacer(*groupes):
    for groupe in groupes:
        for dossier in (groupe.values() if isinstance(groupe, dict) else groupe):
            shutil.rmtree(dossier, ignore_errors=True)


def entier_compte(n):
    if not isinstance(n, int) or n < 0:
        raise Erreur("le greffon doit renvoyer un nombre de sorties comparées (entier positif)")
    return n


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
                           help="construit l'image du conteneur (seule étape avec réseau) et affiche son étiquette")
    analyseur.add_argument("--option", action="append", default=[], help="option du greffon, CLE=VALEUR (répétable)")
    analyseur.add_argument("--repetitions", type=int, default=10)
    analyseur.add_argument("--chauffe", type=int, default=1)
    analyseur.add_argument("--sans-instructions", action="store_true")
    analyseur.add_argument("--prefixe-instructions", type=int, default=131072)
    analyseur.add_argument("--seuil-instructions", type=float, default=0.002)
    analyseur.add_argument("--json")
    analyseur.add_argument("--depot-diff", help="clone git qui contient --base et --tete (diff des sources pour l'analyse)")
    analyseur.add_argument("--base")
    analyseur.add_argument("--tete")
    analyseur.add_argument("--graine", help="graine hexadécimale (reproduction locale) ; défaut : tirée au hasard")
    analyseur.add_argument("--reseau-construction", help="réseau de docker build (« host » sans pont Docker)")
    analyseur.add_argument("--memoire", default="4g")
    analyseur.add_argument("--garder", action="store_true")
    args = analyseur.parse_args(argv)

    debut = time.time()
    if shutil.which("docker") is None:
        raise Erreur("docker introuvable")
    outillage = os.path.abspath(args.outillage)
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
        releves = {"A": construire(docker, projet, source_a, outils, constructions["A"], "A"),
                   "B": construire(docker, projet, source_b, outils, constructions["B"], "B")}
        journal("A et B compilés dans le conteneur")

        diff = ""
        if args.depot_diff and args.base and args.tete:
            diff = subprocess.run(["git", "-C", args.depot_diff, "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--unified=0",
                                   f"{args.base}...{args.tete}", "--"] + list(projet.DIFF),
                                  capture_output=True, text=True, errors="replace").stdout
        suspects = analyse.analyser(releves["A"], releves["B"], diff, prefixes=projet.PREFIXES, permis=getattr(projet, "PERMIS", ()))
        for s in suspects:
            journal(f"construction suspecte : {propre(s['detail'], 300)}")

        # La graine est tirée maintenant, après la compilation : rien de ce qui a été compilé ne la connaît.
        graine = bytes.fromhex(args.graine) if args.graine else secrets.token_bytes(16)
        rng = random.Random(int.from_bytes(graine, "big"))
        corpus = projet.corpus(outillage)
        execution = conteneur.Execution(docker, chrono, constructions, travail)
        comparees = 0

        # 1. Vérification : le greffon choisit les entrées (corpus, tirées au hasard, invalides) et la règle.
        entrees = projet.verification(rng, corpus)
        dossiers = preparer(travail, "verification", entrees, cotes)
        racines = {}
        commande = ["/variante/execution", "verifier", "/entrees", "/sorties"]
        for v in "AB":
            racines[v] = sorties_de(travail, f"sorties-verification-{v}", cotes)
            for cote in cotes:
                execution.lancer(v, dossiers[cote], racines[v][cote], [("verifier", commande)], delai=3600)
        comparees += entier_compte(projet.verifier(Sorties(racines["A"]), Sorties(racines["B"]), entrees))
        fixes = {v: dict(projet.fixes(Sorties(racines[v]), corpus)) for v in "AB"}
        effacer(racines["A"], racines["B"], dossiers)
        journal(f"vérification : {comparees} sorties de B justes ({len(entrees)} entrées)")

        # 2. Mesures au chronomètre (temps processeur du fils, lu par le noyau), A et B entrelacés.
        mesures = {"A": [], "B": []}
        for i in range(args.chauffe + args.repetitions):
            entrees = projet.repetition(rng, corpus)
            dossiers = preparer(travail, f"repetition-{i}", entrees, cotes)
            plans = {c: [(s, ["/variante/execution", s, "/entrees", f"/sorties/{s}"]) for s, cs in projet.SCENARIOS.items() if cs == c]
                     for c in cotes}
            sorties, brut = {}, {}
            for v in (("A", "B") if i % 2 == 0 else ("B", "A")):
                sorties[v] = sorties_de(travail, f"sorties-{i}-{v}", cotes)
                brut[v] = lancer_par_cote(execution, v, dossiers, sorties[v], plans)
            for v in "AB":
                valeurs = {}
                for s in projet.SCENARIOS:
                    vals, n = projet.scenario(s, Sorties(sorties["A"]), Sorties(sorties[v]), entrees, brut[v][s])
                    comparees += entier_compte(n)
                    valeurs.update(vals)
                valeurs.update(fixes[v])
                if i >= args.chauffe:
                    mesures[v].append(valeurs)
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
            entrees = projet.instructions(rng, corpus, args.prefixe_instructions)
            dossiers = preparer(travail, "instructions", entrees, cotes)
            plans = {c: [(s, VALGRIND + ["/variante/execution", s, "/entrees", f"/sorties/{s}"])
                         for s in projet.INSTRUCTIONS if projet.SCENARIOS[s] == c] for c in cotes}
            comptes, sorties = {}, {}
            for v in "AB":
                sorties[v] = sorties_de(travail, f"sorties-instructions-{v}", cotes)
                comptes[v] = lancer_par_cote(execution, v, dossiers, sorties[v], plans, valgrind=True, delai=3600)
            for s in projet.INSTRUCTIONS:
                _, n = projet.scenario(s, Sorties(sorties["A"]), Sorties(sorties["B"]), entrees, comptes["B"][s])
                comparees += entier_compte(n)
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

        verification = {"sorties_comparees": comparees}
        verification.update(getattr(projet, "VERIFICATION", {}))
        rapport["juge"] = {
            "version": VERSION_JUGE,
            "commun": f"juge-v{VERSION_COMMUNE}",
            "projet": projet.NOM,
            "greffon": empreinte_greffon,
            "graine": graine.hex(),
            "image": image,
            "isolation": " ".join(conteneur.ISOLATION) + " --pids-limit 2 (exécution), 64 (compilation)",
            "verification": verification,
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
        print(f"juge : REFUS : {e}", file=sys.stderr)
        sys.exit(1)
    except Erreur as e:
        print(f"juge : erreur : {e}", file=sys.stderr)
        sys.exit(2)
