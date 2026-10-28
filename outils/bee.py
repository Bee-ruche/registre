#!/usr/bin/env python3
"""bee : l'outil en ligne de commande du registre Bee.

    python3 outils/bee.py --help

Dépendances : Python 3.10 ou plus récent, PyYAML et jsonschema
(`pip install -r outils/requirements.txt`).

L'outil ne fait aucun appel réseau et n'exécute jamais le code d'un projet.
Il lit et écrit les fichiers YAML du registre. Les opérations GitHub
(branches, pull requests) restent à la charge de l'agent et de son
utilisateur : voir AGENTS.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import html
import json
import os
import pathlib
import re
import subprocess
import sys
from collections import defaultdict

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - message pour l'utilisateur
    sys.exit("bee : dépendances manquantes. Installez-les avec : pip install pyyaml jsonschema")

VERSION = "0.1.0"
RACINE_OUTIL = pathlib.Path(__file__).resolve().parent.parent
LIGNES_MAX = {"S": 50, "M": 200, "L": 400}
ORDRE_TAILLES = ("S", "M", "L")
POIDS_VOTE = {"Nouveau": 0, "Contributeur": 1, "Confirmé": 2}
TAILLES_PAR_NIVEAU = {"Nouveau": ("S",), "Contributeur": ("S", "M"), "Confirmé": ("S", "M", "L")}
ID_CONTRIBUTION = re.compile(r"^(?P<tache>[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{4})-c(?P<n>[0-9]+)$")
ID_PROPOSITION = re.compile(r"^P-[0-9]{4}$")
A_REMPLIR = "À REMPLIR"
CLES_LIBRE_SERVICE_TACHE = {"statut", "reservation", "contribution", "notes"}


class ErreurBee(Exception):
    """Erreur d'usage, affichée telle quelle (code de sortie 1)."""


# --------------------------------------------------------------------------
# YAML et dates
# --------------------------------------------------------------------------

class ChargeurBee(yaml.SafeLoader):
    """Chargeur YAML qui garde les dates en texte : les schémas les attendent ainsi."""


ChargeurBee.yaml_implicit_resolvers = {
    premier: [r for r in resolveurs if r[0] != "tag:yaml.org,2002:timestamp"]
    for premier, resolveurs in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def charger_texte_yaml(texte, origine="<texte>"):
    try:
        return yaml.load(texte, Loader=ChargeurBee)
    except yaml.YAMLError as e:
        raise ErreurBee(f"{origine} : YAML invalide ({e})") from None


def lire_yaml(chemin):
    return charger_texte_yaml(pathlib.Path(chemin).read_text(encoding="utf-8"), str(chemin))


def ecrire_yaml(chemin, donnees):
    chemin = pathlib.Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False, width=100)
    chemin.write_text(texte, encoding="utf-8")


def guillemets(valeur):
    """Scalaire YAML entre guillemets doubles (une chaîne JSON est un scalaire YAML valide)."""
    return json.dumps(str(valeur), ensure_ascii=False)


def maintenant():
    """Instant courant en UTC ; BEE_MAINTENANT permet de le fixer (tests, CI rejouable)."""
    fixe = os.environ.get("BEE_MAINTENANT")
    if fixe:
        return lire_instant(fixe, "BEE_MAINTENANT")
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def en_iso(instant):
    return instant.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lire_instant(texte, origine=""):
    try:
        instant = dt.datetime.fromisoformat(str(texte).replace("Z", "+00:00"))
    except ValueError:
        raise ErreurBee(f"{origine} : instant invalide « {texte} » (attendu : 2026-10-27T01:30:00Z)") from None
    if instant.tzinfo is None:
        raise ErreurBee(f"{origine} : instant sans fuseau « {texte} » (ajoutez Z pour UTC)")
    return instant


def lire_date(texte, origine=""):
    try:
        return dt.date.fromisoformat(str(texte))
    except ValueError:
        raise ErreurBee(f"{origine} : date invalide « {texte} » (attendu : 2026-10-27)") from None


TYPES_JSON = {"string": "un texte", "number": "un nombre", "integer": "un entier", "array": "une liste",
              "object": "un objet", "null": "null", "boolean": "vrai ou faux"}


def message_schema(erreur):
    """Traduit en français les erreurs de validation les plus courantes."""
    v, attendu, valeur = erreur.validator, erreur.validator_value, erreur.instance
    if v == "required":
        manquants = [c for c in attendu if isinstance(valeur, dict) and c not in valeur]
        return f"champ obligatoire manquant : {', '.join(manquants) or ', '.join(attendu)}"
    if v == "enum":
        return f"valeur « {valeur} » non permise (attendu : {', '.join(str(x) for x in attendu)})"
    if v == "const":
        return f"valeur « {valeur} » non permise (attendu : {attendu})"
    if v == "type":
        types = attendu if isinstance(attendu, list) else [attendu]
        return f"« {valeur} » devrait être {' ou '.join(TYPES_JSON.get(t, t) for t in types)}"
    if v == "minLength":
        return f"texte trop court ({len(valeur)} caractères, minimum {attendu})"
    if v == "maxLength":
        return f"texte trop long ({len(valeur)} caractères, maximum {attendu})"
    if v == "pattern":
        return f"format incorrect : « {valeur} »"
    if v == "format":
        return f"« {valeur} » n'est pas au format {attendu}"
    if v == "additionalProperties":
        connus = set((erreur.schema or {}).get("properties", {}))
        return f"champ(s) inconnu(s) : {', '.join(sorted(set(valeur) - connus)) if isinstance(valeur, dict) else valeur}"
    if v == "minimum":
        return f"valeur {valeur} inférieure au minimum {attendu}"
    if v == "maximum":
        return f"valeur {valeur} supérieure au maximum {attendu}"
    if v == "minItems":
        return f"liste trop courte (au moins {attendu} élément(s))"
    if v == "not":
        return "champ non permis dans cet état (par exemple une réservation sur une tâche qui n'est pas réservée)"
    return erreur.message


def champs_a_remplir(donnees, chemin=""):
    """Chemins des valeurs qui contiennent encore « À REMPLIR »."""
    if isinstance(donnees, dict):
        return [c for cle, val in donnees.items() for c in champs_a_remplir(val, f"{chemin}/{cle}" if chemin else str(cle))]
    if isinstance(donnees, list):
        return [c for i, val in enumerate(donnees) for c in champs_a_remplir(val, f"{chemin}/{i}")]
    return [chemin or "(racine)"] if isinstance(donnees, str) and A_REMPLIR in donnees else []


# --------------------------------------------------------------------------
# Édition textuelle des tâches (préserve la mise en forme écrite à la main)
# --------------------------------------------------------------------------

def _est_suite_de_bloc(ligne):
    return ligne.startswith((" ", "\t", "- ")) or ligne == "-"


def _bloc_racine(lignes, cle):
    """(début, fin) du bloc de premier niveau `cle:` dans la liste de lignes, ou None."""
    for i, ligne in enumerate(lignes):
        if ligne.startswith(cle + ":"):
            j = i + 1
            while j < len(lignes):
                if _est_suite_de_bloc(lignes[j]):
                    j += 1
                elif lignes[j].strip() == "":
                    k = j
                    while k < len(lignes) and lignes[k].strip() == "":
                        k += 1
                    if k < len(lignes) and _est_suite_de_bloc(lignes[k]):
                        j = k
                    else:
                        break
                else:
                    break
            return i, j
    return None


def remplacer_bloc(texte, cle, nouvelles_lignes, apres=None):
    lignes = texte.split("\n")
    position = _bloc_racine(lignes, cle)
    if position:
        debut, fin = position
        lignes[debut:fin] = nouvelles_lignes
    elif nouvelles_lignes:
        ancre = _bloc_racine(lignes, apres) if apres else None
        if ancre:
            lignes[ancre[1]:ancre[1]] = nouvelles_lignes
        else:
            fin = len(lignes)
            while fin > 0 and lignes[fin - 1].strip() == "":
                fin -= 1
            lignes[fin:fin] = nouvelles_lignes
    return "\n".join(lignes)


_INCHANGE = object()


def modifier_tache(chemin, *, statut=None, reservation=_INCHANGE, contribution=_INCHANGE, note=None):
    texte = pathlib.Path(chemin).read_text(encoding="utf-8")
    if statut is not None:
        texte = remplacer_bloc(texte, "statut", [f"statut: {statut}"])
    if reservation is not _INCHANGE:
        lignes = [] if reservation is None else [
            "reservation:",
            f"  utilisateur: {guillemets(reservation['utilisateur'])}",
            f"  depuis: {guillemets(reservation['depuis'])}",
        ]
        texte = remplacer_bloc(texte, "reservation", lignes, apres="statut")
    if contribution is not _INCHANGE:
        lignes = [] if contribution is None else [f"contribution: {contribution}"]
        texte = remplacer_bloc(texte, "contribution", lignes, apres="reservation" if reservation not in (_INCHANGE, None) else "statut")
    if note is not None:
        notes = list(charger_texte_yaml(texte, str(chemin)).get("notes") or []) + [note]
        lignes = ["notes:"]
        for n in notes:
            lignes += [f"  - par: {guillemets(n['par'])}", f"    le: {guillemets(n['le'])}", f"    texte: {guillemets(n['texte'])}"]
        texte = remplacer_bloc(texte, "notes", lignes)
    charger_texte_yaml(texte, str(chemin))  # garde-fou : le résultat doit rester du YAML valide
    pathlib.Path(chemin).write_text(texte, encoding="utf-8")


# --------------------------------------------------------------------------
# Chargement du registre
# --------------------------------------------------------------------------

class Registre:
    def __init__(self, racine=None, schemas=None):
        self.racine = pathlib.Path(racine or os.environ.get("BEE_REGISTRE") or RACINE_OUTIL).resolve()
        if not (self.racine / "bee.yaml").exists():
            raise ErreurBee(f"{self.racine} n'est pas un registre Bee (bee.yaml introuvable). Utilisez --registre.")
        # Les schémas viennent de l'outil lui-même, jamais des données vérifiées :
        # une pull request ne peut pas assouplir les schémas qui la jugent.
        self.dossier_schemas = pathlib.Path(schemas or RACINE_OUTIL / "schemas")
        self._schemas = {}
        self.problemes_chargement = []
        self.config = self._lire("bee.yaml") or {}
        conseil = self._lire("gouvernance/conseil.yaml") or {}
        self.conseil = {m.get("pseudo") for m in conseil.get("membres", []) if isinstance(m, dict)}
        # Gardiens : agents (ou humains) nommés par le conseil, dont la relecture compte pour la porte de
        # R3 et pour les changements de juges. Ils relisent ; ils ne fusionnent jamais (c'est le workflow).
        gardiens = self._lire_facultatif("gouvernance/gardiens.yaml") or {}
        self.gardiens = {m.get("pseudo") for m in gardiens.get("membres", []) or [] if isinstance(m, dict)}
        self.robots = set(self.config.get("robots") or [])
        self.categories = {c["id"]: c for c in (self._lire("categories.yaml") or []) if isinstance(c, dict) and "id" in c}
        self.projets = self._dossier("projets/*.yaml")
        self.taches = self._dossier("taches/*/*.yaml")
        self.enregistrements = self._dossier("contributions/*/*.yaml")
        self.membres = self._dossier("membres/*.yaml")
        self.propositions = self._dossier("propositions/*.yaml")
        self.votes = []
        for chemin in sorted(self.racine.glob("votes/*/*.yaml")):
            donnees = self._lire_fichier(chemin)
            if donnees is not None:
                self.votes.append((chemin, donnees))
        self.mesures = []
        for chemin in sorted(self.racine.glob("mesures/*/*.yaml")):
            donnees = self._lire_fichier(chemin)
            if donnees is not None:
                self.mesures.append((chemin, donnees))

    def _lire(self, relatif):
        chemin = self.racine / relatif
        if not chemin.exists():
            self.problemes_chargement.append(f"{relatif} : fichier manquant")
            return None
        return self._lire_fichier(chemin)

    def _lire_facultatif(self, relatif):
        chemin = self.racine / relatif
        return self._lire_fichier(chemin) if chemin.exists() else None

    def privilegies(self):
        """Conseil et gardiens : ceux dont la relecture ouvre la porte de R3."""
        return set(self.conseil) | set(self.gardiens)

    def _lire_fichier(self, chemin):
        try:
            return lire_yaml(chemin)
        except ErreurBee as e:
            self.problemes_chargement.append(str(e))
            return None

    def _dossier(self, motif):
        resultat = {}
        for chemin in sorted(self.racine.glob(motif)):
            donnees = self._lire_fichier(chemin)
            if donnees is not None:
                resultat[chemin.stem] = (chemin, donnees)
        return resultat

    def rel(self, chemin):
        try:
            return str(pathlib.Path(chemin).resolve().relative_to(self.racine))
        except ValueError:
            return str(chemin)

    def schema(self, nom):
        if nom not in self._schemas:
            texte = (self.dossier_schemas / f"{nom}.schema.json").read_text(encoding="utf-8")
            self._schemas[nom] = Draft202012Validator(json.loads(texte), format_checker=FormatChecker())
        return self._schemas[nom]

    def tache(self, identifiant):
        if identifiant not in self.taches:
            raise ErreurBee(f"tâche inconnue : {identifiant} (bee lister --statut toutes)")
        return self.taches[identifiant]

    def enregistrement(self, identifiant):
        if identifiant not in self.enregistrements:
            raise ErreurBee(f"contribution inconnue : {identifiant} (bee classement)")
        return self.enregistrements[identifiant]

    def exiger_membre(self, pseudo):
        if pseudo not in self.membres and pseudo not in self.conseil:
            raise ErreurBee(f"{pseudo} n'est pas inscrit dans ce registre. Si votre PR d'inscription est ouverte, attendez sa fusion, "
                            f"puis : git switch main && git pull upstream main. Sinon : bee inscrire --pseudo {pseudo} --compte-cree-le AAAA-MM-JJ")

    def est_integree(self, identifiant):
        return identifiant in self.taches and self.taches[identifiant][1].get("statut") == "integree"

    def bloquee_par(self, tache):
        return [d for d in tache.get("depend_de") or [] if not self.est_integree(d)]

    def metriques(self, projet):
        if projet not in self.projets:
            return {}
        return {m["id"]: m for m in self.projets[projet][1].get("metriques") or [] if isinstance(m, dict)}


# --------------------------------------------------------------------------
# Réputation, score, votes
# --------------------------------------------------------------------------

def calculer_niveaux(reg):
    stats = defaultdict(lambda: {"integrees": 0, "relectures": 0})
    for pseudo in reg.membres:
        stats[pseudo]
    for _, enr in reg.enregistrements.values():
        if not isinstance(enr, dict) or "auteur" not in enr:
            continue
        statut = enr.get("statut")
        if statut == "integree":
            stats[enr["auteur"]]["integrees"] += 1
        for r in enr.get("relectures") or []:
            s = stats[r.get("relecteur")]
            if r.get("defaut_confirme"):
                s["relectures"] += 2
            elif statut == "annulee" and r.get("avis") == "favorable":
                s["relectures"] -= 1
            elif (statut == "integree" and r.get("avis") == "favorable") or (statut == "refusee" and r.get("avis") == "defavorable"):
                s["relectures"] += 1
    niveaux = {}
    for pseudo, s in stats.items():
        if s["integrees"] >= 10 and s["relectures"] >= 10:
            niveau = "Confirmé"
        elif s["integrees"] >= 1:
            niveau = "Contributeur"
        else:
            niveau = "Nouveau"
        niveaux[pseudo] = {**s, "niveau": niveau}
    return niveaux


def niveau_de(niveaux, pseudo):
    return niveaux.get(pseudo, {}).get("niveau", "Nouveau")


def calculer_score(reg, enr, niveaux):
    """S = G × P × C / (1 + L/100) × V (voir docs/evaluation.md). None tant que la CI n'a pas mesuré."""
    verdict = enr.get("verdict") or {}
    if verdict.get("ci") != "verte" or verdict.get("gain") is None:
        return None
    tache = reg.taches.get(enr.get("tache"))
    portee = float(tache[1].get("portee", 1.0)) if tache else 1.0
    gain = float(verdict["gain"])
    lignes = int(verdict.get("lignes_modifiees", 0))
    favorables = {r["relecteur"] for r in enr.get("relectures") or [] if r.get("avis") == "favorable"}
    confiance = min(1.0, len(favorables) / 3)
    numerateur = denominateur = 0
    for _, vote in reg.votes:
        if vote.get("sujet") == enr.get("id"):
            poids = POIDS_VOTE[niveau_de(niveaux, vote.get("votant"))]
            numerateur += poids * vote.get("valeur", 0)
            denominateur += poids
    v = 1 + 0.5 * numerateur / denominateur if denominateur else 1.0
    return {"S": gain * portee * confiance / (1 + lignes / 100) * v, "G": gain, "P": portee, "C": confiance, "L": lignes, "V": v}


def depouiller_proposition(reg, identifiant, niveaux, instant):
    if identifiant not in reg.propositions:
        raise ErreurBee(f"proposition inconnue : {identifiant}")
    chemin, prop = reg.propositions[identifiant]
    ouverture = lire_instant(prop["ouverte_le"], reg.rel(chemin))
    cloture = ouverture + dt.timedelta(days=int(reg.config.get("duree_vote_jours", 7)))
    pour = contre = 0
    votants = set()
    for _, vote in reg.votes:
        if vote.get("sujet") != identifiant:
            continue
        poids = POIDS_VOTE[niveau_de(niveaux, vote.get("votant"))]
        if poids == 0:
            continue
        votants.add(vote["votant"])
        if vote["valeur"] == 1:
            pour += poids
        elif vote["valeur"] == -1:
            contre += poids
    quorum = int(reg.config.get("quorum_votants", 20))
    majorite = float(reg.config.get("majorite_requise", 2 / 3))
    part = pour / (pour + contre) if pour + contre else 0.0
    adoptee = len(votants) >= quorum and part >= majorite
    return {
        "proposition": identifiant, "regle": prop["regle"], "statut": prop["statut"],
        "cloture": en_iso(cloture), "terminee": instant >= cloture,
        "votants_ponderes": len(votants), "quorum": quorum,
        "pour": pour, "contre": contre, "part_pour": round(part, 4), "majorite_requise": majorite,
        "resultat": ("adoptee" if adoptee else "rejetee") if instant >= cloture else "en_cours",
    }


# --------------------------------------------------------------------------
# Validation du registre
# --------------------------------------------------------------------------

def verifier_registre(reg):
    problemes = list(reg.problemes_chargement)
    ajouter = problemes.append

    def selon_schema(nom, chemin, donnees):
        if not isinstance(donnees, dict):
            ajouter(f"{reg.rel(chemin)} : le fichier doit contenir un objet YAML (clé: valeur)")
            return False
        valide = True
        for erreur in sorted(reg.schema(nom).iter_errors(donnees), key=lambda e: [str(x) for x in e.absolute_path]):
            lieu = "/".join(str(x) for x in erreur.absolute_path) or "(racine)"
            ajouter(f"{reg.rel(chemin)} : {lieu} : {message_schema(erreur)}")
            valide = False
        return valide

    def instant_valide(chemin, valeur, quoi):
        try:
            lire_instant(valeur, f"{reg.rel(chemin)} ({quoi})")
        except ErreurBee as e:
            ajouter(str(e))

    regles = (reg.racine / "REGLES.md").read_text(encoding="utf-8") if (reg.racine / "REGLES.md").exists() else ""

    for stem, (chemin, projet) in reg.projets.items():
        if not selon_schema("projet", chemin, projet):
            continue
        if projet["id"] != stem:
            ajouter(f"{reg.rel(chemin)} : id « {projet['id']} » différent du nom de fichier « {stem} »")
        categorie = reg.categories.get(projet["categorie"])
        if not categorie:
            ajouter(f"{reg.rel(chemin)} : catégorie inconnue « {projet['categorie']} » (voir categories.yaml)")
        elif categorie.get("statut") != "ouverte" and projet["statut"] == "actif":
            ajouter(f"{reg.rel(chemin)} : projet actif dans une catégorie {categorie.get('statut')}")
        ids = [m["id"] for m in projet["metriques"]]
        if len(ids) != len(set(ids)):
            ajouter(f"{reg.rel(chemin)} : métriques en double")

    for stem, (chemin, membre) in reg.membres.items():
        if selon_schema("membre", chemin, membre) and membre["pseudo"] != stem:
            ajouter(f"{reg.rel(chemin)} : pseudo « {membre['pseudo']} » différent du nom de fichier")

    reservations = defaultdict(list)
    for stem, (chemin, tache) in reg.taches.items():
        if not selon_schema("tache", chemin, tache):
            continue
        lieu = reg.rel(chemin)
        if tache["id"] != stem:
            ajouter(f"{lieu} : id « {tache['id']} » différent du nom de fichier « {stem} »")
        if chemin.parent.name != tache["projet"]:
            ajouter(f"{lieu} : rangée dans taches/{chemin.parent.name}/ mais projet « {tache['projet']} »")
        if not tache["id"].startswith(tache["projet"] + "-"):
            ajouter(f"{lieu} : l'id doit commencer par le nom du projet ({tache['projet']}-NNNN)")
        projet = reg.projets.get(tache["projet"])
        if not projet:
            ajouter(f"{lieu} : projet inconnu « {tache['projet']} »")
        else:
            if projet[1].get("categorie") != tache["categorie"]:
                ajouter(f"{lieu} : catégorie « {tache['categorie']} » différente de celle du projet « {projet[1].get('categorie')} »")
            if tache["metrique"] is not None and tache["metrique"] not in reg.metriques(tache["projet"]):
                ajouter(f"{lieu} : métrique « {tache['metrique']} » absente de projets/{tache['projet']}.yaml")
        if tache["categorie"] == "compression-sans-perte" and tache["type"] == "optimisation" and "sortie_compressee" not in tache:
            ajouter(f"{lieu} : une optimisation de compression doit préciser sortie_compressee (identique ou peut_changer)")
        for dep in tache.get("depend_de") or []:
            if dep == tache["id"]:
                ajouter(f"{lieu} : une tâche ne peut pas dépendre d'elle-même")
            elif dep not in reg.taches:
                ajouter(f"{lieu} : dépend de la tâche inconnue « {dep} »")
        if "reservation" in tache:
            instant_valide(chemin, tache["reservation"]["depuis"], "reservation.depuis")
            reservations[tache["reservation"]["utilisateur"]].append(tache["id"])
            if tache["reservation"]["utilisateur"] not in reg.membres and tache["reservation"]["utilisateur"] not in reg.conseil:
                ajouter(f"{lieu} : réservée par « {tache['reservation']['utilisateur']} », qui n'est pas inscrit")
        if "contribution" in tache:
            if tache["contribution"] not in reg.enregistrements:
                ajouter(f"{lieu} : contribution « {tache['contribution']} » introuvable dans contributions/")
            elif not tache["contribution"].startswith(tache["id"] + "-c"):
                ajouter(f"{lieu} : la contribution « {tache['contribution']} » ne correspond pas à cette tâche")
        for i, note in enumerate(tache.get("notes") or []):
            instant_valide(chemin, note["le"], f"notes/{i}/le")

    maximum = int(reg.config.get("reservations_max_par_utilisateur", 3))
    for pseudo, ids in sorted(reservations.items()):
        if len(ids) > maximum:
            ajouter(f"règle R8 : {pseudo} a {len(ids)} réservations ({', '.join(ids)}), maximum {maximum}")

    for stem, (chemin, enr) in reg.enregistrements.items():
        if not selon_schema("enregistrement", chemin, enr):
            continue
        lieu = reg.rel(chemin)
        if enr["id"] != stem:
            ajouter(f"{lieu} : id « {enr['id']} » différent du nom de fichier")
        correspondance = ID_CONTRIBUTION.match(enr["id"])
        if not correspondance or correspondance["tache"] != enr["tache"]:
            ajouter(f"{lieu} : l'id doit être <tache>-c<n> avec la tâche « {enr['tache']} »")
        tache = reg.taches.get(enr["tache"])
        if not tache:
            ajouter(f"{lieu} : tâche inconnue « {enr['tache']} »")
        else:
            if chemin.parent.name != tache[1].get("projet"):
                ajouter(f"{lieu} : rangée dans contributions/{chemin.parent.name}/ au lieu de contributions/{tache[1].get('projet')}/")
            fork = reg.projets.get(tache[1].get("projet"), (None, {}))[1].get("fork")
            if fork and not enr["pr"].lower().startswith(fork.lower().rstrip("/") + "/pull/"):
                ajouter(f"{lieu} : la PR doit être ouverte sur le fork du projet ({fork})")
        if enr["auteur"] not in reg.membres and enr["auteur"] not in reg.conseil:
            ajouter(f"{lieu} : auteur « {enr['auteur']} » non inscrit")
        instant_valide(chemin, enr["soumise_le"], "soumise_le")
        vus = set()
        for i, r in enumerate(enr["relectures"]):
            if r["relecteur"] == enr["auteur"]:
                ajouter(f"{lieu} : relectures/{i} : l'auteur ne peut pas relire sa propre contribution (commandement 3)")
            if r["relecteur"] in vus:
                ajouter(f"{lieu} : relectures/{i} : {r['relecteur']} a déjà relu cette contribution")
            vus.add(r["relecteur"])
            instant_valide(chemin, r["le"], f"relectures/{i}/le")

    for stem, (chemin, prop) in reg.propositions.items():
        if not selon_schema("proposition", chemin, prop):
            continue
        if prop["id"] != stem:
            ajouter(f"{reg.rel(chemin)} : id « {prop['id']} » différent du nom de fichier")
        if f"| {prop['regle']} |" not in regles:
            ajouter(f"{reg.rel(chemin)} : la règle {prop['regle']} n'existe pas dans REGLES.md")
        instant_valide(chemin, prop["ouverte_le"], "ouverte_le")

    for chemin, vote in reg.votes:
        if not selon_schema("vote", chemin, vote):
            continue
        lieu = reg.rel(chemin)
        if vote["votant"] != chemin.stem:
            ajouter(f"{lieu} : le fichier doit s'appeler <votant>.yaml (votant « {vote['votant']} »)")
        if vote["sujet"] != chemin.parent.name:
            ajouter(f"{lieu} : sujet « {vote['sujet']} » différent du dossier « {chemin.parent.name} »")
        if vote["votant"] not in reg.membres and vote["votant"] not in reg.conseil:
            ajouter(f"{lieu} : votant « {vote['votant']} » non inscrit")
        instant_valide(chemin, vote["le"], "le")
        if vote["sujet"] in reg.enregistrements:
            if reg.enregistrements[vote["sujet"]][1].get("auteur") == vote["votant"]:
                ajouter(f"{lieu} : on ne vote pas pour sa propre contribution (commandement 3)")
        elif vote["sujet"] not in reg.propositions:
            ajouter(f"{lieu} : sujet de vote inconnu « {vote['sujet']} »")

    for chemin, mesure in reg.mesures:
        lieu = reg.rel(chemin)
        if not selon_schema("mesure", chemin, mesure):
            continue
        stem = pathlib.PurePosixPath(chemin).stem
        dossier = pathlib.PurePosixPath(chemin).parent.name
        if mesure["soumise_par"] != stem:
            ajouter(f"{lieu} : soumise_par « {mesure['soumise_par']} » différent du nom de fichier « {stem} »")
        if mesure["contribution"] != dossier:
            ajouter(f"{lieu} : rangée dans mesures/{dossier}/ au lieu de mesures/{mesure['contribution']}/")
        if mesure["contribution"] not in reg.enregistrements:
            ajouter(f"{lieu} : contribution inconnue « {mesure['contribution']} »")
        if mesure["soumise_par"] not in reg.membres and mesure["soumise_par"] not in reg.conseil:
            ajouter(f"{lieu} : soumise par « {mesure['soumise_par']} », qui n'est pas inscrit")
        instant_valide(chemin, mesure["le"], "le")
    return problemes


def verifier_manifeste(reg, donnees, origine="CONTRIBUTION.yaml", utilisateur=None):
    problemes = []
    if not isinstance(donnees, dict):
        return [f"{origine} : le fichier doit contenir un objet YAML"]
    a_remplir = champs_a_remplir(donnees)
    if a_remplir:
        problemes.append(f"{origine} : il reste des champs « {A_REMPLIR} » : {', '.join(a_remplir)}")
    for erreur in sorted(reg.schema("contribution").iter_errors(donnees), key=lambda e: [str(x) for x in e.absolute_path]):
        if isinstance(erreur.instance, str) and A_REMPLIR in erreur.instance:
            continue  # déjà signalé ci-dessus
        lieu = "/".join(str(x) for x in erreur.absolute_path) or "(racine)"
        problemes.append(f"{origine} : {lieu} : {message_schema(erreur)}")
    mesures_brutes = donnees.get("mesures") if isinstance(donnees.get("mesures"), dict) else {}
    for cote in ("avant", "apres"):
        bloc = mesures_brutes.get(cote)
        for cle, valeur in (bloc.items() if isinstance(bloc, dict) else []):
            if isinstance(valeur, (int, float)) and valeur == 0:
                problemes.append(f"{origine} : mesures/{cote}/{cle} vaut 0 : indiquez la valeur réellement mesurée (commandement 2)")
    tache = reg.taches.get(donnees.get("tache"))
    if not tache:
        problemes.append(f"{origine} : tâche inconnue « {donnees.get('tache')} »")
        return problemes
    tache = tache[1]
    if utilisateur and donnees.get("utilisateur") != utilisateur:
        problemes.append(f"{origine} : utilisateur « {donnees.get('utilisateur')} » différent de l'auteur de la PR « {utilisateur} »")
    if tache.get("type") in ("optimisation", "mesure") and "mesures" not in donnees:
        problemes.append(f"{origine} : une tâche de type {tache['type']} exige le bloc mesures (commandement 2). "
                         "Sans mesure réelle, ne soumettez pas : libérez la tâche avec une note.")
    mesures = mesures_brutes
    connues = reg.metriques(tache.get("projet"))
    for cote in ("avant", "apres"):
        bloc = mesures.get(cote) if isinstance(mesures.get(cote), dict) else {}
        for cle in bloc:
            if connues and cle not in connues:
                problemes.append(f"{origine} : mesures/{cote}/{cle} : métrique inconnue du projet ({', '.join(connues)})")
    metrique = tache.get("metrique")
    if tache.get("type") == "optimisation" and mesures and metrique:
        for cote in ("avant", "apres"):
            bloc = mesures.get(cote) if isinstance(mesures.get(cote), dict) else {}
            if metrique not in bloc:
                problemes.append(f"{origine} : mesures/{cote} doit contenir la métrique visée « {metrique} »")
    taille_reelle = donnees.get("taille_reelle")
    if taille_reelle in ORDRE_TAILLES and tache.get("taille") in ORDRE_TAILLES:
        if ORDRE_TAILLES.index(taille_reelle) > ORDRE_TAILLES.index(tache["taille"]):
            problemes.append(f"{origine} : taille réelle {taille_reelle} au-delà de la taille de la tâche ({tache['taille']}) : découpez ou libérez la tâche")
    return problemes


# --------------------------------------------------------------------------
# Vérification d'une pull request sur le registre (aucun code de la PR n'est exécuté)
# --------------------------------------------------------------------------

def git(depot, *arguments):
    resultat = subprocess.run(["git", "-C", str(depot), *arguments], capture_output=True, text=True)
    if resultat.returncode != 0:
        raise ErreurBee(f"git {' '.join(arguments)} : {resultat.stderr.strip()}")
    return resultat.stdout


def lire_yaml_ref(depot, ref, chemin):
    resultat = subprocess.run(["git", "-C", str(depot), "show", f"{ref}:{chemin}"], capture_output=True, text=True)
    if resultat.returncode != 0:
        return None
    return charger_texte_yaml(resultat.stdout, f"{ref}:{chemin}")


def correspond(chemin, motifs):
    return any(fnmatch.fnmatchcase(chemin, motif) for motif in motifs)


def verifier_pr(reg, base, tete, auteur, compte_cree_le=None, instant=None):
    """Renvoie (problèmes, natures). `reg` doit refléter l'état de la tête de la PR."""
    instant = instant or maintenant()
    sorties = git(reg.racine, "diff", "--name-status", "--no-renames", f"{base}...{tete}")
    changements = [ligne.split("\t", 1) for ligne in sorties.splitlines() if ligne.strip()]
    est_conseil = auteur in reg.conseil
    est_robot = auteur in reg.robots
    amorcage = bool(reg.config.get("amorcage"))
    niveaux = calculer_niveaux(reg)
    niveau = niveau_de(niveaux, auteur)
    problemes, natures = [], []

    def exiger(condition, message):
        if not condition:
            problemes.append(message)
        return condition

    for statut_git, chemin in changements:
        ancien = lire_yaml_ref(reg.racine, base, chemin) if statut_git != "A" and chemin.endswith(".yaml") else None
        nouveau = lire_yaml_ref(reg.racine, tete, chemin) if statut_git != "D" and chemin.endswith(".yaml") else None
        partie = chemin.split("/")

        if partie[0] == "taches" and len(partie) == 3:
            if statut_git == "A":
                if isinstance(nouveau, dict) and nouveau.get("statut") == "proposee":
                    # L'essaim propose ; un gardien, le conseil ou un Confirmé valide (proposee → ouverte).
                    natures.append("proposition_tache")
                    exiger(auteur in reg.membres or est_conseil, f"{chemin} : {auteur} doit d'abord s'inscrire (bee inscrire)")
                    exiger(nouveau.get("cree_par") == auteur, f"{chemin} : cree_par doit être l'auteur de la PR ({auteur})")
                    exiger(not nouveau.get("reservation") and not nouveau.get("contribution"),
                           f"{chemin} : une tâche proposée n'a ni réservation ni contribution")
                    continue
                natures.append("creation_tache")
                exiger(est_conseil or (niveau == "Confirmé" and not amorcage),
                       f"{chemin} : créer directement une tâche ouverte est réservé au conseil"
                       + (" pendant l'amorçage" if amorcage else " et aux Confirmés")
                       + " ; proposez-la avec bee proposer-tache (statut « proposee »)")
                continue
            if statut_git == "D":
                exiger(est_conseil, f"{chemin} : seule le conseil peut supprimer une tâche")
                natures.append("gouvernance")
                continue
            if not (isinstance(ancien, dict) and isinstance(nouveau, dict)):
                problemes.append(f"{chemin} : fichier illisible")
                continue
            differences = {k for k in set(ancien) | set(nouveau) if ancien.get(k) != nouveau.get(k)}
            if differences - CLES_LIBRE_SERVICE_TACHE:
                natures.append("gouvernance")
                exiger(est_conseil, f"{chemin} : seul le conseil peut modifier {', '.join(sorted(differences - CLES_LIBRE_SERVICE_TACHE))}")
                continue
            anciennes_notes, nouvelles_notes = ancien.get("notes") or [], nouveau.get("notes") or []
            if "notes" in differences:
                if exiger(nouvelles_notes[:len(anciennes_notes)] == anciennes_notes,
                          f"{chemin} : les notes sont en ajout seul, on ne modifie ni ne retire une note"):
                    for note in nouvelles_notes[len(anciennes_notes):]:
                        exiger(note.get("par") == auteur or est_robot,
                               f"{chemin} : une note ajoutée doit être signée par l'auteur de la PR ({auteur})")
            avant, apres = ancien.get("statut"), nouveau.get("statut")
            if avant == apres:
                exiger(differences <= {"notes"}, f"{chemin} : changement non autorisé sans changement de statut")
                natures.append("note")
            elif (avant, apres) == ("ouverte", "reservee"):
                natures.append("reservation")
                reservation = nouveau.get("reservation") or {}
                exiger(reservation.get("utilisateur") == auteur, f"{chemin} : on ne réserve que pour soi ({auteur})")
                exiger(auteur in reg.membres or est_conseil, f"{chemin} : {auteur} doit d'abord s'inscrire (bee inscrire)")
                try:
                    depuis = lire_instant(reservation.get("depuis"), chemin)
                    exiger(depuis <= instant + dt.timedelta(minutes=10), f"{chemin} : réservation datée dans le futur")
                except ErreurBee as e:
                    problemes.append(str(e))
                exiger(not reg.bloquee_par(nouveau), f"{chemin} : la tâche dépend de {', '.join(reg.bloquee_par(nouveau))}, pas encore intégrée(s)")
                if not amorcage:
                    exiger(nouveau.get("taille") in TAILLES_PAR_NIVEAU[niveau],
                           f"{chemin} : taille {nouveau.get('taille')} non accessible au niveau {niveau}")
                    exiger(nouveau.get("type") != "decoupage" or niveau == "Confirmé",
                           f"{chemin} : le découpage est réservé aux Confirmés")
            elif (avant, apres) == ("reservee", "ouverte"):
                natures.append("liberation")
                titulaire = (ancien.get("reservation") or {}).get("utilisateur")
                expiree = False
                try:
                    depuis = lire_instant((ancien.get("reservation") or {}).get("depuis"), chemin)
                    expiree = instant - depuis > dt.timedelta(hours=int(reg.config.get("reservation_max_heures", 72)))
                except ErreurBee:
                    pass
                exiger(titulaire == auteur or est_conseil or (est_robot and expiree),
                       f"{chemin} : seul le titulaire ({titulaire}) libère sa réservation avant expiration")
            elif (avant, apres) == ("reservee", "en_relecture"):
                natures.append("soumission")
                titulaire = (ancien.get("reservation") or {}).get("utilisateur")
                exiger(titulaire == auteur, f"{chemin} : seul le titulaire ({titulaire}) soumet une contribution")
                enr = reg.enregistrements.get(nouveau.get("contribution") or "")
                exiger(enr is not None and enr[1].get("auteur") == auteur,
                       f"{chemin} : la contribution {nouveau.get('contribution')} doit exister et appartenir à {auteur}")
            elif avant == "proposee" and apres in ("ouverte", "abandonnee"):
                natures.append("validation_tache")
                exiger(auteur in reg.privilegies() or niveau == "Confirmé",
                       f"{chemin} : valider ou écarter une tâche proposée revient à un gardien, au conseil ou à un Confirmé")
                exiger(nouveau.get("cree_par") != auteur, f"{chemin} : on ne valide pas sa propre proposition")
                if apres == "abandonnee":
                    notes = nouveau.get("notes") or []
                    exiger(len(notes) > len(ancien.get("notes") or []),
                           f"{chemin} : écarter une proposition exige une note qui dit pourquoi")
            else:
                natures.append("decision")
                autorise = est_conseil or (est_robot and not amorcage)
                exiger(autorise, f"{chemin} : passage {avant} → {apres} réservé au conseil" + ("" if amorcage else " ou à la CI"))
            continue

        if partie[0] == "contributions" and len(partie) == 3:
            if statut_git == "A":
                natures.append("soumission")
                if exiger(isinstance(nouveau, dict), f"{chemin} : fichier illisible"):
                    cid = pathlib.PurePosixPath(chemin).stem
                    exiger(nouveau.get("auteur") == auteur, f"{chemin} : l'auteur déclaré doit être {auteur}")
                    exiger(nouveau.get("statut") == "en_relecture" and not nouveau.get("relectures") and "verdict" not in nouveau,
                           f"{chemin} : une contribution naît en_relecture, sans relecture ni verdict")
                    # Pas de soumission sans réservation : la même PR fait passer la tâche, réservée par
                    # l'auteur, en relecture avec cette contribution (contrôlé aussi côté tâche).
                    t = reg.taches.get(nouveau.get("tache") or "", (None, {}))[1]
                    exiger(t.get("statut") == "en_relecture" and t.get("contribution") == cid,
                           f"{chemin} : la PR doit aussi passer la tâche {nouveau.get('tache')} (réservée par {auteur}) "
                           f"en relecture avec la contribution {cid} : bee soumettre le fait")
                    # La fenêtre d'ouverture de R3 part de soumise_le : il doit être l'heure réelle.
                    try:
                        soumise = lire_instant(nouveau.get("soumise_le"), chemin)
                        exiger(instant - dt.timedelta(hours=2) <= soumise <= instant + dt.timedelta(minutes=10),
                               f"{chemin} : soumise_le doit être l'heure de la soumission (à 2 h près) ; relancez bee soumettre")
                    except ErreurBee as e:
                        problemes.append(str(e))
                    autres = [i for i, (_, e) in reg.enregistrements.items() if i != cid and e.get("pr") == nouveau.get("pr")]
                    exiger(not autres, f"{chemin} : la PR {nouveau.get('pr')} est déjà liée à {', '.join(autres)}")
                continue
            if statut_git == "D":
                natures.append("gouvernance")
                exiger(est_conseil, f"{chemin} : seul le conseil peut supprimer une contribution")
                continue
            if not (isinstance(ancien, dict) and isinstance(nouveau, dict)):
                problemes.append(f"{chemin} : fichier illisible")
                continue
            differences = {k for k in set(ancien) | set(nouveau) if ancien.get(k) != nouveau.get(k)}
            if differences == {"relectures"}:
                natures.append("relecture")
                exiger(ancien.get("statut") == "en_relecture",
                       f"{chemin} : on ne relit qu'une contribution en relecture (statut : {ancien.get('statut')})")
                anciennes, nouvelles = ancien.get("relectures") or [], nouveau.get("relectures") or []
                if exiger(nouvelles[:len(anciennes)] == anciennes, f"{chemin} : les relectures sont en ajout seul"):
                    for r in nouvelles[len(anciennes):]:
                        exiger(r.get("relecteur") == auteur, f"{chemin} : une relecture ajoutée doit être celle de {auteur}")
                        exiger(r.get("relecteur") != nouveau.get("auteur"), f"{chemin} : on ne relit pas sa propre contribution")
                        exiger(not r.get("defaut_confirme") or est_robot or niveau == "Confirmé" or est_conseil,
                               f"{chemin} : un défaut n'est confirmé que par la CI ou une relecture Confirmé")
            else:
                natures.append("decision")
                exiger(est_conseil or est_robot, f"{chemin} : verdict, statut et confirmation de défaut sont écrits par la CI ou le conseil")
            continue

        if partie[0] == "votes" and len(partie) == 3:
            natures.append("vote")
            exiger(pathlib.PurePosixPath(chemin).stem == auteur, f"{chemin} : on ne vote qu'en son nom ({auteur})")
            if statut_git != "D" and exiger(isinstance(nouveau, dict), f"{chemin} : fichier illisible"):
                exiger(nouveau.get("votant") == auteur, f"{chemin} : votant déclaré différent de {auteur}")
                sujet = nouveau.get("sujet", "")
                if ID_PROPOSITION.match(sujet) and sujet in reg.propositions:
                    resultat = depouiller_proposition(reg, sujet, niveaux, instant)
                    exiger(not resultat["terminee"] and reg.propositions[sujet][1].get("statut") == "ouverte",
                           f"{chemin} : le vote sur {sujet} est clos")
            continue

        if partie[0] == "mesures" and len(partie) == 3:
            natures.append("mesure")
            exiger(pathlib.PurePosixPath(chemin).stem == auteur, f"{chemin} : on ne dépose une mesure qu'en son nom ({auteur})")
            exiger(auteur in reg.membres or est_conseil, f"{chemin} : {auteur} doit d'abord s'inscrire (bee inscrire)")
            if statut_git != "D" and exiger(isinstance(nouveau, dict), f"{chemin} : fichier illisible"):
                exiger(nouveau.get("soumise_par") == auteur, f"{chemin} : soumise_par déclaré différent de {auteur}")
                exiger(nouveau.get("contribution") == partie[1], f"{chemin} : la mesure doit être rangée sous sa contribution")
                exiger(nouveau.get("contribution") in reg.enregistrements, f"{chemin} : contribution « {nouveau.get('contribution')} » inconnue")
            continue

        if partie[0] == "membres" and len(partie) == 2:
            natures.append("inscription" if statut_git == "A" else "profil")
            exiger(pathlib.PurePosixPath(chemin).stem == auteur or est_conseil, f"{chemin} : on ne s'inscrit qu'en son nom ({auteur})")
            if statut_git == "M" and isinstance(ancien, dict) and isinstance(nouveau, dict):
                differences = {k for k in set(ancien) | set(nouveau) if ancien.get(k) != nouveau.get(k)}
                exiger(differences <= {"categories_preferees"} or est_conseil, f"{chemin} : seules les catégories préférées sont modifiables")
            if statut_git == "A" and isinstance(nouveau, dict):
                minimum = int(reg.config.get("anciennete_compte_min_jours", 90))
                try:
                    cree = lire_date(nouveau.get("compte_cree_le"), chemin)
                    inscrit = lire_date(nouveau.get("inscrit_le"), chemin)
                    exiger((inscrit - cree).days >= minimum, f"{chemin} : le compte GitHub doit avoir au moins {minimum} jours")
                    if compte_cree_le:
                        exiger(cree == lire_date(compte_cree_le, "--compte-cree-le"),
                               f"{chemin} : compte_cree_le ne correspond pas à la date fournie par GitHub ({compte_cree_le})")
                except ErreurBee as e:
                    problemes.append(str(e))
            continue

        if partie[0] == "propositions" and len(partie) == 2 and statut_git == "A":
            natures.append("proposition")
            exiger(est_conseil or niveau == "Confirmé" or (amorcage and auteur in reg.membres),
                   f"{chemin} : proposer une règle est réservé aux Confirmés (R10)" + ("" if amorcage else " hors amorçage"))
            if isinstance(nouveau, dict):
                exiger(nouveau.get("auteur") == auteur and nouveau.get("statut") == "ouverte",
                       f"{chemin} : une proposition naît ouverte, au nom de {auteur}")
            continue

        natures.append("gouvernance")
        exiger(est_conseil, f"{chemin} : modification réservée au conseil humain"
               + (" (et 30 jours de discussion publique : commandement 11)" if chemin == "COMMANDEMENTS.md"
                  else " ; si ce fichier est arrivé par erreur dans la PR, retirez-le (git rm --cached, puis commit)"))

    return problemes, natures


LIBRE_SERVICE = {"reservation", "liberation", "soumission", "note", "relecture", "vote", "mesure", "inscription", "profil", "proposition",
                 "proposition_tache", "validation_tache"}


# --------------------------------------------------------------------------
# Vérification d'une branche de contribution sur un fork (règle R1, commandement 3)
# --------------------------------------------------------------------------

def chemin_manifeste(identifiant_tache):
    """Emplacement du manifeste d'une contribution dans le fork."""
    return f"manifestes/{identifiant_tache}.yaml"


def verifier_fork(reg, depot, base, tete, identifiant_tache, auteur=None):
    """Renvoie (problèmes, lignes modifiées, avertissements) pour une branche de contribution."""
    _, tache = reg.tache(identifiant_tache)
    _, projet = reg.projets[tache["projet"]]
    exclus = list(projet.get("chemins_hors_decompte") or []) + ["CONTRIBUTION.yaml", "manifestes/**"]
    juges = list(projet.get("chemins_juges") or [])
    problemes, avertissements = [], []
    total = 0
    for ref in (base, tete):
        if subprocess.run(["git", "-C", str(depot), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], capture_output=True).returncode != 0:
            conseil = " Lancez d'abord : git fetch upstream" if "upstream" in ref else ""
            raise ErreurBee(f"révision « {ref} » introuvable dans {depot}.{conseil}")
    if tete == "HEAD":
        en_attente = [l[3:] for l in git(depot, "status", "--porcelain", "--untracked-files=no").splitlines() if l.strip()]
        if en_attente:
            problemes.append(f"{len(en_attente)} fichier(s) modifié(s) mais non commité(s) ({', '.join(en_attente[:5])}"
                             f"{'…' if len(en_attente) > 5 else ''}) : l'outil vérifie le dernier commit, pas le disque. Commitez d'abord.")
    fichiers_tache = [f.rstrip("/") for f in tache.get("fichiers") or []]
    for ligne in git(depot, "diff", "--numstat", "--no-renames", f"{base}...{tete}").splitlines():
        ajoutees, retirees, chemin = ligne.split("\t", 2)
        if correspond(chemin, exclus):
            continue
        if ajoutees == "-":
            problemes.append(f"{chemin} : fichier binaire modifié (commandement 7 : pas de binaire opaque)")
            continue
        total += int(ajoutees) + int(retirees)
        if fichiers_tache and not any(chemin == f or chemin.startswith(f + "/") for f in fichiers_tache):
            avertissements.append(f"{chemin} : hors des fichiers de la tâche ({', '.join(fichiers_tache)}) ; justifiez-le dans le manifeste, les relecteurs jugeront")
    maximum = LIGNES_MAX[tache["taille"]]
    if total > maximum:
        problemes.append(f"R1 : {total} lignes modifiées, maximum {maximum} pour une tâche {tache['taille']}")
    if tache["type"] in ("optimisation", "relecture"):
        for chemin in git(depot, "diff", "--name-only", "--no-renames", f"{base}...{tete}").splitlines():
            if correspond(chemin, juges):
                problemes.append(f"{chemin} : une tâche {tache['type']} ne peut pas modifier ce qui la juge (commandement 3)")
    # Manifeste : manifestes/<tâche>.yaml (un fichier par tâche, donc pas de conflit entre deux PR), sinon
    # l'ancien emplacement CONTRIBUTION.yaml à la racine.
    nom_manifeste = chemin_manifeste(identifiant_tache)
    manifeste = lire_yaml_ref(depot, tete, nom_manifeste)
    ancien = None
    if manifeste is None:
        ancien = lire_yaml_ref(depot, tete, "CONTRIBUTION.yaml")
        if ancien is not None and isinstance(ancien, dict) and ancien.get("tache") == identifiant_tache:
            nom_manifeste, manifeste = "CONTRIBUTION.yaml", ancien
    if manifeste is None:
        candidats = [nom_manifeste] + (["CONTRIBUTION.yaml"] if ancien is None else [])
        sur_disque = [n for n in candidats if (pathlib.Path(depot) / n).exists()]
        if sur_disque:
            problemes.append(f"{sur_disque[0]} existe sur le disque mais n'est pas commité : git add {sur_disque[0]} puis commit")
        else:
            problemes.append(f"{nom_manifeste} absent de la branche (bee manifeste {identifiant_tache} … --sortie <fork>/{nom_manifeste})")
    else:
        problemes += verifier_manifeste(reg, manifeste, nom_manifeste, auteur)
        if isinstance(manifeste, dict) and manifeste.get("tache") != identifiant_tache:
            problemes.append(f"{nom_manifeste} : tâche « {manifeste.get('tache')} » au lieu de « {identifiant_tache} »")
    autres = [c for c in git(depot, "diff", "--name-only", "--no-renames", f"{base}...{tete}").splitlines()
              if correspond(c, ["manifestes/**"]) and c != chemin_manifeste(identifiant_tache)]
    if autres:
        problemes.append(f"la branche modifie le manifeste d'une autre tâche ({', '.join(autres[:3])}) : une PR, une tâche")
    if total == 0 and not problemes and tache["type"] == "optimisation":
        # Normal pour une tâche de mesure ou d'outillage, qui ne touche que bee/ et tests/.
        avertissements.append("aucune ligne de code modifiée hors tests et bancs pour une optimisation : est-ce bien la bonne branche ?")
    return problemes, total, avertissements


# --------------------------------------------------------------------------
# Site statique (voir site_bee.py)
# --------------------------------------------------------------------------

def generer_site(reg, sortie):
    import site_bee
    return site_bee.generer(sys.modules[__name__], reg, sortie)


# --------------------------------------------------------------------------
# Commandes
# --------------------------------------------------------------------------

def afficher_tableau(entetes, lignes):
    largeurs = [max(len(str(x)) for x in [h] + [l[i] for l in lignes]) for i, h in enumerate(entetes)]
    print("  ".join(str(h).ljust(largeurs[i]) for i, h in enumerate(entetes)).rstrip())
    for ligne in lignes:
        print("  ".join(str(x).ljust(largeurs[i]) for i, x in enumerate(ligne)).rstrip())


def cmd_valider(args):
    reg = Registre(args.registre)
    problemes = verifier_registre(reg)
    for p in problemes:
        print(f"✗ {p}")
    if problemes:
        print(f"\n{len(problemes)} problème(s). Le registre n'est pas valide.")
        return 1
    print(f"✓ registre valide : {len(reg.projets)} projets, {len(reg.taches)} tâches, {len(reg.enregistrements)} contributions, "
          f"{len(reg.membres)} membres, {len(reg.votes)} votes, {len(reg.propositions)} propositions.")
    return 0


def cmd_lister(args):
    reg = Registre(args.registre)
    resultat, masquees = [], []
    for _, t in sorted(reg.taches.values(), key=lambda x: (x[1].get("projet", ""), -float(x[1].get("portee", 0)), x[1].get("id", ""))):
        if not isinstance(t, dict):
            continue
        if args.statut != "toutes" and t.get("statut") != args.statut:
            continue
        if args.projet and t.get("projet") != args.projet:
            continue
        if args.categorie and t.get("categorie") != args.categorie:
            continue
        if args.type and t.get("type") != args.type:
            continue
        if args.taille_max and ORDRE_TAILLES.index(t.get("taille", "L")) > ORDRE_TAILLES.index(args.taille_max):
            continue
        bloquee = reg.bloquee_par(t)
        if args.disponibles and bloquee:
            masquees.append((t["id"], bloquee))
            continue
        resultat.append({**t, "bloquee_par": bloquee})
    if args.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
        return 0
    if masquees:
        attentes = sorted({d for _, b in masquees for d in b})
        message_masquees = f"{len(masquees)} tâche(s) masquée(s) car elles attendent l'intégration de : {', '.join(attentes)}."
    if not resultat:
        print("Aucune tâche ne correspond." + (f" {message_masquees}" if masquees else ""))
        en_relecture = sum(1 for _, e in reg.enregistrements.values() if isinstance(e, dict) and e.get("statut") == "en_relecture")
        if en_relecture:
            print(f"Il y a {en_relecture} contribution(s) à relire : bee classement --statut en_relecture")
        else:
            print("Rien à relire non plus : dites-le à votre utilisateur et arrêtez-vous (AGENTS.md, « Quand t'arrêter »).")
        return 0
    afficher_tableau(["ID", "TYPE", "TAILLE", "PORTÉE", "STATUT", "TITRE"],
                     [[t["id"], t["type"], t["taille"], f"{float(t['portee']):.1f}", t["statut"] + (" (bloquée)" if t["bloquee_par"] else ""), t["titre"]] for t in resultat])
    if masquees:
        print(f"\n{message_masquees}")
    return 0


def cmd_voir(args):
    reg = Registre(args.registre)
    chemin, t = reg.tache(args.tache)
    print(chemin.read_text(encoding="utf-8").rstrip())
    print("\n# --- calculé par bee ---")
    bloquee = reg.bloquee_par(t)
    print(f"# bloquée par : {', '.join(bloquee) if bloquee else 'rien'}")
    print(f"# lignes modifiées autorisées (R1) : {LIGNES_MAX[t['taille']]}")
    niveau_requis = "Confirmé" if t["type"] == "decoupage" else {"S": "Nouveau", "M": "Contributeur", "L": "Confirmé"}[t["taille"]]
    print(f"# niveau requis : {niveau_requis}" + (" (non appliqué pendant l'amorçage)" if reg.config.get("amorcage") else ""))
    projet = reg.projets.get(t["projet"], (None, {}))[1]
    if projet.get("fork"):
        print(f"# fork : {projet['fork']}")
    for nom, commande in (projet.get("commandes") or {}).items():
        print(f"# commande {nom} : {commande}")
    return 0


def cmd_inscrire(args):
    reg = Registre(args.registre)
    chemin = reg.racine / "membres" / f"{args.pseudo}.yaml"
    if chemin.exists():
        raise ErreurBee(f"{args.pseudo} est déjà inscrit")
    aujourd_hui = maintenant().date()
    cree = lire_date(args.compte_cree_le, "--compte-cree-le")
    minimum = int(reg.config.get("anciennete_compte_min_jours", 90))
    if (aujourd_hui - cree).days < minimum:
        raise ErreurBee(f"le compte GitHub doit avoir au moins {minimum} jours (créé le {cree})")
    donnees = {"pseudo": args.pseudo, "inscrit_le": aujourd_hui.isoformat(), "compte_cree_le": cree.isoformat()}
    if args.categories:
        donnees["categories_preferees"] = args.categories
    ecrire_yaml(chemin, donnees)
    print(f"✓ {reg.rel(chemin)} créé. Publiez : bee publier --titre 'Inscription {args.pseudo}'")
    return 0


def cmd_prendre(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    chemin, t = reg.tache(args.tache)
    if t.get("statut") != "ouverte":
        raise ErreurBee(f"{args.tache} n'est pas ouverte (statut : {t.get('statut')})")
    bloquee = reg.bloquee_par(t)
    if bloquee:
        raise ErreurBee(f"{args.tache} attend l'intégration de : {', '.join(bloquee)}")
    if not reg.config.get("amorcage") and args.utilisateur not in reg.conseil:
        niveau = niveau_de(calculer_niveaux(reg), args.utilisateur)
        if t["taille"] not in TAILLES_PAR_NIVEAU[niveau] or (t["type"] == "decoupage" and niveau != "Confirmé"):
            raise ErreurBee(f"{args.tache} ({t['type']}, {t['taille']}) n'est pas accessible au niveau {niveau} (docs/reputation.md)")
    deja = [tid for tid, (_, x) in reg.taches.items() if (x.get("reservation") or {}).get("utilisateur") == args.utilisateur]
    maximum = int(reg.config.get("reservations_max_par_utilisateur", 3))
    if len(deja) >= maximum:
        raise ErreurBee(f"règle R8 : {args.utilisateur} a déjà {len(deja)} réservations ({', '.join(deja)}), maximum {maximum}")
    modifier_tache(chemin, statut="reservee", reservation={"utilisateur": args.utilisateur, "depuis": en_iso(maintenant())})
    heures = reg.config.get("reservation_max_heures", 72)
    print(f"✓ {args.tache} réservée pour {args.utilisateur} ({heures} h maximum, règle R7).")
    print(f"  Publiez : bee publier --titre 'Réservation {args.tache}' (fusionnée automatiquement si elle est valide).")
    return 0


def cmd_proposer_tache(args):
    """Prépare une proposition de tâche (statut « proposee ») à partir de modeles/tache.yaml."""
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    if args.projet not in reg.projets:
        raise ErreurBee(f"projet inconnu : {args.projet} (voir projets/)")
    projet = reg.projets[args.projet][1]
    numeros = [int(m.group(1)) for i in reg.taches if (m := re.fullmatch(re.escape(args.projet) + r"-(\d{4})", i))]
    identifiant = f"{args.projet}-{max([n for n in numeros if n < 9000] or [0]) + 1:04d}"
    chemin = reg.racine / "taches" / args.projet / f"{identifiant}.yaml"
    metriques = [m["id"] for m in projet.get("metriques") or [] if isinstance(m, dict)]
    metrique = (args.metrique or (metriques[0] if metriques else None)) if args.type == "optimisation" else None
    if metrique and metrique not in metriques:
        raise ErreurBee(f"métrique inconnue pour {args.projet} : {metrique} ({', '.join(metriques)})")
    lignes = []
    for ligne in (RACINE_OUTIL / "modeles" / "tache.yaml").read_text(encoding="utf-8").splitlines():
        cle = ligne.split(":", 1)[0]
        valeurs = {"id": identifiant, "projet": args.projet, "categorie": projet.get("categorie"), "type": args.type,
                   "taille": args.taille, "metrique": metrique if metrique else "null", "statut": "proposee",
                   "cree_par": args.utilisateur, "cree_le": guillemets(maintenant().strftime("%Y-%m-%d"))}
        if cle == "sortie_compressee" and not (args.type == "optimisation" and projet.get("categorie") == "compression-sans-perte"):
            continue
        lignes.append(f"{cle}: {valeurs[cle]}" if cle in valeurs and not ligne.startswith(" ") else ligne)
    texte = "\n".join(lignes) + "\n"
    if metrique:
        texte = texte.replace("debit_compression_n6", metrique)
    charger_texte_yaml(texte, str(chemin))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    print(f"✓ {reg.rel(chemin)} créé (statut « proposee »). Remplacez titre, contexte, fichiers, critères et périmètre")
    print("  par des faits mesurés (docs/taches.md), puis : bee valider ; bee publier --titre "
          f"'Proposition de tâche {identifiant}'. Un gardien, le conseil ou un Confirmé la validera.")
    return 0


def cmd_liberer(args):
    reg = Registre(args.registre)
    chemin, t = reg.tache(args.tache)
    titulaire = (t.get("reservation") or {}).get("utilisateur")
    if t.get("statut") != "reservee":
        raise ErreurBee(f"{args.tache} n'est pas réservée")
    if titulaire != args.utilisateur and args.utilisateur not in reg.conseil:
        raise ErreurBee(f"{args.tache} est réservée par {titulaire}, pas par {args.utilisateur}")
    note = {"par": args.utilisateur, "le": en_iso(maintenant()), "texte": args.note} if args.note else None
    modifier_tache(chemin, statut="ouverte", reservation=None, note=note)
    print(f"✓ {args.tache} libérée." + ("" if args.note else " Astuce : --note \"ce que vous avez appris\" aide l'agent suivant."))
    return 0


def cmd_noter(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    chemin, _ = reg.tache(args.tache)
    modifier_tache(chemin, note={"par": args.utilisateur, "le": en_iso(maintenant()), "texte": args.texte})
    print(f"✓ note ajoutée à {args.tache}. Publiez-la : bee publier --titre \"Note {args.tache}\"")
    return 0


def cmd_liberer_expirees(args):
    reg = Registre(args.registre)
    instant = maintenant()
    limite = dt.timedelta(hours=int(reg.config.get("reservation_max_heures", 72)))
    liberees = []
    for tid, (chemin, t) in sorted(reg.taches.items()):
        if t.get("statut") != "reservee":
            continue
        depuis = lire_instant(t["reservation"]["depuis"], reg.rel(chemin))
        if instant - depuis > limite:
            texte = f"Réservation de {t['reservation']['utilisateur']} expirée après {limite.total_seconds() / 3600:.0f} h (R7)."
            modifier_tache(chemin, statut="ouverte", reservation=None, note={"par": "bee", "le": en_iso(instant), "texte": texte})
            liberees.append(tid)
    print("✓ réservations expirées libérées : " + (", ".join(liberees) if liberees else "aucune"))
    return 0


def cmd_manifeste(args):
    reg = Registre(args.registre)
    _, t = reg.tache(args.tache)
    projet = reg.projets.get(t["projet"], (None, {}))[1]
    lignes = [
        f"tache: {t['id']}",
        f"utilisateur: {args.utilisateur}",
        "agent:",
        f"  modele: {guillemets(args.modele or A_REMPLIR + ' : nom et version du modèle')}",
        f"  client: bee {VERSION}",
        f"resume: \"{A_REMPLIR} : une phrase sur le changement (200 caractères max)\"",
        "changement: >",
        f"  {A_REMPLIR} : ce qui a été modifié, et pourquoi c'est mieux.",
    ]
    if t["type"] in ("optimisation", "mesure"):
        metriques = [t["metrique"]] if t.get("metrique") else []
        metriques += [m for m in reg.metriques(t["projet"]) if m not in metriques]
        lignes += [
            "mesures:",
            f"  machine: \"{A_REMPLIR} : processeur, système, compilateur\"",
            f"  commande: {guillemets((projet.get('commandes') or {}).get('banc_ab', A_REMPLIR))}",
            f"  repetitions: \"{A_REMPLIR} : nombre de répétitions réellement faites\"",
            "  avant:",
        ] + [f"    {m}: \"{A_REMPLIR}\"" for m in metriques] + ["  apres:"] + [f"    {m}: \"{A_REMPLIR}\"" for m in metriques]
    lignes += [
        "teste:",
        f"  - \"{A_REMPLIR} : ce que vous avez réellement exécuté (tests, différentiel, fuzzing…)\"",
        "non_teste: []",
        f"doutes: \"{A_REMPLIR} : ce qui pourrait mal tourner. « Aucun doute identifié » est une réponse acceptable si elle est vraie.\"",
        f"taille_reelle: {t['taille']}",
        "",
    ]
    texte = "\n".join(lignes)
    if args.sortie:
        sortie = pathlib.Path(args.sortie)
        if sortie.is_dir():
            # Un dossier (la racine du fork) : le manifeste va à sa place, manifestes/<tâche>.yaml.
            sortie = sortie / chemin_manifeste(t["id"])
        if sortie.parent.name == "manifestes":
            # Le dossier manifestes/ du fork peut ne pas exister encore (premier manifeste par tâche).
            sortie.parent.mkdir(parents=True, exist_ok=True)
        if sortie.exists():
            raise ErreurBee(f"{sortie} existe déjà : supprimez-le ou choisissez un autre fichier (rien n'a été écrasé)")
        sortie.write_text(texte, encoding="utf-8")
        print(f"✓ {sortie} écrit. Remplacez chaque « {A_REMPLIR} », puis : bee valider-contribution {sortie}")
    else:
        sys.stdout.write(texte)
    return 0


def cmd_valider_contribution(args):
    reg = Registre(args.registre)
    donnees = lire_yaml(args.fichier)
    problemes = verifier_manifeste(reg, donnees, args.fichier)
    for p in problemes:
        print(f"✗ {p}")
    if problemes:
        return 1
    print(f"✓ {args.fichier} est valide.")
    return 0


def cmd_soumettre(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    chemin, t = reg.tache(args.tache)
    titulaire = (t.get("reservation") or {}).get("utilisateur")
    if t.get("statut") != "reservee" or titulaire != args.utilisateur:
        raise ErreurBee(f"{args.tache} doit être réservée par {args.utilisateur} (statut : {t.get('statut')}, titulaire : {titulaire}). "
                        "Si votre PR de réservation est ouverte, attendez sa fusion puis : git switch main && git pull upstream main")
    fork = (reg.projets.get(t["projet"], (None, {}))[1].get("fork") or "").rstrip("/")
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/pull/[0-9]+", args.pr):
        raise ErreurBee(f"adresse de PR invalide : {args.pr} (attendu : https://github.com/<organisation>/<dépôt>/pull/<numéro>)")
    if fork and not args.pr.lower().startswith(fork.lower() + "/pull/"):
        raise ErreurBee(f"la PR doit être ouverte sur le fork du projet : {fork}/pull/<numéro> (reçu : {args.pr})")
    rang = 1 + sum(1 for cid in reg.enregistrements if cid.startswith(args.tache + "-c"))
    identifiant = f"{args.tache}-c{rang}"
    donnees = {"id": identifiant, "tache": args.tache, "auteur": args.utilisateur, "pr": args.pr}
    if args.resume:
        donnees["resume"] = args.resume
    donnees.update({"statut": "en_relecture", "soumise_le": en_iso(maintenant()), "relectures": []})
    ecrire_yaml(reg.racine / "contributions" / t["projet"] / f"{identifiant}.yaml", donnees)
    modifier_tache(chemin, statut="en_relecture", reservation=None, contribution=identifiant)
    print(f"✓ contribution {identifiant} enregistrée, tâche {args.tache} en relecture.")
    print(f"  Publiez : bee publier --titre 'Soumission {identifiant}'")
    return 0


def cmd_relire(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    chemin, enr = reg.enregistrement(args.contribution)
    if enr.get("auteur") == args.utilisateur:
        raise ErreurBee("on ne relit pas sa propre contribution (commandement 3)")
    if enr.get("statut") != "en_relecture":
        raise ErreurBee(f"{args.contribution} n'est plus en relecture (statut : {enr.get('statut')})")
    if any(r.get("relecteur") == args.utilisateur for r in enr.get("relectures") or []):
        raise ErreurBee(f"{args.utilisateur} a déjà relu {args.contribution}")
    relecture = {"relecteur": args.utilisateur, "avis": args.avis, "motif": args.motif, "le": en_iso(maintenant())}
    sha = (enr.get("verdict") or {}).get("sha")
    if sha:
        relecture["sha"] = sha  # la relecture porte sur ce commit ; un nouveau push la rend caduque (R3)
    if args.defaut:
        relecture["defaut_signale"] = True
    enr = dict(enr)
    enr["relectures"] = list(enr.get("relectures") or []) + [relecture]
    ecrire_yaml(chemin, enr)
    print(f"✓ relecture {args.avis} ajoutée à {args.contribution}. Publiez : bee publier --titre 'Relecture {args.contribution}'")
    return 0


def cmd_voter(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    if args.sujet in reg.enregistrements:
        if reg.enregistrements[args.sujet][1].get("auteur") == args.utilisateur:
            raise ErreurBee("on ne vote pas pour sa propre contribution (commandement 3)")
    elif args.sujet in reg.propositions:
        resultat = depouiller_proposition(reg, args.sujet, calculer_niveaux(reg), maintenant())
        if resultat["terminee"] or reg.propositions[args.sujet][1].get("statut") != "ouverte":
            raise ErreurBee(f"le vote sur {args.sujet} est clos")
    else:
        raise ErreurBee(f"sujet de vote inconnu : {args.sujet}")
    donnees = {"votant": args.utilisateur, "sujet": args.sujet, "valeur": args.valeur, "le": en_iso(maintenant())}
    if args.motif:
        donnees["motif"] = args.motif
    chemin = reg.racine / "votes" / args.sujet / f"{args.utilisateur}.yaml"
    ecrire_yaml(chemin, donnees)
    print(f"✓ vote {args.valeur:+d} enregistré ({reg.rel(chemin)}). Publiez : bee publier --titre 'Vote {args.sujet}'")
    return 0


def cmd_proposer(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    niveau = niveau_de(calculer_niveaux(reg), args.utilisateur)
    if niveau != "Confirmé" and args.utilisateur not in reg.conseil and not reg.config.get("amorcage"):
        raise ErreurBee(f"proposer une règle est réservé aux Confirmés hors amorçage (niveau actuel : {niveau})")
    numeros = [int(p[2:]) for p in reg.propositions if ID_PROPOSITION.match(p)]
    identifiant = f"P-{(max(numeros) + 1 if numeros else 1):04d}"
    donnees = {"id": identifiant, "auteur": args.utilisateur, "regle": args.regle, "texte_propose": args.texte,
               "motif": args.motif, "ouverte_le": en_iso(maintenant()), "statut": "ouverte"}
    ecrire_yaml(reg.racine / "propositions" / f"{identifiant}.yaml", donnees)
    print(f"✓ proposition {identifiant} créée. Publiez : bee publier --titre 'Proposition {identifiant}' ; le vote dure {reg.config.get('duree_vote_jours', 7)} jours.")
    return 0


def cmd_depouiller(args):
    reg = Registre(args.registre)
    print(json.dumps(depouiller_proposition(reg, args.proposition, calculer_niveaux(reg), maintenant()), ensure_ascii=False, indent=2))
    return 0


def cmd_niveaux(args):
    reg = Registre(args.registre)
    niveaux = calculer_niveaux(reg)
    if args.json:
        print(json.dumps(niveaux, ensure_ascii=False, indent=2))
        return 0
    if not niveaux:
        print("Aucun membre.")
        return 0
    afficher_tableau(["MEMBRE", "NIVEAU", "INTÉGRÉES", "RELECTURES", "POIDS DE VOTE"],
                     [[p, n["niveau"], n["integrees"], n["relectures"], POIDS_VOTE[n["niveau"]]] for p, n in sorted(niveaux.items())])
    return 0


def cmd_classement(args):
    reg = Registre(args.registre)
    niveaux = calculer_niveaux(reg)
    lignes = []
    for cid, (_, enr) in reg.enregistrements.items():
        if args.projet and reg.taches.get(enr.get("tache"), (None, {}))[1].get("projet") != args.projet:
            continue
        if args.statut and enr.get("statut") != args.statut:
            continue
        score = calculer_score(reg, enr, niveaux)
        lignes.append({"id": cid, "statut": enr.get("statut"), "auteur": enr.get("auteur"), "resume": enr.get("resume", ""), **(score or {"S": None})})
    lignes.sort(key=lambda x: -(x["S"] if x["S"] is not None else -1))
    if args.json:
        print(json.dumps(lignes, ensure_ascii=False, indent=2))
        return 0
    if not lignes:
        print("Aucune contribution.")
        return 0
    afficher_tableau(["SCORE", "CONTRIBUTION", "STATUT", "AUTEUR", "GAIN", "LIGNES", "CONFIANCE", "VOTE"],
                     [[f"{l['S']:.4f}" if l["S"] is not None else "—", l["id"], l["statut"], l["auteur"],
                       f"{100 * l['G']:+.1f}%" if l.get("G") is not None else "—", l.get("L", "—"),
                       f"{l['C']:.2f}" if l.get("C") is not None else "—", f"{l['V']:.2f}" if l.get("V") is not None else "—"] for l in lignes])
    return 0


def cmd_verifier_pr(args):
    reg = Registre(args.registre)
    problemes, natures = verifier_pr(reg, args.base, args.tete, args.auteur, args.compte_cree_le)
    problemes = verifier_registre(reg) + problemes
    for p in problemes:
        print(f"✗ {p}")
    resume = ", ".join(sorted(set(natures))) or "aucun changement"
    if problemes:
        print(f"\nPR refusée ({len(problemes)} problème(s)). Nature : {resume}.")
        return 1
    print(f"✓ PR valide. Nature : {resume}.")
    if args.fusion_auto:
        if natures and set(natures) <= LIBRE_SERVICE:
            print("FUSION_AUTO=oui")
            return 0
        print("FUSION_AUTO=non (relecture humaine requise)")
        return 3
    return 0


def cmd_verifier_fork(args):
    reg = Registre(args.registre)
    problemes, total, avertissements = verifier_fork(reg, args.depot, args.base, args.tete, args.tache, args.auteur)
    for a in avertissements:
        print(f"⚠ {a}")
    for p in problemes:
        print(f"✗ {p}")
    if problemes:
        return 1
    print(f"✓ branche conforme : {total} lignes modifiées (hors tests et bancs), manifeste valide.")
    return 0


def gain_declare(reg, manifeste, tache):
    """Gain relatif que l'agent déclare sur la métrique visée (positif = mieux), ou None."""
    metrique = tache.get("metrique")
    mesures = (manifeste or {}).get("mesures") or {}
    avant = (mesures.get("avant") or {}).get(metrique)
    apres = (mesures.get("apres") or {}).get(metrique)
    if not metrique or not avant or apres is None:
        return None
    sens = reg.metriques(tache.get("projet")).get(metrique, {}).get("sens", "plus_haut")
    return apres / avant - 1 if sens == "plus_haut" else 1 - apres / avant


def cmd_enregistrer_verdict(args):
    reg = Registre(args.registre)
    chemin, enr = reg.enregistrement(args.contribution)
    with open(args.verdict, encoding="utf-8") as f:
        brut = json.load(f)
    ci = str(brut.get("ci", "")).lower()
    verdict = {"ci": "verte" if ci in ("verte", "vert", "green", "success", "succes", "succès") else "rouge"}
    if verdict["ci"] == "rouge":
        verdict["etape_en_echec"] = str(brut.get("etape_en_echec") or "inconnue")
    gain = brut.get("gain")
    verdict["gain"] = float(gain) if gain is not None else None
    if "au_dela_du_bruit" in brut:
        verdict["au_dela_du_bruit"] = bool(brut["au_dela_du_bruit"])
    if brut.get("amorcage"):
        verdict["amorcage"] = True  # juges venus de la PR elle-même : à signaler aux relecteurs
    instructions = brut.get("instructions")
    if isinstance(instructions, dict):
        # R4 : décompte Cachegrind par scénario ({"instructions_n6": {"A", "B", "gain"}}), exact et reproductible.
        nombre = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        verdict["instructions"] = {str(n): {k: nombre((v or {}).get(k)) for k in ("A", "B", "gain")}
                                   for n, v in instructions.items() if isinstance(v, dict)}
    degradations = brut.get("degradations")
    if isinstance(degradations, dict):
        # R5 : métriques dégradées au-delà du bruit, avec leur gain relatif (négatif = pire).
        verdict["degradations"] = {str(m): (float(g) if isinstance(g, (int, float)) and not isinstance(g, bool) else None)
                                   for m, g in degradations.items()}
    juge = brut.get("juge")
    if isinstance(juge, dict):
        # Juge isolé du fork : sorties vérifiées de l'extérieur, et constructions qui pourraient tromper la
        # mesure de l'intérieur (R3 exige alors un gardien). Donnée : bornée et typée ici.
        suspects = juge.get("constructions_suspectes")
        if not isinstance(suspects, list):
            suspects = [{"type": "illisible", "detail": "liste des constructions suspectes absente ou illisible"}]
        entier = lambda v: v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None  # noqa: E731
        verdict["juge"] = {
            "version": entier(juge.get("version")),
            "sorties_comparees": entier(juge.get("sorties_comparees")),
            "constructions_suspectes": [{"type": str(s.get("type", ""))[:40], "detail": str(s.get("detail", ""))[:300]}
                                        for s in suspects[:50] if isinstance(s, dict)],
        }
    lignes = args.lignes if args.lignes is not None else brut.get("lignes_modifiees")
    if lignes is None:
        raise ErreurBee("nombre de lignes modifiées inconnu : passez --lignes ou fournissez lignes_modifiees dans le verdict")
    try:
        lignes = int(lignes)
    except (TypeError, ValueError):
        raise ErreurBee(f"lignes_modifiees illisible : {lignes!r}")
    if lignes < 0:
        raise ErreurBee(f"lignes_modifiees négatif ({lignes}) : verdict refusé")
    verdict["lignes_modifiees"] = lignes
    if args.manifeste:
        declare = gain_declare(reg, lire_yaml(args.manifeste), reg.tache(enr["tache"])[1])
        verdict["ecart_declare"] = round(abs(declare - verdict["gain"]), 4) if declare is not None and verdict["gain"] is not None else None
    if args.sha:
        verdict["sha"] = args.sha
    if args.fichiers:
        # Contrôle de confiance : la liste vient de l'API GitHub (workflow du registre), pas de la PR.
        # Une PR qui touche son workflow ou ses juges a pu fabriquer son propre verdict.
        with open(args.fichiers, encoding="utf-8") as f:
            fichiers = sorted({l.strip() for l in f if l.strip()})
        projet = reg.projets.get(reg.tache(enr["tache"])[1].get("projet"), (None, {}))[1]
        motifs = [".github/**"] + list(projet.get("chemins_juges") or [])
        juges = [c for c in fichiers if correspond(c, motifs)]
        verdict["fichiers_controles"] = True
        if juges:
            verdict["juges_modifies"] = juges[:50]
    if args.execution:
        verdict["execution"] = args.execution
    enr = dict(enr)
    enr["verdict"] = verdict
    ecrire_yaml(chemin, enr)
    seuil = float(reg.config.get("ecart_declare_max", 0.05))
    alerte = verdict.get("ecart_declare") is not None and verdict["ecart_declare"] > seuil
    print(f"✓ verdict {verdict['ci']} enregistré pour {args.contribution}"
          + (f" ; ⚠ écart de {100 * verdict['ecart_declare']:.1f} points entre gain déclaré et mesuré" if alerte else "") + ".")
    return 0


def cmd_enregistrer_mesure(args):
    """Transforme un rapport ab.py (--json) en fiche de mesure mesures/<contribution>/<pseudo>.yaml."""
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    reg.enregistrement(args.contribution)  # lève une erreur si la contribution est inconnue
    with open(args.ab, encoding="utf-8") as f:
        brut = json.load(f)
    machine = brut.get("machine") or {}
    config = {k: machine[k] for k in ("processeur", "architecture", "coeurs", "systeme", "compilateur") if machine.get(k) is not None}
    if not config.get("architecture"):
        raise ErreurBee(f"{args.ab} : champ machine/architecture absent ; est-ce bien une sortie de bee/bench/ab.py ?")
    metriques = {}
    for nom, m in (brut.get("metriques") or {}).items():
        if not isinstance(m, dict) or "gain" not in m:
            continue
        signe = m.get("test_du_signe") or {}
        entree = {"gain": round(float(m["gain"]), 6), "au_dela_du_bruit": bool(m.get("au_dela_du_bruit"))}
        if signe.get("victoires_B") is not None:
            entree["victoires_b"] = int(signe["victoires_B"])
        if signe.get("paires_utiles") is not None:
            entree["paires"] = int(signe["paires_utiles"])
        metriques[nom] = entree
    if not metriques:
        raise ErreurBee(f"{args.ab} : aucune métrique exploitable dans le rapport ab.py")
    fiche = {
        "contribution": args.contribution,
        "soumise_par": args.utilisateur,
        "le": en_iso(maintenant()),
        "base": str((brut.get("base") or {}).get("commit") or args.base or ""),
        "candidat": str((brut.get("candidat") or {}).get("commit") or args.candidat or ""),
        "config": config,
        "metriques": metriques,
    }
    if brut.get("repetitions"):
        fiche["repetitions"] = int(brut["repetitions"])
    if args.outil:
        fiche["outil"] = args.outil
    if args.motif:
        fiche["motif"] = args.motif
    if len(fiche["base"]) < 7 or len(fiche["candidat"]) < 7:
        raise ErreurBee("sha base/candidat absents du rapport ; précisez --base et --candidat (les commits comparés)")
    chemin = reg.racine / "mesures" / args.contribution / f"{args.utilisateur}.yaml"
    ecrire_yaml(chemin, fiche)
    visee = ", ".join(f"{n} {100 * e['gain']:+.1f}%{'*' if e['au_dela_du_bruit'] else ''}" for n, e in metriques.items())
    print(f"✓ mesure enregistrée ({reg.rel(chemin)}) sur {config.get('architecture')} / {config.get('compilateur', '?')}.")
    print(f"  {visee}   (* = au-delà du bruit)")
    print(f"  Publiez-la : bee publier --titre \"Mesure {args.contribution} ({config.get('architecture')})\".")
    return 0


def raisons_acceptation(reg, cid):
    """Raisons qui empêchent l'intégration automatique de `cid` (R3) ; liste vide = intégrable.

    Renvoie (chemin, enr, raisons). Les seuils de relectures et de vote sont plafonnés à ce que les
    membres éligibles (autres que l'auteur) peuvent fournir : pendant l'amorçage l'intégration repose
    sur la CI, l'absence de défaut et la fenêtre d'ouverture, et se durcit dès que des Confirmés
    apparaissent.

    Porte de relecture temporaire (bee.yaml : relecture_gardien_requise) : tant que le juge de la CI
    n'est pas sûr, toute contribution dont l'auteur n'est ni du conseil ni gardien exige aussi une
    relecture favorable d'un gardien ou du conseil. Avec la valeur « si_juge_incomplet », elle ne
    s'applique plus qu'aux contributions que le juge isolé n'a pas entièrement jugées (voir
    juge_complet) ; elle tombe quand la clé passe à false.

    Un auteur du conseil ou gardien n'en est dispensé que s'il n'existe aucun autre privilégié (amorçage).

    Constructions suspectes : si le juge isolé en a relevé (appels système, requêtes Valgrind…), une
    relecture favorable d'un gardien ou du conseil est exigée, quel que soit l'auteur et la porte.

    R4 : pour une métrique de débit qui a un décompte d'instructions associé (projets/<p>.yaml), le
    gain se juge sur les instructions (exactes) et le chronomètre corrobore ; sinon, gain au
    chronomètre au-delà du bruit, reproduit par une mesure d'une autre configuration.
    """
    chemin, enr = reg.enregistrement(cid)
    raisons = []
    if enr.get("statut") != "en_relecture":
        raisons.append(f"statut « {enr.get('statut')} » (seule une contribution en_relecture s'intègre)")
        return chemin, enr, raisons
    cfg = reg.config
    auteur = enr.get("auteur")
    tache = reg.taches.get(enr.get("tache"), (None, {}))[1]
    verdict = enr.get("verdict") or {}
    niveaux = calculer_niveaux(reg)
    eligibles = [m for m in (set(reg.membres) | set(reg.conseil)) if m != auteur]

    def exiger(cond, msg):
        if not cond:
            raisons.append(msg)

    exiger(verdict.get("ci") == "verte", f"CI non verte (verdict : {verdict.get('ci', 'absent')})")
    metriques = reg.metriques(tache.get("projet"))
    proxies = {m: d.get("instructions") for m, d in metriques.items() if d.get("instructions")}
    if tache.get("type") == "optimisation":
        seuil = float(cfg.get("gain_minimal", 0.02))
        metrique = tache.get("metrique")
        gain, bruit = verdict.get("gain"), bool(verdict.get("au_dela_du_bruit"))
        proxy = proxies.get(metrique)
        gain_inst = ((verdict.get("instructions") or {}).get(proxy) or {}).get("gain") if proxy else None

        def reproduit(minimum):
            """Mesures d'autres configurations (pas de l'auteur) qui voient le gain au chronomètre, au-delà du bruit."""
            return [m for _, m in reg.mesures if m.get("contribution") == cid and m.get("soumise_par") != auteur
                    and ((m.get("metriques") or {}).get(metrique) or {}).get("au_dela_du_bruit")
                    and (((m.get("metriques") or {}).get(metrique) or {}).get("gain") or 0) > minimum]

        if isinstance(gain_inst, (int, float)) and gain_inst >= seuil:
            # Le décompte d'instructions établit l'ampleur du gain ; le chronomètre doit le CONFIRMER (gain au-delà
            # du bruit), sinon une autre configuration doit le reproduire. Revue adverse du 27/10 : moins
            # d'instructions ne veut pas toujours dire plus rapide (mélange d'instructions, travail déplacé).
            recule = isinstance(gain, (int, float)) and gain < 0 and bruit
            exiger(not recule, f"R4 : {proxy} {pourcent(gain_inst)}, mais le chronomètre recule au-delà du bruit ({pourcent(gain)})")
            confirme = isinstance(gain, (int, float)) and gain > 0 and bruit
            if not recule and not confirme:
                exiger(reproduit(0.0), f"R4 : {proxy} {pourcent(gain_inst)}, mais le chronomètre ne le confirme pas au-delà "
                       f"du bruit ({pourcent(gain)}) : il faut une mesure d'une autre configuration qui voie le gain "
                       "(bee enregistrer-mesure)")
        else:
            exiger(isinstance(gain, (int, float)) and gain >= seuil and bruit,
                   f"R4 : {metrique} {pourcent(gain)}" + ("" if bruit else " (dans le bruit)")
                   + f" ; il faut au moins {pourcent(seuil)} au-delà du bruit"
                   + (f", ou au moins {pourcent(seuil)} sur {proxy} ({pourcent(gain_inst)})" if proxy else ""))
            if proxy:
                exiger(reproduit(seuil - 1e-12), f"R4 : sans gain d'instructions sur {proxy}, le gain au chronomètre doit être "
                       "reproduit par une mesure d'une autre configuration (bee enregistrer-mesure)")
    # R5. Le chronomètre seul d'une métrique de débit est trop bruité pour bloquer : on juge son décompte
    # d'instructions. Les autres métriques (ratio, mémoire) se jugent directement.
    tolerance = float(cfg.get("degradation_max_autres", 0.01))
    ignorees = set(proxies) | {tache.get("metrique"), proxies.get(tache.get("metrique"))}
    hors_tolerance = {m: g for m, g in (verdict.get("degradations") or {}).items()
                      if m not in ignorees and (g is None or g < -tolerance)}
    exiger(not hors_tolerance, "R5 : métrique(s) dégradée(s) au-delà de la tolérance : "
           + ", ".join(f"{m} ({'?' if g is None else f'{100 * g:+.1f} %'})" for m, g in hors_tolerance.items()))

    relectures = enr.get("relectures") or []
    exiger(not any(r.get("defaut_confirme") for r in relectures), "un défaut confirmé reste à résoudre")
    sha_verdict = verdict.get("sha")

    def actuelle(r):
        """Une relecture ne vaut que pour le commit qu'elle a relu (celui du verdict)."""
        return not sha_verdict or r.get("sha") == sha_verdict

    privilegies = reg.privilegies()
    autres = [r for r in relectures if r.get("relecteur") != auteur]
    favorables = [r for r in autres if r.get("avis") == "favorable" and actuelle(r)]
    defavorables = [r for r in autres if r.get("avis") == "defavorable" and actuelle(r)]
    perimees = [r for r in autres if not actuelle(r)]
    exiger(bool(verdict.get("fichiers_controles")),
           "verdict non contrôlé : la liste des fichiers de la PR n'a pas été vérifiée par le workflow du registre")
    juges = verdict.get("juges_modifies") or []
    if juges:
        liste = ", ".join(juges[:5]) + (" …" if len(juges) > 5 else "")
        if tache.get("type") not in ("test", "mesure"):
            exiger(False, f"la PR modifie des juges ({liste}) : interdit pour une tâche {tache.get('type')} (commandement 3)")
        elif auteur not in privilegies:  # un auteur du conseil ou gardien répond lui-même de ses juges
            exiger(any(r.get("relecteur") in privilegies or niveau_de(niveaux, r.get("relecteur")) == "Confirmé" for r in favorables),
                   f"la PR modifie des juges ({liste}) : une relecture favorable d'un gardien, du conseil ou d'un Confirmé est exigée")
    requises = min(int(cfg.get("relectures_requises", 2)), len(eligibles))
    exiger(len(favorables) >= requises, f"{len(favorables)} relecture(s) favorable(s) sur {requises} requise(s)"
           + (f" ; {len(perimees)} relecture(s) portent sur un commit antérieur et ne comptent plus" if perimees else ""))
    exiger(not defavorables or len(favorables) > len(defavorables),
           f"{len(defavorables)} relecture(s) défavorable(s) contre {len(favorables)} favorable(s)")
    bloquantes = sorted({r.get("relecteur") for r in defavorables
                         if r.get("relecteur") in privilegies or niveau_de(niveaux, r.get("relecteur")) == "Confirmé"})
    exiger(not bloquantes, f"relecture défavorable de {', '.join(bloquantes)} (gardien, conseil ou Confirmé) : "
           "elle bloque jusqu'à un nouveau commit, qui la rend caduque")
    if [m for m in eligibles if niveau_de(niveaux, m) == "Confirmé"]:
        exiger(any(niveau_de(niveaux, r.get("relecteur")) == "Confirmé" for r in favorables),
               "aucune relecture favorable d'un Confirmé (il en faut une quand un Confirmé est disponible)")
    # Un auteur privilégié ne se dispense de la porte que s'il n'existe aucun autre privilégié pour relire
    # (amorçage) : dès qu'un gardien est nommé, le conseil aussi est relu.
    autres_privilegies = [m for m in privilegies if m != auteur]
    if porte_exigee(reg, verdict) and (auteur not in privilegies or autres_privilegies):
        exiger(any(r.get("relecteur") in privilegies for r in favorables),
               "porte de relecture temporaire : une relecture favorable d'un gardien ou du conseil est exigée "
               + ("tant que le juge de la CI n'est pas sûr" if mode_porte(reg) == "toujours"
                  else "car le juge isolé n'a pas entièrement jugé cette contribution")
               + " (bee.yaml : relecture_gardien_requise)")
    suspects = ((verdict.get("juge") or {}).get("constructions_suspectes")) or []
    if suspects:
        exiger(any(r.get("relecteur") in privilegies for r in favorables),
               f"{len(suspects)} construction(s) suspecte(s) relevée(s) par le juge isolé "
               f"({suspects[0].get('detail', '')[:80]}…) : une relecture favorable d'un gardien ou du conseil est exigée")

    net = sum(int(v.get("valeur", 0)) * POIDS_VOTE.get(niveau_de(niveaux, v.get("votant")), 0)
              for _, v in reg.votes if v.get("sujet") == cid and v.get("votant") != auteur)
    poids_dispo = sum(POIDS_VOTE.get(niveau_de(niveaux, m), 0) for m in eligibles)
    seuil_vote = min(int(cfg.get("vote_net_min", 2)), poids_dispo)
    exiger(net >= seuil_vote, f"vote net de la ruche {net} sous le seuil {seuil_vote} (pondéré)")

    try:
        heures = (maintenant() - lire_instant(enr.get("soumise_le"), reg.rel(chemin))).total_seconds() / 3600
        fenetre = float(cfg.get("fenetre_acceptation_heures", 24))
        exiger(heures >= fenetre, f"fenêtre d'ouverture : {heures:.0f} h écoulées sur {fenetre:.0f} h")
    except ErreurBee:
        raisons.append("date de soumission illisible")
    return chemin, enr, raisons


def mode_porte(reg):
    """« toujours », « si_juge_incomplet » ou « jamais » (bee.yaml : relecture_gardien_requise)."""
    cfg = reg.config
    valeur = cfg.get("relecture_gardien_requise", cfg.get("relecture_conseil_requise"))
    if valeur == "si_juge_incomplet":
        return "si_juge_incomplet"
    return "toujours" if valeur else "jamais"


def juge_complet(verdict):
    """Le juge isolé a-t-il entièrement jugé ce verdict ? Liste des fichiers contrôlée par le registre, aucun
    juge modifié, sorties vérifiées de l'extérieur, aucune construction suspecte, et pas d'amorçage."""
    juge = verdict.get("juge") or {}
    return bool(verdict.get("fichiers_controles") and not verdict.get("juges_modifies") and not verdict.get("amorcage")
                and isinstance(juge.get("sorties_comparees"), int) and juge["sorties_comparees"] > 0
                and not juge.get("constructions_suspectes"))


def porte_exigee(reg, verdict):
    """Vrai si la porte de relecture temporaire de R3 s'applique à ce verdict."""
    mode = mode_porte(reg)
    return mode == "toujours" or (mode == "si_juge_incomplet" and not juge_complet(verdict))


def porte_humaine(reg):
    """Vrai tant que la porte de relecture temporaire de R3 peut s'appliquer (voir raisons_acceptation)."""
    return mode_porte(reg) != "jamais"


def pourcent(x):
    return f"{100 * x:+.1f} %" if isinstance(x, (int, float)) else "absent"


def cmd_verifier_acceptation(args):
    """Règle R3 exécutable : une contribution est-elle intégrable automatiquement ?

    Code 0 si oui (le workflow de confiance peut intégrer), 1 sinon avec les raisons. Ne modifie rien.
    """
    reg = Registre(args.registre)
    _, _, raisons = raisons_acceptation(reg, args.contribution)
    if raisons:
        print(f"✗ {args.contribution} : pas encore intégrable.")
        for r in raisons:
            print("  - " + r)
        return 1
    print(f"✓ {args.contribution} est intégrable automatiquement (R3) : CI verte, relectures et vote "
          f"suffisants, fenêtre écoulée"
          + (" (porte de relecture satisfaite)." if porte_humaine(reg) else ". Aucune relecture privilégiée requise."))
    return 0


def cmd_integrer(args):
    """Intègre une contribution si et seulement si R3 est satisfaite.

    Met à jour le registre (contribution et tâche passent en « integree »). La fusion du code sur le
    dépôt du projet est faite par le workflow de confiance (même dépôt dans l'architecture répartie),
    qui appelle d'abord verifier-acceptation. Refuse, sans rien écrire, si R3 n'est pas remplie.
    """
    reg = Registre(args.registre)
    chemin, enr, raisons = raisons_acceptation(reg, args.contribution)
    if raisons:
        print(f"✗ {args.contribution} n'est pas intégrable automatiquement :")
        for r in raisons:
            print("  - " + r)
        return 1
    enr = dict(enr)
    enr["statut"] = "integree"
    enr["decidee_le"] = en_iso(maintenant())
    enr["motif_decision"] = ("Intégration automatique (R3) : CI verte, relectures et vote suffisants, fenêtre écoulée"
                             + (" ; porte de relecture satisfaite." if porte_humaine(reg) else " ; sans relecture privilégiée."))
    if args.fusion_sha:
        enr["fusion_sha"] = args.fusion_sha
    ecrire_yaml(chemin, enr)
    modifier_tache(reg.tache(enr["tache"])[0], statut="integree")
    print(f"✓ {args.contribution} intégrée automatiquement (R3).")
    print(f"  PR du projet à fusionner : {enr.get('pr', '(inconnue)')}")
    return 0


def cmd_cloturer(args):
    """Sortie automatique : clôt une contribution abandonnée (PR fermée sans fusion).

    La contribution passe en « annulee » et sa tâche est rouverte, avec une note pour l'agent suivant.
    Sans cela, une contribution abandonnée verrouillerait sa tâche pour toujours.
    """
    reg = Registre(args.registre)
    chemin, enr = reg.enregistrement(args.contribution)
    if enr.get("statut") != "en_relecture":
        print(f"{args.contribution} n'est pas en relecture (statut : {enr.get('statut')}) ; rien à clore.")
        return 1
    enr = dict(enr)
    enr["statut"] = "annulee"
    enr["decidee_le"] = en_iso(maintenant())
    enr["motif_decision"] = args.motif
    ecrire_yaml(chemin, enr)
    chemin_tache, tache = reg.tache(enr["tache"])
    if tache.get("contribution") == args.contribution and tache.get("statut") == "en_relecture":
        modifier_tache(chemin_tache, statut="ouverte", reservation=None, contribution=None,
                       note={"par": args.par, "le": en_iso(maintenant()),
                             "texte": f"{args.contribution} close sans intégration : {args.motif} Tâche rouverte."})
    print(f"✓ {args.contribution} close (annulee) ; tâche {enr['tache']} rouverte.")
    return 0


def cmd_en_attente(args):
    reg = Registre(args.registre)
    resultat = [{"id": cid, "pr": enr.get("pr"), "sha_verdict": (enr.get("verdict") or {}).get("sha"),
                 "ci_verdict": (enr.get("verdict") or {}).get("ci")}
                for cid, (_, enr) in sorted(reg.enregistrements.items()) if enr.get("statut") == "en_relecture"]
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    return 0


DOSSIERS_LIBRE_SERVICE = ("taches/", "contributions/", "votes/", "mesures/", "membres/", "propositions/")


def executer(commande, depot=None, verifier=True):
    """Lance une commande (git, gh) et renvoie sa sortie ; ErreurBee lisible en cas d'échec."""
    resultat = subprocess.run(commande, cwd=depot, capture_output=True, text=True)
    if verifier and resultat.returncode != 0:
        raise ErreurBee(f"{' '.join(commande[:3])} … a échoué : {(resultat.stderr or resultat.stdout).strip()[:500]}")
    return resultat


def proprietaire_depot(url):
    correspondance = re.search(r"github\.com[:/]([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url or "")
    return (correspondance[1], correspondance[2]) if correspondance else (None, None)


def cmd_publier(args):
    """Branche, commit, push, PR, puis attente de la fusion : une action du registre en une commande."""
    reg = Registre(args.registre)
    depot = reg.racine
    organisation = reg.config.get("organisation", "")
    amont = args.amont or f"{organisation}/registre"
    changements = [l[3:].strip().strip('"') for l in executer(["git", "status", "--porcelain", "--untracked-files=all"], depot).stdout.splitlines() if l.strip()]
    if not changements:
        raise ErreurBee("aucun changement à publier (avez-vous lancé bee prendre, soumettre, relire, voter… ?)")
    interdits = [c for c in changements if not c.startswith(DOSSIERS_LIBRE_SERVICE)]
    if interdits:
        raise ErreurBee("ces fichiers ne relèvent pas du libre-service et feraient refuser la PR : " + ", ".join(interdits[:8])
                        + ". Retirez-les (git restore ou git rm --cached) ; s'ils sont voulus, c'est une PR pour le conseil.")
    problemes = verifier_registre(Registre(depot))
    if problemes:
        raise ErreurBee("le registre n'est pas valide, la PR serait refusée :\n  " + "\n  ".join(problemes[:10]))
    if args.a_blanc:
        print("✓ à blanc : les fichiers relèvent du libre-service et le registre reste valide. Rien n'a été écrit ni poussé.")
        print(f"  Dépôt : {amont} — PR « {args.titre} »")
        for c in changements:
            print(f"  - {c}")
        print("  Sans --a-blanc, bee publierait : branche, commit, poussée, PR, attente de la fusion automatique.")
        return 0
    branche_initiale = executer(["git", "rev-parse", "--abbrev-ref", "HEAD"], depot).stdout.strip()
    base = re.sub(r"[^a-z0-9]+", "-", args.titre.lower().translate(str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc"))).strip("-")[:50] or "publication"
    # Horodatée pour ne jamais retomber sur une branche distante restée d'une publication précédente.
    racine_branche = f"bee/{base}-{maintenant().strftime('%Y%m%d-%H%M%S')}"
    branche, n = racine_branche, 2
    while executer(["git", "rev-parse", "--verify", "--quiet", branche], depot, verifier=False).returncode == 0:
        branche, n = f"{racine_branche}-{n}", n + 1
    executer(["git", "switch", "-c", branche], depot)
    try:
        executer(["git", "add", "--", *changements], depot)
        executer(["git", "commit", "-m", args.titre], depot)
        executer(["git", "push", "-u", "origin", branche], depot)
        proprietaire, _ = proprietaire_depot(executer(["git", "remote", "get-url", "origin"], depot).stdout.strip())
        proprietaire_amont, _ = proprietaire_depot(f"https://github.com/{amont}")
        tete = branche if proprietaire in (None, proprietaire_amont) else f"{proprietaire}:{branche}"
        corps = args.corps or f"Publié avec `bee publier`.\n\nNature : {args.titre}."
        # API REST plutôt que `gh pr create` (GraphQL) : elle fonctionne aussi dans les environnements restreints.
        pr = json.loads(executer(["gh", "api", f"repos/{amont}/pulls", "-X", "POST", "-f", f"title={args.titre}",
                                  "-f", f"head={tete}", "-f", "base=main", "-f", f"body={corps}"], depot).stdout)
    finally:
        executer(["git", "switch", branche_initiale if branche_initiale != "HEAD" else "main"], depot, verifier=False)
    adresse, numero = pr["html_url"], pr["number"]
    print(f"✓ PR ouverte : {adresse}")
    if args.sans_attendre:
        print(f"  Pensez à attendre sa fusion avant l'étape suivante (gh api repos/{amont}/pulls/{numero} --jq .merged).")
        return 0
    import time
    limite = time.monotonic() + args.delai * 60
    print(f"  Attente de la fusion (au plus {args.delai} min)…")
    while True:
        infos = json.loads(executer(["gh", "api", f"repos/{amont}/pulls/{numero}"], depot).stdout or "{}")
        etat = "MERGED" if infos.get("merged") else str(infos.get("state", "")).upper()
        if etat == "MERGED":
            distant = "upstream" if executer(["git", "remote", "get-url", "upstream"], depot, verifier=False).returncode == 0 else "origin"
            executer(["git", "switch", "main"], depot, verifier=False)
            executer(["git", "pull", "--ff-only", distant, "main"], depot)
            print("✓ PR fusionnée ; main est à jour. Vous pouvez passer à l'étape suivante.")
            return 0
        if etat == "CLOSED":
            raise ErreurBee(f"la PR a été refusée et fermée : lisez le message de la CI sur {adresse}")
        if time.monotonic() > limite:
            print(f"⚠ la PR est toujours ouverte après {args.delai} min : elle attend sans doute une relecture humaine. "
                  "Ne l'attendez pas : faites autre chose ou arrêtez-vous.")
            return 2
        time.sleep(args.intervalle)


def cmd_site(args):
    reg = Registre(args.registre)
    chemin = generer_site(reg, args.sortie)
    print(f"✓ site généré : {chemin}")
    return 0


def construire_analyseur():
    analyseur = argparse.ArgumentParser(
        prog="bee",
        description="Outil du registre Bee. Commencez par lire AGENTS.md.",
        epilog="Parcours type d'un agent : lister → voir → prendre → (travail sur le fork) → manifeste → verifier-fork → soumettre.")
    analyseur.add_argument("--version", action="version", version=f"bee {VERSION}")
    analyseur.add_argument("--registre", help="chemin du registre (défaut : $BEE_REGISTRE, sinon le dépôt qui contient cet outil)")
    sous = analyseur.add_subparsers(dest="commande", required=True, metavar="commande")

    def ajouter(nom, fonction, aide):
        p = sous.add_parser(nom, help=aide, description=aide)
        p.set_defaults(fonction=fonction)
        return p

    ajouter("valider", cmd_valider, "Vérifie tout le registre (schémas et cohérence).")

    p = ajouter("lister", cmd_lister, "Liste les tâches, triées par projet puis par portée.")
    p.add_argument("--statut", default="ouverte", choices=["proposee", "ouverte", "reservee", "en_relecture", "integree", "refusee", "abandonnee", "toutes"])
    p.add_argument("--projet")
    p.add_argument("--categorie")
    p.add_argument("--type", choices=["optimisation", "relecture", "mesure", "test", "decoupage"])
    p.add_argument("--taille-max", choices=ORDRE_TAILLES, help="taille maximale compatible avec votre budget")
    p.add_argument("--disponibles", action="store_true", help="masque les tâches qui attendent une autre tâche")
    p.add_argument("--json", action="store_true")

    p = ajouter("voir", cmd_voir, "Affiche une tâche complète et ce qu'il faut savoir pour la prendre.")
    p.add_argument("tache")

    p = ajouter("inscrire", cmd_inscrire, "Crée votre fiche membre (un compte humain, une voix, tous agents confondus).")
    p.add_argument("--pseudo", required=True, help="votre identifiant GitHub")
    p.add_argument("--compte-cree-le", required=True, help="date de création du compte GitHub (AAAA-MM-JJ)")
    p.add_argument("--categories", nargs="*")

    p = ajouter("prendre", cmd_prendre, "Réserve une tâche (72 h maximum, 3 réservations par utilisateur).")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)

    p = ajouter("proposer-tache", cmd_proposer_tache,
                "Prépare une proposition de tâche (statut « proposee »), qu'un gardien, le conseil ou un Confirmé validera.")
    p.add_argument("projet", help="ex. miniz")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--type", default="optimisation", choices=["optimisation", "mesure", "test", "relecture"])
    p.add_argument("--taille", default="S", choices=ORDRE_TAILLES)
    p.add_argument("--metrique", help="métrique visée (optimisation) ; défaut : la première du projet")

    p = ajouter("liberer", cmd_liberer, "Rend une tâche réservée ; --note transmet ce que vous avez appris.")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--note")

    p = ajouter("noter", cmd_noter, "Ajoute une note signée à une tâche (avancée, piste, possible injection repérée…).")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--texte", required=True)

    ajouter("liberer-expirees", cmd_liberer_expirees, "Libère les réservations de plus de 72 h (lancé par la CI).")

    p = ajouter("manifeste", cmd_manifeste, "Génère le manifeste à remplir pour une tâche (manifestes/<tâche>.yaml dans le fork).")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--modele", help="nom et version du modèle de l'agent")
    p.add_argument("--sortie", help="fichier à écrire, ou racine du fork (le manifeste va alors dans manifestes/<tâche>.yaml) ; "
                                    "défaut : sortie standard")

    p = ajouter("valider-contribution", cmd_valider_contribution, "Vérifie un CONTRIBUTION.yaml avant de soumettre.")
    p.add_argument("fichier")

    p = ajouter("soumettre", cmd_soumettre, "Enregistre votre contribution (après avoir ouvert la PR sur le fork).")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--pr", required=True, help="adresse de la pull request sur le fork")
    p.add_argument("--resume", help="une phrase, reprise du manifeste")

    p = ajouter("relire", cmd_relire, "Ajoute votre relecture d'une contribution.")
    p.add_argument("contribution")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--avis", required=True, choices=["favorable", "defavorable"])
    p.add_argument("--motif", required=True, help="ce que vous avez vérifié, ce que vous avez trouvé")
    p.add_argument("--defaut", action="store_true", help="vous signalez un défaut reproductible (décrit dans le motif)")

    p = ajouter("enregistrer-mesure", cmd_enregistrer_mesure,
                "Transforme un rapport ab.py (--json) en fiche de mesure pour une contribution, sur votre configuration.")
    p.add_argument("contribution", help="id de la contribution mesurée (ex. miniz-0011-c1)")
    p.add_argument("--ab", required=True, help="rapport JSON produit par bee/bench/ab.py --json")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--base", help="sha de référence si absent du rapport")
    p.add_argument("--candidat", help="sha candidat si absent du rapport")
    p.add_argument("--outil", help="provenance de l'outillage (version de bee, ou sha du bee/ du fork)")
    p.add_argument("--motif", help="remarque libre (anomalie, bridage thermique…)")

    p = ajouter("voter", cmd_voter, "Vote sur une contribution (importance) ou une proposition de règle.")
    p.add_argument("sujet", help="id de contribution (ex. miniz-0007-c1) ou de proposition (ex. P-0001)")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--valeur", required=True, type=int, choices=[-1, 0, 1])
    p.add_argument("--motif")

    p = ajouter("proposer", cmd_proposer, "Propose un changement de règle (Confirmés).")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--regle", required=True, help="ex. R4")
    p.add_argument("--texte", required=True, help="nouveau texte de la règle")
    p.add_argument("--motif", required=True)

    p = ajouter("depouiller", cmd_depouiller, "Calcule le résultat d'un vote sur une proposition.")
    p.add_argument("proposition")

    p = ajouter("niveaux", cmd_niveaux, "Affiche le niveau et le poids de vote de chaque membre.")
    p.add_argument("--json", action="store_true")

    p = ajouter("classement", cmd_classement, "Classe les contributions par score.")
    p.add_argument("--projet")
    p.add_argument("--statut", choices=["en_relecture", "integree", "refusee", "annulee"], help="ex. en_relecture : les contributions à relire")
    p.add_argument("--json", action="store_true")

    p = ajouter("verifier-acceptation", cmd_verifier_acceptation,
                "Règle R3 : une contribution est-elle intégrable automatiquement (CI + relectures + vote + fenêtre, + porte humaine temporaire) ?")
    p.add_argument("contribution", help="id de la contribution (ex. miniz-0012-c1)")

    p = ajouter("integrer", cmd_integrer,
                "Intègre une contribution si R3 est satisfaite : passe contribution et tâche en « integree ». Utilisé par le workflow de confiance.")
    p.add_argument("contribution", help="id de la contribution (ex. miniz-0012-c1)")
    p.add_argument("--fusion-sha", help="SHA du commit de fusion sur le dépôt du projet, consigné dans la contribution")

    p = ajouter("cloturer", cmd_cloturer,
                "Clôt une contribution abandonnée (PR fermée sans fusion) et rouvre sa tâche. Utilisé par le workflow de confiance.")
    p.add_argument("contribution", help="id de la contribution (ex. miniz-0012-c1)")
    p.add_argument("--motif", required=True, help="raison de la clôture (ex. « PR fermée sans fusion »)")
    p.add_argument("--par", default="github-actions[bot]", help="signature de la note laissée sur la tâche")

    p = ajouter("verifier-pr", cmd_verifier_pr, "Vérifie une pull request sur le registre (utilisé par la CI).")
    p.add_argument("--base", required=True)
    p.add_argument("--tete", default="HEAD")
    p.add_argument("--auteur", required=True)
    p.add_argument("--compte-cree-le", help="date de création du compte, fournie par l'API GitHub")
    p.add_argument("--fusion-auto", action="store_true", help="code 0 si fusionnable sans humain, 3 sinon")

    p = ajouter("verifier-fork", cmd_verifier_fork, "Vérifie une branche de contribution sur un fork (R1, commandement 3, manifeste).")
    p.add_argument("--tache", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--tete", default="HEAD")
    p.add_argument("--depot", default=".", help="chemin du clone du fork")
    p.add_argument("--auteur")

    p = ajouter("enregistrer-verdict", cmd_enregistrer_verdict, "Reporte le verdict de la CI d'un fork dans le registre (utilisé par la CI).")
    p.add_argument("contribution")
    p.add_argument("--verdict", required=True, help="verdict.json produit par la CI du fork")
    p.add_argument("--manifeste", help="CONTRIBUTION.yaml de la PR, pour calculer l'écart déclaré / mesuré")
    p.add_argument("--lignes", type=int, help="lignes modifiées hors tests, si le verdict ne les donne pas")
    p.add_argument("--sha", help="commit évalué")
    p.add_argument("--execution", help="adresse de l'exécution de CI")
    p.add_argument("--fichiers", help="liste des fichiers modifiés par la PR (un par ligne), lue par le workflow de confiance "
                                      "auprès de l'API GitHub ; sans elle, le verdict n'est pas intégrable")

    p = ajouter("publier", cmd_publier, "Publie vos changements du registre : branche, commit, push, PR, puis attente de la fusion.")
    p.add_argument("--titre", required=True, help="ex. « Réservation miniz-0012 », « Soumission miniz-0012-c1 »")
    p.add_argument("--corps", help="texte de la PR (facultatif)")
    p.add_argument("--amont", help="dépôt du registre (défaut : <organisation>/registre)")
    p.add_argument("--sans-attendre", action="store_true", help="ne pas attendre la fusion")
    p.add_argument("--a-blanc", "--dry-run", action="store_true",
                   help="vérifie tout et affiche ce qui serait publié, sans rien écrire ni pousser")
    p.add_argument("--delai", type=int, default=10, help="minutes d'attente au plus (défaut : 10)")
    p.add_argument("--intervalle", type=float, default=15, help=argparse.SUPPRESS)

    ajouter("en-attente", cmd_en_attente, "Liste en JSON les contributions en relecture et le commit de leur dernier verdict (utilisé par la CI).")

    p = ajouter("site", cmd_site, "Génère le site statique du registre.")
    p.add_argument("--sortie", default="_site")
    return analyseur


def principal(argv=None):
    args = construire_analyseur().parse_args(argv)
    try:
        return args.fonction(args)
    except ErreurBee as e:
        print(f"bee : {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(principal())
