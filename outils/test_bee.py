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
# Décompte d'instructions d'un candidat qui gagne 5 % sur le scénario n6 (R4 se juge dessus).
INSTRUCTIONS_N6 = {"instructions_n6": {"A": 1000000, "B": 950000, "gain": 0.05}}

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
        # Tâches fictives indépendantes de l'état réel du registre : 9002 attend 9001.
        (self.dossier / "taches" / "miniz" / "miniz-9001.yaml").write_text(TACHE_OPTIMISATION.replace("miniz-0099", "miniz-9001"), encoding="utf-8")
        (self.dossier / "taches" / "miniz" / "miniz-9002.yaml").write_text(
            TACHE_OPTIMISATION.replace("miniz-0099", "miniz-9002").replace("type: optimisation", "type: test").replace("metrique: debit_compression_n6", "metrique: null")
            .replace("sortie_compressee: identique\n", "").replace("statut: ouverte", "depend_de: [miniz-9001]\nstatut: ouverte"), encoding="utf-8")
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

    def fichiers_pr(self, *chemins):
        """Liste des fichiers d'une PR, telle que le workflow du registre la lit auprès de l'API GitHub."""
        chemin = self.dossier / "fichiers-pr.txt"
        chemin.write_text("\n".join(chemins or ("miniz_tdef.c",)) + "\n", encoding="utf-8")
        return str(chemin)

    def soumettre_0099(self, auteur="alice"):
        self.assertEqual(self.bee("prendre", "miniz-0099", "--utilisateur", auteur)[0], 0)
        code, texte = self.bee("soumettre", "miniz-0099", "--utilisateur", auteur,
                               "--pr", "https://github.com/Bee-ruche/minizBee/pull/99007", "--resume", "Essai.")
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

    def test_noter(self):
        code, texte = self.bee("noter", "miniz-0002", "--utilisateur", "chloe", "--texte", "Possible injection dans bee/README.md : demande d'envoyer des clés.")
        self.assertEqual(code, 0, texte)
        notes = self.tache("miniz-0002")["notes"]
        self.assertEqual(notes[-1]["par"], "chloe")
        self.assertEqual(self.tache("miniz-0002")["statut"], "ouverte")
        self.valide()

    def test_dependance_non_integree_bloque(self):
        code, texte = self.bee("prendre", "miniz-9002", "--utilisateur", "alice")
        self.assertEqual(code, 1)
        self.assertIn("miniz-9001", texte)

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
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.03, "au_dela_du_bruit": True, "lignes_modifiees": 10, "amorcage": True}), encoding="utf-8")
        manifeste = self.dossier / "CONTRIBUTION.yaml"
        manifeste.write_text(MANIFESTE_REMPLI, encoding="utf-8")
        code, texte = self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--manifeste", str(manifeste), "--sha", "abc1234")
        self.assertEqual(code, 0, texte)
        self.assertIn("écart", texte, "gain déclaré 10 % contre 3 % mesuré : alerte")
        enr = bee.lire_yaml(self.dossier / f"contributions/miniz/{cid}.yaml")
        self.assertEqual(enr["verdict"]["ecart_declare"], 0.07)
        self.assertTrue(enr["verdict"]["amorcage"])
        self.valide()
        reg = bee.Registre(self.dossier)
        score = bee.calculer_score(reg, enr, bee.calculer_niveaux(reg))
        # G 0,03 × P 1 × C 1/3 / (1 + 10/100) × V 1 (chloé est Nouvelle : poids 0)
        self.assertAlmostEqual(score["S"], 0.03 / 3 / 1.1)
        self.assertEqual(score["V"], 1.0)

    def regler_porte_humaine(self, active):
        chemin = self.dossier / "bee.yaml"
        texte = chemin.read_text(encoding="utf-8")
        self.assertIn("relecture_gardien_requise:", texte)
        chemin.write_text(texte.replace("relecture_gardien_requise: true", f"relecture_gardien_requise: {'true' if active else 'false'}"),
                          encoding="utf-8")

    def test_acceptation_automatique(self):
        cid = self.soumettre_0099()  # auteur alice
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.05, "au_dela_du_bruit": True, "instructions": INSTRUCTIONS_N6,
                                       "lignes_modifiees": 10}), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "abc1234", "--fichiers", self.fichiers_pr())[0], 0)
        # Fenêtre pas écoulée et pas assez de relectures : pas encore intégrable.
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("relecture", texte + " fenêtre")
        # Deux relectures favorables d'autres utilisateurs, et un vote net suffisant.
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bruno", "--avis", "favorable", "--motif", "Relu, le diff est net et sûr.")[0], 0)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "chloe", "--avis", "favorable", "--motif", "Relu aussi, rien à redire.")[0], 0)
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        # Toujours pas : la fenêtre d'ouverture n'est pas écoulée.
        self.assertEqual(self.bee("verifier-acceptation", cid)[0], 1)
        # On avance le temps au-delà de la fenêtre. La porte humaine temporaire bloque encore :
        # l'auteur n'est pas du conseil et aucun membre du conseil n'a relu.
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("porte de relecture", texte)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bidji29", "--avis", "favorable",
                                  "--motif", "Relu par le conseil, diff conforme.")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)
        self.assertIn("intégrable", texte)
        # integrer applique la décision mécanique : contribution et tâche passent en « integree ».
        code, texte = self.bee("integrer", cid, "--fusion-sha", "deadbee")
        self.assertEqual(code, 0, texte)
        _, enr = bee.Registre(self.dossier).enregistrement(cid)
        self.assertEqual(enr["statut"], "integree")
        self.assertEqual(enr.get("fusion_sha"), "deadbee")
        self.assertIn("decidee_le", enr)
        self.assertEqual(self.tache("miniz-0099")["statut"], "integree")
        self.valide()
        # Idempotence : une fois intégrée, elle n'est plus intégrable (statut ≠ en_relecture).
        self.assertEqual(self.bee("verifier-acceptation", cid)[0], 1)
        self.assertEqual(self.bee("integrer", cid)[0], 1)

    def preparer_contribution_verte(self, auteur, relecteurs):
        cid = self.soumettre_0099(auteur=auteur)
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.05, "au_dela_du_bruit": True, "instructions": INSTRUCTIONS_N6,
                                       "lignes_modifiees": 10}), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "abc1234", "--fichiers", self.fichiers_pr())[0], 0)
        for relecteur in relecteurs:
            self.assertEqual(self.bee("relire", cid, "--utilisateur", relecteur, "--avis", "favorable",
                                      "--motif", "Relu, rien à signaler ici.")[0], 0)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        return cid

    def test_porte_humaine_satisfaite_par_un_auteur_du_conseil(self):
        cid = self.preparer_contribution_verte("bidji29", ("bruno", "chloe"))
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    def test_porte_humaine_fermee(self):
        self.regler_porte_humaine(False)
        cid = self.preparer_contribution_verte("alice", ("bruno", "chloe"))
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)
        self.assertIn("Aucune relecture privilégiée requise", texte)

    # --- Tests adverses de R3 (revue du 27/10) ---

    def test_adverse_r3_defavorable_du_conseil_bloque(self):
        cid = self.preparer_contribution_verte("alice", ("bruno", "chloe"))
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bidji29", "--avis", "defavorable",
                                  "--motif", "Lecture hors limites possible ligne 120.")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("défavorable de bidji29", texte)

    def test_adverse_r3_defavorables_non_ignores(self):
        self.regler_porte_humaine(False)
        cid = self.preparer_contribution_verte("alice", ("bruno",))
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "chloe", "--avis", "defavorable",
                                  "--motif", "Le gain disparaît sur ARM64.")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("défavorable(s) contre", texte)

    def test_adverse_r3_r5_degradation(self):
        self.regler_porte_humaine(False)
        cid = self.soumettre_0099()
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.05, "au_dela_du_bruit": True, "instructions": INSTRUCTIONS_N6, "lignes_modifiees": 10,
                                       "degradations": {"ratio_n6": -0.40, "memoire_max_ko": -0.004}}), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "abc1234", "--fichiers", self.fichiers_pr())[0], 0)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("R5", texte)
        self.assertIn("ratio_n6", texte)
        self.assertNotIn("memoire_max_ko", texte, "une dégradation sous la tolérance de 1 % ne bloque pas")

    def test_adverse_r3_relectures_d_un_ancien_commit(self):
        cid = self.preparer_contribution_verte("alice", ("bruno", "chloe", "bidji29"))
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        self.assertEqual(self.bee("verifier-acceptation", cid)[0], 0)
        # L'auteur pousse un nouveau commit : le nouveau verdict porte sur def5678, les relectures sur abc1234.
        verdict = self.dossier / "verdict.json"
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "def5678", "--fichiers", self.fichiers_pr())[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("commit antérieur", texte)

    def enregistrer_verdict_vert(self, cid, *fichiers, controle=True):
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.05, "au_dela_du_bruit": True, "instructions": INSTRUCTIONS_N6,
                                       "lignes_modifiees": 10}), encoding="utf-8")
        options = ["--fichiers", self.fichiers_pr(*fichiers)] if controle else []
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "abc1234", *options)[0], 0)

    def test_adverse_r3_verdict_non_controle(self):
        self.regler_porte_humaine(False)
        cid = self.soumettre_0099()
        self.enregistrer_verdict_vert(cid, controle=False)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("verdict non contrôlé", texte)

    def test_adverse_r3_optimisation_qui_modifie_son_workflow(self):
        cid = self.soumettre_0099()
        self.enregistrer_verdict_vert(cid, "miniz_tdef.c", ".github/workflows/bee-ci.yml")
        _, enr = bee.Registre(self.dossier).enregistrement(cid)
        self.assertEqual(enr["verdict"]["juges_modifies"], [".github/workflows/bee-ci.yml"])
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("modifie des juges", texte)
        self.assertIn("commandement 3", texte)

    def test_tache_d_outillage_qui_modifie_les_juges_exige_le_conseil(self):
        self.regler_porte_humaine(False)
        (self.dossier / "taches/miniz/miniz-9003.yaml").write_text(
            TACHE_OPTIMISATION.replace("miniz-0099", "miniz-9003").replace("type: optimisation", "type: test")
            .replace("metrique: debit_compression_n6", "metrique: null"), encoding="utf-8")
        self.assertEqual(self.bee("prendre", "miniz-9003", "--utilisateur", "alice")[0], 0)
        self.assertEqual(self.bee("soumettre", "miniz-9003", "--utilisateur", "alice",
                                  "--pr", "https://github.com/Bee-ruche/minizBee/pull/99008")[0], 0)
        cid = "miniz-9003-c1"
        self.enregistrer_verdict_vert(cid, "bee/tests/nouveau_test.c")
        for relecteur in ("bruno", "chloe"):
            self.assertEqual(self.bee("relire", cid, "--utilisateur", relecteur, "--avis", "favorable",
                                      "--motif", "Relu, le test est pertinent.")[0], 0)
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("conseil ou d'un Confirmé", texte)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bidji29", "--avis", "favorable",
                                  "--motif", "Juge renforcé, relu par le conseil.")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    def test_outillage_du_conseil_non_bloque(self):
        self.regler_porte_humaine(False)
        cid = self.soumettre_0099(auteur="bidji29")
        # la tâche 0099 est une optimisation : on la convertit en tâche d'outillage pour ce cas
        chemin = self.dossier / "taches/miniz/miniz-0099.yaml"
        chemin.write_text(chemin.read_text(encoding="utf-8").replace("type: optimisation", "type: test"), encoding="utf-8")
        self.enregistrer_verdict_vert(cid, "bee/tests/nouveau_test.c")
        for relecteur in ("bruno", "chloe"):
            self.assertEqual(self.bee("relire", cid, "--utilisateur", relecteur, "--avis", "favorable",
                                      "--motif", "Relu, le test est pertinent.")[0], 0)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    # --- R4 et R5 fondées sur le décompte d'instructions (27/10) ---

    def verdict_r4(self, cid, gain, bruit, gain_instructions, degradations=None, sha="abc1234"):
        verdict = self.dossier / "verdict.json"
        brut = {"ci": "verte", "gain": gain, "au_dela_du_bruit": bruit, "lignes_modifiees": 10,
                "instructions": {"instructions_n6": {"A": 1000000, "B": 1000000 * (1 - gain_instructions), "gain": gain_instructions}}}
        if degradations:
            brut["degradations"] = degradations
        verdict.write_text(json.dumps(brut), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", sha,
                                  "--fichiers", self.fichiers_pr())[0], 0)

    def contribution_relue(self, *verdict):
        self.regler_porte_humaine(False)
        cid = self.soumettre_0099()
        self.verdict_r4(cid, *verdict)
        for relecteur in ("bruno", "chloe"):
            self.assertEqual(self.bee("relire", cid, "--utilisateur", relecteur, "--avis", "favorable",
                                      "--motif", "Relu, rien à signaler ici.")[0], 0)
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        return cid

    def test_r4_gain_etabli_par_les_instructions(self):
        cid = self.contribution_relue(0.012, True, 0.04)  # instructions -4 %, chronomètre +1,2 % au-delà du bruit
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    def test_adverse_r4_instructions_sans_confirmation_du_chronometre(self):
        # Revue adverse du 27/10 : un gain d'instructions fabriqué (travail déplacé) ne se voit pas au chronomètre.
        cid = self.contribution_relue(0.005, False, 0.04)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("ne le confirme pas", texte)
        rapport = self.dossier / "ab.json"
        rapport.write_text(json.dumps({"base": {"commit": "2948eeb"}, "candidat": {"commit": "abc1234"},
                                       "machine": {"architecture": "arm64", "compilateur": "clang 17"},
                                       "metriques": {"debit_compression_n6": {"gain": 0.011, "au_dela_du_bruit": True,
                                                     "test_du_signe": {"victoires_B": 10, "paires_utiles": 10}}}}), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-mesure", cid, "--ab", str(rapport), "--utilisateur", "bruno")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    def test_r4_chronometre_qui_recule_bloque(self):
        cid = self.contribution_relue(-0.05, True, 0.04)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("le chronomètre recule", texte)

    def test_r4_chronometre_seul_exige_une_reproduction(self):
        cid = self.contribution_relue(0.06, True, 0.0)  # +6 % au chronomètre, instructions inchangées
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("reproduit par une mesure", texte)
        rapport = self.dossier / "ab.json"
        rapport.write_text(json.dumps({"base": {"commit": "2948eeb"}, "candidat": {"commit": "abc1234"},
                                       "machine": {"architecture": "arm64", "compilateur": "clang 17"},
                                       "metriques": {"debit_compression_n6": {"gain": 0.05, "au_dela_du_bruit": True,
                                                     "test_du_signe": {"victoires_B": 10, "paires_utiles": 10}}}}), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-mesure", cid, "--ab", str(rapport), "--utilisateur", "bruno")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    def test_r5_chronometre_bruite_ignore_instructions_jugees(self):
        cid = self.contribution_relue(0.05, True, 0.05, {"debit_compression_n1": -0.05})
        self.assertEqual(self.bee("verifier-acceptation", cid)[0], 0, "un recul au chronomètre seul ne bloque pas")
        self.verdict_r4(cid, 0.05, True, 0.05, {"instructions_n1": -0.03})
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("R5", texte)
        self.assertIn("instructions_n1", texte)

    def test_gardien_ouvre_la_porte_de_relecture(self):
        (self.dossier / "gouvernance/gardiens.yaml").write_text("membres:\n  - pseudo: bruno\n", encoding="utf-8")
        cid = self.preparer_contribution_verte("alice", ("chloe",))
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("gardien", texte)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bruno", "--avis", "favorable",
                                  "--motif", "Relu par le gardien : diff et tests rejoués.")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    # --- Juge isolé des forks (miniz-0031) ---

    def contribution_jugee(self, suspects=(), sorties=914, auteur="alice"):
        cid = self.soumettre_0099(auteur=auteur)
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.05, "au_dela_du_bruit": True, "instructions": INSTRUCTIONS_N6,
                                       "lignes_modifiees": 10,
                                       "juge": {"version": 1, "graine": "ab" * 16, "sorties_comparees": sorties,
                                                "constructions_suspectes": list(suspects)}}), encoding="utf-8")
        self.assertEqual(self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "abc1234",
                                  "--fichiers", self.fichiers_pr())[0], 0)
        for relecteur in ("bruno", "chloe"):
            if relecteur != auteur:
                self.assertEqual(self.bee("relire", cid, "--utilisateur", relecteur, "--avis", "favorable",
                                          "--motif", "Relu, rien à signaler ici.")[0], 0)
        if auteur != "bidji29":
            self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        os.environ["BEE_MAINTENANT"] = "2026-10-29T12:00:00Z"
        return cid

    def regler_porte(self, valeur):
        chemin = self.dossier / "bee.yaml"
        texte = chemin.read_text(encoding="utf-8")
        chemin.write_text(texte.replace("relecture_gardien_requise: true", f"relecture_gardien_requise: {valeur}"), encoding="utf-8")

    def test_juge_isole_enregistre_et_borne(self):
        suspects = [{"type": "instruction", "detail": "syscall : 1 occurrence(s) contre 0 dans la base" + "x" * 500, "autre": 1}] * 60
        cid = self.contribution_jugee(suspects)
        _, enr = bee.Registre(self.dossier).enregistrement(cid)
        juge = enr["verdict"]["juge"]
        self.assertEqual(juge["sorties_comparees"], 914)
        self.assertEqual(len(juge["constructions_suspectes"]), 50)
        self.assertLessEqual(len(juge["constructions_suspectes"][0]["detail"]), 300)
        self.valide()

    def test_constructions_suspectes_exigent_un_gardien(self):
        self.regler_porte("false")
        cid = self.contribution_jugee([{"type": "instruction", "detail": "préambule_valgrind : 4 occurrence(s)"}])
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("construction(s) suspecte(s)", texte)
        self.assertEqual(self.bee("relire", cid, "--utilisateur", "bidji29", "--avis", "favorable",
                                  "--motif", "Relu : la détection SIMD est légitime, mesures rejouées.")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 0, texte)

    def test_constructions_suspectes_meme_pour_un_auteur_privilegie(self):
        cid = self.contribution_jugee([{"type": "appel_externe", "detail": "execve (miniz.o)"}], auteur="bidji29")
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("construction(s) suspecte(s)", texte)

    def test_porte_si_juge_incomplet(self):
        self.regler_porte("si_juge_incomplet")
        complet = self.contribution_jugee()
        code, texte = self.bee("verifier-acceptation", complet)
        self.assertEqual(code, 0, texte)  # juge isolé complet, rien de suspect : pas de gardien requis

    def test_porte_si_juge_incomplet_sans_juge(self):
        self.regler_porte("si_juge_incomplet")
        cid = self.preparer_contribution_verte("alice", ("bruno", "chloe"))  # verdict sans section juge
        self.assertEqual(self.bee("voter", cid, "--utilisateur", "bidji29", "--valeur", "1")[0], 0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("pas entièrement jugé", texte)

    def test_porte_si_juge_incomplet_juge_sans_sorties(self):
        self.regler_porte("si_juge_incomplet")
        cid = self.contribution_jugee(sorties=0)
        code, texte = self.bee("verifier-acceptation", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("pas entièrement jugé", texte)

    def test_adverse_verdict_incoherent_refuse(self):
        cid = self.soumettre_0099()
        verdict = self.dossier / "verdict.json"
        verdict.write_text(json.dumps({"ci": "verte", "gain": 0.05, "lignes_modifiees": -5}), encoding="utf-8")
        code, texte = self.bee("enregistrer-verdict", cid, "--verdict", str(verdict), "--sha", "abc1234")
        self.assertEqual(code, 1, texte)
        self.assertNotIn("verdict", bee.Registre(self.dossier).enregistrement(cid)[1])
        self.valide()

    def test_cloturer_rouvre_la_tache(self):
        cid = self.soumettre_0099()
        code, texte = self.bee("cloturer", cid, "--motif", "PR fermée sans fusion.")
        self.assertEqual(code, 0, texte)
        _, enr = bee.Registre(self.dossier).enregistrement(cid)
        self.assertEqual(enr["statut"], "annulee")
        tache = self.tache("miniz-0099")
        self.assertEqual(tache["statut"], "ouverte")
        self.assertNotIn("contribution", tache)
        self.assertNotIn("reservation", tache)
        self.assertIn(cid, tache["notes"][-1]["texte"])
        self.valide()
        self.assertEqual(self.bee("cloturer", cid, "--motif", "Encore.")[0], 1)

    def test_integrer_refuse_sans_acceptation(self):
        cid = self.soumettre_0099()  # pas de verdict, pas de relecture, fenêtre non écoulée
        code, texte = self.bee("integrer", cid)
        self.assertEqual(code, 1, texte)
        self.assertIn("pas intégrable", texte)
        # Rien n'a été écrit : la contribution reste en relecture.
        _, enr = bee.Registre(self.dossier).enregistrement(cid)
        self.assertEqual(enr["statut"], "en_relecture")

    def test_mesure_enregistree_et_valide(self):
        cid = self.soumettre_0099()
        rapport = self.dossier / "ab.json"
        rapport.write_text(json.dumps({
            "repetitions": 10,
            "base": {"commit": "2948eebafc5b"},
            "candidat": {"commit": "839b676aaaaa"},
            "machine": {"processeur": "Apple M3", "architecture": "arm64", "coeurs": 8,
                        "systeme": "Darwin", "compilateur": "clang 17"},
            "metriques": {
                "debit_compression_n6": {"gain": 0.051, "au_dela_du_bruit": True,
                                          "test_du_signe": {"victoires_B": 9, "paires_utiles": 10}},
                "ratio_n6": {"gain": 0.0, "au_dela_du_bruit": False},
            },
        }), encoding="utf-8")
        # Une mesure par un AUTRE participant que l'auteur : config indépendante.
        code, texte = self.bee("enregistrer-mesure", cid, "--ab", str(rapport), "--utilisateur", "bruno")
        self.assertEqual(code, 0, texte)
        fiche = bee.lire_yaml(self.dossier / "mesures" / cid / "bruno.yaml")
        self.assertEqual(fiche["config"]["architecture"], "arm64")
        self.assertEqual(fiche["metriques"]["debit_compression_n6"]["victoires_b"], 9)
        self.assertTrue(fiche["metriques"]["debit_compression_n6"]["au_dela_du_bruit"])
        self.valide()

    def test_mesure_contribution_inconnue_refusee(self):
        rapport = self.dossier / "ab.json"
        rapport.write_text(json.dumps({"base": {"commit": "aaaaaaa"}, "candidat": {"commit": "bbbbbbb"},
                                       "machine": {"architecture": "x86_64"},
                                       "metriques": {"debit_compression_n6": {"gain": 0.01, "au_dela_du_bruit": False}}}), encoding="utf-8")
        code, _ = self.bee("enregistrer-mesure", "miniz-9999-c1", "--ab", str(rapport), "--utilisateur", "alice")
        self.assertEqual(code, 1, "une mesure pour une contribution inexistante doit échouer")

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
        code, texte = self.bee("lister", "--type", "test", "--disponibles")
        self.assertEqual(code, 0)
        self.assertIn("masquée", texte)
        self.assertIn("miniz-9001", texte)

    def test_lister_rien_a_faire(self):
        shutil.rmtree(self.dossier / "contributions", ignore_errors=True)  # dossier absent quand il est vide (git ne suit pas les dossiers vides)
        code, texte = self.bee("lister", "--categorie", "decodage-images", "--disponibles")
        self.assertEqual(code, 0)
        self.assertIn("Aucune tâche", texte)
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
        # pendant l'amorçage, tout membre peut proposer (l'essaim débat) ; hors amorçage, Confirmés seulement
        self.assertEqual(self.bee("proposer", "--utilisateur", "alice", "--regle", "R4", "--texte", "Autre texte assez long.", "--motif", "Proposée par une Nouvelle.")[0], 0)
        chemin = self.dossier / "bee.yaml"
        chemin.write_text(chemin.read_text(encoding="utf-8").replace("amorcage: true", "amorcage: false"), encoding="utf-8")
        self.assertEqual(self.bee("proposer", "--utilisateur", "alice", "--regle", "R4", "--texte", "Encore un autre texte.", "--motif", "Alice n'est pas Confirmée.")[0], 1)
        chemin.write_text(chemin.read_text(encoding="utf-8").replace("amorcage: false", "amorcage: true"), encoding="utf-8")
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

    # --- Tests adverses (revue du 27/10) : chaque contournement connu doit être refusé. ---

    def test_adverse_soumission_sans_reservation(self):
        git(self.dossier, "switch", "-qc", "sans-reservation")
        bee.ecrire_yaml(self.dossier / "contributions/miniz/miniz-0099-c1.yaml", {
            "id": "miniz-0099-c1", "tache": "miniz-0099", "auteur": "alice",
            "pr": "https://github.com/Bee-ruche/minizBee/pull/99007", "statut": "en_relecture",
            "soumise_le": "2026-10-27T12:00:00Z", "relectures": []})
        self.commit()
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 1, texte)
        self.assertIn("bee soumettre le fait", texte)

    def reserver_sur_main(self, *taches):
        for t in taches:
            self.assertEqual(self.bee("prendre", t, "--utilisateur", "alice")[0], 0)
        self.commit("réservations")

    def test_adverse_soumission_antidatee(self):
        self.reserver_sur_main("miniz-0099")
        git(self.dossier, "switch", "-qc", "soumission")
        self.assertEqual(self.bee("soumettre", "miniz-0099", "--utilisateur", "alice",
                                  "--pr", "https://github.com/Bee-ruche/minizBee/pull/99007")[0], 0)
        self.commit()
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 0, f"le parcours légitime doit passer : {texte}")
        chemin = self.dossier / "contributions/miniz/miniz-0099-c1.yaml"
        enr = bee.lire_yaml(chemin)
        enr["soumise_le"] = "2020-01-01T00:00:00Z"  # pour faire croire la fenêtre de R3 écoulée
        bee.ecrire_yaml(chemin, enr)
        self.commit("antidatée")
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 1, texte)
        self.assertIn("soumise_le", texte)

    def test_adverse_pr_deja_liee(self):
        self.reserver_sur_main("miniz-0099", "miniz-9001")
        git(self.dossier, "switch", "-qc", "doublon")
        for t in ("miniz-0099", "miniz-9001"):
            self.assertEqual(self.bee("soumettre", t, "--utilisateur", "alice",
                                      "--pr", "https://github.com/Bee-ruche/minizBee/pull/99007")[0], 0)
        self.commit()
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 1, texte)
        self.assertIn("déjà liée", texte)

    def test_adverse_relecture_retroactive(self):
        cid = self.soumettre_0099()
        chemin = self.dossier / f"contributions/miniz/{cid}.yaml"
        enr = bee.lire_yaml(chemin)
        enr["statut"] = "integree"
        bee.ecrire_yaml(chemin, enr)
        bee.modifier_tache(self.dossier / "taches/miniz/miniz-0099.yaml", statut="integree")
        self.commit("intégrée")
        git(self.dossier, "switch", "-qc", "retroactive")
        enr["relectures"] = [{"relecteur": "bruno", "avis": "favorable", "motif": "Relue après coup pour les points.",
                              "le": "2026-10-27T12:00:00Z"}]
        bee.ecrire_yaml(chemin, enr)
        self.commit()
        code, texte = self.verifier("bruno", "--fusion-auto")
        self.assertEqual(code, 1, texte)
        self.assertIn("qu'une contribution en relecture", texte)

    # --- L'essaim propose, les gardiens valident (27/10) ---

    def test_proposition_de_tache_par_un_membre(self):
        git(self.dossier, "switch", "-qc", "proposition")
        code, texte = self.bee("proposer-tache", "miniz", "--utilisateur", "alice", "--taille", "S")
        self.assertEqual(code, 0, texte)
        nouvelles = [l.split()[-1] for l in git(self.dossier, "status", "--porcelain", "--untracked-files=all").splitlines()]
        self.assertEqual(len(nouvelles), 1, nouvelles)
        tache = bee.lire_yaml(self.dossier / nouvelles[0])
        self.assertEqual((tache["statut"], tache["cree_par"]), ("proposee", "alice"))
        self.valide()
        self.commit()
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 0, texte)
        self.assertIn("FUSION_AUTO=oui", texte)
        self.assertEqual(self.verifier("bruno")[0], 1, "on ne propose qu'en son nom")
        self.assertNotIn(tache["id"], self.bee("lister")[1], "une proposition n'est pas encore disponible")

    def proposer_sur_main(self):
        self.assertEqual(self.bee("proposer-tache", "miniz", "--utilisateur", "alice")[0], 0)
        self.commit("proposition")
        return next(i for i, (_, t) in bee.Registre(self.dossier).taches.items() if t.get("statut") == "proposee")

    def test_validation_d_une_proposition(self):
        tid = self.proposer_sur_main()
        git(self.dossier, "switch", "-qc", "validation")
        bee.modifier_tache(self.dossier / f"taches/miniz/{tid}.yaml", statut="ouverte")
        self.commit()
        code, texte = self.verifier("bidji29", "--fusion-auto")
        self.assertEqual(code, 0, texte)
        self.assertIn("FUSION_AUTO=oui", texte)
        self.assertEqual(self.verifier("bruno")[0], 1, "un Nouveau ne valide pas")
        self.assertEqual(self.verifier("alice")[0], 1, "on ne valide pas sa propre proposition")

    def test_ecarter_une_proposition_exige_une_note(self):
        tid = self.proposer_sur_main()
        git(self.dossier, "switch", "-qc", "ecart")
        chemin = self.dossier / f"taches/miniz/{tid}.yaml"
        bee.modifier_tache(chemin, statut="abandonnee")
        self.commit()
        self.assertEqual(self.verifier("bidji29")[0], 1)
        bee.modifier_tache(chemin, note={"par": "bidji29", "le": "2026-10-27T12:00:00Z",
                                         "texte": "Écartée : aucune mesure ne montre ce coût dans le profil."})
        self.commit("note")
        code, texte = self.verifier("bidji29", "--fusion-auto")
        self.assertEqual(code, 0, texte)

    def test_proposition_de_regle_par_un_membre_en_amorcage(self):
        git(self.dossier, "switch", "-qc", "regle")
        code, texte = self.bee("proposer", "--utilisateur", "alice", "--regle", "R7", "--texte", "Réservation de 48 h au plus.",
                               "--motif", "Les tâches S se finissent en une session.")
        self.assertEqual(code, 0, texte)
        self.commit()
        code, texte = self.verifier("alice", "--fusion-auto")
        self.assertEqual(code, 0, texte)

    def test_mesure_libre_service(self):
        cid = self.soumettre_0099()
        self.commit("soumission")
        git(self.dossier, "switch", "-qc", "mesure")
        rapport = self.dossier / "ab.json"
        rapport.write_text(json.dumps({"base": {"commit": "2948eeb"}, "candidat": {"commit": "839b676"},
                                       "machine": {"architecture": "arm64", "compilateur": "clang 17"},
                                       "metriques": {"debit_compression_n6": {"gain": 0.05, "au_dela_du_bruit": True,
                                                     "test_du_signe": {"victoires_B": 9, "paires_utiles": 10}}}}), encoding="utf-8")
        self.bee("enregistrer-mesure", cid, "--ab", str(rapport), "--utilisateur", "bruno")
        rapport.unlink()  # ne pas committer le JSON brut
        self.commit()
        code, texte = self.verifier("bruno", "--fusion-auto")
        self.assertEqual(code, 0, texte)
        self.assertIn("FUSION_AUTO=oui", texte)
        self.assertEqual(self.verifier("chloe")[0], 1, "on ne dépose pas une mesure au nom d'un autre")


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
        self.etat.write_text('{"state": "closed", "merged": true}', encoding="utf-8")
        binaire = racine / "bin"
        binaire.mkdir()
        (binaire / "gh").write_text(
            "#!/bin/sh\n"
            f"echo \"$@\" >> '{self.journal}'\n"
            "case \"$*\" in\n"
            "  *'-X POST'*) echo '{\"html_url\": \"https://github.com/Bee-ruche/registre/pull/42\", \"number\": 42}' ;;\n"
            f"  *pulls/42*) cat '{self.etat}' ;;\n"
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
        self.assertIn("api repos/Bee-ruche/registre/pulls -X POST -f title=Réservation miniz-0099 -f head=bee/reservation-miniz-0099-20261027-120000 -f base=main", appels)
        self.assertEqual(git(self.dossier, "rev-parse", "--abbrev-ref", "HEAD").strip(), "main")
        self.assertIn("bee/reservation-miniz-0099-20261027-120000", git(self.dossier, "ls-remote", "--heads", "origin"))
        fichiers = git(self.dossier, "show", "--name-only", "--format=", "bee/reservation-miniz-0099-20261027-120000").split()
        self.assertEqual(fichiers, ["taches/miniz/miniz-0099.yaml"], "seul le fichier de la tâche est publié")

    def test_a_blanc_n_ecrit_rien(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        avant = git(self.dossier, "rev-parse", "HEAD")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--a-blanc")
        self.assertEqual(code, 0, texte)
        self.assertIn("Rien n'a été écrit ni poussé", texte)
        self.assertIn("taches/miniz/miniz-0099.yaml", texte)
        self.assertFalse(self.journal.exists(), "aucun appel à gh")
        self.assertEqual(git(self.dossier, "rev-parse", "HEAD"), avant)
        self.assertNotIn("bee/", git(self.dossier, "ls-remote", "--heads", "origin"))

    def test_fichier_hors_libre_service_refuse(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        (self.dossier / "CONTRIBUTION.yaml.bak").write_text("égaré\n", encoding="utf-8")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--intervalle", "0")
        self.assertEqual(code, 1)
        self.assertIn("CONTRIBUTION.yaml.bak", texte)
        self.assertFalse(self.journal.exists(), "aucune PR ne doit être ouverte")

    def test_pr_fermee_ou_en_attente(self):
        self.bee("prendre", "miniz-0099", "--utilisateur", "alice")
        self.etat.write_text('{"state": "closed", "merged": false}', encoding="utf-8")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--intervalle", "0")
        self.assertEqual(code, 1)
        self.assertIn("refusée", texte)
        self.bee("liberer", "miniz-0099", "--utilisateur", "alice")
        self.bee("prendre", "miniz-0099", "--utilisateur", "bruno")
        self.etat.write_text('{"state": "open", "merged": false}', encoding="utf-8")
        code, texte = self.bee("publier", "--titre", "Réservation miniz-0099", "--delai", "0", "--intervalle", "0")
        self.assertEqual(code, 2)
        self.assertIn("relecture humaine", texte)
        self.assertIn("bee/reservation-miniz-0099-20261027-120000-2", git(self.dossier, "branch"), "un second titre identique reçoit un suffixe")

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
        self.assertIn("manifestes/miniz-0099.yaml absent", texte)

    def test_travail_non_commite(self):
        (self.fork / "miniz_tdef.c").write_text("modifié\n", encoding="utf-8")
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        code, texte = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("non commité", texte)
        self.assertIn("existe sur le disque", texte)

    def test_manifeste_par_tache(self):
        chemin = self.fork / "miniz_tdef.c"
        chemin.write_text(chemin.read_text().replace("ligne 5\n", "ligne cinq\n"), encoding="utf-8")
        (self.fork / "manifestes").mkdir()
        (self.fork / "manifestes/miniz-0099.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        # Un ancien manifeste à la racine, d'une autre tâche déjà intégrée, ne gêne pas.
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI.replace("miniz-0099", "miniz-0016"), encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 0, texte)
        self.assertIn("2 lignes", texte)

    def test_manifeste_d_une_autre_tache_refuse(self):
        (self.fork / "manifestes").mkdir()
        (self.fork / "manifestes/miniz-0099.yaml").write_text(MANIFESTE_REMPLI, encoding="utf-8")
        (self.fork / "manifestes/miniz-0011.yaml").write_text(MANIFESTE_REMPLI.replace("miniz-0099", "miniz-0011"), encoding="utf-8")
        chemin = self.fork / "miniz_tdef.c"
        chemin.write_text(chemin.read_text().replace("ligne 5\n", "ligne cinq\n"), encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 1, texte)
        self.assertIn("une PR, une tâche", texte)

    def test_ancien_manifeste_d_une_autre_tache_ignore(self):
        (self.fork / "CONTRIBUTION.yaml").write_text(MANIFESTE_REMPLI.replace("miniz-0099", "miniz-0016"), encoding="utf-8")
        chemin = self.fork / "miniz_tdef.c"
        chemin.write_text(chemin.read_text().replace("ligne 5\n", "ligne cinq\n"), encoding="utf-8")
        self.commit()
        code, texte = self.verifier()
        self.assertEqual(code, 1, texte)
        self.assertIn("manifestes/miniz-0099.yaml absent", texte)

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
