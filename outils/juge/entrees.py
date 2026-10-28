"""Juge commun Bee : entrées données au harnais d'un projet.

Une entrée a un côté (« f », « z »…), un nom, des octets, un entier passé au harnais (souvent la
taille, ou la taille du tampon à fournir) et ce que l'hôte attend d'elle (connu du seul greffon).
Chaque côté a son propre conteneur : un harnais ne voit jamais les entrées d'un autre côté (pour
miniz, une décompression ne voit jamais les originaux qu'elle pourrait recopier).

Format lu par le harnais (dossier monté sur /entrees) :
  liste            une ligne par entrée : « <côté> <nom> <entier> »
  <côté>/<nom>     les octets de l'entrée
"""

import collections
import os
import re
import subprocess
import sys

from lecture import Erreur

Entree = collections.namedtuple("Entree", "cote nom donnees taille attendu")
Entree.__new__.__defaults__ = (None,)

NOM_PERMIS = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}")
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
    """Écrit les entrées d'UN côté (déjà filtrées) ; tous les sous-dossiers de côté existent, même vides."""
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
    """Copie de fichiers [(nom, octets)] avec quelques octets changés au hasard (un par 64 Kio, au moins un).

    Mêmes formes que le corpus, réponses imprévisibles : rien ne peut être mis en cache d'une répétition à l'autre."""
    resultat = []
    for nom, d in fichiers:
        b = bytearray(d[:prefixe] if prefixe else d)
        for _ in range(max(1, len(b) // 65536) if b else 0):
            b[rng.randrange(len(b))] ^= rng.randrange(1, 256)
        resultat.append((nom, bytes(b)))
    return resultat


def charger_corpus(outillage, generateur, dossier, prefixe_nom="k"):
    """Lance le générateur de corpus de la BASE (python, sur l'hôte), puis lit les fichiers produits, triés.

    Renvoie [(nom, octets)] avec des noms neutres (k000, k001…) : le harnais ne voit pas les noms d'origine."""
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
