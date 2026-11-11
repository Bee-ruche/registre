"""Bee's common judge: errors, log and safe reading of the outputs the container wrote.

Everything the container produced is hostile: a file can be a symbolic link to a file of the
host, a named pipe that blocks reading, a huge file, or a text that holds GitHub workflow
commands. Nothing in this module follows a link, opens a special file or reads beyond a
bounded size. A project's plugin sees the outputs only through `Sorties`.
"""

import hashlib
import os
import re
import stat
import sys

TAILLE_MAX_SORTIE = 256 * 1024 * 1024


class Erreur(Exception):
    """The environment is not suitable (Docker missing, a base that does not compile, a badly set-up judge): code 2."""


class Panne(Erreur):
    """A failure of the machine that judges (Docker, its runtime, an image): an environment error, never a refusal (ruche-0136)."""


class Refus(Exception):
    """The judge refuses variant B: code 1."""


def journal(message):
    print(f"juge : {message}", file=sys.stderr, flush=True)


def propre(octets, maximum=1500):
    """Text from the container, safe to show: truncated, control characters removed."""
    texte = octets.decode("utf-8", "replace") if isinstance(octets, bytes) else str(octets)
    texte = re.sub("[^\x20-\x7e\n\xa0-\ud7ff\ue000-\uffff]", "?", texte[-maximum:])  # nor a lone surrogate
    return texte.replace("::", ": :")  # no GitHub workflow command


def lire_sortie(racine, relatif, maximum=TAILLE_MAX_SORTIE):
    """Reads racine/relatif without ever following a symbolic link (the container wrote in racine).

    Returns None if the file does not exist; Refus if it is not a regular file or if it exceeds maximum (TAILLE_MAX_SORTIE at most)."""
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
    """Status file « CODE INTEGER\\n » written by a harness (return code, length produced)."""
    texte = exiger(racine, relatif, 64) if texte is None else texte
    m = re.fullmatch(rb"(-?\d{1,6}) (\d{1,12})\n", texte)
    if not m:
        raise Refus(f"statut illisible : {relatif}")
    return int(m.group(1)), int(m.group(2))


def _illisible(erreur):
    raise Refus(f"sorties illisibles : {propre(str(erreur), 300)}")


def figer(racine):
    """Fingerprint of an outputs folder, taken as soon as the container that wrote it ends (ruche-0036): {relative path:
    SHA-256 of a regular file, « dossier », or « autre » (link, special file)}. Its keys are the folder's listing;
    no link is followed, each file is read by lire_sortie (bounded size), an unreadable folder is a refusal."""
    try:
        return _figer(racine)
    except OSError as e:  # status, listing or opening of what the container left: a refusal (1), never an error (2)
        _illisible(e)


def _figer(racine):
    empreinte = {}
    for dossier, sous, fichiers in os.walk(racine, onerror=_illisible):
        for nom in sous + fichiers:
            relatif = os.path.relpath(os.path.join(dossier, nom), racine).replace(os.sep, "/")
            mode = os.lstat(os.path.join(dossier, nom)).st_mode
            empreinte[relatif] = (hashlib.sha256(exiger(racine, relatif)).hexdigest() if stat.S_ISREG(mode)
                                  else "dossier" if stat.S_ISDIR(mode) else "autre")
    return empreinte


def copier(source, cible):
    """The outputs a container left on its own tmpfs, copied into cible (an empty folder of the judge) before that tmpfs goes
    (ruche-0117): no link followed, each file read by lire_sortie (size bounded), a link or special file left as a link (figer:
    « autre », a refusal when read); anything unreadable is a refusal, as in figer."""
    try:
        for dossier, sous, fichiers in os.walk(source, onerror=_illisible):
            for nom in sous + fichiers:
                relatif = os.path.relpath(os.path.join(dossier, nom), source)
                mode, copie = os.lstat(os.path.join(source, relatif)).st_mode, os.path.join(cible, relatif)
                if stat.S_ISDIR(mode):
                    os.mkdir(copie)
                elif stat.S_ISREG(mode):
                    with open(copie, "xb") as f:
                        f.write(exiger(source, relatif.replace(os.sep, "/")))
                else:
                    os.symlink("autre", copie)
    except OSError as e:
        _illisible(e)


class Sorties:
    """The outputs of a variant (A or B) for a step, one folder per side (« f », « z »…).

    It is the only view a project's plugin has of what the container wrote. It keeps what
    the plugin actually read (`lues`): the common judge then checks that each input had at
    least one output of B read, so that a plugin that forgets an input or a scenario is stopped
    instead of letting through an output nobody looked at (adversarial review of 28 October).

    `noms` ({(side, the plugin's name): written name}): the inputs were written under other names (ruche-0037); the
    plugin keeps its own, translated here in the path's last component (« c/k000.6 » reads « c/e0012.6 »).

    With `figees` ({side: figer's fingerprint}, always passed by the judge), only what was frozen is read: a file
    changed, added or removed after its fingerprint is a refusal (ruche-0036)."""

    def __init__(self, racines, noms=None, figees=None):
        if isinstance(racines, Sorties):  # a new view of the same frozen outputs: its reads count apart
            racines, noms, figees = racines._racines, racines._noms if noms is None else noms, racines.figees
        self._racines, self._noms, self.figees = dict(racines), dict(noms or {}), figees
        self.lues = set()

    def __iter__(self):  # its folders (judge.erase)
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
        """The output written under this path (no translation of names), as it was frozen."""
        donnees = lire_sortie(self._racine(cote), chemin, maximum)
        empreinte = None if donnees is None else hashlib.sha256(donnees).hexdigest()
        if self.figees is not None and empreinte != self.figees[cote].get(chemin):
            raise Refus(f"sortie modifiée, ajoutée ou retirée après son empreinte : {propre(chemin, 200)}")
        return donnees

    def controler(self):
        """After the comparison: each folder is still exactly what was frozen (listing and contents)."""
        for cote, racine in self._racines.items():
            if figer(racine) != self.figees[cote]:
                raise Refus(f"sorties modifiées, ajoutées ou retirées après leur empreinte (côté {cote})")

    def couvre(self, cote, nom):
        """True if an output read on this side bears the input's name (« c/k000.6 » covers k000)."""
        for c, relatif in self.lues:
            dernier = relatif.rsplit("/", 1)[-1]
            if c == cote and (dernier == nom or dernier.startswith(nom + ".")):
                return True
        return False
