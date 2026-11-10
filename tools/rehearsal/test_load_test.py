"""Tests du générateur de l'essai de charge (ruche-0080) : python3 tools/rehearsal/test_load_test.py

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

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import test_bee  # noqa: E402
import load_test  # noqa: E402

UTC = dt.timezone.utc
BASE = int(dt.datetime(2026, 10, 27, 13, tzinfo=UTC).timestamp())  # inscriptions le lendemain du commit de base ; la semaine ensuite
MONDAY = dt.datetime(2026, 11, 2, tzinfo=UTC)
END = "2026-11-09T00:00:00Z"
SURVEILLANCE = None  # pendant test_hors_ligne : les événements d'audit relevés


def spy(event, arguments):
    if SURVEILLANCE is not None and (event.startswith("socket.") or event in (
            "open", "os.mkdir", "os.rename", "os.remove", "os.rmdir", "os.symlink", "shutil.rmtree", "subprocess.Popen")):
        SURVEILLANCE.append((event, arguments))


sys.addaudithook(spy)


def source_registry(folder):
    """Le registre des tests de bee et un débat ouvert (où argumenter), commités sur main à BASE."""
    model = test_bee.BaseTest()
    model.setUp()
    try:
        code, text = model.bee("debate", "open", "--user", "alice", "--question", "Faut-il un essai de charge ?")
        assert code == 0, text
        shutil.copytree(model.dir, folder)
    finally:
        model.tearDown()
    date = f"{BASE} +0000"
    load_test.git(folder, "init", "-q", "-b", "main")
    load_test.git(folder, "add", "-A")
    load_test.git(folder, "commit", "-q", "-m", "Base des tests", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                  GIT_COMMITTER_EMAIL="t@t", GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return folder


def generate(source, folder, members, seed="7"):
    output_text = io.StringIO()
    with contextlib.redirect_stdout(output_text):
        code = load_test.principal([str(folder), "--members", str(members), "--seed", seed, "--registry", str(source)])
    return code, output_text.getvalue()


def read(path):
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def log_text(root):
    """Les PR de la semaine : [(sha, auteur, ouverte, fusionnée, titre, corps)], dans l'ordre de main."""
    base = load_test.git(root, "rev-list", "--max-parents=0", "main").decode().strip()
    output_text = load_test.git(root, "log", "--reverse", "--format=%H %an %at %ct%n%B%x00", f"{base}..main").decode()
    prs = []
    for block in filter(str.strip, output_text.split("\0")):
        header, title, _, body = block.strip("\n").split("\n")[:4]
        sha, author, open, merge = header.split()
        prs.append((sha, author, int(open), int(merge), title, body))
    return prs


class TestLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.temp_root = pathlib.Path(cls.temp.name)
        cls.source = source_registry(cls.temp_root / "source")
        cls.dir = cls.temp_root / "ruche100"
        cls.code, cls.output = generate(cls.source, cls.dir, 100)
        cls.reg = cls.dir / "trust"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def copied(self, name):
        target = self.temp_root / name
        self.addCleanup(shutil.rmtree, target, True)
        shutil.copytree(self.dir, target, symlinks=True)
        return target

    # Critère 1 : bee valider, sans contrôle retiré ni outil modifié, à 100, 300 et 1 000 membres.
    def test_valid_at_100_300_and_1000_members_without_removing_anything(self):
        for members in (100, 300, 1000):
            with self.subTest(members=members):
                folder = self.dir if members == 100 else self.temp_root / f"ruche{members}"
                code, output_text = (self.code, self.output) if members == 100 else generate(self.source, folder, members)
                self.assertEqual(code, 0, output_text)
                self.assertIn(f"{members} membres, ", output_text)
                r = load_test.run_bee(folder / "trust", END, "validate")  # le code de sortie, jamais à travers un tube
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                # Rien de ce qui juge n'a changé : l'outil, ses schémas, les règles et leurs valeurs sont ceux de la base.
                base = (folder / "state" / "base").read_text(encoding="utf-8").strip()
                touched = load_test.git(folder / "trust", "diff", "--name-only", base, "main").decode().split()
                self.assertEqual(sorted({c.split("/")[0] for c in touched}),
                                 ["contributions", "debates", "governance", "members", "tasks", "votes"])
                self.assertEqual(sorted(c for c in touched if c.startswith("governance/")),
                                 ["governance/guarantors.yaml", "governance/guardians.yaml"])
                if members != 100:
                    shutil.rmtree(folder)

    def test_validate_refuses_a_doctored_week(self):
        """Détournement : un auteur qui relit sa propre contribution, glissé dans la ruche générée, est refusé."""
        reg = self.copied("trafiquee") / "trust"
        path = next(p for p in sorted((reg / "contributions").glob("*/*-c1.yaml")) if read(p)["author"].startswith("abeille-"))
        rec = read(path)
        rec["reviews"][0]["reviewer"] = rec["author"]
        path.write_text(yaml.safe_dump(rec, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        r = load_test.run_bee(reg, END, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("l'auteur ne peut pas relire sa propre contribution", r.stdout)

    def test_the_activity_model(self):
        """Par membre actif et par semaine : une contribution, deux relectures, deux votes, une note ; une tâche proposée pour
        10 membres, un argument pour 5 ; la moitié des contributions le vendredi soir ; un gardien pour 20, chacun garanti."""
        members = sorted(p.stem for p in (self.reg / "members").glob("abeille-*.yaml"))
        self.assertEqual(len(members), 100)
        contributions = [read(p) for p in (self.reg / "contributions").glob("*/*.yaml") if read(p)["author"] in members]
        self.assertEqual(sorted(c["author"] for c in contributions), members)
        reviewers = [r["reviewer"] for c in contributions for r in c["reviews"]]
        self.assertTrue(all(len(c["reviews"]) == 2 and c["author"] not in {r["reviewer"] for r in c["reviews"]}
                            for c in contributions))
        self.assertEqual(sorted(reviewers), sorted(members * 2))
        votes = [read(p) for p in (self.reg / "votes").glob("*/*.yaml")]
        self.assertEqual(sorted(v["voter"] for v in votes), sorted(members * 2))
        notes = [n["by"] for p in (self.reg / "tasks").glob("*/*.yaml") for n in read(p).get("notes") or [] if n["by"] in members]
        self.assertEqual(sorted(notes), members)
        proposed_ones = [t["created_by"] for p in (self.reg / "tasks").glob("*/*.yaml") if (t := read(p))["status"] == "proposed"]
        self.assertEqual(len(proposed_ones), 10)
        self.assertTrue(set(proposed_ones) <= set(members))
        arguments = [a["by"] for p in (self.reg / "debates").glob("*.yaml") for a in read(p).get("arguments") or []]
        self.assertEqual(len(arguments), 20)
        self.assertEqual(len(set(arguments)), 20)
        friday = (MONDAY + dt.timedelta(days=4, hours=18), MONDAY + dt.timedelta(days=5))
        submitted_ones = [dt.datetime.fromisoformat(c["submitted_at"].replace("Z", "+00:00")) for c in contributions]
        self.assertEqual(sum(friday[0] <= s < friday[1] for s in submitted_ones), 50)
        self.assertTrue(all(MONDAY <= s < MONDAY + dt.timedelta(days=7) for s in submitted_ones))
        guardians = read(self.reg / "governance" / "guardians.yaml")["members"]
        guarantors = {g["login"] for g in read(self.reg / "governance" / "guarantors.yaml")["members"]}
        self.assertTrue(all(g["login"] in members and g["guarantor"] in guarantors for g in guardians))
        self.assertLessEqual(max(sum(g["guarantor"] == x for g in guardians) for x in guarantors), 2)
        # Le frein de R13, lu par bee dans l'historique à la fin de la semaine : au maximum, sans être serré (un gardien de moins
        # le serrerait). Les membres actifs : les 100 simulés et ceux que la base rend actifs (le conseil, auteur du jeu figé).
        with mock.patch.dict(os.environ, {"BEE_NOW": END}):
            brake = test_bee.bee.brake_state(test_bee.bee.Registry(self.reg))
        self.assertEqual((brake["guardians_in_office"], brake["oversight"]), (len(guardians), []))
        self.assertGreater(brake["active_members"], 100)
        self.assertTrue(20 * (len(guardians) - 1) < brake["active_members"] <= 20 * len(guardians), brake)

    # Critère 2 : la forme exacte qu'écrit bee, et un historique qui se rejoue en PR.
    def test_the_history_is_a_series_of_prs_with_author_and_time(self):
        prs = log_text(self.reg)
        self.assertEqual(len(prs), 100 * 8 + 1 + 10 + 20)  # inscription, 7 gestes par membre, le conseil, propositions, arguments
        for i, (_, author, open, merge, title, body) in enumerate(prs, 1):
            self.assertRegex(title, rf" \(#{i}\)$")
            self.assertEqual(merge, open + load_test.MERGE)
            if body.startswith("bee "):
                self.assertRegex(body, rf"--(utilisateur|pseudo) {re.escape(author)}( |$)")
            else:
                self.assertEqual((author, title.split(" (#")[0]), ("bidji29", "Ruche de charge : garants, gardiens et une tâche par membre"))
        self.assertEqual([p[3] for p in prs], sorted(p[3] for p in prs))
        self.assertEqual(load_test.git(self.dir / "central.git", "rev-parse", "main"), load_test.git(self.reg, "rev-parse", "main"))
        self.assertEqual(len((self.dir / "state" / "prs.tsv").read_text(encoding="utf-8").splitlines()), len(prs))

    def test_a_gesture_of_each_kind_replays(self):
        """La commande bee de la PR, sur l'état d'avant, écrit les mêmes octets ; bee check-pr --auto-merge l'accepte."""
        first_ones = {}
        for i, (_, _, _, _, title, _) in enumerate(log_text(self.reg), 1):
            first_ones.setdefault(re.sub(r" [^ ]+ \(#\d+\)$| \(#\d+\)$", "", title), i)
        self.assertEqual(len(first_ones), 9, first_ones)
        self.assertEqual(load_test.replay(self.dir, set(first_ones.values())), [])

    def test_the_replay_refuses_a_pr_that_does_not_come_from_its_command(self):
        """Détournements : un vote dont le fichier ne dit pas ce que dit sa commande ; un auteur qui vote pour lui-même."""
        folder = self.copied("rejeu-trafique")
        reg, n = folder / "trust", len(log_text(self.reg))
        contribution = next(c for p in sorted((reg / "contributions").glob("*/*-c1.yaml")) if (c := read(p))["author"].startswith("abeille-"))
        cid, author = contribution["id"], contribution["author"]
        voter = next(p.stem for p in sorted((reg / "members").glob("abeille-*.yaml"))
                      if p.stem != author and not (reg / "votes" / cid / f"{p.stem}.yaml").exists())
        for k, (who_is, value, command) in enumerate(((voter, -1, 1), (author, 1, 1)), 1):
            path = reg / "votes" / cid / f"{who_is}.yaml"
            test_bee.bee.write_yaml(path, {"voter": who_is, "subject": cid, "value": value, "at": "2026-11-08T23:59:00Z"})
            load_test.git(reg, "add", "-A")
            load_test.git(reg, "commit", "-q", "-m", f"Vote {cid} (#{n + k})\n\nbee voter {cid} --user {who_is} --value {command}",
                          GIT_AUTHOR_NAME=who_is, GIT_AUTHOR_EMAIL="q@sim.bee", GIT_COMMITTER_NAME="GitHub",
                          GIT_COMMITTER_EMAIL="noreply@github.com", GIT_AUTHOR_DATE="2026-11-08T23:59:00Z",
                          GIT_COMMITTER_DATE="2026-11-09T00:00:00Z")
        gaps = {}
        for number_of, cause in load_test.replay(folder, {n + 1, n + 2}):
            gaps[number_of] = gaps.get(number_of, "") + cause
        self.assertEqual(sorted(gaps), [n + 1, n + 2])
        self.assertIn("n'écrit pas ce que porte la PR", gaps[n + 1])
        self.assertIn("on ne vote pas pour sa propre contribution", gaps[n + 2])

    # Critère 3 : déterministe.
    def test_the_same_seed_gives_the_same_bytes(self):
        folders = {name: self.temp_root / name for name in ("graine7a", "graine7b", "graine8")}
        for name, folder in folders.items():
            self.addCleanup(shutil.rmtree, folder, True)
            self.assertEqual(generate(self.source, folder, 20, "8" if name == "graine8" else "7")[0], 0)
        heads = {name: load_test.git(d / "central.git", "rev-parse", "main") for name, d in folders.items()}
        self.assertEqual(heads["graine7a"], heads["graine7b"])  # un commit couvre tout : contenus, auteurs, heures, messages
        self.assertNotEqual(heads["graine7a"], heads["graine8"])
        for name in ("base", "end", "prs.tsv", "pr_authors.tsv"):
            self.assertEqual((folders["graine7a"] / "state" / name).read_bytes(), (folders["graine7b"] / "state" / name).read_bytes())

    # Critère 4 : hors ligne ; rien n'est écrit hors de la ruche jetable.
    def test_offline_and_nothing_outside_the_folder(self):
        global SURVEILLANCE
        folder = self.temp_root / "surveillee"
        self.addCleanup(shutil.rmtree, folder, True)
        before = (load_test.git(self.source, "status", "--porcelain", "--ignored"), load_test.git(self.source, "for-each-ref"))
        SURVEILLANCE = []
        try:
            code, output_text = generate(self.source, folder, 20)
        finally:
            events, SURVEILLANCE = SURVEILLANCE, None
        self.assertEqual(code, 0, output_text)
        self.assertEqual([e for e, _ in events if e.startswith("socket.")], [])
        self.assertGreater(sum(e == "subprocess.Popen" for e, _ in events), 10)  # l'espion a bien vu git et bee valider
        self.assertGreater(sum(e == "open" and isinstance(a[1], str) and "w" in a[1] for e, a in events), 100)

        def inside_it(path):
            return pathlib.Path(os.path.abspath(os.fsdecode(path))).is_relative_to(folder)

        for event, arguments in events:
            if event == "subprocess.Popen":
                argv = [os.fsdecode(a) for a in arguments[1]]
                if pathlib.Path(argv[0]).name == "git":
                    target = argv[argv.index("-C") + 1]
                    self.assertTrue(inside_it(target) or (target == str(self.source) and argv[3] in ("rev-parse", "log", "archive")), argv)
                else:
                    self.assertEqual((argv[0], inside_it(argv[1])), (sys.executable, True), argv)
            elif event == "open":
                path, mode, flag_bits = arguments
                written = (isinstance(mode, str) and set(mode) & set("wax+")) or (
                    mode is None and flag_bits & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
                if written and not isinstance(path, int):
                    self.assertTrue(inside_it(path), path)
            else:
                self.assertTrue(inside_it(arguments[0]), (event, arguments))
        self.assertEqual((load_test.git(self.source, "status", "--porcelain", "--ignored"), load_test.git(self.source, "for-each-ref")),
                         before)

    def test_an_existing_folder_is_refused_intact(self):
        folder = self.temp_root / "existant"
        folder.mkdir()
        (folder / "keeper.txt").write_text("à garder", encoding="utf-8")
        self.addCleanup(shutil.rmtree, folder, True)
        with self.assertRaises(FileExistsError):
            generate(self.source, folder, 20)
        self.assertEqual([p.name for p in folder.iterdir()], ["keeper.txt"])

    def test_fewer_than_20_members_is_refused(self):
        with self.assertRaises(SystemExit):
            generate(self.source, self.temp_root / "trop-petite", 19)
        self.assertFalse((self.temp_root / "trop-petite").exists())


if __name__ == "__main__":
    unittest.main()
