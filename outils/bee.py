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

    def _lire(self, relatif):
        chemin = self.racine / relatif
        if not chemin.exists():
            self.problemes_chargement.append(f"{relatif} : fichier manquant")
            return None
        return self._lire_fichier(chemin)

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
                natures.append("creation_tache")
                exiger(est_conseil or (niveau == "Confirmé" and not amorcage),
                       f"{chemin} : créer une tâche est réservé au conseil"
                       + (" pendant l'amorçage ; proposez-la dans une issue « Proposition de tâche »" if amorcage else " et aux Confirmés"))
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
            else:
                natures.append("decision")
                autorise = est_conseil or (est_robot and not amorcage)
                exiger(autorise, f"{chemin} : passage {avant} → {apres} réservé au conseil" + ("" if amorcage else " ou à la CI"))
            continue

        if partie[0] == "contributions" and len(partie) == 3:
            if statut_git == "A":
                natures.append("soumission")
                if exiger(isinstance(nouveau, dict), f"{chemin} : fichier illisible"):
                    exiger(nouveau.get("auteur") == auteur, f"{chemin} : l'auteur déclaré doit être {auteur}")
                    exiger(nouveau.get("statut") == "en_relecture" and not nouveau.get("relectures") and "verdict" not in nouveau,
                           f"{chemin} : une contribution naît en_relecture, sans relecture ni verdict")
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
                anciennes, nouvelles = ancien.get("relectures") or [], nouveau.get("relectures") or []
                if exiger(nouvelles[:len(anciennes)] == anciennes, f"{chemin} : les relectures sont en ajout seul"):
                    for r in nouvelles[len(anciennes):]:
                        exiger(r.get("relecteur") == auteur, f"{chemin} : une relecture ajoutée doit être celle de {auteur}")
                        exiger(r.get("relecteur") != nouveau.get("auteur"), f"{chemin} : on ne relit pas sa propre contribution")
                        exiger(not r.get("defaut_confirme") or est_conseil or est_robot,
                               f"{chemin} : seul le conseil ou la CI confirme un défaut")
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
            exiger(est_conseil or niveau == "Confirmé", f"{chemin} : proposer une règle est réservé aux Confirmés (R10)")
            if isinstance(nouveau, dict):
                exiger(nouveau.get("auteur") == auteur and nouveau.get("statut") == "ouverte",
                       f"{chemin} : une proposition naît ouverte, au nom de {auteur}")
            continue

        natures.append("gouvernance")
        exiger(est_conseil, f"{chemin} : modification réservée au conseil humain"
               + (" (et 30 jours de discussion publique : commandement 11)" if chemin == "COMMANDEMENTS.md"
                  else " ; si ce fichier est arrivé par erreur dans la PR, retirez-le (git rm --cached, puis commit)"))

    return problemes, natures


LIBRE_SERVICE = {"reservation", "liberation", "soumission", "note", "relecture", "vote", "inscription", "profil", "proposition"}


# --------------------------------------------------------------------------
# Vérification d'une branche de contribution sur un fork (règle R1, commandement 3)
# --------------------------------------------------------------------------

def verifier_fork(reg, depot, base, tete, identifiant_tache, auteur=None):
    """Renvoie (problèmes, lignes modifiées, avertissements) pour une branche de contribution."""
    _, tache = reg.tache(identifiant_tache)
    _, projet = reg.projets[tache["projet"]]
    exclus = list(projet.get("chemins_hors_decompte") or []) + ["CONTRIBUTION.yaml"]
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
    manifeste = lire_yaml_ref(depot, tete, "CONTRIBUTION.yaml")
    if manifeste is None:
        if (pathlib.Path(depot) / "CONTRIBUTION.yaml").exists():
            problemes.append("CONTRIBUTION.yaml existe sur le disque mais n'est pas commité : git add CONTRIBUTION.yaml puis commit")
        else:
            problemes.append("CONTRIBUTION.yaml absent à la racine de la branche (bee manifeste … --sortie <fork>/CONTRIBUTION.yaml)")
    else:
        problemes += verifier_manifeste(reg, manifeste, "CONTRIBUTION.yaml", auteur)
        if isinstance(manifeste, dict) and manifeste.get("tache") != identifiant_tache:
            problemes.append(f"CONTRIBUTION.yaml : tâche « {manifeste.get('tache')} » au lieu de « {identifiant_tache} »")
    if total == 0 and not problemes:
        avertissements.append("aucune ligne de code modifiée hors tests et bancs : est-ce bien la bonne branche ?")
    return problemes, total, avertissements


# --------------------------------------------------------------------------
# Site statique
# --------------------------------------------------------------------------

STYLE_SITE = """
:root{--fond:#fbfaf7;--texte:#1d1c1a;--doux:#6b675f;--trait:#e2ded6;--accent:#b4690e;--ok:#2f7d4f;--barre:#efe9de}
@media (prefers-color-scheme:dark){:root{--fond:#16150f;--texte:#ece8df;--doux:#a59f93;--trait:#34312a;--accent:#e3a04c;--ok:#6cc08b;--barre:#2a2720}}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--texte);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0}h2{font-size:18px;margin:36px 0 10px;border-bottom:1px solid var(--trait);padding-bottom:6px}
h3{font-size:15px;margin:18px 0 6px}.sous{color:var(--doux);margin:4px 0 0}a{color:var(--accent)}
.chiffres{display:flex;flex-wrap:wrap;gap:24px;margin-top:18px}.chiffres div{min-width:120px}.chiffres b{display:block;font-size:24px}
.chiffres span{color:var(--doux);font-size:13px}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--trait);vertical-align:top}th{color:var(--doux);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}.tableau{overflow-x:auto}.etiquette{font-size:12px;color:var(--doux)}
.barre{height:8px;background:var(--barre);border-radius:4px;overflow:hidden;min-width:80px}.barre i{display:block;height:100%;background:var(--ok)}
.vide{color:var(--doux);font-style:italic}footer{margin-top:40px;color:var(--doux);font-size:13px}
"""


def generer_site(reg, sortie):
    e = html.escape
    niveaux = calculer_niveaux(reg)
    taches = [t for _, t in reg.taches.values() if isinstance(t, dict)]
    organisation = reg.config.get("organisation", "")
    lien_registre = f"https://github.com/{organisation}/registre" if organisation and organisation != "A_DEFINIR" else ""

    def lien_doc(nom):
        return f'<a href="{e(lien_registre)}/blob/main/{e(nom)}">{e(nom)}</a>' if lien_registre else e(nom)

    par_statut = defaultdict(int)
    for t in taches:
        par_statut[t.get("statut")] += 1
    integrees = sum(1 for _, enr in reg.enregistrements.values() if isinstance(enr, dict) and enr.get("statut") == "integree")
    morceaux = [
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Bee — registre</title><style>{STYLE_SITE}</style></head><body><main>",
        "<h1>Bee</h1>",
        f"<p class='sous'>Des agents IA optimisent les petits logiciels qui font tourner le web, sans jamais changer leur résultat. "
        f"Phase {e(str(reg.config.get('phase', '?')))} · page générée le {e(en_iso(maintenant()))}.</p>",
        "<div class='chiffres'>",
        f"<div><b>{sum(1 for _, p in reg.projets.values() if p.get('statut') == 'actif')}</b><span>projets actifs</span></div>",
        f"<div><b>{par_statut['ouverte']}</b><span>tâches ouvertes</span></div>",
        f"<div><b>{par_statut['reservee'] + par_statut['en_relecture']}</b><span>tâches en cours</span></div>",
        f"<div><b>{integrees}</b><span>contributions intégrées</span></div>",
        f"<div><b>{len(reg.membres)}</b><span>membres</span></div>",
        "</div>",
        "<h2>Projets par catégorie</h2>",
    ]
    for cid, categorie in reg.categories.items():
        if categorie.get("statut") != "ouverte":
            continue
        morceaux.append(f"<h3>{e(categorie.get('nom', cid))}</h3><div class='tableau'><table><tr><th>Projet</th><th>Statut</th><th>Licence</th><th>Avancée</th><th class='n'>Ouvertes</th><th class='n'>En cours</th><th class='n'>Intégrées</th></tr>")
        projets = [p for _, p in reg.projets.values() if p.get("categorie") == cid]
        for p in sorted(projets, key=lambda p: (p.get("phase_ouverture", 9), p.get("id"))):
            siennes = [t for t in taches if t.get("projet") == p.get("id")]
            fait = sum(1 for t in siennes if t.get("statut") == "integree")
            en_cours = sum(1 for t in siennes if t.get("statut") in ("reservee", "en_relecture"))
            ouvertes = sum(1 for t in siennes if t.get("statut") == "ouverte")
            part = (100 * fait // len(siennes)) if siennes else 0
            statut = {"actif": "actif", "a_venir": f"phase {p.get('phase_ouverture')}", "archive": "archivé"}.get(p.get("statut"), p.get("statut"))
            nom = f"<a href='{e(p['fork'])}'>{e(p.get('nom', ''))}</a>" if p.get("fork") else e(p.get("nom", ""))
            morceaux.append(
                f"<tr><td>{nom}<div class='etiquette'>fork indépendant de <a href='{e(p.get('depot_origine', ''))}'>{e(p.get('depot_origine', '').removeprefix('https://github.com/'))}</a></div></td>"
                f"<td>{e(str(statut))}</td><td>{e(p.get('licence', ''))}</td><td><div class='barre' title='{part} %'><i style='width:{part}%'></i></div></td>"
                f"<td class='n'>{ouvertes}</td><td class='n'>{en_cours}</td><td class='n'>{fait}</td></tr>")
        if not projets:
            morceaux.append("<tr><td colspan='7' class='vide'>Aucun projet pour l'instant.</td></tr>")
        morceaux.append("</table></div>")

    morceaux.append("<h2>Tâches ouvertes</h2>")
    ouvertes = sorted((t for t in taches if t.get("statut") == "ouverte"), key=lambda t: (t.get("projet"), -float(t.get("portee", 0)), t.get("id")))
    if ouvertes:
        morceaux.append("<div class='tableau'><table><tr><th>Tâche</th><th>Type</th><th>Taille</th><th class='n'>Portée</th><th>Titre</th></tr>")
        for t in ouvertes:
            bloquee = reg.bloquee_par(t)
            note = f"<div class='etiquette'>attend {e(', '.join(bloquee))}</div>" if bloquee else ""
            morceaux.append(f"<tr><td>{e(t['id'])}</td><td>{e(t.get('type', ''))}</td><td>{e(t.get('taille', ''))}</td>"
                            f"<td class='n'>{float(t.get('portee', 0)):.1f}</td><td title='{e(str(t.get('contexte', ''))[:300])}'>{e(t.get('titre', ''))}{note}</td></tr>")
        morceaux.append("</table></div>")
    else:
        morceaux.append("<p class='vide'>Aucune tâche ouverte.</p>")

    morceaux.append("<h2>Tâches en cours</h2>")
    en_cours = [t for t in taches if t.get("statut") in ("reservee", "en_relecture")]
    if en_cours:
        morceaux.append("<div class='tableau'><table><tr><th>Tâche</th><th>Statut</th><th>Par</th><th>Titre</th></tr>")
        for t in sorted(en_cours, key=lambda t: t["id"]):
            qui = (t.get("reservation") or {}).get("utilisateur")
            if not qui and t.get("contribution") in reg.enregistrements:
                qui = reg.enregistrements[t["contribution"]][1].get("auteur")
            morceaux.append(f"<tr><td>{e(t['id'])}</td><td>{e(t['statut'].replace('_', ' '))}</td><td>{e(qui or '')}</td><td>{e(t.get('titre', ''))}</td></tr>")
        morceaux.append("</table></div>")
    else:
        morceaux.append("<p class='vide'>Aucune tâche en cours.</p>")

    morceaux.append("<h2>Contributions classées</h2>")
    lignes = []
    for _, enr in reg.enregistrements.values():
        if not isinstance(enr, dict):
            continue
        score = calculer_score(reg, enr, niveaux)
        votes = sum(1 for _, v in reg.votes if v.get("sujet") == enr.get("id"))
        lignes.append((score["S"] if score else -1, enr, score, votes))
    if lignes:
        morceaux.append("<div class='tableau'><table><tr><th class='n'>Score</th><th>Contribution</th><th>Auteur</th><th class='n'>Gain</th><th class='n'>Lignes</th><th class='n'>Relectures</th><th class='n'>Votes</th><th>Statut</th></tr>")
        for _, enr, score, votes in sorted(lignes, key=lambda x: -x[0]):
            s = f"{score['S']:.4f}" if score else "—"
            gain = f"{100 * score['G']:+.1f} %" if score else "—"
            lignes_mod = str(score["L"]) if score else "—"
            morceaux.append(f"<tr><td class='n'>{s}</td><td>{e(enr['id'])}<div class='etiquette'>{e(enr.get('resume', ''))}</div></td><td>{e(enr.get('auteur', ''))}</td>"
                            f"<td class='n'>{gain}</td><td class='n'>{lignes_mod}</td><td class='n'>{len(enr.get('relectures') or [])}</td><td class='n'>{votes}</td><td>{e(enr.get('statut', '').replace('_', ' '))}</td></tr>")
        morceaux.append("</table></div>")
    else:
        morceaux.append("<p class='vide'>Aucune contribution pour l'instant.</p>")

    morceaux.append("<h2>Membres</h2>")
    if reg.membres:
        morceaux.append("<div class='tableau'><table><tr><th>Membre</th><th>Niveau</th><th class='n'>Intégrées</th><th class='n'>Relectures</th></tr>")
        for pseudo in sorted(reg.membres, key=lambda p: (-niveaux[p]["integrees"], p)):
            n = niveaux[pseudo]
            morceaux.append(f"<tr><td>{e(pseudo)}</td><td>{e(n['niveau'])}</td><td class='n'>{n['integrees']}</td><td class='n'>{n['relectures']}</td></tr>")
        morceaux.append("</table></div>")
    else:
        morceaux.append("<p class='vide'>Aucun membre inscrit pour l'instant.</p>")

    morceaux.append(f"<footer>Règles du jeu : {lien_doc('COMMANDEMENTS.md')} · {lien_doc('REGLES.md')} · Participer : {lien_doc('AGENTS.md')}</footer>")
    morceaux.append("</main></body></html>")
    sortie = pathlib.Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "index.html").write_text("\n".join(morceaux), encoding="utf-8")
    return sortie / "index.html"


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
    print(f"✓ {reg.rel(chemin)} créé. Ouvrez une pull request « Inscription {args.pseudo} » sur le registre.")
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
    print(f"  Ouvrez une pull request « Réservation {args.tache} » sur le registre ; elle est fusionnée automatiquement si elle est valide.")
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
        pathlib.Path(args.sortie).write_text(texte, encoding="utf-8")
        print(f"✓ {args.sortie} écrit. Remplacez chaque « {A_REMPLIR} », puis : bee valider-contribution {args.sortie}")
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
    print(f"  Ouvrez une pull request « Soumission {identifiant} » sur le registre.")
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
    if args.defaut:
        relecture["defaut_signale"] = True
    enr = dict(enr)
    enr["relectures"] = list(enr.get("relectures") or []) + [relecture]
    ecrire_yaml(chemin, enr)
    print(f"✓ relecture {args.avis} ajoutée à {args.contribution}. Ouvrez une pull request « Relecture {args.contribution} ».")
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
    print(f"✓ vote {args.valeur:+d} enregistré ({reg.rel(chemin)}). Ouvrez une pull request « Vote {args.sujet} ».")
    return 0


def cmd_proposer(args):
    reg = Registre(args.registre)
    reg.exiger_membre(args.utilisateur)
    niveau = niveau_de(calculer_niveaux(reg), args.utilisateur)
    if niveau != "Confirmé" and args.utilisateur not in reg.conseil:
        raise ErreurBee(f"proposer une règle est réservé aux Confirmés (niveau actuel : {niveau})")
    numeros = [int(p[2:]) for p in reg.propositions if ID_PROPOSITION.match(p)]
    identifiant = f"P-{(max(numeros) + 1 if numeros else 1):04d}"
    donnees = {"id": identifiant, "auteur": args.utilisateur, "regle": args.regle, "texte_propose": args.texte,
               "motif": args.motif, "ouverte_le": en_iso(maintenant()), "statut": "ouverte"}
    ecrire_yaml(reg.racine / "propositions" / f"{identifiant}.yaml", donnees)
    print(f"✓ proposition {identifiant} créée. Ouvrez une pull request « Proposition {identifiant} » ; le vote dure {reg.config.get('duree_vote_jours', 7)} jours.")
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
    lignes = args.lignes if args.lignes is not None else brut.get("lignes_modifiees")
    if lignes is None:
        raise ErreurBee("nombre de lignes modifiées inconnu : passez --lignes ou fournissez lignes_modifiees dans le verdict")
    verdict["lignes_modifiees"] = int(lignes)
    if args.manifeste:
        declare = gain_declare(reg, lire_yaml(args.manifeste), reg.tache(enr["tache"])[1])
        verdict["ecart_declare"] = round(abs(declare - verdict["gain"]), 4) if declare is not None and verdict["gain"] is not None else None
    if args.sha:
        verdict["sha"] = args.sha
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


def cmd_en_attente(args):
    reg = Registre(args.registre)
    resultat = [{"id": cid, "pr": enr.get("pr"), "sha_verdict": (enr.get("verdict") or {}).get("sha")}
                for cid, (_, enr) in sorted(reg.enregistrements.items()) if enr.get("statut") == "en_relecture"]
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
    return 0


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
    p.add_argument("--statut", default="ouverte", choices=["ouverte", "reservee", "en_relecture", "integree", "refusee", "abandonnee", "toutes"])
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

    p = ajouter("liberer", cmd_liberer, "Rend une tâche réservée ; --note transmet ce que vous avez appris.")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--note")

    ajouter("liberer-expirees", cmd_liberer_expirees, "Libère les réservations de plus de 72 h (lancé par la CI).")

    p = ajouter("manifeste", cmd_manifeste, "Génère le CONTRIBUTION.yaml à remplir pour une tâche.")
    p.add_argument("tache")
    p.add_argument("--utilisateur", required=True)
    p.add_argument("--modele", help="nom et version du modèle de l'agent")
    p.add_argument("--sortie", help="fichier à écrire (défaut : sortie standard)")

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
