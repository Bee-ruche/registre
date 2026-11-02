"""Juge commun Bee : erreurs, journal et lecture sûre des sorties écrites par le conteneur.

Tout ce que le conteneur a produit est hostile : un fichier peut être un lien symbolique vers un
fichier de l'hôte, un tube nommé qui bloque la lecture, un fichier énorme, ou un texte qui contient
des commandes de workflow GitHub. Rien de ce module ne suit un lien, n'ouvre un fichier spécial ni
ne lit au-delà d'une taille bornée. Le greffon d'un projet ne voit les sorties qu'à travers `Sorties`.
"""

import hashlib
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

    Renvoie None si le fichier n'existe pas ; Refus s'il n'est pas un fichier ordinaire ou s'il dépasse maximum (TAILLE_MAX_SORTIE au plus)."""
    maximum, morceaux = min(maximum, TAILLE_MAX_SORTIE), relatif.split("/")
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


def statut(racine, relatif, texte=None):
    """Fichier de statut « CODE ENTIER\\n » écrit par un harnais (code de retour, longueur produite)."""
    texte = exiger(racine, relatif, 64) if texte is None else texte
    m = re.fullmatch(rb"(-?\d{1,6}) (\d{1,12})\n", texte)
    if not m:
        raise Refus(f"statut illisible : {relatif}")
    return int(m.group(1)), int(m.group(2))


def _illisible(erreur):
    raise Refus(f"sorties illisibles : {propre(str(erreur), 300)}")


def figer(racine):
    """Empreinte d'un dossier de sorties, relevée dès la fin du conteneur qui l'a écrit (ruche-0036) : {chemin relatif :
    SHA-256 d'un fichier ordinaire, « dossier », ou « autre » (lien, fichier spécial)}. Ses clés sont la liste du dossier ;
    aucun lien n'est suivi, chaque fichier est lu par lire_sortie (taille bornée), un dossier illisible est un refus."""
    empreinte = {}
    for dossier, sous, fichiers in os.walk(racine, onerror=_illisible):
        for nom in sous + fichiers:
            relatif = os.path.relpath(os.path.join(dossier, nom), racine).replace(os.sep, "/")
            mode = os.lstat(os.path.join(dossier, nom)).st_mode
            empreinte[relatif] = (hashlib.sha256(exiger(racine, relatif)).hexdigest() if stat.S_ISREG(mode)
                                  else "dossier" if stat.S_ISDIR(mode) else "autre")
    return empreinte


class Sorties:
    """Les sorties d'une variante (A ou B) pour une étape, un dossier par côté (« f », « z »…).

    C'est la seule vue que le greffon d'un projet a sur ce que le conteneur a écrit. Elle retient ce que
    le greffon a effectivement lu (`lues`) : le juge commun vérifie ensuite que chaque entrée a eu au
    moins une sortie de B lue, si bien qu'un greffon qui oublie une entrée ou un scénario est arrêté au
    lieu de laisser passer une sortie que personne n'a regardée (revue adverse du 28/10).

    `noms` ({(côté, nom du greffon): nom écrit}) : les entrées ont été écrites sous d'autres noms (ruche-0037) ; le
    greffon garde les siens, traduits ici dans le dernier composant du chemin (« c/k000.6 » se lit « c/e0012.6 »).

    Avec `figees` ({côté: empreinte de figer}, toujours passé par le juge), seul ce qui a été figé se lit : un fichier
    modifié, ajouté ou retiré après son empreinte est un refus (ruche-0036)."""

    def __init__(self, racines, noms=None, figees=None):
        if isinstance(racines, Sorties):  # une vue neuve sur les mêmes sorties figées : ses lectures comptent à part
            racines, noms, figees = racines._racines, racines._noms if noms is None else noms, racines.figees
        self._racines, self._noms, self.figees = dict(racines), dict(noms or {}), figees
        self.lues = set()

    def __iter__(self):  # ses dossiers (juge.effacer)
        return iter(self._racines.values())

    def _chemin(self, cote, relatif):
        tete, barre, dernier = relatif.rpartition("/")
        for i in [len(dernier)] + [j for j in range(len(dernier) - 1, 0, -1) if dernier[j] == "."]:
            if (cote, dernier[:i]) in self._noms:
                return tete + barre + self._noms[(cote, dernier[:i])] + dernier[i:]
        return relatif

    def _racine(self, cote):
        if cote not in self._racines:
            raise Erreur(f"côté inconnu : {cote}")
        return self._racines[cote]

    def lire(self, cote, relatif, maximum=TAILLE_MAX_SORTIE):
        donnees = self.ecrite(cote, self._chemin(cote, relatif), maximum)
        if donnees is not None:
            self.lues.add((cote, relatif))
        return donnees

    def exiger(self, cote, relatif, maximum=TAILLE_MAX_SORTIE):
        donnees = self.lire(cote, relatif, maximum)
        if donnees is None:
            raise Refus(f"sortie absente : {relatif}")
        return donnees

    def statut(self, cote, relatif):
        return statut(None, relatif, self.exiger(cote, relatif, 64))

    def ecrite(self, cote, chemin, maximum=TAILLE_MAX_SORTIE):
        """La sortie écrite sous ce chemin (sans traduction de noms), telle qu'elle a été figée."""
        donnees = lire_sortie(self._racine(cote), chemin, maximum)
        empreinte = None if donnees is None else hashlib.sha256(donnees).hexdigest()
        if self.figees is not None and empreinte != self.figees[cote].get(chemin):
            raise Refus(f"sortie modifiée, ajoutée ou retirée après son empreinte : {propre(chemin, 200)}")
        return donnees

    def controler(self):
        """Après la comparaison : chaque dossier est encore exactement ce qui a été figé (liste et contenus)."""
        for cote, racine in self._racines.items():
            if figer(racine) != self.figees[cote]:
                raise Refus(f"sorties modifiées, ajoutées ou retirées après leur empreinte (côté {cote})")

    def couvre(self, cote, nom):
        """Vrai si une sortie lue de ce côté porte le nom de l'entrée (« c/k000.6 » couvre k000)."""
        for c, relatif in self.lues:
            dernier = relatif.rsplit("/", 1)[-1]
            if c == cote and (dernier == nom or dernier.startswith(nom + ".")):
                return True
        return False
