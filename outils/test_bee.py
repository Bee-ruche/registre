"""Tests de l'outil bee : python3 -m unittest outils/test_bee.py"""
import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bee  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parent.parent

TACHE_OPTIMISATION = """id: miniz-0099
projet: miniz
categorie: compression-sans-perte
type: optimisation
taille: S
titre: "Tâche d'essai pour les tests de l'outil"
contexte: >
  Tâche fictive utilisée uniquement par les tests automatiques de l'outil bee,
  sur deux lignes repliées pour vérifier que la mise en forme est préservée.
fichiers: [miniz_tdef.c]
portee: 1.0
metrique: debit_compression_n6
sortie_compressee: identique
critere_acceptation:
  - "CI verte (R2)"
hors_perimetre: [format de sortie]
statut: ouverte
cree_par: tests
cree_le: "2026-10-27"
"""


def lancer(*arguments):
    sortie, erreur = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
        code = bee.principal(list(arguments))
    return code, sortie.getvalue() + erreur.getvalue()


def git(depot, *arguments):
    return subprocess.run(["git", "-C", str(depot), *arguments], check=True, capture_output=True, text=True).stdout


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = pathlib.Path(self.temp.name) / "registre"
        shutil.copytree(RACINE, self.dossier, ignore=shutil.ignore_patterns(".git", "_site", "__pycache__"))
        (self.dossier / "taches" / "miniz" / "miniz-0099.yaml").write_text(TACHE_OPTIMISATION, encoding="utf-8")
        self.ancien_maintenant = os.environ.get("BEE_MAINTENANT")
        os.environ["BEE_MAINTENANT"] = "2026-10-27T12:00:00Z"
        for pseudo in ("alice", "bruno", "chloe"):
            code, texte = self.bee("inscrire", "--pseudo", pseudo, "--compte-cree-le", "2020-01-01")
            self.assertEqual(code, 0, texte)

    def tearDown(self):
        if self.ancien_maintenant is None:
            os.environ.pop("BEE_MAINTENANT", None)
        else:
            os.environ["BEE_MAINTENANT"] = self.ancien_maintenant
        self.temp.cleanup()

    def bee(self, *arguments):
        return lancer("--registre", str(self.dossier), *arguments)

    def valide(self):
        code, texte = self.bee("valider")
        self.assertEqual(code, 0, texte)

    def tache(self, identifiant):
        projet = identifiant.rsplit("-", 1)[0]
        return bee.lire_yaml(self.dossier / "taches" / projet / f"{identifiant}.yaml")

    def soumettre_0099(self, auteur="alice"):
        self.assertEqual(self.bee("prendre", "miniz-0099", "--utilisateur", auteur)[0], 0)
        code, texte = self.bee("soumettre", "miniz-0099", "--utilisateur", auteur,
                               "--pr", "https://github.com/Bee-ruche/minizBee/pull/7", "--resume", "Essai.")
        self.assertEqual(code, 0, texte)
        return "miniz-0099-c1"


class TestRegistre(BaseTest):
    def test_le_registre_livre_est_valide(self):
        code, texte = lancer("--registre", str(RACINE), "valider")
        self.assertEqual(code, 0, texte)

    def test_inscription_compte_trop_recent(self):
        code, texte = self.bee("inscrire", "--pseudo", "jeune", "--compte-cree-le", "2026-10-01")
        self.assertEqual(code, 1)
        self.assertIn("90 jours", texte)

    def test_reserver_puis_liberer_avec_note(self):
        avant = (self.dossier / "taches/miniz/miniz-0099.yaml").read_text(encoding="utf-8")
        self.assertEqual(self.bee("prendre", "miniz-0099", "--utilisateur", "alice")[0], 0)
        t = self.tache("miniz-0099")
        self.assertEqual(t["statut"], "reservee")
        self.assertEqual(t["reservation"], {"utilisateur": "alice", "depuis": "2026-10-27T12:00:00Z"})
        self.valide()
        code, texte = self.bee("prendre", "miniz-0099", "--utilisateur", "bruno")
        self.assertEqual(code, 1)
        code, texte = self.bee("liberer", "miniz-0099", "--utilisateur", "bruno")
        self.assertEqual(code, 1, "seul le titulaire libère")
        self.assertEqual(self.bee("liberer", "miniz-0099", "--utilisateur", "alice", "--note", "Essayé X : dans le bruit.")[0], 0)
        t = self.tache("miniz-0099")
        self.assertEqual(t["statut"], "ouverte")
        self.assertNotIn("reservation", t)
        self.assertEqual(t["notes"][0]["texte"], "Essayé X : dans le bruit.")
        apres = (self.dossier / "taches/miniz/miniz-0099.yaml").read_text(encoding="utf-8")
        self.assertIn("contexte: >\n  Tâche fictive", apres, "la mise en forme écrite à la main est préservée")
        self.assertTrue(apres.startswith(avant.split("statut:")[0]))
        self.valide()

    def test_dependance_non_integree_bloque(self):
        code, texte = self.bee("prendre", "miniz-0002", "--utilisateur", "alice")
        self.assertEqual(code, 1)
        self.assertIn("miniz-0001", texte)

    def test_limite_r8(self):
        for i in range(4):
            (self.dossier / f"taches/miniz/miniz-009{i}.yaml").write_text(
                TACHE_OPTIMISATION.replace("miniz-0099", f"miniz-009{i}"), encoding="utf-8")
        for i in range(3):
            self.assertEqual(self.bee("prendre", f"miniz-009{i}", "--utilisateur", "alice")[0], 0)
        code, texte = self.bee("prendre", "miniz-0093", "--utilisateur", "alice")
        self.assertEqual(code, 1)
        self.assertIn("R8", texte)

    def test_expiration_r7(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        os.environ["BEE_MAINTENANT"] = "2026-10-30T11:00:00Z"
        self.bee("liberer-expirees")
        self.assertEqual(self.tache("miniz-0099")["statut"], "reservee", "71 h : pas encore expirée")
        os.environ["BEE_MAINTENANT"] = "2026-10-30T13:00:00Z"
        self.bee("liberer-expirees")
        t = self.tache("miniz-0099")
        self.assertEqual(t["statut"], "ouverte")
        self.assertIn("R7", t["notes"][-1]["texte"])
        self.valide()

    def test_manifeste_a_remplir_puis_valide(self):
        chemin = self.dossier / "CONTRIBUTION.yaml"
        self.assertEqual(self.bee("manifeste", "miniz-0099", "--utilisateur", "alice", "--sortie", str(chemin))[0], 0)
        code, texte = self.bee("valider-contribution", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("À REMPLIR", texte)
        chemin.write_text(MANIFESTE_REMPLI, encoding="utf-8")
        code, texte = self.bee("valider-contribution", str(chemin))
        self.assertEqual(code, 0, texte)

    def test_manifeste_sans_mesure_refuse(self):
        chemin = self.dossier / "CONTRIBUTION.yaml"
        chemin.write_text(MANIFESTE_REMPLI.split("mesures:")[0] + "teste: [tests]\nnon_teste: []\ndoutes: Aucun.\ntaille_reelle: S\n", encoding="utf-8")
        code, texte = self.bee("valider-contribution", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("commandement 2", texte)

    def test_soumission_relecture_vote_verdict_score(self):
        cid = self.soumettre_0099()
        t = self.tache("miniz-0099")
        self.assertEqual(t["statut"], "en_relecture")
        self.assertEqual(t["contribution"], cid)
        self.valide()
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "alice", "--avis", "favorable", "--motif", "Ma propre contribution.")[0], 1)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bruno", "--avis", "favorable", "--motif", "Diff relu en entier.")[0], 0)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bruno", "--avis", "favorable", "--motif", "Encore une fois.")[0], 1)
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "alice", "--valeur", "1")[0], 1)
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "chloe", "--valeur", "1")[0], 0)
        self.valide()
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.03, "au_dela_du_bruit": True, "lignes_modifiees": 10}), encoding="utf-8")
        manifeste = self.dossier / "CONTRIBUTION.yaml"
        manifeste.write_text(MANIFESTE_REMPLI, encoding="utf-8")
        code, texte = self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--manifeste", str(manifeste), "--sha", "abc1234")
        self.assertEqual(code, 0, texte)
        self.assertIn("écart", texte, "gain déclaré 10 % contre 3 % mesuré : alerte")
        enr = bee.lire_yaml(self.dossier / f"contributions/miniz/{cid}.yaml")
        self.assertEqual(enr["verdict"]["ecart_declare"], 0.07)
        self.valide()
        reg = bee.Registre(self.dossier)
        score = bee.calculer_score(reg, enr, bee.calculer_niveaux(reg))
        # G 0,03 × P 1 × C 1/3 / (1 + 10/100) × V 1 (chloé est Nouvelle : poids 0)
        self.assertAlmostEqual(score["S"], 0.03 / 3 / 1.1)
        self.assertEqual(score["V"], 1.0)

    def test_score_de_la_charte(self):
        reg = bee.Registre(self.dossier)
        enr = {"id": "x-0001-c1", "tache": "miniz-0099", "verdict": {"ci": "verte", "gain": 0.03, "lignes_modifiees": 10},
               "relectures": [{"relecteur": r, "avis": "favorable"} for r in ("a", "b", "c")]}
        self.assertAlmostEqual(bee.calculer_score(reg, enr, {})["S"], 0.0272727, places=6)
        enr["verdict"] = {"ci": "verte", "gain": 0.05, "lignes_modifiees": 300}
        self.assertAlmostEqual(bee.calculer_score(reg, enr, {})["S"], 0.0125)

    def test_niveaux(self):
        cid = self.soumettre_0099()
        chemin = self.dossier / f"contributions/miniz/{cid}.yaml"
        enr = bee.lire_yaml(chemin)
        enr["statut"] = "integree"
        enr["relectures"] = [{"relecteur": "bruno", "avis": "favorable", "motif": "Relu en entier.", "le": "2026-10-27T12:00:00Z"}]
        bee.ecrire_yaml(chemin, enr)
        niveaux = bee.calculer_niveaux(bee.Registre(self.dossier))
        self.assertEqual(niveaux["alice"]["niveau"], "Contributeur")
        self.assertEqual(niveaux["bruno"]["relectures"], 1)
        enr["statut"] = "annulee"
        bee.ecrire_yaml(chemin, enr)
        niveaux = bee.calculer_niveaux(bee.Registre(self.dossier))
        self.assertEqual(niveaux["alice"]["niveau"], "Nouveau")
        self.assertEqual(niveaux["bruno"]["relectures"], -1)

    def test_vote_pour_sa_contribution_detecte_par_valider(self):
        cid = self.soumettre_0099()
        bee.ecrire_yaml(self.dossier / f"votes/{cid}/alice.yaml",
                        {"votant": "alice", "sujet": cid, "valeur": 1, "le": "2026-10-27T12:00:00Z"})
        code, texte = self.bee("valider")
        self.assertEqual(code, 1)
        self.assertIn("commandement 3", texte)

    def test_pr_hors_fork_refusee(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        code, texte = self.bee("soumettre", "miniz-0099", "--utilisateur", "alice", "--pr", "https://github.com/autre/depot/pull/1")
        self.assertEqual(code, 1)
        self.assertIn("fork du projet", texte)
        # et si quelqu'un écrit l'enregistrement à la main, valider le refuse aussi
        bee.ecrire_yaml(self.dossier / "contributions/miniz/miniz-0099-c1.yaml",
                        {"id": "miniz-0099-c1", "tache": "miniz-0099", "auteur": "alice", "pr": "https://github.com/autre/depot/pull/1",
                         "statut": "en_relecture", "soumise_le": "2026-10-27T12:00:00Z", "relectures": []})
        code, texte = self.bee("valider")
        self.assertEqual(code, 1)
        self.assertIn("fork du projet", texte)

    def test_mesures_a_zero_refusees(self):
        chemin = self.dossier / "CONTRIBUTION.yaml"
        chemin.write_text(MANIFESTE_REMPLI.replace("debit_compression_n6: 55.0", "debit_compression_n6: 0"), encoding="utf-8")
        code, texte = self.bee("valider-contribution", str(chemin))
        self.assertEqual(code, 1)
        self.assertIn("vaut 0", texte)

    def test_messages_en_francais(self):
        bee.ecrire_yaml(self.dossier / "membres/zoe.yaml", {"pseudo": "zoe", "inscrit_le": "2026-10-27"})
        code, texte = self.bee("valider")
        self.assertEqual(code, 1)
        self.assertIn("champ obligatoire manquant : compte_cree_le", texte)

    def test_lister_signale_les_taches_masquees(self):
        code, texte = self.bee("lister", "--type", "relecture", "--disponibles")
        self.assertEqual(code, 0)
        self.assertIn("masquée", texte)
        self.assertIn("miniz-0001", texte)
        self.assertIn("arrêtez-vous", texte)

    def test_attente_de_fusion_expliquee(self):
        code, texte = self.bee("prendre", "miniz-0099", "--utilisateur", "inconnu")
        self.assertEqual(code, 1)
        self.assertIn("attendez sa fusion", texte)

    def test_site(self):
        self.soumettre_0099()
        code, texte = self.bee("site", "--sortie", str(self.dossier / "_site"))
        self.assertEqual(code, 0, texte)
        page = (self.dossier / "_site/index.html").read_text(encoding="utf-8")
        self.assertIn("miniz-0001", page)
        self.assertIn("miniz-0099-c1", page)
        self.assertIn("Compression sans perte", page)

    def test_proposition_et_depouillement(self):
        # bidji29 (conseil) peut proposer pendant l'amorçage
        bee.ecrire_yaml(self.dossier / "membres/bidji29.yaml", {"pseudo": "bidji29", "inscrit_le": "2026-10-27", "compte_cree_le": "2015-01-01"})
        code, texte = self.bee("proposer", "--utilisateur", "bidji29", "--regle", "R4", "--texte", "Au moins 1,5 % sur la métrique visée.", "--motif", "Le bruit mesuré est plus faible que prévu.")
        self.assertEqual(code, 0, texte)
        self.assertEqual(self.bee("proposer", "--utilisateur", "alice", "--regle", "R4", "--texte", "Autre texte assez long.", "--motif", "Alice n'est pas Confirmée.")[0], 1)
        self.assertEqual(self.bee("voter", "P-0001", "--utilisateur", "alice", "--valeur", "1")[0], 0)
        self.valide()
        os.environ["BEE_MAINTENANT"] = "2026-11-04T12:00:01Z"
        code, texte = self.bee("depouiller", "P-0001")
        resultat = json.loads(texte)
        self.assertTrue(resultat["terminee"])
        self.assertEqual(resultat["resultat"], "rejetee", "pas de quorum")
        self.assertEqual(self.bee("voter", "P-0001", "--utilisateur", "bruno", "--valeur", "1")[0], 1, "vote clos")


class TestPullRequests(BaseTest):
    def setUp(self):
        super().setUp()
        git(self.dossier, "init", "-q", "-b", "main")
        git(self.dossier, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(self.dossier, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")

    def commit(self, message="pr"):
        git(self.dossier, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(self.dossier, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)

    def verifier(self, auteur, *options):
        return self.bee("verifier-pr", "--base", "main", "--tete", "HEAD", "--auteur", auteur, *options)

    def test_reservation_libre_service(self):
        git(self.dossier, "switch", "-qc", "reservation")
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        self.commit()
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 0, texte)
        self.assertIn("FUSION_AUTO=oui", texte)
        code, texte = self.verifier("bruno")
        self.assertEqual(code, 1, "bruno ne peut pas réserver au nom d'alice")

    def test_modifier_une_tache_reserve_au_conseil(self):
        git(self.dossier, "switch", "-qc", "modif")
        chemin = self.dossier / "taches/miniz/miniz-0099.yaml"
        chemin.write_text(chemin.read_text(encoding="utf-8").replace("portee: 1.0", "portee: 0.5"), encoding="utf-8")
        self.commit()
        self.assertEqual(self.verifier("alice")[0], 1)
        code, texte = self.verifier("bidji29", "--fusion-auto")
        self.assertEqual(code, 3, texte)
        self.assertIn("relecture humaine", texte)

    def test_commandements_reserves_au_conseil(self):
        git(self.dossier, "switch", "-qc", "c")
        (self.dossier / "COMMANDEMENTS.md").write_text("Plus de règles.\n", encoding="utf-8")
        self.commit()
        code, texte = self.verifier("alice")
        self.assertEqual(code, 1)
        self.assertIn("30 jours", texte)

    def test_inscription_et_date_github(self):
        git(self.dossier, "switch", "-qc", "i")
        self.bee("inscrire", "--pseudo", "david", "--compte-cree-le", "2021-05-05")
        self.commit()
        self.assertEqual(self.verifier("david", "--compte-cree-le", "2021-05-05")[0], 0)
        self.assertEqual(self.verifier("david", "--compte-cree-le", "2026-10-20")[0], 1, "date déclarée ≠ date GitHub")
        self.assertEqual(self.verifier("eve")[0], 1, "on ne s'inscrit qu'en son nom")

    def test_relecture_et_note_falsifiees(self):
        cid = self.soumettre_0099()
        self.commit("soumission")
        git(self.dossier, "switch", "-qc", "relecture")
        chemin = self.dossier / f"contributions/miniz/{cid}.yaml"
        enr = bee.lire_yaml(chemin)
        enr["relectures"] = [{"relecteur": "chloe", "avis": "favorable", "motif": "Relecture au nom d'une autre.", "le": "2026-10-27T12:00:00Z"}]
        bee.ecrire_yaml(chemin, enr)
        self.commit()
        self.assertEqual(self.verifier("bruno")[0], 1)
        code, texte = self.verifier("chloe", "--fusion-auto")
        self.assertEqual(code, 0, texte)


class TestPublier(BaseTest):
    """bee publier avec de vrais dépôts git locaux et un faux gh qui journalise ses appels."""

    def setUp(self):
        super().setUp()
        racine = pathlib.Path(self.temp.name)
        git(self.dossier, "init", "-q", "-b", "main")
        git(self.dossier, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(self.dossier, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        git(self.dossier, "config", "user.name", "t")
        git(self.dossier, "config", "user.email", "t@t")
        subprocess.run(["git", "clone", "-q", "--bare", str(self.dossier), str(racine / "distant.git")], check=True)
        git(self.dossier, "remote", "add", "origin", str(racine / "distant.git"))
        git(self.dossier, "fetch", "-q", "origin")
        self.journal = racine / "gh.journal"
        self.etat = racine / "gh.etat"
        self.etat.write_text('{"state": "MERGED"}', encoding="utf-8")
        binaire = racine / "bin"
        binaire.mkdir()
        (binaire / "gh").write_text(
            "#!/bin/sh\n"
            f"echo \"$@\" >> '{self.journal}'\n"
            "case \"$1 $2\" in\n"
            "  'pr create') echo 'https://github.com/Bee-ruche/registre/pull/42' ;;\n"
            f"  'pr view') cat '{self.etat}' ;;\n"
            "esac\n", encoding="utf-8")
        (binaire / "gh").chmod(0o755)
        self.ancien_path = os.environ["PATH"]
        os.environ["PATH"] = f"{binaire}{os.pathsep}{self.ancien_path}"

    def tearDown(self):
        os.environ["PATH"] = self.ancien_path
        super().tearDown()

    def test_reservation_publiee_et_fusionnee(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--intervalle", "0")
        self.assertEqual(code, 0, texte)
        self.assertIn("fusionnée", texte)
        appels = self.journal.read_text(encoding="utf-8")
        self.assertIn("pr create --repo Bee-ruche/registre --head bee/reservation-miniz-0099 --base main --title Réservation miniz-0099", appels)
        self.assertEqual(git(self.dossier, "rev-parse", "--abbrev-ref", "HEAD").strip(), "main")
        self.assertIn("bee/reservation-miniz-0099", git(self.dossier, "ls-remote", "--heads", "origin"))
        fichiers = git(self.dossier, "show", "--name-only", "--format=", "bee/reservation-miniz-0099").split()
        self.assertEqual(fichiers, ["taches/miniz/miniz-0099.yaml"], "seul le fichier de la tâche est publié")

    def test_fichier_hors_libre_service_refuse(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        (self.dossier / "CONTRIBUTION.yaml.bak").write_text("égaré\n", encoding="utf-8")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--intervalle", "0")
        self.assertEqual(code, 1)
        self.assertIn("CONTRIBUTION.yaml.bak", texte)
        self.assertFalse(self.journal.exists(), "aucune PR ne doit être ouverte")

    def test_pr_fermee_ou_en_attente(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        self.etat.write_text('{"state": "CLOSED"}', encoding="utf-8")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--intervalle", "0")
        self.assertEqual(code, 1)
        self.assertIn("refusée", texte)
        self.bee("liberer", "miniz-0099", "--utilisateur", "alice")
        self.bee("prendre", "miniz-0099", "--utilisateur", "bruno")
        self.etat.write_text('{"state": "OPEN"}', encoding="utf-8")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--delai", "0", "--intervalle", "0")
        self.assertEqual(code, 2)
        self.assertIn("relecture humaine", texte)
        self.assertIn("bee/reservation-miniz-0099-2", git(self.dossier, "branch"), "un second titre identique reçoit un suffixe")

    def test_rien_a_publier(self):
        code, texte = self.bee("publier", "--titre", "Rien")
        self.assertEqual(code, 1)
        self.assertIn("aucun changement", texte)


class TestFork(BaseTest):
    def setUp(self):
        super().setUp()
        self.fork = pathlib.Path(self.temp.name) / "fork"
        (self.fork / "bee/tests").mkdir(parents=True)
        (self.fork / "miniz_tdef.c").write_text("".join(f"ligne {i}\n" for i in range(100)), encoding="utf-8")
        (self.fork / "bee/tests/juge.sh").write_text("exit 0\n", encoding="utf-8")
        git(self.fork, "init", "-q", "-b", "master")
        self.commit("base")
        git(self.fork, "switch", "-qc", "tache/miniz-0099")

    def commit(self, message="travail"):
        git(self.fork, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(self.fork, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)

    def verifier(self):
        return self.bee("verifier-fork", "--tache", "miniz-0099", "--base", "master", "--depot", str(self.fork))

    def test_branche_conforme(self):
        chemin = self.fork / "miniz_tdef.c"
        chemin.write_text(chemin.read_text().replace("ligne 5\n", "ligne cinq\n"), encoding="utf-8")
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 0, texte)
        self.assertIn("2 lignes", texte)

    def test_juge_modifie_et_taille_depassee(self):
        (self.fork / "bee/tests/juge.sh").write_text("exit 0 # toujours vert\n", encoding="utf-8")
        (self.fork / "miniz_tdef.c").write_text("".join(f"autre {i}\n" for i in range(100)), encoding="utf-8")
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("commandement 3", texte)
        self.assertIn("R1", texte)

    def test_manifeste_absent(self):
        (self.fork / "miniz_tdef.c").write_text("modifié\n", encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("CONTRIBUTION.yaml absent", texte)

    def test_travail_non_commite(self):
        (self.fork / "miniz_tdef.c").write_text("modifié\n", encoding="utf-8")
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        code, texte = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("non commité", texte)
        self.assertIn("existe sur le disque", texte)

    def test_fichier_hors_tache_et_base_inconnue(self):
        chemin = self.fork / "miniz_tdef.c"
        chemin.write_text(chemin.read_text().replace("ligne 5\n", "ligne cinq\n"), encoding="utf-8")
        (self.fork / "miniz_zip.c").write_text("hors périmètre\n", encoding="utf-8")
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 0, texte)
        self.assertIn("⚠ miniz_zip.c : hors des fichiers de la tâche", texte)
        code, texte = self.bee("verifier-fork", "--tache", "miniz-0099", "--base", "upstream/master", "--depot", str(self.fork))
        self.assertEqual(code, 1)
        self.assertIn("git fetch upstream", texte)


MANIFESTE_REMPLI = """tache: miniz-0099
utilisateur: alice
agent:
  modele: modèle d'essai 1.0
  client: bee 0.1.0
resume: Remplace une division par un décalage dans la boucle chaude.
changement: >
  La division par une puissance de deux est remplacée par un décalage, ce qui
  supprime une instruction lente dans la boucle principale.
mesures:
  machine: x86-64, Linux, gcc 13
  commande: python3 bee/bench/ab.py --base upstream/master --candidate HEAD
  repetitions: 10
  avant: {debit_compression_n6: 50.0, memoire_max_ko: 4000}
  apres: {debit_compression_n6: 55.0, memoire_max_ko: 4000}
teste: [tests différentiels, fuzzing 2 min]
non_teste: [ARM64]
doutes: Aucun doute identifié.
taille_reelle: S
"""


if __name__ == "__main__":
    unittest.main()
