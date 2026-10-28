"""Juge commun Bee : image, conteneurs isolés et exécution sous le lanceur chrono.

Toute exécution de code issu de la PR passe par `Docker.lancer` : pas de réseau, système de fichiers en
lecture seule, aucune capacité, pas d'élévation de privilège, utilisateur 65534, /tmp non exécutable,
nombre de processus et mémoire bornés. Le conteneur ne voit que ce qui lui est monté.
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile

from lecture import Erreur, Refus, journal, lire_sortie, propre

ICI = os.path.dirname(os.path.abspath(__file__))
ISOLATION = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
             "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "-e", "HOME=/tmp", "-e", "LC_ALL=C"]
PAQUET = re.compile(r"[a-z0-9][a-z0-9+.-]{0,63}")


class Docker:
    def __init__(self, image, memoire="4g"):
        self.image, self.memoire = image, memoire

    def lancer(self, commande, montages, pids=2, entree=None, delai=3600):
        nom = "bee-juge-" + secrets.token_hex(6)
        cmd = ["docker", "run", "--rm", "--name", nom, "--pids-limit", str(pids),
               "--memory", self.memoire, "--memory-swap", self.memoire] + ISOLATION
        if entree is not None:
            cmd.append("-i")
        for hote, cible, lecture_seule in montages:
            if "," in hote or "," in cible:
                raise Erreur(f"chemin de montage invalide : {hote}")
            cmd += ["--mount", f"type=bind,source={hote},target={cible}" + (",readonly" if lecture_seule else "")]
        cmd += [self.image] + commande
        try:
            return subprocess.run(cmd, input=entree, capture_output=True, timeout=delai)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", nom], capture_output=True)
            raise Refus(f"délai de {delai} s dépassé dans le conteneur ({commande[0]})")


def dockerfile(paquets):
    """Texte du Dockerfile : l'image commune, les paquets du projet, l'utilisateur sans privilège."""
    with open(os.path.join(ICI, "Dockerfile.base"), encoding="utf-8") as f:
        texte = f.read().rstrip("\n") + "\n"
    paquets = list(paquets or [])
    for p in paquets:
        if not PAQUET.fullmatch(p):
            raise Erreur(f"nom de paquet invalide dans le greffon : {p!r}")
    if paquets:
        texte += ("\n# Paquets propres au projet (PAQUETS du greffon).\n"
                  "RUN apt-get update -q \\\n"
                  " && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends \\\n"
                  f"      {' '.join(paquets)} \\\n"
                  " && rm -rf /var/lib/apt/lists/*\n")
    return texte + "\n# Utilisateur sans privilège sous lequel tourne tout le reste (Docker.lancer passe aussi --user).\nUSER 65534:65534\nWORKDIR /\n"


def construire_image(paquets, reseau=None):
    texte = dockerfile(paquets)
    etiquette = "bee-juge-commun:" + hashlib.sha256(texte.encode()).hexdigest()[:16]
    if subprocess.run(["docker", "image", "inspect", etiquette], capture_output=True).returncode == 0:
        return etiquette
    journal(f"construction de l'image {etiquette} (seule étape avec réseau, avant tout fichier de la PR)")
    contexte = tempfile.mkdtemp(prefix="bee-image-")
    try:
        with open(os.path.join(contexte, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(texte)
        commande = ["docker", "build", "-q", "-t", etiquette] + (["--network", reseau] if reseau else []) + [contexte]
        r = subprocess.run(commande, capture_output=True, text=True)
    finally:
        shutil.rmtree(contexte, ignore_errors=True)
    if r.returncode != 0:
        raise Erreur("construction de l'image impossible : " + r.stderr[-2000:])
    return etiquette


def dossier_ouvert(chemin):
    """Dossier que le conteneur (utilisateur 65534) peut écrire."""
    os.makedirs(chemin, exist_ok=True)
    os.chmod(chemin, 0o777)
    return chemin


def compiler_chrono(docker, travail):
    """Compile le lanceur chrono du JUGE COMMUN (jamais une ligne du projet ni de la PR), dans le conteneur."""
    source = os.path.join(travail, "chrono-source")
    os.makedirs(source)
    shutil.copyfile(os.path.join(ICI, "chrono.c"), os.path.join(source, "chrono.c"))
    sortie = dossier_ouvert(os.path.join(travail, "chrono-construction"))
    r = docker.lancer(["sh", "-c", "umask 000 && cc -O2 -std=gnu99 -Wall -Wextra /source/chrono.c -o /sortie/chrono"],
                      [(source, "/source", True), (sortie, "/sortie", False)], pids=64, delai=300)
    if r.returncode != 0:
        raise Erreur("compilation de chrono impossible : " + propre(r.stderr))
    chrono = os.path.join(travail, "chrono")
    os.makedirs(chrono)
    shutil.copyfile(os.path.join(sortie, "chrono"), os.path.join(chrono, "chrono"))
    os.chmod(os.path.join(chrono, "chrono"), 0o755)
    os.chmod(chrono, 0o755)
    return chrono


class Execution:
    """Lance un plan de commandes dans un conteneur, sous le lanceur chrono du juge commun."""

    def __init__(self, docker, chrono, constructions, travail):
        self.docker, self.chrono, self.constructions, self.travail = docker, chrono, constructions, travail

    def lancer(self, variante, entrees, sorties, plan, valgrind=False, delai=1800):
        """plan : [(étiquette, [programme, arguments…])]. Renvoie {étiquette: mesure}."""
        dossier_plan = tempfile.mkdtemp(prefix="plan-", dir=self.travail)
        os.chmod(dossier_plan, 0o755)
        with open(os.path.join(dossier_plan, "plan.txt"), "w", encoding="utf-8") as f:
            for etiquette, commande in plan:
                f.write("\t".join([etiquette] + commande) + "\n")
        os.chmod(os.path.join(dossier_plan, "plan.txt"), 0o644)
        dossier_ouvert(sorties)
        dossier_ouvert(os.path.join(sorties, "journal"))
        jeton = secrets.token_hex(16)
        commande = ["/chrono/chrono", "--delai", str(delai), "--journal", "/sorties/journal"] + (["--valgrind"] if valgrind else []) + ["/plan/plan.txt"]
        montages = [(self.chrono, "/chrono", True), (self.constructions[variante], "/variante", True), (entrees, "/entrees", True),
                    (sorties, "/sorties", False), (dossier_plan, "/plan", True)]
        r = self.docker.lancer(commande, montages, pids=2, entree=(jeton + "\n").encode(), delai=delai * len(plan) + 300)
        shutil.rmtree(dossier_plan, ignore_errors=True)
        if r.returncode != 0:
            raise Refus(f"le lanceur a échoué pour {variante} (code {r.returncode}) : " + propre(r.stderr))
        mesures = {}
        lignes = [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
        if len(lignes) != len(plan):
            raise Refus(f"{variante} : {len(lignes)} mesure(s) pour {len(plan)} commande(s)")
        for ligne, (etiquette, _) in zip(lignes, plan):
            try:
                m = json.loads(ligne)
            except ValueError:
                raise Refus(f"{variante} : ligne de mesure illisible ({etiquette})")
            if not isinstance(m, dict) or m.get("jeton") != jeton or m.get("etiquette") != etiquette:
                raise Refus(f"{variante} : ligne de mesure non authentique ({etiquette})")
            if m.get("code") != 0 or m.get("signal") != 0:
                trace = lire_sortie(sorties, f"journal/{etiquette}.err", 1 << 20) or b""
                raise Refus(f"{variante}/{etiquette} : code {m.get('code')}, signal {m.get('signal')}. " + propre(trace, 800))
            if valgrind and not isinstance(m.get("instructions"), int):
                raise Refus(f"{variante}/{etiquette} : résumé de Valgrind absent ou illisible")
            mesures[etiquette] = m
        return mesures
