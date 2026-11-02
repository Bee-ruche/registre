"""Tests du générateur de l'essai de charge (ruche-0080) : python3 outils/repetition/test_load_test.py

La base est le registre des tests de bee (test_bee.BaseTest : le dépôt sans les données du registre réel, plus son jeu
figé) et un débat ouvert, dans un dépôt git à un commit daté : jamais l'état réel du registre. Le garde de test_bee
(importé ici) fait échouer un test qui lirait ces données réelles."""
import contextlib
import datetime as dt
import io
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import yaml

ICI = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(ICI), str(ICI.parent)]
import test_bee  # noqa: E402
import load_test  # noqa: E402

UTC = dt.timezone.utc
BASE = int(dt.datetime(2026, 10, 27, 13, tzinfo=UTC).timestamp())  # la veille de la semaine : le 28/10 ; la semaine : le 2/11
LUNDI = dt.datetime(2026, 11, 2, tzinfo=UTC)
FIN = "2026-11-09T00:00:00Z"
SURVEILLANCE = None  # pendant test_hors_ligne : les événements d'audit relevés


def espion(evenement, arguments):
    if SURVEILLANCE is not None and (evenement.startswith("socket.") or evenement in (
            "open", "os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.symlink", "shutil.rmtree", "subprocess.Popen")):
        SURVEILLANCE.append((evenement, arguments))


sys.addaudithook(espion)


def registre_source(dossier):
    """Le registre des tests de bee et un débat ouvert (où argumenter), commités sur main à BASE."""
    modele = test_bee.BaseTest()
    modele.setUp()
    try:
        code, texte = modele.bee("debattre", "ouvrir", "--utilisateur", "alice", "--question", "Faut-il un essai de charge ?")
        assert code == 0, texte
        shutil.copytree(modele.dossier, dossier)
    finally:
        modele.tearDown()
    date = f"{BASE} +0000"
    load_test.git(dossier, "init", "-q", "-b", "main")
    load_test.git(dossier, "add", "-A")
    load_test.git(dossier, "commit", "-q", "-m", "Base des tests", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                  GIT_COMMITTER_EMAIL="t@t", GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return dossier


def generer(source, dossier, membres, graine="7"):
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = load_test.principal([str(dossier), "--membres", str(membres), "--graine", graine, "--registre", str(source)])
    return code, sortie.getvalue()


def lire(chemin):
    return yaml.safe_load(pathlib.Path(chemin).read_text(encoding="utf-8"))


def journal(racine):
    """Les PR de la semaine : [(sha, auteur, ouverte, fusionnée, titre, corps)], dans l'ordre de main."""
    base = load_test.git(racine, "rev-list", "--max-parents=0", "main").decode().strip()
    sortie = load_test.git(racine, "log", "--reverse", "--format=%H %an %at %ct%n%B%x00", f"{base}..main").decode()
    prs = []
    for bloc in filter(str.strip, sortie.split("\0")):
        entete, titre, _, corps = bloc.strip("\n").split("\n")[:4]
        sha, auteur, ouverte, fusion = entete.split()
        prs.append((sha, auteur, int(ouverte), int(fusion), titre, corps))
    return prs


class TestEssaiDeCharge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.racine_temp = pathlib.Path(cls.temp.name)
        cls.source = registre_source(cls.racine_temp / "source")
        cls.dossier = cls.racine_temp / "ruche100"
        cls.code, cls.sortie = generer(cls.source, cls.dossier, 100)
        cls.reg = cls.dossier / "confiance"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def copie(self, nom):
        cible = self.racine_temp / nom
        self.addCleanup(shutil.rmtree, cible, True)
        shutil.copytree(self.dossier, cible, symlinks=True)
        return cible

    # Critère 1 : bee valider, sans contrôle retiré ni outil modifié, à 100, 300 et 1 000 membres.
    def test_valide_a_100_300_et_1000_membres_sans_rien_retirer(self):
        for membres in (100, 300, 1000):
            with self.subTest(membres=membres):
                dossier = self.dossier if membres == 100 else self.racine_temp / f"ruche{membres}"
                code, sortie = (self.code, self.sortie) if membres == 100 else generer(self.source, dossier, membres)
                self.assertEqual(code, 0, sortie)
                self.assertIn(f"{membres} membres, ", sortie)
                r = load_test.lancer_bee(dossier / "confiance", FIN, "valider")  # le code de sortie, jamais à travers un tube
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                # Rien de ce qui juge n'a changé : l'outil, ses schémas, les règles et leurs valeurs sont ceux de la base.
                base = (dossier / "etat" / "base").read_text(encoding="utf-8").strip()
                touches = load_test.git(dossier / "confiance", "diff", "--name-only", base, "main").decode().split()
                self.assertEqual(sorted({c.split("/")[0] for c in touches}),
                                 ["contributions", "debats", "gouvernance", "membres", "taches", "votes"])
                self.assertEqual(sorted(c for c in touches if c.startswith("gouvernance/")),
                                 ["gouvernance/garants.yaml", "gouvernance/gardiens.yaml"])
                if membres != 100:
                    shutil.rmtree(dossier)

    def test_valider_refuse_une_semaine_trafiquee(self):
        """Détournement : un auteur qui relit sa propre contribution, glissé dans la ruche générée, est refusé."""
        reg = self.copie("trafiquee") / "confiance"
        chemin = next(p for p in sorted((reg / "contributions").glob("*/*-c1.yaml")) if lire(p)["auteur"].startswith("abeille-"))
        enr = lire(chemin)
        enr["relectures"][0]["relecteur"] = enr["auteur"]
        chemin.write_text(yaml.safe_dump(enr, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        r = load_test.lancer_bee(reg, FIN, "valider")
        self.assertEqual(r.returncode, 1)
        self.assertIn("l'auteur ne peut pas relire sa propre contribution", r.stdout)

    def test_le_modele_d_activite(self):
        """Par membre actif et par semaine : une contribution, deux relectures, deux votes, une note ; une tâche proposée pour
        10 membres, un argument pour 5 ; la moitié des contributions le vendredi soir ; un gardien pour 20, chacun garanti."""
        membres = sorted(p.stem for p in (self.reg / "membres").glob("abeille-*.yaml"))
        self.assertEqual(len(membres), 100)
        contributions = [lire(p) for p in (self.reg / "contributions").glob("*/*.yaml") if lire(p)["auteur"] in membres]
        self.assertEqual(sorted(c["auteur"] for c in contributions), membres)
        relecteurs = [r["relecteur"] for c in contributions for r in c["relectures"]]
        self.assertTrue(all(len(c["relectures"]) == 2 and c["auteur"] not in {r["relecteur"] for r in c["relectures"]}
                            for c in contributions))
        self.assertEqual(sorted(relecteurs), sorted(membres * 2))
        votes = [lire(p) for p in (self.reg / "votes").glob("*/*.yaml")]
        self.assertEqual(sorted(v["votant"] for v in votes), sorted(membres * 2))
        notes = [n["par"] for p in (self.reg / "taches").glob("*/*.yaml") for n in lire(p).get("notes") or [] if n["par"] in membres]
        self.assertEqual(sorted(notes), membres)
        proposees = [t["cree_par"] for p in (self.reg / "taches").glob("*/*.yaml") if (t := lire(p))["statut"] == "proposee"]
        self.assertEqual(len(proposees), 10)
        self.assertTrue(set(proposees) <= set(membres))
        arguments = [a["par"] for p in (self.reg / "debats").glob("*.yaml") for a in lire(p).get("arguments") or []]
        self.assertEqual(len(arguments), 20)
        self.assertEqual(len(set(arguments)), 20)
        vendredi = (LUNDI + dt.timedelta(days=4, hours=18), LUNDI + dt.timedelta(days=5))
        soumises = [dt.datetime.fromisoformat(c["soumise_le"].replace("Z", "+00:00")) for c in contributions]
        self.assertEqual(sum(vendredi[0] <= s < vendredi[1] for s in soumises), 50)
        self.assertTrue(all(LUNDI <= s < LUNDI + dt.timedelta(days=7) for s in soumises))
        gardiens = lire(self.reg / "gouvernance" / "gardiens.yaml")["membres"]
        garants = {g["pseudo"] for g in lire(self.reg / "gouvernance" / "garants.yaml")["membres"]}
        self.assertTrue(all(g["pseudo"] in membres and g["garant"] in garants for g in gardiens))
        self.assertLessEqual(max(sum(g["garant"] == x for g in gardiens) for x in garants), 2)
        # Le frein de R13, lu par bee dans l'historique à la fin de la semaine : au maximum, sans être serré (un gardien de moins
        # le serrerait). Les membres actifs : les 100 simulés et ceux que la base rend actifs (le conseil, auteur du jeu figé).
        with mock.patch.dict(os.environ, {"BEE_MAINTENANT": FIN}):
            frein = test_bee.bee.etat_frein(test_bee.bee.Registre(self.reg))
        self.assertEqual((frein["gardiens_en_fonction"], frein["encadrement"]), (len(gardiens), []))
        self.assertGreater(frein["membres_actifs"], 100)
        self.assertTrue(20 * (len(gardiens) - 1) < frein["membres_actifs"] <= 20 * len(gardiens), frein)

    # Critère 2 : la forme exacte qu'écrit bee, et un historique qui se rejoue en PR.
    def test_l_historique_est_une_suite_de_prs_avec_auteur_et_heure(self):
        prs = journal(self.reg)
        self.assertEqual(len(prs), 100 * 8 + 1 + 10 + 20)  # inscription, 7 gestes par membre, le conseil, propositions, arguments
        for i, (_, auteur, ouverte, fusion, titre, corps) in enumerate(prs, 1):
            self.assertRegex(titre, rf" \(#{i}\)$")
            self.assertEqual(fusion, ouverte + load_test.FUSION)
            if corps.startswith("bee "):
                self.assertRegex(corps, rf"--(utilisateur|pseudo) {re.escape(auteur)}( |$)")
            else:
                self.assertEqual((auteur, titre.split(" (#")[0]), ("bidji29", "Ruche de charge : garants, gardiens et une tâche par membre"))
        self.assertEqual([p[3] for p in prs], sorted(p[3] for p in prs))
        self.assertEqual(load_test.git(self.dossier / "central.git", "rev-parse", "main"), load_test.git(self.reg, "rev-parse", "main"))
        self.assertEqual(len((self.dossier / "etat" / "prs.tsv").read_text(encoding="utf-8").splitlines()), len(prs))

    def test_un_geste_de_chaque_sorte_se_rejoue(self):
        """La commande bee de la PR, sur l'état d'avant, écrit les mêmes octets ; bee verifier-pr --fusion-auto l'accepte."""
        premieres = {}
        for i, (_, _, _, _, titre, _) in enumerate(journal(self.reg), 1):
            premieres.setdefault(re.sub(r" [^ ]+ \(#\d+\)$| \(#\d+\)$", "", titre), i)
        self.assertEqual(len(premieres), 9, premieres)
        self.assertEqual(load_test.rejouer(self.dossier, set(premieres.values())), [])

    def test_le_rejeu_refuse_une_pr_qui_ne_vient_pas_de_sa_commande(self):
        """Détournements : un vote dont le fichier ne dit pas ce que dit sa commande ; un auteur qui vote pour lui-même."""
        dossier = self.copie("rejeu-trafique")
        reg, n = dossier / "confiance", len(journal(self.reg))
        contribution = next(c for p in sorted((reg / "contributions").glob("*/*-c1.yaml")) if (c := lire(p))["auteur"].startswith("abeille-"))
        cid, auteur = contribution["id"], contribution["auteur"]
        votant = next(p.stem for p in sorted((reg / "membres").glob("abeille-*.yaml"))
                      if p.stem != auteur and not (reg / "votes" / cid / f"{p.stem}.yaml").exists())
        for k, (qui, valeur, commande) in enumerate(((votant, -1, 1), (auteur, 1, 1)), 1):
            chemin = reg / "votes" / cid / f"{qui}.yaml"
            test_bee.bee.ecrire_yaml(chemin, {"votant": qui, "sujet": cid, "valeur": valeur, "le": "2026-11-08T23:59:00Z"})
            load_test.git(reg, "add", "-A")
            load_test.git(reg, "commit", "-q", "-m", f"Vote {cid} (#{n + k})\n\nbee voter {cid} --utilisateur {qui} --valeur {commande}",
                          GIT_AUTHOR_NAME=qui, GIT_AUTHOR_EMAIL="q@simu.bee", GIT_COMMITTER_NAME="GitHub",
                          GIT_COMMITTER_EMAIL="noreply@github.com", GIT_AUTHOR_DATE="2026-11-08T23:59:00Z",
                          GIT_COMMITTER_DATE="2026-11-09T00:00:00Z")
        ecarts = {}
        for numero, raison in load_test.rejouer(dossier, {n + 1, n + 2}):
            ecarts[numero] = ecarts.get(numero, "") + raison
        self.assertEqual(sorted(ecarts), [n + 1, n + 2])
        self.assertIn("n'écrit pas ce que porte la PR", ecarts[n + 1])
        self.assertIn("on ne vote pas pour sa propre contribution", ecarts[n + 2])

    # Critère 3 : déterministe.
    def test_la_meme_graine_donne_les_memes_octets(self):
        dossiers = {nom: self.racine_temp / nom for nom in ("graine7a", "graine7b", "graine8")}
        for nom, dossier in dossiers.items():
            self.addCleanup(shutil.rmtree, dossier, True)
            self.assertEqual(generer(self.source, dossier, 20, "8" if nom == "graine8" else "7")[0], 0)
        tetes = {nom: load_test.git(d / "central.git", "rev-parse", "main") for nom, d in dossiers.items()}
        self.assertEqual(tetes["graine7a"], tetes["graine7b"])  # un commit couvre tout : contenus, auteurs, heures, messages
        self.assertNotEqual(tetes["graine7a"], tetes["graine8"])
        for nom in ("base", "fin", "prs.tsv", "auteurs_pr.tsv"):
            self.assertEqual((dossiers["graine7a"] / "etat" / nom).read_bytes(), (dossiers["graine7b"] / "etat" / nom).read_bytes())

    # Critère 4 : hors ligne ; rien n'est écrit hors de la ruche jetable.
    def test_hors_ligne_et_rien_hors_du_dossier(self):
        global SURVEILLANCE
        dossier = self.racine_temp / "surveillee"
        self.addCleanup(shutil.rmtree, dossier, True)
        avant = (load_test.git(self.source, "status", "--porcelain", "--ignored"), load_test.git(self.source, "for-each-ref"))
        SURVEILLANCE = []
        try:
            code, sortie = generer(self.source, dossier, 20)
        finally:
            evenements, SURVEILLANCE = SURVEILLANCE, None
        self.assertEqual(code, 0, sortie)
        self.assertEqual([e for e, _ in evenements if e.startswith("socket.")], [])
        self.assertGreater(sum(e == "subprocess.Popen" for e, _ in evenements), 10)  # l'espion a bien vu git et bee valider
        self.assertGreater(sum(e == "open" and isinstance(a[1], str) and "w" in a[1] for e, a in evenements), 100)

        def dedans(chemin):
            return pathlib.Path(os.path.abspath(os.fsdecode(chemin))).is_relative_to(dossier)

        for evenement, arguments in evenements:
            if evenement == "subprocess.Popen":
                argv = [os.fsdecode(a) for a in arguments[1]]
                if pathlib.Path(argv[0]).name == "git":
                    cible = argv[argv.index("-C") + 1]
                    self.assertTrue(dedans(cible) or (cible == str(self.source) and argv[3] in ("rev-parse", "log", "archive")), argv)
                else:
                    self.assertEqual((argv[0], dedans(argv[1])), (sys.executable, True), argv)
            elif evenement == "open":
                chemin, mode, drapeaux = arguments
                ecrit = (isinstance(mode, str) and set(mode) & set("wax+")) or (
                    mode is None and drapeaux & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
                if ecrit and not isinstance(chemin, int):
                    self.assertTrue(dedans(chemin), chemin)
            else:
                self.assertTrue(dedans(arguments[0]), (evenement, arguments))
        self.assertEqual((load_test.git(self.source, "status", "--porcelain", "--ignored"), load_test.git(self.source, "for-each-ref")),
                         avant)

    def test_un_dossier_qui_existe_est_refuse_intact(self):
        dossier = self.racine_temp / "existant"
        dossier.mkdir()
        (dossier / "garde.txt").write_text("à garder", encoding="utf-8")
        self.addCleanup(shutil.rmtree, dossier, True)
        with self.assertRaises(FileExistsError):
            generer(self.source, dossier, 20)
        self.assertEqual([p.name for p in dossier.iterdir()], ["garde.txt"])

    def test_moins_de_20_membres_est_refuse(self):
        with self.assertRaises(SystemExit):
            generer(self.source, self.racine_temp / "trop-petite", 19)
        self.assertFalse((self.racine_temp / "trop-petite").exists())


if __name__ == "__main__":
    unittest.main()
