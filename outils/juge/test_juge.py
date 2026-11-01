#!/usr/bin/env python3
"""Tests du juge commun Bee (outils/juge/).

  python3 outils/juge/test_juge.py                      tests unitaires (sans Docker)
  BEE_JUGE_INTEGRATION=1 python3 outils/juge/test_juge.py
                                                        + méta-tests : le juge commun contre le projet jouet
                                                          (outils/juge/jouet/) honnête et MALVEILLANT (Docker requis)
  BEE_JUGE_RESEAU=host                                  réseau de « docker build » (machines sans pont Docker)

Les variantes malveillantes sont des transformations du texte de rle.c, compilées et exécutées
uniquement DANS le conteneur du juge. Ce sont les mêmes ruses que celles des méta-tests de minizBee
(bee/juge/test_juge.py du fork), plus deux propres au juge commun :
  sortie_anticipee   le programme s'arrête « avec succès » au milieu des entrées
  faux_chronos       le code remplace clock_gettime pour annoncer des temps flatteurs, et il est plus lent
  table_precalculee  le compresseur ne marche que sur les entrées qu'il connaît d'avance (le corpus)
  requete_valgrind   le code suspend le décompte d'instructions de Valgrind pendant son propre travail
  faux_resume        le code écrit un faux résumé « I refs » sur la sortie d'erreur
  travail_deplace    le travail de rle_compresser est fait d'avance dans rle_borne, appelée juste avant
  greffon_de_la_pr   la PR apporte son propre greffon et son propre harnais, qui acceptent tout : ignorés
  lien_symbolique    rle.c de la PR est un lien symbolique (vers un fichier de l'hôte)
et, depuis la revue adverse du 28/10 (défauts de contrat d'un greffon) :
  releves_vides      le script de construction de la base écrit un désassemblage vide : sans effet, le juge
                     relève lui-même les objets, et la requête Valgrind reste signalée
  objet_oublie       le script de construction ne laisse pas l'objet du projet dans obj/ : erreur
  jetons_scindes     l'assembleur est formé par concaténation de jetons (a##sm) : vu dans les objets
  greffon_distrait   un greffon qui ne lit pas les sorties de B d'un scénario : erreur, pas d'acceptation

Without Docker, the analysis is also tested on objects of the toy project built on the host as the judge
builds them (DockerLocal; built, surveyed and analysed, never run): seeded constructs in every family and
variant (TestSeededObjects), constructs added anywhere in a judged file (TestSeededText), failing tools
(TestFailClosed).

ruche-0024 (juge-v2): juge.yml's scripts are run as the runner would (TestWorkflowJuge: judge code at the workflow's
own commit, preparation failing closed, a hostile journal that issues no workflow command), the architectures'
reports merged (TestFusion), the declared history fetched then read without git transport (TestHistorique); with
Docker, historique_declare, historique_non_declare and faux_gain_sur_une_architecture (also run on ARM64).
"""

import concurrent.futures
import json
import os
import platform
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ICI = os.path.dirname(os.path.abspath(__file__))
JOUET = os.path.join(ICI, "jouet")
sys.path.insert(0, ICI)
import analyse  # noqa: E402
import conteneur  # noqa: E402
import entrees  # noqa: E402
import juge  # noqa: E402
import lecture  # noqa: E402
import stats  # noqa: E402

sys.path.insert(0, os.path.join(JOUET, "bee", "juge"))
import projet as greffon_jouet  # noqa: E402


def architecture_ici():
    """This machine's key in juge.json's « chronometres » (x86_64, arm64)."""
    a = platform.machine().lower()
    return {"amd64": "x86_64", "aarch64": "arm64"}.get(a, a)


# ------------------------------------------------------------------ tests unitaires

NM_A = """/s/obj/rle.o: rle_compresser T 0000000000000100 0000000000000080
/s/obj/rle.o: memcpy U
/s/obj/rle.o: .LC0 r 0
"""
SECTIONS_A = """
Idx Name          Size      VMA               LMA               File off  Algn
  0 .text         00001000  0000000000000000  0000000000000000  00000040  2**4
"""
DESASSEMBLAGE_A = "0000000000000000 <rle_compresser>:\n   0:\tendbr64\n   4:\tpush   %rbp\n"


def releves(nm=NM_A, sections=SECTIONS_A, desassemblage=DESASSEMBLAGE_A, objets=(), programme=()):
    return {"symboles": nm, "sections": sections, "desassemblage": desassemblage, "objets": list(objets),
            "programme": list(programme)}


class TestAnalyse(unittest.TestCase):
    def test_base_contre_elle_meme(self):
        self.assertEqual(analyse.analyser(releves(), releves(), {}, {}, prefixes=("rle_",)), [])

    def test_prefixes_et_permis_du_greffon(self):
        b = releves(nm=NM_A + "/s/obj/rle.o: rle_aide T 0000000000000300 0000000000000010\n/s/obj/rle.o: qsort U\n")
        self.assertEqual([s["type"] for s in analyse.analyser(releves(), b, {}, {}, prefixes=("rle_",))], ["appel_externe"])
        self.assertEqual(analyse.analyser(releves(), b, {}, {}, prefixes=("rle_",), permis=("qsort",)), [])
        # Sans espace de noms, une nouvelle fonction globale est suspecte (elle pourrait en remplacer une autre).
        self.assertEqual(sorted(s["type"] for s in analyse.analyser(releves(), b, {}, {}, permis=("qsort",))), ["symbole_defini"])

    def test_symbole_qui_remplace_la_libc(self):
        b = releves(nm=NM_A + "/s/obj/rle.o: clock_gettime T 0000000000000300 0000000000000010\n"
                             "/s/obj/rle.o: memcmp T 0000000000000400 0000000000000010\n")
        self.assertEqual(sorted(s["type"] for s in analyse.analyser(releves(), b, {}, {}, prefixes=("rle_",))),
                         ["symbole_defini", "symbole_interdit"])

    def test_jamais_permis_malgre_prefixe_ou_permis(self):
        """Revue adverse n° 2 : un préfixe « ge » ou une entrée PERMIS ne blanchit pas getenv."""
        b = releves(nm=NM_A + "/s/obj/rle.o: getenv U\n/s/obj/rle.o: syscall U\n")
        types = [s["type"] for s in analyse.analyser(releves(), b, {}, {}, prefixes=("rle_", "ge", "sy"), permis=("getenv",))]
        self.assertEqual(types, ["appel_interdit", "appel_interdit"])
        a = releves(nm=NM_A + "/s/obj/rle.o: getenv U\n")
        self.assertEqual([s["type"] for s in analyse.analyser(a, b, {}, {}, prefixes=("rle_",))], ["appel_interdit"])  # syscall seul

    def test_continuation_de_ligne(self):
        b = {"rle.c": "    __as\\\nm volatile(\"\");\n    int x = 1;\n"}
        self.assertEqual(list(analyse.constructions_du_texte(b)), [("rle.c", "assembleur en ligne", "__as" + "m volatile(\"\");")])
        self.assertEqual(len(analyse.analyser(releves(), releves(), {}, b, prefixes=("rle_",))), 1)

    def test_constructeur_et_instructions(self):
        b = releves(sections=SECTIONS_A + "  1 .init_array   00000008  0000000000000000  0000000000000000  00001140  2**3\n",
                    desassemblage=DESASSEMBLAGE_A + "   9:\tsyscall\n  10:\trol    $0x3,%rdi\n")
        self.assertEqual(sorted(s["type"] for s in analyse.analyser(releves(), b, {}, {}, prefixes=("rle_",))),
                         ["instruction", "instruction", "section"])

    def test_source(self):
        b = {"rle.c": "    __asm__ volatile(\"\");\n#include <time.h>\n    int ordinaire = 1;\n"}
        self.assertEqual(len(analyse.analyser(releves(), releves(), {}, b, prefixes=("rle_",))), 2)

    def test_mnemonics_any_word(self):
        instructions = {m: m for m in analyse.MNEMONIQUES_SUSPECTS if m[0].isalpha() and m not in NON_INSTRUCTIONS}
        instructions.update({"int": "int $0x80", "(bad)": "(bad)", ".byte": ".byte 0xf", "preambule_valgrind": "rol $0x3,%rdi"})
        suites = [()] + [(p,) for p in PREFIXES_X86] + [(p, q) for p in PREFIXES_X86 for q in PREFIXES_X86]
        lignes = [f"  1f:\t{' '.join(suite + (texte,))}" for texte in instructions.values() for suite in suites]
        lignes += ["   e:\tcall   13 <syscall+0x3>", "  13:\tlea    0x0(%rip),%rax        # 1a <int>"]
        self.assertEqual(analyse.mnemoniques("\n".join(lignes)), {m: len(suites) for m in instructions})

    def test_unreadable_bytes_make_the_analysis_incomplete(self):
        for donnees in (b"", b"\x7fELF", b"MZ" + bytes(100), b"\x7fELF\x02\x01\x01" + bytes(57)):
            b = releves(objets=[("rle.o", donnees)])
            self.assertEqual([s["type"] for s in analyse.analyser(releves(), b, {}, {}, prefixes=("rle_",))], ["analyse_incomplete"])

    def test_unreadable_a_object(self):
        a, b = releves(objets=[("rle.o", b"\x7fELF")]), releves(objets=[("rle.o", elf(1, [(".text", 6, b"\x90")]))])
        self.assertEqual([s["type"] for s in analyse.analyser(a, b, {}, {})], ["analyse_incomplete"])

    def test_texts_required(self):
        with self.assertRaises(TypeError):
            analyse.analyser(releves(), releves(), prefixes=("rle_",))

    def test_whole_files_compared(self):
        a = {"x.c": "#pragma once\nint a;\n", "y.c": "int b;\n"}
        self.assertEqual(analyse.analyser(releves(), releves(), a, {"x.c": "int c;\n  #pragma   once\n", "y.c": "int b;\n"}), [])
        b = {"x.c": "int a;\n", "y.c": "#pragma once\nint b;\n"}
        self.assertEqual([s["detail"][-5:] for s in analyse.analyser(releves(), releves(), a, b)], ["(y.c)"])
        b = {"x.c": "#pragma once\nint a;\n#pragma once\n", "y.c": "int b;\n"}
        self.assertEqual(len(analyse.analyser(releves(), releves(), a, b)), 1)


# Every prefix word objdump prints before an x86-64 instruction.
PREFIXES_X86 = ["es", "cs", "ss", "ds", "fs", "gs", "data16", "addr32", "lock", "rep", "repz", "repnz", "notrack", "bnd",
                "xacquire", "xrelease"] + ["rex" + ("." + "".join(c for c, bit in zip("WRXB", (8, 4, 2, 1)) if m & bit) if m else "")
                                           for m in range(16)]
NON_INSTRUCTIONS = ("preambule_valgrind", "segment_wx", "pile_executable")
GNU_STACK = 0x6474E551


def elf(genre, sections=(), segments=(), shstrndx=None, queue=b""):
    """Minimal x86-64 ELF file: an object (genre 1) with sections [(name, flags, bytes)] and its name table, or a program
    (genre 3) with segments [(type, flags, bytes)]; `queue` is appended after everything."""
    noms = b"\0" + b"".join(n.encode() + b"\0" for n, _, _ in sections) + b".shstrtab\0"
    debut = 64 + 56 * len(segments)
    corps, ph, sh, position = b"", b"", bytes(64), 1
    for type_, drapeaux, donnees in segments:
        ph += struct.pack("<IIQQQQQQ", type_, drapeaux, debut + len(corps), 0, 0, len(donnees), len(donnees), 0)
        corps += donnees
    for nom, drapeaux, donnees in sections:
        sh += struct.pack("<IIQQQQIIQQ", position, 1, drapeaux, 0, debut + len(corps), len(donnees), 0, 0, 1, 0)
        position, corps = position + len(nom) + 1, corps + donnees
    sh += struct.pack("<IIQQQQIIQQ", position, 3, 0, 0, debut + len(corps), len(noms), 0, 0, 1, 0)
    corps += noms
    nombre = len(sections) + 2 if sections else 0
    tete = b"\x7fELF\x02\x01\x01" + bytes(9) + struct.pack(
        "<HHIQQQIHHHHHH", genre, 62, 1, 0, 64 if segments else 0, debut + len(corps) if sections else 0, 0, 64, 56,
        len(segments), 64, nombre, max(nombre - 1, 0) if shstrndx is None else shstrndx)
    return tete + ph + corps + (sh if sections else b"") + queue


class TestExecutableBytes(unittest.TestCase):
    """Executable bytes read from hand-built ELF files."""

    def test_object_sections(self):
        objet = elf(1, [(".text", 6, b"\x90\xc3"), (".data.x", 6, b"\x90\x0f\x05\x90"), (".data", 3, b"\x0f\x05"),
                        (".text.y", 2, b"\x0f\x31")])
        self.assertEqual(analyse.octets_executables(objet), ([b"\x90\xc3", b"\x90\x0f\x05\x90", b"\x0f\x31"], []))
        b = releves(objets=[("rle.o", objet)])
        self.assertEqual(sorted(s["detail"].split(":")[0] for s in analyse.analyser(releves(), b, {}, {})), ["rdtsc", "syscall"])

    def test_hit_context_and_object(self):
        def objets(nom, octets):
            return releves(objets=[(nom, elf(1, [(".text", 6, octets)]))])
        a = objets("rle.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3" * 8)
        self.assertEqual(analyse.analyser(a, objets("rle.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3" * 8), {}, {}), [])
        for b in (objets("rle.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3\xcc" * 4), objets("rle.o", b"\x90\xcc" * 4 + b"\x0f\x05" + b"\xc3" * 8),
                  objets("rle2.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3" * 8)):
            with self.subTest(b=b["objets"][0][0]):
                self.assertEqual([s["detail"].split(":")[0] for s in analyse.analyser(a, b, {}, {})], ["syscall"])

    def test_compressed_executable_section(self):
        with self.assertRaises(ValueError):
            analyse.octets_executables(elf(1, [(".text.z", 0x806, b"\x0f\x05")]))

    def test_section_name_table_index(self):
        analyse.octets_executables(elf(1, [(".text", 6, b"\x90")], queue=bytes(256)))
        for indice in (3, 4):
            with self.assertRaises(ValueError):
                analyse.octets_executables(elf(1, [(".text", 6, b"\x90")], shstrndx=indice, queue=bytes(256)))

    def test_program_segments_and_stack(self):
        code, pile = (1, 5, b"\x90\xc3"), (GNU_STACK, 6, b"")
        self.assertEqual(analyse.octets_executables(elf(3, segments=[code, pile])), ([b"\x90\xc3"], []))
        self.assertEqual(analyse.octets_executables(elf(3, segments=[code]))[1], ["pile_executable"])
        self.assertEqual(analyse.octets_executables(elf(3, segments=[code, (GNU_STACK, 7, b"")]))[1], ["pile_executable"])
        self.assertEqual(analyse.octets_executables(elf(3, segments=[(1, 7, b"\x90"), pile]))[1], ["segment_wx"])


class TestLectureSure(unittest.TestCase):
    def setUp(self):
        self.racine = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.racine, "c"))

    def tearDown(self):
        shutil.rmtree(self.racine)

    def test_fichier_ordinaire_et_absent(self):
        with open(os.path.join(self.racine, "c", "x"), "wb") as f:
            f.write(b"abc")
        self.assertEqual(lecture.lire_sortie(self.racine, "c/x"), b"abc")
        self.assertIsNone(lecture.lire_sortie(self.racine, "c/absent"))

    def test_liens_tubes_et_chemins_refuses(self):
        os.symlink("/etc/hostname", os.path.join(self.racine, "c", "lien"))
        os.symlink("/etc", os.path.join(self.racine, "d"))
        os.mkfifo(os.path.join(self.racine, "c", "tube"))
        for relatif in ("c/lien", "d/hostname", "c/tube", "../x", "c/../c/x", "/etc/hostname"):
            with self.assertRaises(lecture.Refus, msg=relatif):
                lecture.lire_sortie(self.racine, relatif)

    def test_taille_bornee_et_statut(self):
        with open(os.path.join(self.racine, "c", "x"), "wb") as f:
            f.write(b"0" * 100)
        with self.assertRaises(lecture.Refus):
            lecture.lire_sortie(self.racine, "c/x", maximum=10)
        with open(os.path.join(self.racine, "c", "s"), "wb") as f:
            f.write(b"-2 12\n")
        self.assertEqual(lecture.Sorties({"f": self.racine}).statut("f", "c/s"), (-2, 12))
        with open(os.path.join(self.racine, "c", "s"), "wb") as f:
            f.write(b"0 12 ; rm -rf /\n")
        with self.assertRaises(lecture.Refus):
            lecture.statut(self.racine, "c/s")

    def test_propre(self):
        self.assertEqual(lecture.propre(b"::error::x\x1b[31m"), ": :error: :x?[31m")


class TestStatistiques(unittest.TestCase):
    """Mêmes définitions que bee/bench/ab.py de minizBee (valeurs de référence calculées avec ab.py)."""

    def test_seuil_du_signe(self):
        self.assertEqual([stats.seuil_signe(n) for n in (5, 6, 10, 20)], [None, 6, 9, 16])

    def test_test_du_signe(self):
        t = stats.test_du_signe([1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 2, 2, 2, 2, 2, 1], "plus_haut")
        self.assertEqual((t["victoires_B"], t["egalites"], t["seuil_k"], t["au_dela_du_bruit"]), (9, 1, 8, True))
        t = stats.test_du_signe([2] * 10, [1] * 10, "plus_haut")
        self.assertTrue(t["degradation_au_dela_du_bruit"])

    def test_resume_et_gain(self):
        self.assertEqual(stats.resume([3, None, 1, 2])["mediane"], 2)
        self.assertAlmostEqual(stats.gain_relatif(100, 98, "plus_bas"), 0.02)
        self.assertAlmostEqual(stats.gain_relatif(100, 103, "plus_haut"), 0.03)
        self.assertIsNone(stats.gain_relatif(0, 1, "plus_haut"))


class TestEntrees(unittest.TestCase):
    def test_validation(self):
        bonne = entrees.Entree("f", "k000", b"x", 1)
        entrees.verifier_entrees([bonne], ("f", "z"))
        for mauvaise in (entrees.Entree("q", "k", b"", 0), entrees.Entree("f", "../k", b"", 0),
                         entrees.Entree("f", "k", "texte", 0), entrees.Entree("f", "k", b"", -1)):
            with self.assertRaises(lecture.Erreur):
                entrees.verifier_entrees([mauvaise], ("f", "z"))
        with self.assertRaises(lecture.Erreur):
            entrees.verifier_entrees([bonne, bonne], ("f",))

    def test_ecriture(self):
        dossier = tempfile.mkdtemp()
        try:
            entrees.ecrire(dossier, [entrees.Entree("z", "z000", b"abc", 7)], ("f", "z"))
            self.assertEqual(open(os.path.join(dossier, "liste")).read(), "z z000 7\n")
            self.assertTrue(os.path.isdir(os.path.join(dossier, "f")))
        finally:
            shutil.rmtree(dossier)

    def test_perturber_reproductible(self):
        corpus = [("k000", bytes(200_000)), ("k001", b"")]
        a = entrees.perturber(random.Random(1), corpus)
        self.assertEqual(a, entrees.perturber(random.Random(1), corpus))
        self.assertEqual(sum(1 for x in a[0][1] if x), 3)
        self.assertEqual(a[1][1], b"")


class TestGreffon(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "bee", "juge"))

    def tearDown(self):
        shutil.rmtree(self.base)

    def ecrire(self, texte):
        with open(os.path.join(self.base, "bee", "juge", "projet.py"), "w", encoding="utf-8") as f:
            f.write(texte)

    def test_greffon_du_jouet(self):
        projet, empreinte = juge.charger_greffon(JOUET, {})
        self.assertEqual(projet.NOM, "jouet")
        self.assertEqual(len(empreinte), 64)
        with self.assertRaises(lecture.Erreur):
            juge.charger_greffon(JOUET, {"inconnue": "1"})

    def test_greffon_absent_ou_incomplet(self):
        with self.assertRaises(lecture.Erreur):
            juge.charger_greffon(self.base, {})
        self.ecrire("class Projet:\n    NOM = 'x'\n    def __init__(self, options): pass\n")
        with self.assertRaises(lecture.Erreur) as e:
            juge.charger_greffon(self.base, {})
        self.assertIn("SCENARIOS", str(e.exception))

    def test_greffon_lien_refuse(self):
        os.symlink(os.path.join(JOUET, "bee", "juge", "projet.py"), os.path.join(self.base, "bee", "juge", "projet.py"))
        with self.assertRaises(lecture.Erreur):
            juge.charger_greffon(self.base, {})

    def greffon_modifie(self, ancien, nouveau):
        texte = open(os.path.join(JOUET, "bee", "juge", "projet.py"), encoding="utf-8").read()
        self.assertEqual(texte.count(ancien), 1)
        self.ecrire(texte.replace(ancien, nouveau))

    def test_prefixes_vides_ou_courts_refuses(self):
        for valeur in ('("",)', '()', '("r",)', '("rle-",)', '("rle",)', '("ge",)', '("rle_", "cl")', '("sys",)'):
            self.greffon_modifie('PREFIXES = ("rle_",)', f"PREFIXES = {valeur}")
            with self.assertRaises(lecture.Erreur, msg=valeur):
                juge.charger_greffon(self.base, {})

    def test_permis_jamais_permis(self):
        self.greffon_modifie("PERMIS = ()", 'PERMIS = ("qsort", "clock_gettime")')
        with self.assertRaises(lecture.Erreur) as e:
            juge.charger_greffon(self.base, {})
        self.assertIn("clock_gettime", str(e.exception))
        self.greffon_modifie("PERMIS = ()", 'PERMIS = ("qsort",)')
        juge.charger_greffon(self.base, {})

    def test_diff_n_existe_plus(self):
        self.greffon_modifie('SOURCES = ["rle.c", "rle.h"]', 'SOURCES = ["rle.c", "rle.h"]\n    DIFF = ["rle.c"]')
        with self.assertRaises(lecture.Erreur):
            juge.charger_greffon(self.base, {})

    def test_scenario_hors_cotes(self):
        texte = open(os.path.join(JOUET, "bee", "juge", "projet.py"), encoding="utf-8").read()
        self.ecrire(texte.replace('SCENARIOS = {"compression": "f"', 'SCENARIOS = {"compression": "q"'))
        sys.path.insert(0, ICI)
        with self.assertRaises(lecture.Erreur):
            juge.charger_greffon(self.base, {})


class TestObjetsAttendus(unittest.TestCase):
    def test_unites_et_homonymes(self):
        racine = tempfile.mkdtemp()
        try:
            for chemin in ("src/a.c", "src/b.S", "src/c.cc", "src/d.h", "lib/e.c"):
                os.makedirs(os.path.join(racine, os.path.dirname(chemin)), exist_ok=True)
                open(os.path.join(racine, chemin), "w").close()
            self.assertEqual(juge.objets_attendus(racine), ({"a.o", "b.o", "c.o", "e.o"}, []))
            open(os.path.join(racine, "lib", "a.c"), "w").close()
            self.assertEqual(juge.objets_attendus(racine)[1], ["a.o"])
        finally:
            shutil.rmtree(racine)


class TestCouverture(unittest.TestCase):
    def test_sorties_lues_et_couverture(self):
        racine = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(racine, "c"))
            for nom in ("k000.6", "k001"):
                with open(os.path.join(racine, "c", nom), "wb") as f:
                    f.write(b"x")
            vue = lecture.Sorties({"f": racine})
            vue.exiger("f", "c/k000.6")
            self.assertTrue(vue.couvre("f", "k000"))
            self.assertFalse(vue.couvre("f", "k00"))
            self.assertFalse(vue.couvre("f", "k001"))
            liste = [entrees.Entree("f", "k000", b"", 0), entrees.Entree("f", "k001", b"", 0)]
            with self.assertRaises(lecture.Erreur):
                juge.exiger_couverture(vue, liste, "essai")
            vue.lire("f", "c/k001")
            juge.exiger_couverture(vue, liste, "essai")
        finally:
            shutil.rmtree(racine)


class TestCodecDeReference(unittest.TestCase):
    def test_aller_retour(self):
        rng = random.Random(5)
        projet = greffon_jouet.Projet({})
        for _, d in projet.corpus(None) + projet.aleatoires(rng):
            self.assertEqual(greffon_jouet.decompresser(greffon_jouet.compresser(d)), d)

    def test_flux_invalides_reconnus(self):
        z = greffon_jouet.compresser(b"abc" * 100)
        self.assertIsNone(greffon_jouet.decompresser(z[:-1]))
        self.assertIsNone(greffon_jouet.decompresser(z + b"\x00"))
        self.assertIsNone(greffon_jouet.decompresser(z[:-4] + bytes(4)))


class TestCopieDesSources(unittest.TestCase):
    def test_liens_refuses(self):
        depot, destination = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            shutil.copyfile(os.path.join(JOUET, "rle.h"), os.path.join(depot, "rle.h"))
            os.symlink("/etc/hostname", os.path.join(depot, "rle.c"))
            with self.assertRaises(lecture.Refus):
                juge.copier_sources(depot, destination, ["rle.c", "rle.h"], ["rle.c", "rle.h"])
        finally:
            shutil.rmtree(depot)
            shutil.rmtree(destination)

    def test_sous_dossier(self):
        depot, destination = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(depot, "src"))
            open(os.path.join(depot, "src", "a.c"), "w").close()
            os.symlink("/etc", os.path.join(depot, "piege"))
            juge.copier_sources(depot, destination, ["src/*.c", "piege/*"], ["src/a.c"])
            self.fail("le dossier lien aurait dû être refusé")
        except lecture.Refus:
            pass
        finally:
            shutil.rmtree(depot)
            shutil.rmtree(destination)


class TestImage(unittest.TestCase):
    def test_paquets(self):
        self.assertIn("RUN apt-get update", conteneur.dockerfile(["zlib1g-dev"]))
        self.assertTrue(conteneur.dockerfile([]).rstrip().endswith("WORKDIR /"))
        for mauvais in ("x; curl", "-y", "A"):
            with self.assertRaises(lecture.Erreur):
                conteneur.dockerfile([mauvais])



# ------------------------------------------------------------------ juge.yml (ruche-0024): read and run its scripts

JUGE_YML = os.path.join(os.path.dirname(os.path.dirname(ICI)), ".github", "workflows", "juge.yml")
try:
    import yaml
except ImportError:  # the registry's CI (validation.yml) installs PyYAML; the Docker meta-test job may not have it
    yaml = None


def workflow_juge():
    with open(JUGE_YML, encoding="utf-8") as f:
        texte = f.read()
    donnees = yaml.safe_load(texte)
    donnees["on"] = donnees.pop(True)  # YAML 1.1: the key « on » reads as true
    return texte, donnees


def etape(donnees, job, nom):
    trouvees = [e for e in donnees["jobs"][job]["steps"] if e.get("name") == nom]
    if len(trouvees) != 1:
        raise AssertionError(f"step {nom!r} of job {job!r} not found exactly once in juge.yml")
    return trouvees[0]


def commandes_du_runner(sortie):
    """Workflow commands the GitHub Actions runner would act on in a step's output (actions/runner,
    ActionCommandManager): « ::name properties::data » at the start of a line (leading blanks ignored) and
    « ##[name properties]data » anywhere in it; lines split at \\n, \\r\\n and lone \\r. After
    « ::stop-commands::TOKEN », none until a command named TOKEN, which resumes them."""
    vues, jeton = [], None
    for ligne in re.split(r"\r\n|\r|\n", sortie):
        ligne = ligne.lstrip()
        m = re.match(r"::([^\s:]+)[^:]*::(.*)", ligne) or re.search(r"##\[([^\s\]]+)[^\]]*\](.*)", ligne)
        if not m:
            continue
        nom, donnees = m.group(1), m.group(2)
        if jeton is not None:
            if nom.lower() == jeton.lower():
                jeton = None
                vues.append("<resume>")
            continue
        if nom == "stop-commands":
            jeton = donnees
        vues.append(nom)
    return vues


@unittest.skipUnless(yaml, "PyYAML required (pip install -r outils/requirements.txt)")
class TestWorkflowJuge(unittest.TestCase):
    """juge.yml reads the judge at its own commit, prints the journal without workflow commands, judges on two
    architectures with one seed and merges their reports (ruche-0024)."""

    @classmethod
    def setUpClass(cls):
        cls.texte, cls.wf = workflow_juge()

    def lancer(self, script, env, dossier):
        environnement = {"PATH": os.environ["PATH"], "HOME": dossier, **env}
        return subprocess.run(["bash", "-e", "-c", script], cwd=dossier, env=environnement, capture_output=True, text=True,
                              timeout=120)

    def test_judge_code_read_at_the_workflow_commit(self):
        """No tag, no branch: the registry is checked out at job.workflow_repository@job.workflow_sha, validated first."""
        self.assertNotIn("JUGE_COMMUN_REF", self.texte)
        self.assertIn(f"juge-v{juge.VERSION_COMMUNE}", self.texte)  # the version label stays named in the usage comment
        prep = etape(self.wf, "preparation", "Commit de ce workflow (code du juge) et graine commune aux architectures")
        self.assertEqual(prep["env"], {"DEPOT": "${{ job.workflow_repository }}", "COMMIT": "${{ job.workflow_sha }}"})
        extractions = 0
        for job, contenu in self.wf["jobs"].items():
            for e in contenu["steps"]:
                if str(e.get("uses", "")).startswith("actions/checkout@") and e["with"].get("path") == "juge-commun":
                    extractions += 1
                    self.assertIn("preparation", contenu["needs"])
                    self.assertEqual(e["with"]["repository"], "${{ needs.preparation.outputs.depot }}")
                    self.assertEqual(e["with"]["ref"], "${{ needs.preparation.outputs.commit }}")
                elif str(e.get("uses", "")).startswith("actions/checkout@"):
                    self.assertNotIn("repository", e["with"], f"{job}: only the judge comes from another repository")
        self.assertEqual(extractions, 2)
        self.assertEqual(self.wf["jobs"]["rapport"]["if"], "always() && needs.preparation.result == 'success'")

    def test_preparation_fails_closed(self):
        script = etape(self.wf, "preparation", "Commit de ce workflow (code du juge) et graine commune aux architectures")["run"]
        bon = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory() as d:
            sortie = os.path.join(d, "sortie")
            for depot, commit in (("", ""), ("Bee-ruche/registre", ""), ("Bee-ruche/registre", "juge-v2"),
                                  ("Bee-ruche/registre", "main"), ("Bee-ruche/registre", bon[:39]), ("", bon),
                                  ("Bee-ruche/registre", bon + "\nx"), ("a/b;c", bon)):
                with self.subTest(depot=depot, commit=commit):
                    open(sortie, "w").close()
                    r = self.lancer(script, {"DEPOT": depot, "COMMIT": commit, "GITHUB_OUTPUT": sortie}, d)
                    self.assertNotEqual(r.returncode, 0)
                    with open(sortie) as f:
                        self.assertEqual(f.read(), "")
            open(sortie, "w").close()
            r = self.lancer(script, {"DEPOT": "Bee-ruche/registre", "COMMIT": bon, "GITHUB_OUTPUT": sortie}, d)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(sortie) as f:
                lignes = f.read().splitlines()
        self.assertEqual(lignes[:2], ["depot=Bee-ruche/registre", f"commit={bon}"])
        self.assertRegex(lignes[2], r"^graine=[0-9a-f]{32}$")

    def test_two_architectures_one_seed(self):
        juge_job = self.wf["jobs"]["juge"]
        self.assertFalse(juge_job["strategy"]["fail-fast"])  # an ARM64 failure never cancels the x86-64 judgment
        self.assertEqual(juge_job["strategy"]["matrix"], {"architecture": list(juge.ARCHITECTURES_JUGEES)})
        self.assertEqual(juge_job["runs-on"], "${{ matrix.architecture == 'arm64' && 'ubuntu-24.04-arm' || 'ubuntu-24.04' }}")
        envoi = etape(self.wf, "juge", "Conserver le rapport")
        self.assertEqual((envoi["if"], envoi["with"]["name"]), ("always()", "juge-${{ matrix.architecture }}"))
        env = etape(self.wf, "juge", "Juger")["env"]
        self.assertEqual(env["GRAINE"], "${{ needs.preparation.outputs.graine }}")
        self.assertEqual(env["SANS_INSTRUCTIONS"], "${{ inputs.sans_instructions || matrix.architecture != 'x86_64' }}")
        self.assertIn('--graine "$GRAINE"', etape(self.wf, "juge", "Juger")["run"])
        self.assertEqual(self.wf["on"]["workflow_call"]["outputs"]["code"]["value"], "${{ jobs.rapport.outputs.code }}")

    def test_history_input_reaches_the_judge_through_the_environment(self):
        """The declared history is never interpolated into a script, and is fetched in the network step, before the PR."""
        self.assertEqual(self.wf["on"]["workflow_call"]["inputs"]["historique"]["type"], "string")
        noms = [e.get("name") for e in self.wf["jobs"]["juge"]["steps"]]
        image = etape(self.wf, "juge", "Image du juge et historique déclaré (seule étape avec réseau, avant tout fichier de la PR)")
        self.assertEqual(image["env"], {"HISTORIQUE": "${{ inputs.historique }}"})
        self.assertIn('--historique "$HISTORIQUE"', image["run"])
        self.assertLess(noms.index(image["name"]), noms.index("Tête de la PR (données ; rien n'en est exécuté hors conteneur)"))
        for job in self.wf["jobs"].values():
            for e in job["steps"]:
                self.assertNotIn("${{ inputs.", e.get("run", ""), "inputs reach scripts through env only")

    def test_journal_cannot_issue_workflow_commands(self):
        """The judged PR fills the journal; printed between ::stop-commands::<token> and ::<token>::, none of its lines
        is a workflow command for the runner (a line ::error:: in the journal, among others)."""
        script = etape(self.wf, "juge", "Juger")["run"]
        hostile = ("juge : début\n::error::injected annotation\n  ::add-mask::abc\n::stop-commands::faux\n::faux::\n"
                   "::error::after a forged resume\n##[error]old syntax\nx\r::warning::after a carriage return\n"
                   "::set-output name=code::0\n::warning file=rle.c,line=1::props")
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "juge-commun", "outils", "juge"))
            with open(os.path.join(d, "juge-commun", "outils", "juge", "juge.py"), "w", encoding="utf-8") as f:
                f.write(f"import sys\nsys.stderr.write({hostile!r})\nsys.exit(1)\n")
            r = self.lancer(script, {"OPTIONS": "sortie_compressee=identique", "REPETITIONS": "2", "SANS_INSTRUCTIONS": "false",
                                     "GRAINE": "00" * 16, "SOURCE": "Bee-ruche/registre@" + "0" * 40}, d)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(d, "resultats", "code")) as f:
                self.assertEqual(f.read().strip(), "1")
            with open(os.path.join(d, "resultats", "journal.txt"), newline="") as f:
                journal = f.read()
        self.assertEqual(journal, hostile)
        self.assertGreaterEqual(len([c for c in commandes_du_runner(journal) if c != "<resume>"]), 6)  # the simulator sees them
        lignes = r.stdout.splitlines()
        jeton = re.fullmatch(r"::stop-commands::([0-9a-f]{64})", lignes[0]).group(1)
        self.assertEqual(lignes[-1], f"::{jeton}::")
        self.assertNotIn(jeton, journal)
        self.assertEqual(r.stdout.count(jeton), 2)
        self.assertEqual(commandes_du_runner(r.stdout), ["stop-commands", "<resume>"])

    def test_merge_step(self):
        script = etape(self.wf, "rapport", "Un rapport pour toutes les architectures (sans rapport x86-64 lisible, code 2)")["run"]
        self.assertIn('--fusionner architectures >> "$GITHUB_OUTPUT"', script)
        envoi = etape(self.wf, "rapport", "Conserver le rapport")
        self.assertEqual((envoi["with"]["name"], envoi["with"]["path"]), ("juge", "architectures/"))


def rapport_simule(arch, gain, au_dela, autres=()):
    """A juge.json as one judging job writes it: its metrics, and its timer under its architecture's key."""
    m = {"debit_compression": {"sens": "plus_haut", "gain": gain, "au_dela_du_bruit": au_dela}}
    chronos = {a: {"machine": {"architecture": a}, "metriques": m} for a in (arch,) + tuple(autres)}
    return {"metriques": m, "juge": {"commun": f"juge-v{juge.VERSION_COMMUNE}", "projet": "jouet"}, "chronometres": chronos}


class TestFusion(unittest.TestCase):
    """juge.yml's last job: the x86-64 report gathers every architecture's timer, each from its own job."""

    def setUp(self):
        self.dossier = tempfile.mkdtemp(prefix="bee-fusion-")

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def deposer(self, arch, code, rapport=None, brut=None):
        d = os.path.join(self.dossier, f"juge-{arch}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "code"), "w") as f:
            f.write(f"{code}\n")
        if rapport is not None or brut is not None:
            with open(os.path.join(d, "juge.json"), "w") as f:
                f.write(brut if brut is not None else json.dumps(rapport))

    def fusion(self):
        code = juge.fusionner(self.dossier)
        with open(os.path.join(self.dossier, "code")) as f:
            self.assertEqual(f.read(), f"{code}\n")
        chemin = os.path.join(self.dossier, "juge.json")
        if not os.path.exists(chemin):
            return code, None
        with open(chemin) as f:
            return code, json.load(f)

    def test_gain_on_one_architecture_is_seen_only_there(self):
        self.deposer("x86_64", 0, rapport_simule("x86_64", 0.001, False))
        self.deposer("arm64", 0, rapport_simule("arm64", 0.40, True))
        code, r = self.fusion()
        self.assertEqual(code, 0)
        self.assertEqual(set(r["chronometres"]), {"x86_64", "arm64"})
        self.assertTrue(r["chronometres"]["arm64"]["metriques"]["debit_compression"]["au_dela_du_bruit"])
        self.assertFalse(r["chronometres"]["x86_64"]["metriques"]["debit_compression"]["au_dela_du_bruit"])
        self.assertFalse(r["metriques"]["debit_compression"]["au_dela_du_bruit"])  # the report's own metrics stay x86-64's
        self.assertEqual((r["chronometres"]["x86_64"]["code"], r["chronometres"]["arm64"]["code"]), (0, 0))

    def test_each_timer_comes_from_its_own_job(self):
        """The ARM64 job's report cannot write the x86-64 timer, and a job that ran elsewhere publishes nothing."""
        self.deposer("x86_64", 0, rapport_simule("x86_64", 0.0, False))
        self.deposer("arm64", 0, rapport_simule("arm64", 0.0, False, autres=("x86_64",)))
        faux = rapport_simule("arm64", 9.0, True)["chronometres"]["arm64"]
        with open(os.path.join(self.dossier, "juge-arm64", "juge.json")) as f:
            arm = json.load(f)
        arm["chronometres"]["x86_64"] = faux
        self.deposer("arm64", 0, arm)
        code, r = self.fusion()
        self.assertEqual(r["chronometres"]["x86_64"]["metriques"]["debit_compression"]["gain"], 0.0)
        self.deposer("arm64", 0, rapport_simule("x86_64", 9.0, True))  # the "arm64" job ran on x86-64
        code, r = self.fusion()
        self.assertEqual((code, r["chronometres"]["arm64"]), (0, {"code": 2}))

    def test_codes(self):
        cas = [  # (x86-64 code, x86-64 report, arm64 code, arm64 report) -> (code, juge.json written, arm64 entry)
            ((0, True), (1, False), 1, True, {"code": 1}),
            ((0, True), (2, False), 0, True, {"code": 2}),
            ((0, True), None, 0, True, {"code": 2}),
            ((1, False), (0, True), 1, False, None),
            ((2, False), (0, True), 2, False, None),
            ((2, False), (1, False), 2, False, None),
            (None, (0, True), 2, False, None),
            ((0, False), (0, True), 2, False, None),
        ]
        for x86, arm, attendu, ecrit, entree in cas:
            with self.subTest(x86=x86, arm=arm):
                shutil.rmtree(self.dossier)
                os.makedirs(self.dossier)
                if x86:
                    self.deposer("x86_64", x86[0], rapport_simule("x86_64", 0.0, False) if x86[1] else None)
                if arm:
                    self.deposer("arm64", arm[0], rapport_simule("arm64", 0.0, False) if arm[1] else None)
                code, r = self.fusion()
                self.assertEqual(code, attendu)
                self.assertEqual(r is not None, ecrit)
                if entree:
                    self.assertEqual(r["chronometres"]["arm64"], entree)

    def test_unreadable_reports(self):
        for code, brut in (("0", "{"), ("0", "[]"), ("0", '{"chronometres": {"x86_64": 3}}'), ("7", None),
                           ("0; echo", '{}'), ("", None)):
            with self.subTest(code=code, brut=brut):
                shutil.rmtree(self.dossier)
                os.makedirs(os.path.join(self.dossier, "juge-x86_64"))
                with open(os.path.join(self.dossier, "juge-x86_64", "code"), "w") as f:
                    f.write(code)
                if brut is not None:
                    with open(os.path.join(self.dossier, "juge-x86_64", "juge.json"), "w") as f:
                        f.write(brut)
                self.deposer("arm64", 0, rapport_simule("arm64", 0.0, False))
                self.assertEqual(self.fusion(), (2, None))

    def test_command_line(self):
        self.deposer("x86_64", 0, rapport_simule("x86_64", 0.0, False))
        self.deposer("arm64", 1)
        r = subprocess.run([sys.executable, os.path.join(ICI, "juge.py"), "--fusionner", self.dossier],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual((r.returncode, r.stdout), (0, "code=1\n"))


def git_test(depot, *args):
    return subprocess.run(["git", "-C", depot, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "protocol.file.allow=always"]
                          + list(args), capture_output=True, text=True, check=True).stdout.strip()


def depot_jouet_avec_historique(travail):
    """An origin whose older commit X has another rle.c, and a base cloned from it without history (as actions/checkout
    does): X's objects are not in the base. Returns (origin, base, X, rle.c at X)."""
    source, origine, base = (os.path.join(travail, n) for n in ("source", "origine.git", "base"))
    shutil.copytree(JOUET, source, ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(source, "rle.c"), "a", encoding="utf-8") as f:
        f.write("/* rle.c as it was at the corpus commit */\n")
    subprocess.run(["git", "init", "-q", "-b", "main", source], check=True)
    git_test(source, "add", "-A")
    git_test(source, "commit", "-qm", "X")
    commit = git_test(source, "rev-parse", "HEAD")
    with open(os.path.join(source, "rle.c"), "rb") as f:
        ancien = f.read()
    shutil.copyfile(os.path.join(JOUET, "rle.c"), os.path.join(source, "rle.c"))
    git_test(source, "commit", "-qam", "Y")
    subprocess.run(["git", "clone", "-q", "--bare", source, origine], check=True)
    subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + origine, base], check=True)
    return origine, base, commit, ancien


@unittest.skipUnless(shutil.which("git"), "git required")
class TestHistorique(unittest.TestCase):
    """juge.yml's `historique` input: the commits a plugin reads are fetched into the base before the PR, then judging
    runs without any git transport (ruche-0024)."""

    def setUp(self):
        self.travail = tempfile.mkdtemp(prefix="bee-historique-")
        self.origine, self.base, self.commit, self.ancien = depot_jouet_avec_historique(self.travail)

    def tearDown(self):
        shutil.rmtree(self.travail, ignore_errors=True)

    def test_declared_commit_is_read_without_network(self):
        self.assertEqual(juge.recuperer_historique(self.base, f" {self.commit}\n{self.commit} "), [self.commit])
        os.rename(self.origine, self.origine + ".parti")  # from now on, no origin to fetch from
        projet = greffon_jouet.Projet({"commit_corpus": self.commit})
        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "none"}):
            corpus = projet.corpus(self.base)
        self.assertEqual(corpus[-1][1], self.ancien)
        self.assertEqual(projet.VERIFICATION["historique"], f"{self.commit}:rle.c ({len(self.ancien)} octets)")

    def test_undeclared_commit_fails_cleanly(self):
        with self.assertRaises(lecture.Erreur) as e:
            greffon_jouet.Projet({"commit_corpus": self.commit}).corpus(self.base)
        self.assertIn("historique", str(e.exception))
        with self.assertRaises(lecture.Erreur):
            greffon_jouet.Projet({"commit_corpus": "HEAD"})

    def test_declared_history_is_checked(self):
        for texte in ("abc", self.commit[:39], self.commit.upper(), "--upload-pack=touch /tmp/x", f"{self.commit}:refs/x",
                      " ".join(f"{i:040x}" for i in range(juge.HISTORIQUE_MAX + 1))):
            with self.subTest(texte=texte):
                with mock.patch.object(juge.subprocess, "run") as run, self.assertRaises(lecture.Erreur):
                    juge.recuperer_historique(self.base, texte)
                run.assert_not_called()
        self.assertEqual(juge.recuperer_historique(self.base, ""), [])
        with self.assertRaises(lecture.Erreur) as e:
            juge.recuperer_historique(self.base, "0123456789abcdef0123456789abcdef01234567")
        self.assertIn("not fetched", str(e.exception))

    def test_judging_refuses_every_git_transport(self):
        """In judging mode the judge sets GIT_ALLOW_PROTOCOL before loading the plugin; a plugin's own fetch then fails."""
        vus = {}

        def charger(outillage, options):
            vus["GIT_ALLOW_PROTOCOL"] = os.environ.get("GIT_ALLOW_PROTOCOL")
            raise lecture.Erreur("stop")
        for image, attendu in ((False, "none"), (True, None)):
            with mock.patch.dict(os.environ), mock.patch.object(juge.shutil, "which", return_value="/usr/bin/docker"), \
                    mock.patch.object(juge, "charger_greffon", side_effect=charger), self.assertRaises(lecture.Erreur):
                os.environ.pop("GIT_ALLOW_PROTOCOL", None)
                juge.main(["--outillage", self.base] + (["--image-seulement"] if image else ["--source-a", "a", "--source-b", "b"]))
            self.assertEqual(vus["GIT_ALLOW_PROTOCOL"], attendu)
        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "none"}), self.assertRaises(lecture.Erreur):
            juge.recuperer_historique(self.base, self.commit)


# ------------------------------------------------------------------ meta-tests of the analysis (built on the host, no Docker)

OUTILS_LOCAUX = all(shutil.which(o) for o in ("sh", "cc", "nm", "objdump"))


class DockerLocal:
    """Stand-in for conteneur.Docker: runs the judge's build and analysis commands on the host, each mount target
    replaced by its host path. Only the toy project and the fixtures below are built this way; nothing built is run."""

    def __init__(self, outils=None):
        self.outils = outils

    def lancer(self, commande, montages, pids=2, entree=None, delai=3600):
        cibles = {cible: hote for hote, cible, _ in montages}
        motif = re.compile("|".join(re.escape(c) for c in sorted(cibles, key=len, reverse=True)))
        env = dict(os.environ)
        if self.outils:
            env["PATH"] = self.outils + os.pathsep + env["PATH"]
        return subprocess.run([motif.sub(lambda m: cibles[m.group(0)], c) for c in commande], capture_output=True,
                              env=env, timeout=delai)


def construire_jouet(travail, etiquette="B", ajout="", docker=None):
    """The toy project, `ajout` appended to rle.c, built and surveyed as the judge does; returns (releves, sources)."""
    projet = greffon_jouet.Projet({})
    os.makedirs(travail)
    depot = os.path.join(travail, "depot")
    shutil.copytree(JOUET, depot, ignore=shutil.ignore_patterns("bee", "__pycache__"))
    with open(os.path.join(depot, "rle.c"), "a", encoding="utf-8") as f:
        f.write(ajout)
    sources = juge.copier_sources(depot, os.path.join(travail, "sources"), projet.SOURCES, projet.SOURCES_REQUISES)
    outils = juge.copier_outillage(JOUET, JOUET, os.path.join(travail, "outillage"), projet)
    releves = juge.construire(docker or DockerLocal(), projet, sources, outils, os.path.join(travail, "construction"),
                              etiquette, travail)
    return releves, sources


def octets_asm(hexa, section=".text", fin="ret"):
    return '__asm__("%s\\n.p2align 4\\nrle_seeded_%s:\\n.byte %s\\n%s\\n.previous\\n");\n' % (
        section, hexa, ", ".join("0x" + hexa[i:i + 2] for i in range(0, len(hexa), 2)), fin)


SEEDED_CONSTRUCTS = {
    "syscall": "0f05", "sysenter": "0f34", "int": "cd80", "rdtsc": "0f31", "rdtscp": "0f01f9", "rdpmc": "0f33",
    "cpuid": "0fa2", "xgetbv": "0f01d0", "rdrand": "0fc7f0", "rdseed": "0fc7f8", "rdpid": "f30fc7f8",
    "preambule_valgrind": "48c1c70348c1c70d48c1c73d48c1c733",
}
# Every x86-64 prefix byte: legacy prefixes, then REX.
PREFIXES_OCTETS = ["26", "2e", "36", "3e", "64", "65", "66", "67", "f0", "f2", "f3"] + [f"{r:02x}" for r in range(0x40, 0x50)]
# variant: (bytes before the construct, length it is padded to, bytes after it, ending its own section)
VARIANTS = {"variant_a": ("", 0, None), "variant_b": ("06", 0, None), "variant_c": ("48b8", 8, None),
            "variant_d": ("b8", 4, None), "variant_e": ("", 0, "0f")}
VARIANTS.update({f"variant_{i:02d}": (p, 0, None) for i, p in enumerate(PREFIXES_OCTETS)})
# f2 and f3 select other instructions for some of these opcodes.
SHOWN_BY_DISASSEMBLY = ["variant_a"] + [f"variant_{i:02d}" for i, p in enumerate(PREFIXES_OCTETS) if p not in ("f2", "f3")]


@unittest.skipUnless(OUTILS_LOCAUX, "sh, cc, nm and objdump required")
class TestSeededObjects(unittest.TestCase):
    """Constructs seeded into the object of the toy project, built and surveyed as the judge does; analysed, never run."""

    @classmethod
    def setUpClass(cls):
        cls.travail = tempfile.mkdtemp(prefix="bee-seeded-")
        cls.a, cls.sources_a = construire_jouet(os.path.join(cls.travail, "A"), "A")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.travail, ignore_errors=True)

    def analyse_de(self, nom, ajout):
        b, sources_b = construire_jouet(os.path.join(self.travail, nom), "B", ajout)
        return analyse.analyser(self.a, b, juge.textes(self.sources_a), juge.textes(sources_b), prefixes=("rle_",))

    def test_honest(self):
        self.assertEqual(self.analyse_de("honest", ""), [])

    def test_every_family_seeded(self):
        self.assertEqual(set(SEEDED_CONSTRUCTS), set(analyse.SEQUENCES))

    def test_seeded_constructs_found(self):
        def cas(c, v):
            avant, longueur, apres = VARIANTS[v]
            hexa = avant + SEEDED_CONSTRUCTS[c] + "90" * max(0, longueur - len(SEEDED_CONSTRUCTS[c]) // 2)
            if apres is None:
                return self.analyse_de(f"{c}-{v}", octets_asm(hexa))
            return self.analyse_de(f"{c}-{v}", octets_asm(hexa + apres, '.section .text.rle_e,\\"ax\\",@progbits', ""))
        liste = [(c, v) for c in SEEDED_CONSTRUCTS for v in VARIANTS]
        with concurrent.futures.ThreadPoolExecutor(max(2, os.cpu_count() or 2)) as pool:
            resultats = dict(zip(liste, pool.map(lambda cv: cas(*cv), liste)))
        for (c, v), suspects in resultats.items():
            with self.subTest(construct=c, variant=v):
                octets = [s["detail"] for s in suspects if s["type"] == "octets"]
                self.assertTrue(any(d.startswith(c + ":") and "objects'" in d for d in octets), octets)
                self.assertTrue(any(d.startswith(c + ":") and "program's" in d for d in octets), octets)
                instructions = [s["detail"].split(" ")[0] for s in suspects if s["type"] == "instruction"]
                if v in SHOWN_BY_DISASSEMBLY:
                    self.assertIn(c, instructions)
                if v == "variant_b":
                    self.assertIn("(bad)", instructions)
                if v == "variant_e":
                    self.assertIn(".byte", instructions)
                self.assertEqual({s["type"] for s in suspects} - {"octets", "instruction", "source"}, set())

    def test_seeded_construct_int3(self):
        self.assertIn("int3", [s["detail"].split(" ")[0] for s in self.analyse_de("int3", octets_asm("cc"))
                               if s["type"] == "instruction"])

    def test_bytes_read_independently(self):
        b, _ = construire_jouet(os.path.join(self.travail, "independent"), "B", octets_asm("0f05"))
        b["desassemblage"] = self.a["desassemblage"]
        self.assertEqual({s["type"] for s in analyse.analyser(self.a, b, {}, {}, prefixes=("rle_",))}, {"octets"})

    def test_variant_f(self):
        suspects = self.analyse_de("variant_f", octets_asm("900f0590", '.section .data.rle_x,\\"ax\\",@progbits'))
        self.assertTrue(any(s["detail"].startswith("syscall:") and "objects'" in s["detail"] for s in suspects), suspects)

    def test_variant_t(self):
        """Each new hit is reported by its place and context."""
        travail = os.path.join(self.travail, "variant_t")
        a, sources_a = construire_jouet(os.path.join(travail, "A"), "A", octets_asm("48b80f31909090909090"))
        for nom, ajout in (("same", octets_asm("48b80f31909090909090")), ("other", octets_asm("b80f319090"))):
            b, sources_b = construire_jouet(os.path.join(travail, nom), "B", ajout)
            suspects = analyse.analyser(a, b, juge.textes(sources_a), juge.textes(sources_b), prefixes=("rle_",))
            octets = [s["detail"] for s in suspects if s["type"] == "octets"]
            if nom == "same":
                self.assertEqual(suspects, [])
            else:
                self.assertTrue(any(d.startswith("rdtsc:") and "objects'" in d for d in octets), octets)
                self.assertTrue(any(d.startswith("rdtsc:") and "program's" in d for d in octets), octets)

    def test_memory_flags(self):
        for nom, ajout, drapeau in (
                ("variant_r", '__asm__(".section .note.GNU-stack,\\"x\\",@progbits\\n.previous\\n");\n', "pile_executable"),
                ("variant_s", '__asm__(".section .data.rle_x,\\"awx\\",@progbits\\n.byte 0\\n.previous\\n");\n', "segment_wx")):
            with self.subTest(variant=nom):
                octets = [s["detail"] for s in self.analyse_de(nom, ajout) if s["type"] == "octets"]
                self.assertTrue(any(d.startswith(drapeau + ":") for d in octets), octets)

    def test_unreadable_object(self):
        b, _ = construire_jouet(os.path.join(self.travail, "unreadable"), "B")
        b["objets"] = [(nom, donnees[:len(donnees) // 2]) for nom, donnees in b["objets"]]
        self.assertIn("analyse_incomplete", {s["type"] for s in analyse.analyser(self.a, b, {}, {}, prefixes=("rle_",))})


SEEDED_LINES = [
    '__asm__ volatile("");', 'static void rle_h(void) { asm(""); }',
    '#include <time.h>', '%:include <sys/syscall.h>', '#include "time.h"', '#  include_next <unistd.h>',
    '__attribute__((used, constructor)) static void rle_f(void) {}', '__as\\\nm volatile("");', '__as\\  \r\nm("");',
    '__attribute__ ((\nconstructor)) static void rle_g(void) {}', 'static unsigned long rle_t(void) { return __rdtsc(); }',
    '#define RLE_C(a, b) a %:%: b', '_Pragma("GCC optimize(0)")',
]


class TestSeededText(unittest.TestCase):
    """A construct added anywhere in a judged file is found: each file of B is read whole, against A's."""

    def test_seeded_line_found_anywhere(self):
        a = {}
        for nom in ("rle.c", "rle.h"):
            with open(os.path.join(JOUET, nom), encoding="latin-1") as f:
                a[nom] = f.read()
        self.assertEqual(analyse.analyser(releves(), releves(), a, dict(a)), [])
        for nom, texte in a.items():
            lignes = texte.split("\n")
            for seeded in SEEDED_LINES:
                for i in range(len(lignes) + 1):
                    b = dict(a, **{nom: "\n".join(lignes[:i] + [seeded] + lignes[i:])})
                    types = [s["type"] for s in analyse.analyser(releves(), releves(), a, b)]
                    if "source" not in types:
                        self.fail(f"{nom}, line {i + 1}: {seeded!r} not found")


@unittest.skipUnless(OUTILS_LOCAUX, "sh, cc, nm and objdump required")
class TestFailClosed(unittest.TestCase):
    """A failing tool never leaves the judge complete."""

    def setUp(self):
        self.travail = tempfile.mkdtemp(prefix="bee-tools-")
        self.outils = os.path.join(self.travail, "outils")
        os.makedirs(self.outils)

    def tearDown(self):
        shutil.rmtree(self.travail, ignore_errors=True)

    def outil(self, nom, script):
        chemin = os.path.join(self.outils, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n" + script + "\n")
        os.chmod(chemin, 0o755)

    def test_disassembler_or_nm_failure(self):
        objdump, nm = shutil.which("objdump"), shutil.which("nm")
        scenarios = [("objdump", "exit 1"), ("objdump", f'"{objdump}" "$@"; exit 1'), ("objdump", "exit 0"),
                     ("objdump", f'case "$1" in -d) exit 2;; esac; exec "{objdump}" "$@"'), ("nm", f'"{nm}" "$@"; exit 1')]
        for i, (nom, script) in enumerate(scenarios):
            for f in os.listdir(self.outils):
                os.remove(os.path.join(self.outils, f))
            self.outil(nom, script)
            for etiquette in "AB":
                with self.subTest(outil=nom, script=script, etiquette=etiquette):
                    with self.assertRaises((lecture.Refus, lecture.Erreur)):
                        construire_jouet(os.path.join(self.travail, f"{i}{etiquette}"), etiquette, docker=DockerLocal(self.outils))

    def test_git_failure(self):
        marque = os.path.join(self.travail, "git-called")
        self.outil("git", f'touch "{marque}"; exit 1')
        with mock.patch.dict(os.environ, {"PATH": self.outils + os.pathsep + os.environ["PATH"]}):
            a, sources_a = construire_jouet(os.path.join(self.travail, "A"), "A")
            b, sources_b = construire_jouet(os.path.join(self.travail, "B"), "B", "#include <time.h>\n")
            suspects = analyse.analyser(a, b, juge.textes(sources_a), juge.textes(sources_b), prefixes=("rle_",))
        self.assertEqual([s["type"] for s in suspects], ["source"])
        self.assertFalse(os.path.exists(marque))


# ------------------------------------------------------------------ méta-tests (Docker)

DEBUT_COMPRESSER = """size_t rle_compresser(const unsigned char *src, size_t n, unsigned char *dst)
{
    unsigned long table[256];
    size_t i = 0, debut = 0, o = 4;
    rle_table_crc(table);
"""
INCLUDE = '#include "rle.h"\n'


def remplacer(texte, ancien, nouveau):
    if texte.count(ancien) != 1:
        raise AssertionError(f"marqueur introuvable ou ambigu dans rle.c : {ancien[:60]!r}")
    return texte.replace(ancien, nouveau)


def sortie_anticipee(texte, corpus):
    texte = remplacer(texte, INCLUDE, INCLUDE + "#include <stdlib.h>\nstatic int rle_appels = 0;\n")
    return remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER + "    if (++rle_appels > 3)\n        exit(0);\n")


def faux_chronos(texte, corpus):
    texte = remplacer(texte, INCLUDE, INCLUDE + "#include <time.h>\n"
                      "int clock_gettime(clockid_t c, struct timespec *t) { (void)c; t->tv_sec = 0; t->tv_nsec = 1; return 0; }\n")
    return remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER +
                     "    { volatile unsigned long rle_k; for (rle_k = 0; rle_k < (unsigned long)n * 200; rle_k++) ; }\n")


def table_precalculee(texte, corpus):
    tailles = ", ".join(str(len(d)) for _, d in corpus)
    texte = remplacer(texte, INCLUDE, INCLUDE + f"static const unsigned long rle_connues[] = {{ {tailles} }};\n")
    return remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER +
                     "    { size_t k; int vu = 0;\n"
                     "      for (k = 0; k < sizeof(rle_connues) / sizeof(rle_connues[0]); k++) vu |= rle_connues[k] == n;\n"
                     "      if (!vu) return 0; }\n")


def requete_valgrind(texte, corpus):
    texte = remplacer(texte, INCLUDE, INCLUDE + "#include <valgrind/cachegrind.h>\n")
    texte = remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER + "    CACHEGRIND_STOP_INSTRUMENTATION;\n")
    return remplacer(texte, "    rle_ecrire32(dst + o, rle_crc(table, src, n));\n    return o + 4;\n",
                     "    rle_ecrire32(dst + o, rle_crc(table, src, n));\n    CACHEGRIND_START_INSTRUMENTATION;\n    return o + 4;\n")


def faux_resume(texte, corpus):
    texte = remplacer(texte, INCLUDE, INCLUDE + "#include <stdio.h>\n")
    return remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER + '    fputs("==1== I   refs:        1\\n", stderr);\n')


def jetons_scindes(texte, corpus):
    """Préambule des requêtes Valgrind en assembleur, le mot « asm » formé par concaténation de jetons."""
    texte = remplacer(texte, INCLUDE, INCLUDE + "#define RLE_COLLE(a, b) a##b\n#define RLE_Z RLE_COLLE(a, sm)\n")
    return remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER +
                     '    RLE_Z volatile("rol $3, %%rdi\\n\\trol $13, %%rdi\\n\\trol $61, %%rdi\\n\\trol $51, %%rdi" ::: "rdi");\n')


def appel_blanchi_par_prefixe(texte, corpus):
    texte = remplacer(texte, INCLUDE, INCLUDE + "#include <stdlib.h>\n")
    return remplacer(texte, DEBUT_COMPRESSER, DEBUT_COMPRESSER + '    { char *volatile e = getenv("BEE_SECRET"); (void)e; }\n')


def travail_deplace(texte, corpus):
    """La table du CRC est construite d'avance dans rle_borne, que le harnais appelle juste avant de compresser."""
    texte = remplacer(texte, INCLUDE, INCLUDE + "#include <stdlib.h>\n")
    texte = remplacer(texte, """size_t rle_borne(size_t n)
{
""", """static unsigned long **rle_reserve = NULL;
static size_t rle_capacite = 0, rle_poses = 0, rle_pris = 0;

size_t rle_borne(size_t n)
{
    unsigned long *t = (unsigned long *)malloc(256 * sizeof(unsigned long));
    if (t)
        rle_table_crc(t);
    if (rle_poses == rle_capacite) {
        rle_capacite = rle_capacite ? 2 * rle_capacite : 64;
        rle_reserve = (unsigned long **)realloc(rle_reserve, rle_capacite * sizeof(*rle_reserve));
    }
    rle_reserve[rle_poses++] = t;
""")
    return remplacer(texte, DEBUT_COMPRESSER, """size_t rle_compresser(const unsigned char *src, size_t n, unsigned char *dst)
{
    unsigned long table_locale[256], *table = (rle_reserve && rle_pris < rle_poses) ? rle_reserve[rle_pris++] : NULL;
    size_t i = 0, debut = 0, o = 4;
    if (!table) {
        rle_table_crc(table_locale);
        table = table_locale;
    }
""")


@unittest.skipUnless(os.environ.get("BEE_JUGE_INTEGRATION") == "1" and shutil.which("docker"),
                     "méta-tests : BEE_JUGE_INTEGRATION=1 et Docker requis")
class TestJugeContreVariantes(unittest.TestCase):
    """Le juge commun complet, en conteneur, contre le projet jouet et des variantes malveillantes."""

    @classmethod
    def setUpClass(cls):
        cls.travail = tempfile.mkdtemp(prefix="bee-meta-commun-")
        cls.corpus = greffon_jouet.Projet({}).corpus(JOUET)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.travail, ignore_errors=True)

    def preparer(self, nom, transformation=None):
        source_b = os.path.join(self.travail, nom)
        os.makedirs(source_b)
        for fichier in ("rle.c", "rle.h"):
            shutil.copyfile(os.path.join(JOUET, fichier), os.path.join(source_b, fichier))
        if transformation:
            with open(os.path.join(source_b, "rle.c"), encoding="utf-8") as f:
                texte = f.read()
            with open(os.path.join(source_b, "rle.c"), "w", encoding="utf-8") as f:
                f.write(transformation(texte, self.corpus))
        return source_b

    def base_modifiee(self, nom, fichier, ancien, nouveau):
        """Copie du jouet (la BASE) dont un fichier d'outillage est modifié."""
        base = os.path.join(self.travail, "base-" + nom)
        shutil.copytree(JOUET, base, ignore=shutil.ignore_patterns("__pycache__"))
        chemin = os.path.join(base, fichier)
        with open(chemin, encoding="utf-8") as f:
            texte = f.read()
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(texte.replace(ancien, nouveau) if texte.count(ancien) >= 1 else remplacer(texte, ancien, nouveau))
        return base

    def juger(self, nom, source_b, sans_instructions=False, base=JOUET, repetitions=2, options=()):
        commande = [sys.executable, os.path.join(ICI, "juge.py"), "--outillage", base, "--source-a", base,
                    "--source-b", source_b, "--repetitions", str(repetitions), "--chauffe", "0"]
        for o in options:
            commande += ["--option", o]
        if sans_instructions:
            commande.append("--sans-instructions")
        if os.environ.get("BEE_JUGE_RESEAU"):
            commande += ["--reseau-construction", os.environ["BEE_JUGE_RESEAU"]]
        r = subprocess.run(commande, capture_output=True, text=True, timeout=1800)
        rapport = json.loads(r.stdout) if r.returncode == 0 else None
        print(f"\n[{nom}] code {r.returncode} : {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}", file=sys.stderr)
        return r.returncode, rapport, r.stderr

    def types_suspects(self, rapport):
        return {s["type"] for s in rapport["juge"]["constructions_suspectes"]}

    def test_honnete(self):
        code, rapport, _ = self.juger("honnete", self.preparer("honnete"))
        self.assertEqual(code, 0)
        self.assertEqual(rapport["juge"]["constructions_suspectes"], [])
        self.assertEqual(rapport["juge"]["projet"], "jouet")
        self.assertGreater(rapport["juge"]["verification"]["sorties_comparees"], 30)
        for m in rapport["instructions"].values():
            self.assertEqual(m["A"], m["B"])
        self.assertEqual(set(rapport["metriques"]), {"debit_compression", "debit_decompression", "ratio", "memoire_max_ko"})
        self.assertEqual(rapport["chronometres"], {architecture_ici(): {"machine": rapport["machine"], "metriques": rapport["metriques"]}})
        self.assertIsNone(rapport["juge"]["source"])  # named by juge.yml (--source-juge), not by a local run

    def test_historique_declare(self):
        """ruche-0024: the toy plugin reads rle.c at a commit the base does not have; declared, it is fetched with the
        image (before the PR), then the judge runs with the origin gone and every git transport refused."""
        origine, base, commit, ancien = depot_jouet_avec_historique(os.path.join(self.travail, "historique-declare"))
        r = subprocess.run([sys.executable, os.path.join(ICI, "juge.py"), "--outillage", base, "--image-seulement",
                            "--historique", commit] + (["--reseau-construction", os.environ["BEE_JUGE_RESEAU"]]
                                                       if os.environ.get("BEE_JUGE_RESEAU") else []),
                           capture_output=True, text=True, timeout=1800)
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.rmtree(origine)
        code, rapport, sortie = self.juger("historique_declare", self.preparer("historique_declare"), True, base=base,
                                          options=[f"commit_corpus={commit}"])
        self.assertEqual(code, 0, sortie)
        self.assertEqual(rapport["juge"]["verification"]["historique"], f"{commit}:rle.c ({len(ancien)} octets)")

    def test_historique_non_declare(self):
        """Not declared: a clean environment error (code 2), even for a plugin that tries to fetch it itself from an
        origin that is still there (minizBee's former workaround): judging has no git transport."""
        _, base, commit, _ = depot_jouet_avec_historique(os.path.join(self.travail, "historique-non-declare"))
        chemin = os.path.join(base, "bee", "juge", "projet.py")
        with open(chemin, encoding="utf-8") as f:
            texte = f.read()
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(remplacer(texte, '        r = subprocess.run(["git", "-C", outillage, "cat-file"',
                              '        subprocess.run(["git", "-C", outillage, "fetch", "-q", "--depth=1", "origin", '
                              'self.commit_corpus], capture_output=True, timeout=60)\n'
                              '        r = subprocess.run(["git", "-C", outillage, "cat-file"'))
        code, _, sortie = self.juger("historique_non_declare", self.preparer("historique_non_declare"), True, base=base,
                                     options=[f"commit_corpus={commit}"])
        self.assertEqual(code, 2)
        self.assertIn("historique", sortie)

    def test_faux_gain_sur_une_architecture(self):
        """ruche-0024: A is slowed down on one architecture only (a busy loop under #if): B's fake gain shows in that
        architecture's timer and not in the other's. Run on x86-64 and on ARM64 (juge-commun.yml)."""
        ici = architecture_ici()
        for cible, macro in (("x86_64", "__x86_64__"), ("arm64", "__aarch64__")):
            with self.subTest(lente=cible, ici=ici):
                base = self.base_modifiee("lente-" + cible, "rle.c", DEBUT_COMPRESSER, DEBUT_COMPRESSER +
                                          f"#if defined({macro})\n    {{ volatile unsigned long rle_k;\n"
                                          "      for (rle_k = 0; rle_k < (unsigned long)n * 2000; rle_k++) ; }\n#endif\n")
                code, rapport, sortie = self.juger("lente-" + cible, self.preparer("rapide-" + cible), True, base=base,
                                                   repetitions=6)
                self.assertEqual(code, 0, sortie)
                self.assertEqual(set(rapport["chronometres"]), {ici})
                m = rapport["chronometres"][ici]["metriques"]["debit_compression"]
                if cible == ici:
                    self.assertTrue(m["au_dela_du_bruit"])
                    self.assertGreater(m["gain"], 2.0)
                else:
                    self.assertLess(m["gain"], 1.0)

    def test_sortie_anticipee(self):
        code, _, sortie = self.juger("sortie_anticipee", self.preparer("sortie_anticipee", sortie_anticipee), True)
        self.assertEqual(code, 1)
        self.assertIn("REFUS", sortie)

    def test_faux_chronos(self):
        code, rapport, _ = self.juger("faux_chronos", self.preparer("faux_chronos", faux_chronos), True)
        self.assertEqual(code, 0)
        self.assertIn("symbole_interdit", self.types_suspects(rapport))
        m = rapport["metriques"]["debit_compression"]
        self.assertLess(m["B"]["mediane"], m["A"]["mediane"])

    def test_table_precalculee(self):
        code, _, sortie = self.juger("table_precalculee", self.preparer("table_precalculee", table_precalculee), True)
        self.assertEqual(code, 1)
        self.assertIn("REFUS", sortie)

    def test_requete_valgrind(self):
        code, rapport, _ = self.juger("requete_valgrind", self.preparer("requete_valgrind", requete_valgrind))
        self.assertEqual(code, 0)
        self.assertIn("preambule_valgrind", " ".join(s["detail"] for s in rapport["juge"]["constructions_suspectes"]))

    def test_faux_resume(self):
        code, rapport, _ = self.juger("faux_resume", self.preparer("faux_resume", faux_resume))
        self.assertEqual(code, 0)
        self.assertIn("appel_externe", self.types_suspects(rapport))
        m = rapport["instructions"]["instructions_compression"]
        self.assertGreater(m["B"], 0.99 * m["A"])

    def test_travail_deplace(self):
        code, rapport, _ = self.juger("travail_deplace", self.preparer("travail_deplace", travail_deplace))
        self.assertEqual(code, 0)
        self.assertEqual(rapport["juge"]["constructions_suspectes"], [])
        m = rapport["instructions"]["instructions_compression"]
        self.assertLess(m["gain"], 0.002, "le travail déplacé dans rle_borne doit rester compté")

    def test_greffon_de_la_pr(self):
        """B est faux (sortie compressée tronquée) mais apporte un greffon et un harnais qui acceptent tout."""
        source_b = self.preparer("greffon_de_la_pr", lambda t, c: remplacer(t, "    return o + 4;\n", "    return o > 8 ? o - 1 : o + 4;\n"))
        shutil.copytree(os.path.join(JOUET, "bee"), os.path.join(source_b, "bee"))
        with open(os.path.join(source_b, "bee", "juge", "projet.py"), "a", encoding="utf-8") as f:
            f.write("\nProjet.verifier = lambda self, a, b, e: 1\nProjet.compressee = lambda self, a, b, r, o: 0\n")
        code, _, sortie = self.juger("greffon_de_la_pr", source_b, True)
        self.assertEqual(code, 1)
        self.assertIn("REFUS", sortie)

    def test_releves_vides(self):
        base = self.base_modifiee("releves_vides", "bee/juge/construire.sh", 'echo "construction terminée"',
                                  ': > "$sortie/desassemblage.txt"\necho "construction terminée"')
        code, rapport, _ = self.juger("releves_vides", self.preparer("releves_vides", requete_valgrind), True, base=base)
        self.assertEqual(code, 0)
        self.assertIn("preambule_valgrind", " ".join(s["detail"] for s in rapport["juge"]["constructions_suspectes"]))

    def test_objet_oublie(self):
        """L'objet du projet est compilé hors de obj/ : il échapperait à l'analyse, le juge s'arrête."""
        base = self.base_modifiee("objet_oublie", "bee/juge/construire.sh", '"$sortie/obj/rle.o"', '"$sortie/rle.o"')
        code, _, sortie = self.juger("objet_oublie", self.preparer("objet_oublie"), True, base=base)
        self.assertEqual(code, 2)
        self.assertIn("sans objet", sortie)

    def test_jetons_scindes(self):
        code, rapport, _ = self.juger("jetons_scindes", self.preparer("jetons_scindes", jetons_scindes), True)
        self.assertEqual(code, 0)
        self.assertIn("preambule_valgrind", " ".join(s["detail"] for s in rapport["juge"]["constructions_suspectes"]))

    def test_greffon_distrait(self):
        """Le greffon de la base oublie de lire les décompressions de B : erreur, jamais une acceptation."""
        base = self.base_modifiee("greffon_distrait", "bee/juge/projet.py",
                                  'if b.exiger("z", f"decompression/d/{e.nom}") != e.attendu:', "if False:")
        code, _, sortie = self.juger("greffon_distrait", self.preparer("greffon_distrait"), True, base=base)
        self.assertEqual(code, 2)
        self.assertIn("aucune sortie de B", sortie)

    def test_appel_interdit(self):
        """Revue adverse n° 2 : getenv est signalé par son nom, quel que soit l'espace de noms déclaré."""
        code, rapport, _ = self.juger("appel_interdit", self.preparer("appel_interdit", appel_blanchi_par_prefixe), True)
        self.assertEqual(code, 0)
        self.assertIn("getenv", " ".join(s["detail"] for s in rapport["juge"]["constructions_suspectes"]))

    def test_seeded_bytes(self):
        code, rapport, _ = self.juger("seeded_bytes", self.preparer("seeded_bytes", lambda t, c: t + octets_asm("48b80f05909090909090")), True)
        self.assertEqual(code, 0)
        self.assertIn("octets", self.types_suspects(rapport))

    def test_lien_symbolique(self):
        source_b = self.preparer("lien_symbolique")
        os.remove(os.path.join(source_b, "rle.c"))
        os.symlink(os.path.join(JOUET, "rle.c"), os.path.join(source_b, "rle.c"))
        code, _, sortie = self.juger("lien_symbolique", source_b, True)
        self.assertEqual(code, 1)
        self.assertIn("lien symbolique", sortie)


if __name__ == "__main__":
    unittest.main(verbosity=2)
