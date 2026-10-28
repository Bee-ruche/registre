"""Juge commun Bee : erreurs, journal et lecture sûre des sorties écrites par le conteneur.

Tout ce que le conteneur a produit est hostile : un fichier peut être un lien symbolique vers un
fichier de l'hôte, un tube nommé qui bloque la lecture, un fichier énorme, ou un texte qui contient
des commandes de workflow GitHub. Rien de ce module ne suit un lien, n'ouvre un fichier spécial ni
ne lit au-delà d'une taille bornée. Le greffon d'un projet ne voit les sorties qu'à travers `Sorties`.
"""

import os
import re
import stat
import sys

TAILLE_MAX_SORTIE = 256 * 1024 * 1024


class Erreur(Exception):
    """L'environnement ne convient pas (Docker absent, base qui ne compile pas, juge mal monté) : code 2."""


class Refus(Exception):
    """Le juge refuse la variante B : code 1."""


def journal(message):
    print(f"juge : {message}", file=sys.stderr, flush=True)


def propre(octets, maximum=1500):
    """Texte venu du conteneur, affichable sans risque : tronqué, caractères de contrôle retirés."""
    texte = octets.decode("utf-8", "replace") if isinstance(octets, bytes) else str(octets)
    texte = re.sub(r"[^\x20-\x7e\n -￿]", "?", texte[-maximum:])
    return texte.replace("::", ": :")  # pas de commande de workflow GitHub


def lire_sortie(racine, relatif, maximum=TAILLE_MAX_SORTIE):
    """Lit racine/relatif sans jamais suivre un lien symbolique (le conteneur a écrit dans racine).

    Renvoie None si le fichier n'existe pas ; Refus s'il n'est pas un fichier ordinaire ou s'il est trop gros."""
    morceaux = relatif.split("/")
    if any(m in ("", ".", "..") for m in morceaux):
        raise Refus(f"chemin de sortie invalide : {relatif}")
    fd = os.open(racine, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for m in morceaux[:-1]:
            try:
                suivant = os.open(m, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                return None
            except OSError:
                raise Refus(f"sortie invalide (dossier piégé) : {relatif}")
            os.close(fd)
            fd = suivant
        try:
            ffd = os.open(morceaux[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        except FileNotFoundError:
            return None
        except OSError:
            raise Refus(f"sortie invalide (lien ou fichier spécial) : {relatif}")
    finally:
        os.close(fd)
    try:
        st = os.fstat(ffd)
        if not stat.S_ISREG(st.st_mode):
            raise Refus(f"sortie invalide (pas un fichier ordinaire) : {relatif}")
        if st.st_size > maximum:
            raise Refus(f"sortie trop grosse : {relatif} ({st.st_size} octets)")
        morceaux_lus, total = [], 0
        while True:
            bloc = os.read(ffd, 1 << 20)
            if not bloc:
                break
            total += len(bloc)
            if total > maximum:
                raise Refus(f"sortie trop grosse : {relatif}")
            morceaux_lus.append(bloc)
        return b"".join(morceaux_lus)
    finally:
        os.close(ffd)


def exiger(racine, relatif, maximum=TAILLE_MAX_SORTIE):
    donnees = lire_sortie(racine, relatif, maximum)
    if donnees is None:
        raise Refus(f"sortie absente : {relatif}")
    return donnees


def statut(racine, relatif):
    """Fichier de statut « CODE ENTIER\\n » écrit par un harnais (code de retour, longueur produite)."""
    texte = exiger(racine, relatif, 64)
    m = re.fullmatch(rb"(-?\d{1,6}) (\d{1,12})\n", texte)
    if not m:
        raise Refus(f"statut illisible : {relatif}")
    return int(m.group(1)), int(m.group(2))


class Sorties:
    """Les sorties d'une variante (A ou B) pour une étape, un dossier par côté (« f », « z »…).

    C'est la seule vue que le greffon d'un projet a sur ce que le conteneur a écrit."""

    def __init__(self, racines):
        self._racines = dict(racines)

    def _racine(self, cote):
        if cote not in self._racines:
            raise Erreur(f"côté inconnu : {cote}")
        return self._racines[cote]

    def lire(self, cote, relatif, maximum=TAILLE_MAX_SORTIE):
        return lire_sortie(self._racine(cote), relatif, maximum)

    def exiger(self, cote, relatif, maximum=TAILLE_MAX_SORTIE):
        return exiger(self._racine(cote), relatif, maximum)

    def statut(self, cote, relatif):
        return statut(self._racine(cote), relatif)
