"""Juge commun Bee : image, conteneurs isolés et exécution sous le lanceur chrono.

Toute exécution de code issu de la PR passe par `Docker.lancer` : pas de réseau, système de fichiers en
lecture seule, aucune capacité, pas d'élévation de privilège, utilisateur 65534, /tmp non exécutable,
nombre de processus et mémoire bornés. Le conteneur ne voit que ce qui lui est monté.
"""

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading

from lecture import Erreur, Refus, copier, journal, propre

ICI = os.path.dirname(os.path.abspath(__file__))
ISOLATION = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
             "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "-e", "HOME=/tmp", "-e", "LC_ALL=C", "--hostname", "juge"]
PAQUET = re.compile(r"[a-z0-9][a-z0-9+.-]{0,63}")
HARNAIS = "/variante/execution"  # what follows it in a plan command reaches it on its descriptor 0, not in argv
TEMPS = 946684800  # access and modification times of everything mounted for an execution, set before each container
# Each execution's own tmpfs (ruche-0117), mounted just before its container and gone once its outputs are copied out: all the
# container sees of the judge (chrono, the harness, its inputs, /etc files Docker would write on the host's disk, its outputs) is
# created there anew, in a fixed order: no inode, link count, time, free space or mount line follows the run's progress.
TMPFS = "size=4g,nr_inodes=262144,mode=0755,nosuid,nodev"
ETC = {"hostname": "juge\n", "hosts": "127.0.0.1\tlocalhost\n", "resolv.conf": ""}


def temps_fixes(*dossiers):
    """Fixed times on these folders (the judge's own) and everything in them, no link followed."""
    for dossier in dossiers:
        for racine, sous, noms in os.walk(dossier):
            for chemin in [racine] + [os.path.join(racine, n) for n in sous + noms]:
                os.utime(chemin, (TEMPS, TEMPS), follow_symlinks=False)


def monture(*commande):
    """mount or umount, as root or through sudo -n (juge.yml's runner); failing is an error of the environment."""
    r = subprocess.run(([] if os.geteuid() == 0 else ["sudo", "-n"]) + list(commande), capture_output=True, text=True)
    if r.returncode != 0:
        raise Erreur(f"{commande[0]} du tmpfs d'une exécution impossible (root ou sudo -n requis) : " + propre(r.stderr, 300))


def copier_arbre(source, cible):
    """A folder of the judge copied in a fixed order (names sorted), modes kept: the same tree gets the same inodes."""
    for dossier, sous, noms in os.walk(source):
        sous.sort()
        os.makedirs(os.path.join(cible, os.path.relpath(dossier, source)), exist_ok=True)
        for n in sorted(noms):
            shutil.copy(os.path.join(dossier, n), os.path.join(cible, os.path.relpath(dossier, source), n))


class Docker:
    # No file above lecture.TAILLE_MAX_SORTIE, no log on the host's disk; the host keeps SORTIE_MAX of stdout (start), stderr (end).
    BORNES = ["--ulimit", f"fsize={256 << 20}", "--log-driver", "none"]
    SORTIE_MAX = 1 << 20

    def __init__(self, image, memoire="4g"):
        self.image, self.memoire = image, memoire

    def lancer(self, commande, montages, pids=2, entree=None, delai=3600):
        nom = "bee-juge-" + secrets.token_hex(6)
        cmd = ["docker", "run", "--rm", "--name", nom, "--pids-limit", str(pids),
               "--memory", self.memoire, "--memory-swap", self.memoire] + self.BORNES + ISOLATION
        if entree is not None:
            cmd.append("-i")
        for hote, cible, lecture_seule in montages:
            if "," in hote or "," in cible:
                raise Erreur(f"chemin de montage invalide : {hote}")
            cmd += ["--mount", f"type=bind,source={hote},target={cible}" + (",readonly" if lecture_seule else "")]
        cmd += [self.image] + commande
        with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
            lus = (bytearray(), bytearray())
            fils = [threading.Thread(target=_garder, args=(f, g, self.SORTIE_MAX, fin), daemon=True)
                    for f, g, fin in ((p.stdout, lus[0], False), (p.stderr, lus[1], True))]
            for f in fils:
                f.start()
            with contextlib.suppress(BrokenPipeError):  # a token and a plan: far below a pipe's capacity
                p.stdin.write(entree or b"")
                p.stdin.close()
            try:
                p.wait(timeout=delai)
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "kill", nom], capture_output=True)
                p.kill()
                raise Refus(f"délai de {delai} s dépassé dans le conteneur ({commande[0]})")
            finally:
                for f in fils:
                    f.join()
        return subprocess.CompletedProcess(cmd, p.returncode, bytes(lus[0]), bytes(lus[1]))


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


def identifiant_image(etiquette):
    """The image's id, the SHA-256 of its configuration (which names its layers): containers run it, juge.json records it."""
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", etiquette], capture_output=True, text=True)
    if r.returncode != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", r.stdout.strip()):
        raise Erreur(f"identifiant de l'image {etiquette} illisible : " + propre(r.stderr, 300))
    return r.stdout.strip()


def _garder(flux, garde, maximum, fin):
    """Reads a container's stream to its end, keeping at most `maximum` bytes of it: its start, or its end (fin)."""
    for bloc in iter(lambda: flux.read(1 << 16), b""):
        garde += bloc if fin else bloc[:maximum - len(garde)]
        del garde[:-maximum if fin else 0]


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
        """plan : [(étiquette, [programme, arguments…])], HARNAIS among them. Renvoie {étiquette: mesure}.
        Plan, options and the harness's arguments go through standard inputs: same argv and files in every mode."""
        lignes = []
        for etiquette, commande in plan:
            i = commande.index(HARNAIS) + 1 if HARNAIS in commande else len(commande)
            if i == len(commande) or any(c in x for x in [etiquette] + commande for c in "\t\n"):
                raise Erreur(f"commande de plan invalide : {propre(etiquette, 80)}")
            lignes.append("\t".join([etiquette, " ".join(commande[i:])] + commande[:i]))
        dossier_ouvert(sorties)
        jeton = secrets.token_hex(16)
        entree = "\n".join([jeton, f"{int(delai)} {int(bool(valgrind))}"] + lignes) + "\n"
        racine = os.path.join(self.travail, "execution")  # the same path each time: one execution at a time
        os.mkdir(racine)
        monture("mount", "-t", "tmpfs", "-o", f"{TMPFS},uid={os.getuid()},gid={os.getgid()}", "tmpfs", racine)
        try:
            copier_arbre(self.chrono, os.path.join(racine, "chrono"))
            copier_arbre(self.constructions[variante], os.path.join(racine, "variante"))
            os.mkdir(os.path.join(racine, "etc"))
            for nom, texte in ETC.items():
                with open(os.path.join(racine, "etc", nom), "w", encoding="ascii") as f:
                    f.write(texte)
            dossier_ouvert(os.path.join(racine, "sorties"))
            copier_arbre(entrees, os.path.join(racine, "entrees"))  # last: the other inodes do not depend on the inputs
            temps_fixes(racine)
            montages = [(os.path.join(racine, n), "/" + n, n != "sorties") for n in ("chrono", "variante", "entrees", "sorties")]
            montages += [(os.path.join(racine, "etc", n), "/etc/" + n, True) for n in ETC]
            r = self.docker.lancer(["/chrono/chrono"], montages, pids=2, entree=entree.encode(), delai=delai * len(plan) + 300)
            copier(os.path.join(racine, "sorties"), sorties)
        finally:
            monture("umount", "--lazy", racine)
            os.rmdir(racine)
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
                raise Refus(f"{variante}/{etiquette} : code {m.get('code')}, signal {m.get('signal')}. " + propre(r.stderr, 800))
            if valgrind and not isinstance(m.get("instructions"), int):
                raise Refus(f"{variante}/{etiquette} : résumé de Valgrind absent ou illisible")
            mesures[etiquette] = m
        return mesures
