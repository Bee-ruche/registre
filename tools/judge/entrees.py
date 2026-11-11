"""Bee's common judge: inputs given to a project's harness.

An input has a side (« f », « z »…), a name, bytes, an integer passed to the harness (often the
size, or the size of the buffer to provide) and what the host expects of it (known to the plugin alone).
Each side has its own container: a harness never sees the inputs of another side (for
miniz, a decompression never sees the originals it could copy).

Format read by the harness (folder mounted on /entrees):
  liste            one line per input: « <side> <name> <integer> »
  <side>/<name>    the input's bytes
"""

import collections
import os
import re
import subprocess
import sys

from lecture import Erreur

Entree = collections.namedtuple("Entree", "cote nom donnees taille attendu")
Entree.__new__.__defaults__ = (None,)

NOM_PERMIS = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,62}")  # 63 characters at most: the harnesses' « %63s »
COTE_PERMIS = re.compile(r"[a-z]")


def verifier_entrees(entrees, cotes):
    noms = set()
    for e in entrees:
        if e.cote not in cotes or not COTE_PERMIS.fullmatch(e.cote):
            raise Erreur(f"côté inconnu pour {e.nom!r} : {e.cote!r}")
        if not NOM_PERMIS.fullmatch(e.nom) or (e.cote, e.nom) in noms:
            raise Erreur(f"nom d'entrée invalide ou en double : {e.nom!r}")
        if not isinstance(e.donnees, bytes) or not isinstance(e.taille, int) or e.taille < 0:
            raise Erreur(f"entrée mal formée : {e.nom!r}")
        noms.add((e.cote, e.nom))


def ecrire(dossier, entrees, cotes):
    """Writes the inputs of ONE side (already filtered); every side's subfolder exists, even empty."""
    for c in cotes:
        os.makedirs(os.path.join(dossier, c), exist_ok=True)
    lignes = []
    for e in entrees:
        with open(os.path.join(dossier, e.cote, e.nom), "wb") as f:
            f.write(e.donnees)
        lignes.append(f"{e.cote} {e.nom} {e.taille}")
    with open(os.path.join(dossier, "liste"), "w", encoding="ascii") as f:
        f.write("\n".join(lignes) + "\n")


def perturber(rng, fichiers, prefixe=None):
    """Copy of files [(name, bytes)] with a few bytes changed at random (one per 64 KiB, at least one).

    The same shapes as the corpus, unpredictable answers: nothing can be cached from one repetition to the next."""
    resultat = []
    for nom, d in fichiers:
        b = bytearray(d[:prefixe] if prefixe else d)
        for _ in range(max(1, len(b) // 65536) if b else 0):
            b[rng.randrange(len(b))] ^= rng.randrange(1, 256)
        resultat.append((nom, bytes(b)))
    return resultat


def charger_corpus(outillage, generateur, dossier, prefixe_nom="k"):
    """Runs the BASE's corpus generator (python, on the host), then reads the files produced, sorted.

    Returns [(name, bytes)] with neutral names (k000, k001…): the harness does not see the original names."""
    if generateur:
        r = subprocess.run([sys.executable, os.path.join(outillage, generateur)], capture_output=True, text=True, cwd=outillage)
        if r.returncode != 0:
            raise Erreur("corpus non conforme : " + r.stderr[-1000:])
    racine = os.path.join(outillage, dossier)
    fichiers = []
    for chemin, sous, noms in os.walk(racine):
        sous.sort()
        for n in sorted(noms):
            with open(os.path.join(chemin, n), "rb") as f:
                fichiers.append((f"{prefixe_nom}{len(fichiers):03d}", f.read()))
    if not fichiers:
        raise Erreur("corpus vide")
    return fichiers
