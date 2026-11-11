#!/usr/bin/env python3
"""Tests du juge commun Bee (tools/judge/).

  python3 tools/judge/test_judge.py                      tests unitaires (sans Docker)
  BEE_JUGE_INTEGRATION=1 python3 tools/judge/test_judge.py
                                                        + méta-tests : le juge commun contre le projet jouet
                                                          (tools/judge/jouet/) honnête et MALVEILLANT (Docker requis)
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
et, depuis ruche-0037 (le code jugé ne peut pas savoir s'il est vérifié ou mesuré) :
  memes_conditions            B relève tout ce qu'il peut observer de son processus : le même relevé dans chaque mode
  sortie_fausse_chronometree  B juste quand il est vérifié, faux quand il est chronométré (le harnais de la base le
                              lui dit) : refusé par les entrées de vérification mêlées aux mesures
  memes_compteurs             sur les mêmes /entrees, le même relevé dans chaque mode, compteurs du processus compris
  sortie_changeante_chronometree  sorties libres : B donne, chronométré, une autre sortie juste : refusé
  cote_sans_melange, instructions_sans_melange  un côté mesuré sans entrée à mêler : erreur ; un décompte sans : signalé

Without Docker, the analysis is also tested on objects of the toy project built on the host as the judge
builds them (DockerLocal; built, surveyed and analysed, never run): seeded constructs in every family and
variant (TestSeededObjects), constructs added anywhere in a judged file (TestSeededText), failing tools
(TestFailClosed).

ruche-0024 (juge-v2): juge.yml's scripts are run with bash, gh replaced by a stand-in (TestWorkflowJuge: judge code
at a commit of the registry's main, preparation failing closed, a hostile journal that issues no workflow command);
the declared history is checked against the base's ancestry, fetched within a time budget, then read without any
git transport (TestHistorique); with Docker, historique_declare and historique_non_declare.

ruche-0037, without Docker: the harness is started the same way in every mode (TestMemesConditions); inputs are renamed
and each verification input passes in a measurement, drawn from the seed, with the same output (TestMelange); fixed times,
the harness alone in /variante, at least one repetition (TestConditionsFixes).

ruche-0036: outputs frozen when their container ends, order drawn at each repetition, each scenario's CPU time, on a toy
with two scenarios per side (jouet_a_quatre_scenarios). Without Docker, conteneur.Docker is replaced by an emulation of
chrono and of the toy harness (DockerEmule, nothing is run): the order recorded is the order run, each scenario's CPU
time is chrono's, an output changed, added or removed after its freeze is refused (TestOrdreEtEmpreintes, TestFigees).
With Docker, scenarios_voisins: every scenario of B tries to read and to modify the others' outputs, before and after
its own work: the honest toy's verdict and comparisons, the order changing between repetitions.

ruche-0117 (before the juge-v3 tag): suspicious constructs ranked and counted, each detail cut (test_detail_cut_when_built,
test_suspectes_les_plus_graves_d_abord, test_rapport_du_job); the judging step publishes the code once the report is checked,
--verify wants the code 0 and the PR's commits (test_code_published_once_the_report_is_checked,
test_verifier_requires_code_0_and_the_pull_request_commits); a fixed metric read on verification alone is flagged
(test_fixed_metric_read_on_verification_alone); the identity check counts per scenario
(test_mixed_input_same_output_as_in_verification); each execution on its own tmpfs (test_each_execution_on_its_own_tmpfs),
unmounted at once (test_tmpfs_in_use_is_an_error); the judge's mounts in one order whatever order Docker draws for those of
equal depth (test_one_mount_order_whatever_docker_draws); with Docker, test_memes_montures: identical scenarios at different
positions, variant passes, repetitions and modes see the same thing, mount by mount (RESTE aside), and none sees what another
left in its outputs.

ruche-0136: a failure of the machine (Docker, its runtime) is an error of the environment, read on Docker's own record; a judged
code that mimics one stays a refusal (test_machine_failure_is_an_environment_error, test_judged_code_that_mimics_a_failure_stays_a_refusal,
test_juge_json_says_the_environment_error; with Docker, panne_de_la_machine, panne_simulee); where each seed came from
(test_where_each_seed_came_from, verifier_les_graines); each folder of the judge at a depth of its own, in every container
(test_one_mount_order_whatever_docker_draws; with Docker, test_profondeurs).
"""

import ast
import concurrent.futures
import contextlib
import glob
import hashlib
import io
import itertools
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import tracemalloc
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOY = os.path.join(HERE, "jouet")
sys.path.insert(0, HERE)
import analysis  # noqa: E402
import container  # noqa: E402
import entrees  # noqa: E402
import judge  # noqa: E402
import lecture  # noqa: E402
import report  # noqa: E402
import stats  # noqa: E402

sys.path.insert(0, os.path.join(TOY, "bee", "juge"))
import projet as toy_plugin  # noqa: E402

# ruche-0148 (J2): the toy's twin in the English contract, its plugin and build script alone (toy/bee/judge/); english_toy makes it
# a whole base with the toy's sources and harness. Each meta-test runs on both (TestJudgeAgainstVariantsEnglish).
ENGLISH_TOY = os.path.join(HERE, "toy")
TOY_FILES = {"plugin": ("projet.py", "project.py"), "build": ("construire.sh", "build.sh"), "harness": ("execution.c", "execution.c")}


def english_toy(folder):
    """The toy project as a base that speaks the English contract: bee/judge/ (the twin's plugin and build script, the toy's
    harness) and the toy's sources, no bee/juge/."""
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "bee"))
    shutil.copytree(os.path.join(ENGLISH_TOY, "bee"), os.path.join(folder, "bee"), ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(os.path.join(TOY, "bee", "juge", "execution.c"), os.path.join(folder, "bee", "judge", "execution.c"))
    return folder


def toy_file(base, kind):
    """A toy base's plugin, build script or harness, in the contract it speaks."""
    english = os.path.isdir(os.path.join(base, "bee", "judge"))
    return os.path.join(base, "bee", "judge" if english else "juge", TOY_FILES[kind][english])


def contract(base, text):
    """A text that names the French contract (Projet.verifier…), in the contract the base speaks."""
    english = os.path.isdir(os.path.join(base, "bee", "judge"))
    return re.sub(r"\b\w+\b", lambda m: judge.PLUGIN_NAMES.get(m.group(0), m.group(0)) if english else m.group(0), text)


# ------------------------------------------------------------------ tests unitaires

NM_A = """/s/obj/rle.o: rle_compresser T 0000000000000100 0000000000000080
/s/obj/rle.o: memcpy U
/s/obj/rle.o: .LC0 r 0
"""
SECTIONS_A = """
Idx Name          Size      VMA               LMA               File off  Algn
  0 .text         00001000  0000000000000000  0000000000000000  00000040  2**4
"""
DISASSEMBLY_A = "0000000000000000 <rle_compresser>:\n   0:\tendbr64\n   4:\tpush   %rbp\n"


def surveys(nm=NM_A, sections=SECTIONS_A, disassembly=DISASSEMBLY_A, objects_found=(), program=()):
    return {"symboles": nm, "sections": sections, "desassemblage": disassembly, "objets": list(objects_found),
            "programme": list(program)}


class TestAnalyse(unittest.TestCase):
    def test_base_against_itself(self):
        self.assertEqual(analysis.analyse(surveys(), surveys(), {}, {}, prefixes=("rle_",)), [])

    def test_prefixes_and_allowed_of_the_plugin(self):
        b = surveys(nm=NM_A + "/s/obj/rle.o: rle_aide T 0000000000000300 0000000000000010\n/s/obj/rle.o: qsort U\n")
        self.assertEqual([s["type"] for s in analysis.analyse(surveys(), b, {}, {}, prefixes=("rle_",))], ["appel_externe"])
        self.assertEqual(analysis.analyse(surveys(), b, {}, {}, prefixes=("rle_",), allowed_set=("qsort",)), [])
        # Sans espace de noms, une nouvelle fonction globale est suspecte (elle pourrait en remplacer une autre).
        self.assertEqual(sorted(s["type"] for s in analysis.analyse(surveys(), b, {}, {}, allowed_set=("qsort",))), ["symbole_defini"])

    def test_symbol_that_replaces_the_libc(self):
        b = surveys(nm=NM_A + "/s/obj/rle.o: clock_gettime T 0000000000000300 0000000000000010\n"
                             "/s/obj/rle.o: memcmp T 0000000000000400 0000000000000010\n")
        self.assertEqual(sorted(s["type"] for s in analysis.analyse(surveys(), b, {}, {}, prefixes=("rle_",))),
                         ["symbole_defini", "symbole_interdit"])

    def test_never_allowed_despite_prefix_or_allowed(self):
        """Revue adverse n° 2 : un préfixe « ge » ou une entrée PERMIS ne blanchit pas getenv."""
        b = surveys(nm=NM_A + "/s/obj/rle.o: getenv U\n/s/obj/rle.o: syscall U\n")
        types = [s["type"] for s in analysis.analyse(surveys(), b, {}, {}, prefixes=("rle_", "ge", "sy"), allowed_set=("getenv",))]
        self.assertEqual(types, ["appel_interdit", "appel_interdit"])
        a = surveys(nm=NM_A + "/s/obj/rle.o: getenv U\n")
        self.assertEqual([s["type"] for s in analysis.analyse(a, b, {}, {}, prefixes=("rle_",))], ["appel_interdit"])  # syscall seul

    def test_line_continuation(self):
        b = {"rle.c": "    __as\\\nm volatile(\"\");\n    int x = 1;\n"}
        self.assertEqual(list(analysis.text_constructs(b)), [("rle.c", "assembleur en ligne", "__as" + "m volatile(\"\");")])
        self.assertEqual(len(analysis.analyse(surveys(), surveys(), {}, b, prefixes=("rle_",))), 1)

    def test_constructor_and_instructions(self):
        b = surveys(sections=SECTIONS_A + "  1 .init_array   00000008  0000000000000000  0000000000000000  00001140  2**3\n",
                    disassembly=DISASSEMBLY_A + "   9:\tsyscall\n  10:\trol    $0x3,%rdi\n")
        self.assertEqual(sorted(s["type"] for s in analysis.analyse(surveys(), b, {}, {}, prefixes=("rle_",))),
                         ["instruction", "instruction", "section"])

    def test_source(self):
        b = {"rle.c": "    __asm__ volatile(\"\");\n#include <time.h>\n    int ordinaire = 1;\n"}
        self.assertEqual(len(analysis.analyse(surveys(), surveys(), {}, b, prefixes=("rle_",))), 2)

    def test_mnemonics_any_word(self):
        instructions = {m: m for m in analysis.SUSPICIOUS_MNEMONICS if m[0].isalpha() and m not in NON_INSTRUCTIONS}
        instructions.update({"int": "int $0x80", "(bad)": "(bad)", ".byte": ".byte 0xf", "preambule_valgrind": "rol $0x3,%rdi"})
        suites = [()] + [(p,) for p in PREFIXES_X86] + [(p, q) for p in PREFIXES_X86 for q in PREFIXES_X86]
        lines = [f"  1f:\t{' '.join(suite + (text,))}" for text in instructions.values() for suite in suites]
        lines += ["   e:\tcall   13 <syscall+0x3>", "  13:\tlea    0x0(%rip),%rax        # 1a <int>"]
        self.assertEqual(analysis.mnemonics_found("\n".join(lines)), {m: len(suites) for m in instructions})

    def test_unreadable_bytes_make_the_analysis_incomplete(self):
        for data in (b"", b"\x7fELF", b"MZ" + bytes(100), b"\x7fELF\x02\x01\x01" + bytes(57)):
            b = surveys(objects_found=[("rle.o", data)])
            self.assertEqual([s["type"] for s in analysis.analyse(surveys(), b, {}, {}, prefixes=("rle_",))], ["analyse_incomplete"])

    def test_unreadable_a_object(self):
        a, b = surveys(objects_found=[("rle.o", b"\x7fELF")]), surveys(objects_found=[("rle.o", elf(1, [(".text", 6, b"\x90")]))])
        self.assertEqual([s["type"] for s in analysis.analyse(a, b, {}, {})], ["analyse_incomplete"])

    def test_texts_required(self):
        with self.assertRaises(TypeError):
            analysis.analyse(surveys(), surveys(), prefixes=("rle_",))

    def test_whole_files_compared(self):
        a = {"x.c": "#pragma once\nint a;\n", "y.c": "int b;\n"}
        self.assertEqual(analysis.analyse(surveys(), surveys(), a, {"x.c": "int c;\n  #pragma   once\n", "y.c": "int b;\n"}), [])
        b = {"x.c": "int a;\n", "y.c": "#pragma once\nint b;\n"}
        self.assertEqual([s["detail"][-5:] for s in analysis.analyse(surveys(), surveys(), a, b)], ["(y.c)"])
        b = {"x.c": "#pragma once\nint a;\n#pragma once\n", "y.c": "int b;\n"}
        self.assertEqual(len(analysis.analyse(surveys(), surveys(), a, b)), 1)

    def test_detail_cut_when_built(self):
        """ruche-0117: names and extracts come from the judged code; a symbol of 5,000 characters gives a detail of DETAIL_MAX."""
        nom = "bee_" + "x" * 5000
        found_ones = analysis.analyse(surveys(), surveys(nm=NM_A + f"/s/obj/rle.o: {nom} D 0000000000000000 4\n"), {}, {},
                                    prefixes=("rle_",))
        self.assertEqual([s["type"] for s in found_ones], ["symbole_defini"])
        self.assertEqual(len(found_ones[0]["detail"]), analysis.DETAIL_MAX)
        self.assertTrue(found_ones[0]["detail"].startswith(nom[:200]) and found_ones[0]["detail"].endswith("…"))


# Every prefix word objdump prints before an x86-64 instruction.
PREFIXES_X86 = ["es", "cs", "ss", "ds", "fs", "gs", "data16", "addr32", "lock", "rep", "repz", "repnz", "notrack", "bnd",
                "xacquire", "xrelease"] + ["rex" + ("." + "".join(c for c, bit in zip("WRXB", (8, 4, 2, 1)) if m & bit) if m else "")
                                           for m in range(16)]
NON_INSTRUCTIONS = ("preambule_valgrind", "segment_wx", "pile_executable")
GNU_STACK = 0x6474E551


def elf(kind_of, sections=(), segments=(), shstrndx=None, queue=b""):
    """Minimal x86-64 ELF file: an object (genre 1) with sections [(name, flags, bytes)] and its name table, or a program
    (genre 3) with segments [(type, flags, bytes)]; `queue` is appended after everything."""
    names = b"\0" + b"".join(n.encode() + b"\0" for n, _, _ in sections) + b".shstrtab\0"
    beginning = 64 + 56 * len(segments)
    body, ph, sh, position = b"", b"", bytes(64), 1
    for type_, flag_bits, data in segments:
        ph += struct.pack("<IIQQQQQQ", type_, flag_bits, beginning + len(body), 0, 0, len(data), len(data), 0)
        body += data
    for nom, flag_bits, data in sections:
        sh += struct.pack("<IIQQQQIIQQ", position, 1, flag_bits, 0, beginning + len(body), len(data), 0, 0, 1, 0)
        position, body = position + len(nom) + 1, body + data
    sh += struct.pack("<IIQQQQIIQQ", position, 3, 0, 0, beginning + len(body), len(names), 0, 0, 1, 0)
    body += names
    number = len(sections) + 2 if sections else 0
    head = b"\x7fELF\x02\x01\x01" + bytes(9) + struct.pack(
        "<HHIQQQIHHHHHH", kind_of, 62, 1, 0, 64 if segments else 0, beginning + len(body) if sections else 0, 0, 64, 56,
        len(segments), 64, number, max(number - 1, 0) if shstrndx is None else shstrndx)
    return head + ph + body + (sh if sections else b"") + queue


class TestExecutableBytes(unittest.TestCase):
    """Executable bytes read from hand-built ELF files."""

    def test_object_sections(self):
        object_name = elf(1, [(".text", 6, b"\x90\xc3"), (".data.x", 6, b"\x90\x0f\x05\x90"), (".data", 3, b"\x0f\x05"),
                        (".text.y", 2, b"\x0f\x31")])
        self.assertEqual(analysis.executable_bytes(object_name), ([b"\x90\xc3", b"\x90\x0f\x05\x90", b"\x0f\x31"], []))
        b = surveys(objects_found=[("rle.o", object_name)])
        self.assertEqual(sorted(s["detail"].split(":")[0] for s in analysis.analyse(surveys(), b, {}, {})), ["rdtsc", "syscall"])

    def test_hit_context_and_object(self):
        def objects_found(nom, bytes_count):
            return surveys(objects_found=[(nom, elf(1, [(".text", 6, bytes_count)]))])
        a = objects_found("rle.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3" * 8)
        self.assertEqual(analysis.analyse(a, objects_found("rle.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3" * 8), {}, {}), [])
        for b in (objects_found("rle.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3\xcc" * 4), objects_found("rle.o", b"\x90\xcc" * 4 + b"\x0f\x05" + b"\xc3" * 8),
                  objects_found("rle2.o", b"\x90" * 8 + b"\x0f\x05" + b"\xc3" * 8)):
            with self.subTest(b=b["objets"][0][0]):
                self.assertEqual([s["detail"].split(":")[0] for s in analysis.analyse(a, b, {}, {})], ["syscall"])

    def test_compressed_executable_section(self):
        with self.assertRaises(ValueError):
            analysis.executable_bytes(elf(1, [(".text.z", 0x806, b"\x0f\x05")]))

    def test_section_name_table_index(self):
        analysis.executable_bytes(elf(1, [(".text", 6, b"\x90")], queue=bytes(256)))
        for index_hint in (3, 4):
            with self.assertRaises(ValueError):
                analysis.executable_bytes(elf(1, [(".text", 6, b"\x90")], shstrndx=index_hint, queue=bytes(256)))

    def test_program_segments_and_stack(self):
        code, stack_of = (1, 5, b"\x90\xc3"), (GNU_STACK, 6, b"")
        self.assertEqual(analysis.executable_bytes(elf(3, segments=[code, stack_of])), ([b"\x90\xc3"], []))
        self.assertEqual(analysis.executable_bytes(elf(3, segments=[code]))[1], ["pile_executable"])
        self.assertEqual(analysis.executable_bytes(elf(3, segments=[code, (GNU_STACK, 7, b"")]))[1], ["pile_executable"])
        self.assertEqual(analysis.executable_bytes(elf(3, segments=[(1, 7, b"\x90"), stack_of]))[1], ["segment_wx"])


class TestSafeReading(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "c"))

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_regular_and_absent_file(self):
        with open(os.path.join(self.root, "c", "x"), "wb") as f:
            f.write(b"abc")
        self.assertEqual(lecture.lire_sortie(self.root, "c/x"), b"abc")
        self.assertIsNone(lecture.lire_sortie(self.root, "c/absent"))

    def test_links_pipes_and_paths_refused(self):
        os.symlink("/etc/hostname", os.path.join(self.root, "c", "lien"))
        os.symlink("/etc", os.path.join(self.root, "d"))
        os.mkfifo(os.path.join(self.root, "c", "tube"))
        for relative_one in ("c/lien", "d/hostname", "c/tube", "../x", "c/../c/x", "/etc/hostname"):
            with self.assertRaises(lecture.Refus, msg=relative_one):
                lecture.lire_sortie(self.root, relative_one)

    def test_bounded_size_and_status(self):
        with open(os.path.join(self.root, "c", "x"), "wb") as f:
            f.write(b"0" * 100)
        with self.assertRaises(lecture.Refus):
            lecture.lire_sortie(self.root, "c/x", maximum=10)
        with open(os.path.join(self.root, "c", "s"), "wb") as f:
            f.write(b"-2 12\n")
        self.assertEqual(lecture.Sorties({"f": self.root}).statut("f", "c/s"), (-2, 12))
        with open(os.path.join(self.root, "c", "s"), "wb") as f:
            f.write(b"0 12 ; rm -rf /\n")
        with self.assertRaises(lecture.Refus):
            lecture.statut(self.root, "c/s")

    def test_clean(self):
        self.assertEqual(lecture.propre(b"::error::x\x1b[31m"), ": :error: :x?[31m")


class TestStatistics(unittest.TestCase):
    """Mêmes définitions que bee/bench/ab.py de minizBee (valeurs de référence calculées avec ab.py)."""

    def test_sign_threshold(self):
        self.assertEqual([stats.sign_threshold(n) for n in (5, 6, 10, 20)], [None, 6, 9, 16])

    def test_sign_test(self):
        t = stats.sign_test([1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 2, 2, 2, 2, 2, 1], "plus_haut")
        self.assertEqual((t["b_wins"], t["ties"], t["threshold_k"], t["beyond_noise"]), (9, 1, 8, True))
        t = stats.sign_test([2] * 10, [1] * 10, "plus_haut")
        self.assertTrue(t["degradation_beyond_noise"])

    def test_summary_and_gain(self):
        self.assertEqual(stats.summary([3, None, 1, 2])["median"], 2)
        self.assertAlmostEqual(stats.relative_gain(100, 98, "plus_bas"), 0.02)
        self.assertAlmostEqual(stats.relative_gain(100, 103, "plus_haut"), 0.03)
        self.assertIsNone(stats.relative_gain(0, 1, "plus_haut"))


class TestInputs(unittest.TestCase):
    def test_validation(self):
        good = entrees.Entree("f", "k000", b"x", 1)
        entrees.verifier_entrees([good], ("f", "z"))
        for bad_one in (entrees.Entree("q", "k", b"", 0), entrees.Entree("f", "../k", b"", 0),
                         entrees.Entree("f", "k", "texte", 0), entrees.Entree("f", "k", b"", -1)):
            with self.assertRaises(lecture.Erreur):
                entrees.verifier_entrees([bad_one], ("f", "z"))
        with self.assertRaises(lecture.Erreur):
            entrees.verifier_entrees([good, good], ("f",))

    def test_writing(self):
        folder = tempfile.mkdtemp()
        try:
            entrees.ecrire(folder, [entrees.Entree("z", "z000", b"abc", 7)], ("f", "z"))
            self.assertEqual(open(os.path.join(folder, "liste")).read(), "z z000 7\n")
            self.assertTrue(os.path.isdir(os.path.join(folder, "f")))
        finally:
            shutil.rmtree(folder)

    def test_reproducible_perturb(self):
        corpus = [("k000", bytes(200_000)), ("k001", b"")]
        a = entrees.perturber(random.Random(1), corpus)
        self.assertEqual(a, entrees.perturber(random.Random(1), corpus))
        self.assertEqual(sum(1 for x in a[0][1] if x), 3)
        self.assertEqual(a[1][1], b"")


class TestPlugin(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base, "bee", "juge"))

    def tearDown(self):
        shutil.rmtree(self.base)

    def ecrire(self, text):
        with open(os.path.join(self.base, "bee", "juge", "projet.py"), "w", encoding="utf-8") as f:
            f.write(text)

    def test_toy_plugin(self):
        projet, fingerprint = judge.load_plugin(TOY, {})
        self.assertEqual(projet.NOM, "jouet")
        self.assertEqual(len(fingerprint), 64)
        with self.assertRaises(lecture.Erreur):
            judge.load_plugin(TOY, {"inconnue": "1"})

    def test_plugin_absent_or_incomplete(self):
        with self.assertRaises(lecture.Erreur):
            judge.load_plugin(self.base, {})
        self.ecrire("class Projet:\n    NOM = 'x'\n    def __init__(self, options): pass\n")
        with self.assertRaises(lecture.Erreur) as e:
            judge.load_plugin(self.base, {})
        self.assertIn("SCENARIOS", str(e.exception))

    def test_plugin_link_refused(self):
        os.symlink(os.path.join(TOY, "bee", "juge", "projet.py"), os.path.join(self.base, "bee", "juge", "projet.py"))
        with self.assertRaises(lecture.Erreur):
            judge.load_plugin(self.base, {})

    def changed_plugin(self, old, new):
        text = open(os.path.join(TOY, "bee", "juge", "projet.py"), encoding="utf-8").read()
        self.assertEqual(text.count(old), 1)
        self.ecrire(text.replace(old, new))

    def test_empty_or_short_prefixes_refused(self):
        for value in ('("",)', '()', '("r",)', '("rle-",)', '("rle",)', '("ge",)', '("rle_", "cl")', '("sys",)'):
            self.changed_plugin('PREFIXES = ("rle_",)', f"PREFIXES = {value}")
            with self.assertRaises(lecture.Erreur, msg=value):
                judge.load_plugin(self.base, {})

    def test_allowed_never_allowed(self):
        self.changed_plugin("PERMIS = ()", 'PERMIS = ("qsort", "clock_gettime")')
        with self.assertRaises(lecture.Erreur) as e:
            judge.load_plugin(self.base, {})
        self.assertIn("clock_gettime", str(e.exception))
        self.changed_plugin("PERMIS = ()", 'PERMIS = ("qsort",)')
        judge.load_plugin(self.base, {})

    def test_diff_no_longer_exists(self):
        self.changed_plugin('SOURCES = ["rle.c", "rle.h"]', 'SOURCES = ["rle.c", "rle.h"]\n    DIFF = ["rle.c"]')
        with self.assertRaises(lecture.Erreur):
            judge.load_plugin(self.base, {})

    def test_scenario_outside_sides(self):
        text = open(os.path.join(TOY, "bee", "juge", "projet.py"), encoding="utf-8").read()
        self.ecrire(text.replace('SCENARIOS = {"compression": "f"', 'SCENARIOS = {"compression": "q"'))
        sys.path.insert(0, HERE)
        with self.assertRaises(lecture.Erreur):
            judge.load_plugin(self.base, {})

    def test_english_toy_plugin(self):
        """ruche-0148 (J2): the twin's bee/judge/project.py is read under the French names, its directions as the French ones."""
        base = english_toy(os.path.join(self.base, "en"))
        (projet, fingerprint), french = judge.load_plugin(base, {}), judge.load_plugin(TOY, {})[0]
        self.assertIsInstance(projet, judge.EnglishPlugin)
        self.assertEqual((projet.OUTILLAGE, projet.CONSTRUIRE), (["bee/judge"], "bee/judge/build.sh"))
        for n in set(judge.REQUIRED_ATTRIBUTES + ("PAQUETS", "PERMIS", "METHODE", "VERIFICATION")) - {"OUTILLAGE", "CONSTRUIRE"}:
            self.assertEqual(getattr(projet, n), getattr(french, n), n)
        self.assertEqual(projet.METRIQUES[3], ("memoire_max_ko", "plus_bas", "Ko"))
        self.assertEqual([callable(getattr(projet, m, None)) for m in judge.REQUIRED_METHODS], [True] * len(judge.REQUIRED_METHODS))
        with open(toy_file(base, "plugin"), "rb") as f:
            self.assertEqual(fingerprint, hashlib.sha256(f.read()).hexdigest())
        with self.assertRaises(lecture.Erreur):
            judge.load_plugin(base, {"inconnue": "1"})
        os.remove(toy_file(base, "plugin"))
        with self.assertRaises(lecture.Erreur) as e:  # bee/judge/ without its plugin: none found, in either contract
            judge.load_plugin(base, {})
        self.assertIn("bee/judge/project.py ou bee/juge/projet.py", str(e.exception))

    def test_one_plugin_per_base(self):
        """Both bee/judge/project.py and bee/juge/projet.py, a link or a folder counting: refused, whichever is valid."""
        base = english_toy(os.path.join(self.base, "deux"))
        french = os.path.join(base, "bee", "juge", "projet.py")
        os.makedirs(os.path.dirname(french))
        for make in (lambda: shutil.copyfile(toy_file(TOY, "plugin"), french), lambda: os.symlink("nowhere", french), lambda: os.mkdir(french)):
            make()
            with self.assertRaises(lecture.Erreur) as e:
                judge.load_plugin(base, {})
            self.assertIn("a base holds one", str(e.exception))
            (os.rmdir if os.path.isdir(french) and not os.path.islink(french) else os.remove)(french)
        self.assertIsInstance(judge.load_plugin(base, {})[0], judge.EnglishPlugin)
        shutil.rmtree(os.path.join(base, "bee", "judge"))
        shutil.copytree(os.path.join(TOY, "bee", "juge"), os.path.dirname(french), dirs_exist_ok=True)
        self.assertNotIsInstance(judge.load_plugin(base, {})[0], judge.EnglishPlugin)

    def test_every_component_of_the_plugin_path_a_real_folder_or_file(self):
        """bee, bee/judge or bee/juge, and the plugin itself: each a real folder or file, not a link, in either contract."""
        for english in (True, False):
            for linked in (("bee",), ("bee", "judge" if english else "juge")):
                with self.subTest(english=english, linked=linked):
                    root = tempfile.mkdtemp(dir=self.base)
                    real = english_toy(os.path.join(root, "real")) if english else shutil.copytree(TOY, os.path.join(root, "real"))
                    base = os.path.join(root, "base")
                    os.makedirs(os.path.join(base, *linked[:-1]), exist_ok=True)
                    os.symlink(os.path.join(real, *linked), os.path.join(base, *linked))
                    self.assertTrue(os.path.isfile(toy_file(real, "plugin")) and os.path.isfile(os.path.join(base, os.path.relpath(
                        toy_file(real, "plugin"), real))))
                    with self.assertRaises(lecture.Erreur) as e:
                        judge.load_plugin(base, {})
                    self.assertIn("every component of its path must be a real folder or file, not a link", str(e.exception))
                    judge.load_plugin(real, {})

    def test_other_contract_names_an_instance_answers_are_not_refused(self):
        """Only names the module or the class body defines count as the other contract's: an instance's attributes do not, so a
        plugin that sets fixed or NAME (French) or fixes or NOM (English) on itself loads as before."""
        base = english_toy(os.path.join(self.base, "en"))
        for root, cls, added in ((self.base, "Projet", "self.fixed, self.NAME = {}, 'x'"), (base, "Project", "self.fixes, self.NOM = {}, 'x'")):
            with open(toy_file(TOY if root == self.base else ENGLISH_TOY, "plugin"), encoding="utf-8") as f:
                text = f.read()
            with self.subTest(cls=cls), open(toy_file(root, "plugin"), "w", encoding="utf-8") as f:
                f.write(f"{text}\n_init = {cls}.__init__\n\n\ndef _init_too(self, options):\n    _init(self, options)\n    {added}\n\n\n"
                        f"{cls}.__init__ = _init_too\n")
            self.assertEqual(judge.load_plugin(root, {})[0].NOM, "jouet")

    def test_other_contract_names_a_base_class_defines_are_refused(self):
        """A name of the other contract defined in a base class of the plugin's class counts as the class body's: refused, each way."""
        base = english_toy(os.path.join(self.base, "en"))
        for root, cls, name in ((self.base, "Projet", "fixed"), (base, "Project", "NOM")):
            with open(toy_file(TOY if root == self.base else ENGLISH_TOY, "plugin"), encoding="utf-8") as f:
                text = f.read()
            with self.subTest(cls=cls), open(toy_file(root, "plugin"), "w", encoding="utf-8") as f:
                f.write(f"{text}\n\nclass _Base:\n    {name} = None\n\n\nclass {cls}({cls}, _Base):\n    pass\n")
            with self.assertRaises(lecture.Erreur) as e:
                judge.load_plugin(root, {})
            self.assertIn(f"({name}): one contract per plugin", str(e.exception))

    def test_one_contract_per_plugin(self):
        """A plugin that also bears a name of the other contract (the class, a constant, a method) is refused, each way."""
        base = english_toy(os.path.join(self.base, "en"))
        with open(toy_file(base, "plugin"), encoding="utf-8") as f:
            english_text = f.read()
        with open(toy_file(TOY, "plugin"), encoding="utf-8") as f:
            french_text = f.read()
        for french, english in judge.PLUGIN_NAMES.items():
            for root, text, added in ((base, english_text, "Projet = Project" if french == "Projet" else f"Project.{french} = Project.{english}"),
                                      (self.base, french_text, "Project = Projet" if french == "Projet" else f"Projet.{english} = Projet.{french}")):
                with self.subTest(added=added), open(toy_file(root, "plugin"), "w", encoding="utf-8") as f:
                    f.write(f"{text}\n{added}\n")
                with self.assertRaises(lecture.Erreur) as e:
                    judge.load_plugin(root, {})
                self.assertIn("one contract per plugin", str(e.exception))

    def test_directions_in_the_contract_language(self):
        """A metric's direction is higher or lower in English, plus_haut or plus_bas in French: the other language's, any
        other value or shape is refused (before ruche-0148, anything but plus_haut was read as lower)."""
        base = english_toy(os.path.join(self.base, "en"))
        with open(toy_file(base, "plugin"), encoding="utf-8") as f:
            english_text = f.read()
        for old, new in (("higher", "plus_haut"), ("higher", "Higher"), ("higher", "plus haut"), ("lower", "plus_bas")):
            with self.subTest(english=new), open(toy_file(base, "plugin"), "w", encoding="utf-8") as f:
                f.write(replace_with(english_text, f'("ratio", "{old}", "ratio")' if old == "higher" else f'"{old}", "Ko"',
                                     f'("ratio", "{new}", "ratio")' if old == "higher" else f'"{new}", "Ko"'))
            with self.assertRaises(lecture.Erreur) as e:
                judge.load_plugin(base, {})
            self.assertIn("higher or lower", str(e.exception))
        for new in ('("ratio", "higher", "ratio")', '("ratio", "plus_bas")', '("ratio", ["plus_haut"], "ratio")', '"ratio"'):
            with self.subTest(french=new):
                self.changed_plugin('("ratio", "plus_haut", "ratio")', new)
                with self.assertRaises(lecture.Erreur) as e:
                    judge.load_plugin(self.base, {})
                self.assertIn("plus_haut or plus_bas", str(e.exception))

    def test_english_toy_is_the_toy_renamed(self):
        """The twin is the toy's plugin with the contract's names (PLUGIN_NAMES) and four strings (its folder, its build script,
        the directions) in English, and nothing else: the same syntax tree once they are put back; its build script is the
        toy's with bee/judge/ for bee/juge/."""
        back, strings = {e: f for f, e in judge.PLUGIN_NAMES.items()}, {"bee/judge": "bee/juge", "bee/judge/build.sh": "bee/juge/construire.sh",
                                                                         "higher": "plus_haut", "lower": "plus_bas"}

        class French(ast.NodeTransformer):
            def visit_Name(self, node):
                node.id = back.get(node.id, node.id)
                return node

            def visit_Attribute(self, node):
                self.generic_visit(node)
                node.attr = back.get(node.attr, node.attr)
                return node

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                node.name = back.get(node.name, node.name)
                return node

            visit_ClassDef = visit_FunctionDef

            def visit_Constant(self, node):
                node.value = strings.get(node.value, node.value) if isinstance(node.value, str) else node.value
                return node
        texts = {}
        for key, path in (("en", toy_file(ENGLISH_TOY, "plugin")), ("fr", toy_file(TOY, "plugin")), ("en.sh", toy_file(ENGLISH_TOY, "build")),
                          ("fr.sh", toy_file(TOY, "build"))):
            with open(path, encoding="utf-8") as f:
                texts[key] = f.read()
        self.assertNotEqual(texts["en"], texts["fr"])
        self.assertEqual(ast.dump(French().visit(ast.parse(texts["en"]))), ast.dump(ast.parse(texts["fr"])))
        self.assertEqual(texts["en.sh"], texts["fr.sh"].replace("bee/juge", "bee/judge"))
        self.assertEqual(sorted(os.listdir(os.path.join(ENGLISH_TOY, "bee", "judge"))), ["build.sh", "project.py"])


class TestExpectedObjects(unittest.TestCase):
    def test_units_and_homonyms(self):
        root = tempfile.mkdtemp()
        try:
            for path in ("src/a.c", "src/b.S", "src/c.cc", "src/d.h", "lib/e.c"):
                os.makedirs(os.path.join(root, os.path.dirname(path)), exist_ok=True)
                open(os.path.join(root, path), "w").close()
            self.assertEqual(judge.expected_objects(root), ({"a.o", "b.o", "c.o", "e.o"}, []))
            open(os.path.join(root, "lib", "a.c"), "w").close()
            self.assertEqual(judge.expected_objects(root)[1], ["a.o"])
        finally:
            shutil.rmtree(root)


class TestCoverage(unittest.TestCase):
    def test_outputs_read_and_coverage(self):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, "c"))
            for nom in ("k000.6", "k001"):
                with open(os.path.join(root, "c", nom), "wb") as f:
                    f.write(b"x")
            view = lecture.Sorties({"f": root})
            view.exiger("f", "c/k000.6")
            self.assertTrue(view.couvre("f", "k000"))
            self.assertFalse(view.couvre("f", "k00"))
            self.assertFalse(view.couvre("f", "k001"))
            list_of = [entrees.Entree("f", "k000", b"", 0), entrees.Entree("f", "k001", b"", 0)]
            with self.assertRaises(lecture.Erreur):
                judge.require_coverage(view, list_of, "essai")
            view.lire("f", "c/k001")
            judge.require_coverage(view, list_of, "essai")
        finally:
            shutil.rmtree(root)


def add_to(path, bytes_count):
    with open(path, "ab") as f:
        f.write(bytes_count)


# lecture.figer in a subprocess, as uid 65534 when started as root (lecture imported first): exit 10 on Refus, 0 without
# error, 1 on any other exception (Python's own exit code), 11 if root cannot drop its privileges.
FREEZE_WITHOUT_PRIVILEGE = """import os, sys
sys.path.insert(0, sys.argv[1])
import lecture
if os.geteuid() == 0:
    try:
        os.setgroups([]); os.setgid(65534); os.setuid(65534)
    except OSError:
        sys.exit(11)
try:
    lecture.figer(sys.argv[2])
except lecture.Refus:
    sys.exit(10)
"""


class TestFrozen(unittest.TestCase):
    """ruche-0036: outputs are frozen (listing and SHA-256 of each file); only what was frozen is read."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "s", "c"))
        for nom, bytes_count in (("s/c/k000", b"abc"), ("s/c/k001", b""), ("s/s.err", b"")):
            with open(os.path.join(self.root, nom), "wb") as f:
                f.write(bytes_count)
        os.symlink("/etc/hostname", os.path.join(self.root, "s", "lien"))
        self.figees = {"f": lecture.figer(self.root)}

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_fingerprint(self):
        empty_one = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(self.figees["f"], {"s": "dossier", "s/c": "dossier", "s/lien": "autre", "s/s.err": empty_one, "s/c/k001": empty_one,
                                            "s/c/k000": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"})

    def test_only_the_frozen_one_reads(self):
        view = lecture.Sorties({"f": self.root}, figees=self.figees)
        self.assertEqual((view.exiger("f", "s/c/k000"), view.lire("f", "s/c/absent")), (b"abc", None))
        view.controler()
        copied = lecture.Sorties(view)
        self.assertEqual((copied.lues, list(copied)), (set(), [self.root]))

        def path(relative_one):
            return os.path.join(self.root, relative_one)
        for nom, change, relative_one in (("modifié", lambda: add_to(path("s/c/k000"), b"x"), "s/c/k000"),
                                      ("retiré", lambda: os.remove(path("s/c/k000")), "s/c/k000"),
                                      ("ajouté", lambda: add_to(path("s/c/absent"), b""), "s/c/absent")):
            with self.subTest(nom=nom):
                change()
                with self.assertRaises(lecture.Refus):
                    copied.lire("f", relative_one)
                with self.assertRaises(lecture.Refus):
                    copied.controler()
                shutil.rmtree(self.root)
                self.setUp()
                copied = lecture.Sorties({"f": self.root}, figees=self.figees)

    def test_addition_not_read(self):
        add_to(os.path.join(self.root, "s", "ajout"), b"")
        view = lecture.Sorties({"f": self.root}, figees=self.figees)
        self.assertEqual(view.exiger("f", "s/c/k000"), b"abc")
        with self.assertRaises(lecture.Refus):
            view.controler()

    def test_judge_without_privilege(self):
        """The judge not root (as on a hosted runner, here uid 65534 in a subprocess): any system error while freezing what
        the container left (status, listing, opening) is a refusal (Refus, exit 1), never an error of the environment (exit 2)."""
        def freeze_without_privilege():
            r = subprocess.run([sys.executable, "-I", "-c", FREEZE_WITHOUT_PRIVILEGE, HERE, self.root], capture_output=True,
                               text=True, timeout=60)
            if r.returncode == 11:
                self.skipTest("root cannot drop to uid 65534 here: the non-root judge is not tested")
            return r.returncode, r.stderr
        for folder, _, files in os.walk(self.root):
            os.chmod(folder, 0o755)
            for path in (os.path.join(folder, nom) for nom in files):
                if not os.path.islink(path):  # s/lien is not followed
                    os.chmod(path, 0o644)
        self.assertEqual(freeze_without_privilege(), (0, ""))  # everything readable: frozen as root freezes it
        for relative_one, mode in (("s", 0o444), ("s/c", 0o444), ("s", 0o111), ("s", 0o000), ("s/c/k000", 0o000)):
            with self.subTest(relative_one=relative_one, mode=oct(mode)):
                path = os.path.join(self.root, relative_one)
                old = 0o755 if os.path.isdir(path) else 0o644  # as set above
                os.chmod(path, mode)
                try:
                    self.assertEqual(freeze_without_privilege(), (10, ""))
                finally:
                    os.chmod(path, old)


class TestReferenceCodec(unittest.TestCase):
    def test_round_trip(self):
        rng = random.Random(5)
        projet = toy_plugin.Projet({})
        for _, d in projet.corpus(None) + projet.aleatoires(rng):
            self.assertEqual(toy_plugin.decompresser(toy_plugin.compresser(d)), d)

    def test_invalid_streams_recognized(self):
        z = toy_plugin.compresser(b"abc" * 100)
        self.assertIsNone(toy_plugin.decompresser(z[:-1]))
        self.assertIsNone(toy_plugin.decompresser(z + b"\x00"))
        self.assertIsNone(toy_plugin.decompresser(z[:-4] + bytes(4)))


class TestSourceCopy(unittest.TestCase):
    def test_links_refused(self):
        repo, destination = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            shutil.copyfile(os.path.join(TOY, "rle.h"), os.path.join(repo, "rle.h"))
            os.symlink("/etc/hostname", os.path.join(repo, "rle.c"))
            with self.assertRaises(lecture.Refus):
                judge.copy_sources(repo, destination, ["rle.c", "rle.h"], ["rle.c", "rle.h"])
        finally:
            shutil.rmtree(repo)
            shutil.rmtree(destination)

    def test_subfolder(self):
        repo, destination = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(repo, "src"))
            open(os.path.join(repo, "src", "a.c"), "w").close()
            os.symlink("/etc", os.path.join(repo, "piege"))
            judge.copy_sources(repo, destination, ["src/*.c", "piege/*"], ["src/a.c"])
            self.fail("le dossier lien aurait dû être refusé")
        except lecture.Refus:
            pass
        finally:
            shutil.rmtree(repo)
            shutil.rmtree(destination)


class TestImage(unittest.TestCase):
    def test_packages(self):
        self.assertIn("RUN apt-get update", container.dockerfile(["zlib1g-dev"]))
        self.assertTrue(container.dockerfile([]).rstrip().endswith("WORKDIR /"))
        for wrong_one in ("x; curl", "-y", "A"):
            with self.assertRaises(lecture.Erreur):
                container.dockerfile([wrong_one])


# ------------------------------------------------------------------ ruche-0037: the same conditions in every mode

class FakeDocker:
    """Stand-in for conteneur.Docker: records each container (command, mounts, standard input) and answers like chrono."""

    def __init__(self):
        self.calls = []

    def launch(self, command, mounts, pids=2, entry=None, timeout_seconds=3600):
        self.calls.append((command, mounts, entry.decode()))
        token, _, *plan = entry.decode().splitlines()
        output_text = "".join(json.dumps({"jeton": token, "etiquette": line_text.split("\t")[0], "code": 0, "signal": 0,
                                     "instructions": 1}) + "\n" for line_text in plan)
        return subprocess.CompletedProcess(command, 0, output_text.encode(), b"")


# A stand-in for docker that records each call (arguments, standard input) and answers as chrono would.
DOCKER_STOPWATCH = r"""#!/usr/bin/env python3
import json, os, sys
if sys.argv[1] != "run":  # ruche-0136: Docker's record of the container, read after it ends, then its removal
    print(json.dumps({"Status": "exited", "Error": "", "ExitCode": 0}) if sys.argv[1] == "inspect" else "")
    sys.exit(0)
entree = sys.stdin.read()
with open(os.environ["FAUX_DOCKER_JOURNAL"], "a") as f:
    f.write(json.dumps([sys.argv[1:], entree]) + "\n")
jeton, _, *plan = entree.splitlines()
for ligne in plan:
    print(json.dumps({"jeton": jeton, "etiquette": ligne.split("\t")[0], "code": 0, "signal": 0, "instructions": 1}))
"""


# Docker's own mounts in a container of the judge (cgroup v1 and v2, /proc and /sys masked; /dev/shm also sorted with the judge's).
DOCKER_MOUNTS = ["/proc", "/dev", "/dev/pts", "/sys", "/sys/fs/cgroup", "/sys/fs/cgroup/cpu", "/dev/mqueue", "/dev/shm",
                   "/proc/bus", "/proc/sys", "/proc/acpi", "/sys/firmware", "/sys/devices/virtual/powercap"]


class TestSameConditions(unittest.TestCase):
    """The judge starts the harness the same way in every mode (same arguments, same mounts); the mode reaches it on its
    descriptor 0 only."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workdir)

    def test_modes_differ_only_on_the_harness_input(self):
        docker = FakeDocker()
        run = container.Execution(docker, "/c", {"B": "/b"}, self.workdir)
        harness = [container.HARNESS, "/entrees", "/sorties"]
        run.launch("B", "/e", os.path.join(self.workdir, "s"), [("verifier", [container.HARNESS, "verifier", "/entrees", "/sorties"])], timeout_seconds=3600)
        run.launch("B", "/e", os.path.join(self.workdir, "s"), [("compression", [container.HARNESS, "compression", "/entrees", "/sorties"])])
        run.launch("B", "/e", os.path.join(self.workdir, "s"), [("compression", judge.VALGRIND + [container.HARNESS, "compression", "/entrees", "/sorties"])],
                         valgrind=True, timeout_seconds=3600)
        seen_items = []
        for command, mounts, entry in docker.calls:
            self.assertEqual(command, ["/chrono/chrono"])
            self.assertEqual(sorted(target.replace(container.LINK, "") for _, target, _ in mounts),
                             sorted(["/chrono", "/entrees", "/sorties", "/variante"] + ["/etc/" + n for n in container.ETC]))
            _, options, line_text = entry.splitlines()
            label, parameters, *argv = line_text.split("\t")
            self.assertEqual(argv[argv.index(container.HARNESS):], [container.HARNESS])
            self.assertEqual(parameters.split(), [label] + harness[1:])
            seen_items.append((options, argv))
        self.assertEqual(seen_items, [("3600 0", [container.HARNESS]), ("1800 0", [container.HARNESS]), ("3600 1", judge.VALGRIND + [container.HARNESS])])
        for wrong_one in ([container.HARNESS], ["/bin/sh", "-c", "x"], [container.HARNESS, "a\tb"]):
            with self.assertRaises(lecture.Erreur):
                run.launch("B", "/e", os.path.join(self.workdir, "s"), [("x", wrong_one)])

    def test_same_docker_request_in_every_mode(self):
        """The Docker command is the same in every mode (bounds, isolation, mounts, their options and their order, the
        image), but for the container's name; only the standard input differs. A stand-in docker, first on PATH, records
        each call made through the real Docker.lancer and answers as chrono would."""
        folder = os.path.join(self.workdir, "bin")
        os.makedirs(folder)
        with open(os.path.join(folder, "docker"), "w", encoding="utf-8") as f:
            f.write(DOCKER_STOPWATCH)
        os.chmod(os.path.join(folder, "docker"), 0o755)
        docker_log = os.path.join(self.workdir, "docker.journal")
        run = container.Execution(container.Docker("sha256:" + "0" * 64), "/c", {"B": "/b"}, self.workdir)
        outputs = os.path.join(self.workdir, "s")
        with mock.patch.dict(os.environ, {"PATH": folder + os.pathsep + os.environ["PATH"], "FAUX_DOCKER_JOURNAL": docker_log}):
            for mode, prefix_text, valgrind in (("verifier", [], False), ("compression", [], False), ("compression", judge.VALGRIND, True)):
                run.launch("B", "/e", outputs, [(mode, prefix_text + [container.HARNESS, mode, "/entrees", "/sorties"])],
                                 valgrind=valgrind)
        with open(docker_log, encoding="utf-8") as f:
            calls = [json.loads(line_text) for line_text in f]
        self.assertEqual(len(calls), 3)
        commands = []
        for command, _ in calls:
            i = command.index("--name")
            self.assertRegex(command[i + 1], r"^bee-juge-[0-9a-f]{12}$")
            commands.append(command[:i + 1] + command[i + 2:])
        self.assertEqual(commands, [commands[0]] * 3)
        command = commands[0]
        self.assertEqual(command[command.index("--ulimit"):command.index("--ulimit") + 4], container.Docker.BOUNDS)
        for option in container.ISOLATION:
            self.assertIn(option, command)
        root = os.path.join(self.workdir, "execution")  # ruche-0117: each execution's own tmpfs, at the same path
        self.assertEqual([c for c in command if c.startswith("type=bind")],
                         [f"type=bind,source={root}/chrono,target={container.LINK * 7}/chrono,readonly",
                          f"type=bind,source={root}/variante,target={container.LINK * 8}/variante,readonly",
                          f"type=bind,source={root}/entrees,target={container.LINK * 9}/entrees,readonly",
                          f"type=bind,source={root}/sorties,target={container.LINK * 10}/sorties"]
                         + [f"type=bind,source={root}/etc/{n},target=/etc/{n},readonly" for n in container.ETC])
        self.assertEqual(command[-2:], ["sha256:" + "0" * 64, "/chrono/chrono"])
        self.assertEqual(len({entry for _, entry in calls}), 3)

    def docker_commands(self, *calls):
        """The docker run commands the real Docker.lancer makes for these calls, a stand-in docker first on PATH."""
        folder, docker_log = os.path.join(self.workdir, "bin"), os.path.join(self.workdir, "docker.journal")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "docker"), "w", encoding="utf-8") as f:
            f.write(DOCKER_STOPWATCH)
        os.chmod(os.path.join(folder, "docker"), 0o755)
        with mock.patch.dict(os.environ, {"PATH": folder + os.pathsep + os.environ["PATH"], "FAUX_DOCKER_JOURNAL": docker_log}):
            for call in calls:
                call()
        with open(docker_log, encoding="utf-8") as f:
            return [json.loads(line_text)[0] for line_text in f]

    def test_one_mount_order_whatever_docker_draws(self):
        """ruche-0136: Docker up to 29.0 sorts the mounts it is given (binds, tmpfs, /dev/shm, /etc's files) by depth alone,
        those of equal depth in an order drawn for each container. Each folder the judge mounts, in an execution's container
        as in a build's, has a depth no other mount of the container shares, Docker's own included (MONTURES_DOCKER;
        test_profondeurs with Docker): whatever order Docker draws, they come out in one order, and land, through the image's
        link to its root, where they are named. The layout of juge-v3 (/variante at /etc's depth) fails this check."""
        run = container.Execution(container.Docker("i"), "/c", {"B": "/b"}, self.workdir)
        commands = self.docker_commands(
            lambda: run.launch("B", "/e", os.path.join(self.workdir, "s"), [("verifier", [container.HARNESS, "verifier", "/entrees", "/sorties"])]),
            lambda: container.Docker("i").launch(["true"], [(self.workdir, n, n != "/sortie") for n in ("/sources", "/outillage", "/sortie")],
                                                entry=b"jeton\n0 0\n"))
        depth = lambda c: os.path.normpath(c).count("/")  # noqa: E731

        def orders(command):
            targets = [o.split("target=")[1].split(",")[0] for o in command if o.startswith("type=bind")]
            folders = [c for c in targets if not c.startswith("/etc/")]
            others = [c for c in targets if c.startswith("/etc/")] + ["/dev/shm"] + [command[i + 1].split(":")[0] for i, o
                                                                                    in enumerate(command) if o == "--tmpfs"]
            unique_ones = len({depth(c) for c in folders}) == len(folders) and \
                not {depth(c) for c in folders} & {depth(c) for c in others + DOCKER_MOUNTS}
            return unique_ones, {tuple(c if c in folders else "" for c in sorted(draw, key=depth))  # where each one comes
                             for draw in itertools.permutations(folders + others)}
        for command, names in zip(commands, (["/chrono", "/variante", "/entrees", "/sorties"], ["/sources", "/outillage", "/sortie"])):
            unique_ones, drawn = orders(command)
            self.assertTrue(unique_ones)
            self.assertEqual(len(drawn), 1)
            self.assertEqual([c.replace(container.LINK, "") for c in drawn.pop() if c], names)
        old = [o.replace(container.LINK * 7 + "/chrono", "/chrono").replace(container.LINK * 8, container.LINK)
                  for o in commands[0]]  # juge-v3: /chrono at depth 1 (/tmp's), /variante at 2 (/etc's)
        self.assertFalse(orders(old)[0])
        self.assertGreater(len(orders(old)[1]), 1)
        image = container.dockerfile([])
        self.assertLess(image.index(f"\nRUN ln -s / {container.LINK}\n"), image.index("\nUSER "))

    def test_tmpfs_in_use_is_an_error(self):
        """ruche-0117: each execution's tmpfs is unmounted at once, not detached (no --lazy): one still in use when its
        container has ended stops the judge with an error, rather than staying alive out of sight."""
        docker, held = FakeDocker(), []
        launch = docker.launch

        def hold_it(command, mounts, **options):
            held.append(os.open(os.path.dirname(mounts[0][0]), os.O_RDONLY))
            return launch(command, mounts, **options)
        docker.launch = hold_it
        root = os.path.join(self.workdir, "execution")
        try:
            with self.assertRaisesRegex(lecture.Erreur, "^umount du tmpfs"):
                container.Execution(docker, "/c", {"B": "/b"}, self.workdir).launch(
                    "B", "/e", os.path.join(self.workdir, "s"), [("verifier", [container.HARNESS, "verifier", "/entrees", "/sorties"])])
            self.assertTrue(os.path.ismount(root))
        finally:
            for fd in held:
                os.close(fd)
            if os.path.ismount(root):
                container.mount_point("umount", root)
        self.assertEqual(len(held), 1)

    def test_mounted_folders_have_neutral_names(self):
        """A scenario's outputs are mounted on /sorties, as verification's, from a neutral folder renamed afterwards."""
        projet = toy_plugin.Projet({})
        folders = judge.prepare(self.workdir, "verification", projet.repetition(random.Random(1), projet.corpus(TOY)), ("f", "z"))
        outputs = judge.outputs_of(self.workdir, "sorties-verification-B", ("f", "z"))
        for folder in list(folders.values()) + list(outputs.values()):
            self.assertRegex(os.path.basename(folder), r"^[0-9a-f]{16}$")
        mounted, test = [], self

        class FakeRun:
            def launch(self, variant, entrees, folder, plan, **options):
                test.assertRegex(os.path.relpath(folder, test.workdir), r"^[0-9a-f]{16}$")
                test.assertEqual([c[-1] for _, c in plan], ["/sorties"])
                mounted.append(folder)
                with open(os.path.join(folder, "sortie"), "w", encoding="utf-8") as f:
                    f.write(plan[0][0])
                return {plan[0][0]: {}}
        plans = {c: [(s, [container.HARNESS, s, "/entrees", "/sorties"]) for s, cs in projet.SCENARIOS.items() if cs == c] for c in "fz"}
        measurements, _ = judge.launch_by_side(FakeRun(), "B", folders, outputs, plans, list(projet.SCENARIOS))
        self.assertEqual(set(measurements), set(projet.SCENARIOS))
        self.assertEqual(len(set(mounted)), len(projet.SCENARIOS))
        for s, c in projet.SCENARIOS.items():
            self.assertEqual(lecture.exiger(outputs[c], f"{s}/sortie"), s.encode())


class TestShuffle(unittest.TestCase):
    """Verification inputs are mixed into the measured inputs, drawn from the judge's seed (A and B get the same); every
    input is written shuffled and renamed, the plugin keeping its names."""

    def draw(self, seed, repetitions=3):
        projet = toy_plugin.Projet({})
        rng = random.Random(seed)
        corpus = projet.corpus(TOY)
        verification = projet.verification(rng, corpus)
        written_ones, neutral_ones = judge.rename(rng, verification)
        names = {(e.cote, e.nom): n for e, n in zip(verification, neutral_ones)}
        by_side = {c: [e for e in verification if e.cote == c] for c in "fz"}
        rounds = {c: judge.round_number(rng, l) for c, l in by_side.items()}
        how_many = {c: -(-len(l) // repetitions) for c, l in by_side.items()}
        return verification, written_ones, names, [(judge.interleave(rng, projet.repetition(rng, corpus), rounds, how_many, names), how_many)
                                             for _ in range(repetitions)]

    def test_verification_inputs_renamed(self):
        verification, written_ones, names, _ = self.draw(1)
        entrees.verifier_entrees(written_ones, ("f", "z"))
        self.assertEqual(sorted(e.nom for e in written_ones), [f"e{i:04d}" for i in range(len(verification))])
        self.assertNotEqual([e.donnees for e in written_ones], [e.donnees for e in verification], "shuffled")
        by_name = {(e.cote, e.nom): e for e in written_ones}
        for e in verification:
            self.assertEqual(by_name[(e.cote, names[(e.cote, e.nom)])]._replace(nom=e.nom), e)

    def test_each_verification_input_passes_in_a_measurement(self):
        verification, written_ones, names, draws = self.draw(1)
        written_one = {(e.cote, e.nom): e for e in written_ones}
        passed_ones = set()
        for (interleaved, shuffled), how_many in draws:
            entrees.verifier_entrees(interleaved, ("f", "z"))
            self.assertTrue(all(re.fullmatch(r"e\d{4}", e.nom) for e in interleaved))
            self.assertEqual(len(shuffled), sum(how_many.values()))
            by_name = {(e.cote, e.nom): e for e in interleaved}
            positions = sorted(interleaved.index(by_name[key]) for key in shuffled)
            self.assertLess(positions[0], len(interleaved) - len(shuffled), "mixed in, not appended")
            for (quoted_side, nom), verification_name in shuffled.items():
                self.assertEqual(by_name[(quoted_side, nom)]._replace(nom=verification_name), written_one[(quoted_side, verification_name)])
            for c in "fz":
                self.assertEqual(sum(1 for quoted_side, _ in shuffled if quoted_side == c), how_many[c])
            passed_ones |= set(shuffled.values())
        self.assertEqual(passed_ones, {e.nom for e in written_ones})

    def test_drawn_from_the_seed(self):
        self.assertEqual(self.draw(7)[3], self.draw(7)[3])
        self.assertNotEqual(self.draw(7)[3], self.draw(8)[3])

    def test_names_translated_for_the_plugin(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        os.makedirs(os.path.join(root, "c"))
        for nom in ("e0003", "e0003.6", "e0007"):
            with open(os.path.join(root, "c", nom), "wb") as f:
                f.write(nom.encode())
        view = lecture.Sorties({"f": root}, {("f", "k000"): "e0003", ("f", "a.b"): "e0007"})
        self.assertEqual((view.exiger("f", "c/k000"), view.exiger("f", "c/k000.6"), view.lire("f", "c/a.b")), (b"e0003", b"e0003.6", b"e0007"))
        self.assertTrue(view.couvre("f", "k000") and view.couvre("f", "a.b"))
        self.assertIsNone(view.lire("f", "c/k001"))

    def test_mixed_input_same_output_as_in_verification(self):
        """B's output of a mixed-in input, in a measured run, must be its own verification output, byte for byte."""
        travail = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, travail)

        def ecrire(path, bytes_count):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(bytes_count)
        def frozen_one(folder):  # ruche-0036: the judge compares outputs as frozen when their container ended
            return lecture.Sorties({"f": os.path.join(travail, folder)}, figees={"f": lecture.figer(os.path.join(travail, folder))})
        ecrire(os.path.join(travail, "v", "c", "e0004"), b"sortie")
        ecrire(os.path.join(travail, "v", "e", "e0004.6"), b"0 6\n")
        verification = frozen_one("v")
        index = judge.outputs_by_input(verification.figees)
        self.assertEqual(sorted(index[("f", "e0004")]), ["c/e0004", "e/e0004.6"])
        ecrire(os.path.join(travail, "m", "compression", "c", "e0011"), b"sortie")
        ecrire(os.path.join(travail, "m", "compression", "e", "e0011.6"), b"0 6\n")
        self.assertEqual(judge.same_outputs(index, verification, frozen_one("m"), {("f", "e0011"): "e0004"}, [("compression", "f")]), 2)
        ecrire(os.path.join(travail, "m", "compression", "c", "e0011"), b"autre")
        with self.assertRaisesRegex(lecture.Refus, "différente"):
            judge.same_outputs(index, verification, frozen_one("m"), {("f", "e0011"): "e0004"}, [("compression", "f")])
        with self.assertRaises(lecture.Erreur):
            judge.same_outputs(index, verification, frozen_one("m"), {("f", "e0012"): "e0004"}, [("compression", "f")])
        measured = frozen_one("m")
        ecrire(os.path.join(travail, "m", "compression", "c", "e0011"), b"sortie")
        with self.assertRaisesRegex(lecture.Refus, "empreinte"):
            judge.same_outputs(index, verification, measured, {("f", "e0011"): "e0004"}, [("compression", "f")])
        # ruche-0117: counted per scenario, not per side: a scenario of the side without a comparable output is an error.
        two = [("compression", "f"), ("compression_bis", "f")]
        with self.assertRaisesRegex(lecture.Erreur, "compression_bis"):
            judge.same_outputs(index, verification, frozen_one("m"), {("f", "e0011"): "e0004"}, two)
        ecrire(os.path.join(travail, "m", "compression_bis", "e", "e0011.6"), b"0 6\n")
        self.assertEqual(judge.same_outputs(index, verification, frozen_one("m"), {("f", "e0011"): "e0004"}, two), 3)


class TestConditionsFixes(unittest.TestCase):
    """Fixed times on what a container sees; /variante holds the harness alone; repetitions at least 1."""

    def test_times_and_variant(self):
        travail = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, travail)
        build_step = os.path.join(travail, "construction")
        os.makedirs(os.path.join(build_step, "obj"))
        for nom in ("execution", "obj/rle.o"):
            with open(os.path.join(build_step, nom), "wb") as f:
                f.write(nom.encode())
        variant = judge.variant(build_step, os.path.join(travail, "variante"))
        self.assertEqual(os.listdir(variant), ["execution"])
        container.fixed_times(variant)
        for path in (variant, os.path.join(variant, "execution")):
            st = os.stat(path)
            self.assertEqual((st.st_atime, st.st_mtime), (container.TIME, container.TIME))
        os.remove(os.path.join(build_step, "execution"))
        os.symlink("/etc/hostname", os.path.join(build_step, "execution"))
        with self.assertRaises(lecture.Refus):
            judge.variant(build_step, os.path.join(travail, "variante-2"))

    def test_repetitions_at_least_one(self):
        for options in (["--repetitions", "0", "--warmup", "0"], ["--warmup", "-1"]):
            with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as end:
                judge.main(["--tooling", TOY, "--source-a", TOY, "--source-b", TOY] + options)
            self.assertEqual(end.exception.code, 2)
            self.assertIn("--repetitions", error.getvalue())

# ------------------------------------------------------------------ ruche-0036: frozen outputs, drawn order, CPU times

FOUR_SCENARIOS = {"compression": "f", "compression_bis": "f", "decompression": "z", "decompression_bis": "z"}
# ruche-0148 (J2b): every key of juge.json as judge.py wrote it before J2b, on the four-scenario toy (TestOrderAndFingerprints).
JUGE_V3_KEYS = """A B analyse architecture au_dela_du_bruit base chauffe chronometre code coeurs commun compilateur compression compression_bis
constructions_suspectes constructions_suspectes_omises constructions_suspectes_par_type debit_compression debit_decompression decompression
decompression_bis degradation_au_dela_du_bruit deroulement duree_s egalites entrees_melees etape f fixes_sans_mesure gain graine graine_ordre
greffon image image_id instructions instructions_compression instructions_decompression instructions_sans_melange isolation isolement issue
juge machine max mediane melees_par_repetition memoire memoire_max_ko mesures methode metriques min minmax_disjoints ordre
origine_des_graines p_amelioration p_degradation paires paires_utiles permis prefixes processeur projet ratio repetitions scenarios sens
seuil_k sortie_compressee sorties_comparees source systeme temps_processeur temps_processeur_s test_du_signe tete unite valeur_retenue
valeurs variantes verification verification_seulement version victoires_A victoires_B z"""


def toy_with_four_scenarios(folder, toy=TOY):
    """A copy of the toy project (or of its English twin's base) with two scenarios per side (the harness does the same work
    in every mode)."""
    shutil.copytree(toy, folder, ignore=shutil.ignore_patterns("__pycache__"))
    for file, old, new in (
            ("plugin", 'SCENARIOS = {"compression": "f", "decompression": "z"}', f"SCENARIOS = {FOUR_SCENARIOS!r}"),
            ("harness", '|| strcmp(mode, "decompression") == 0);',
             '|| strcmp(mode, "decompression") == 0 || strcmp(mode, "compression_bis") == 0\n'
             '         || strcmp(mode, "decompression_bis") == 0);')):
        path = toy_file(folder, file)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(replace_with(text, old, new))
    return folder


def toy_harness(entrees, outputs):
    """The toy harness (jouet/bee/juge/execution.c), emulated with the plugin's reference codec: the same work in every
    mode, f inputs give c/NAME, z inputs d/NAME and e/NAME."""
    def ecrire(folder, nom, bytes_count):
        os.makedirs(os.path.join(outputs, folder), exist_ok=True)
        with open(os.path.join(outputs, folder, nom), "wb") as f:
            f.write(bytes_count)
    with open(os.path.join(entrees, "liste"), encoding="ascii") as f:
        for line_text in filter(str.strip, f):
            quoted_side, nom, _ = line_text.split()
            with open(os.path.join(entrees, quoted_side, nom), "rb") as g:
                data = g.read()
            if quoted_side == "f":
                ecrire("c", nom, toy_plugin.compresser(data))
            else:
                original = toy_plugin.decompresser(data)
                ecrire("d", nom, original or b"")
                ecrire("e", nom, b"-1 0\n" if original is None else b"0 %d\n" % len(original))


class EmulatedDocker:
    """Stand-in for conteneur.Docker: nothing is run; chrono (plan on its standard input) and the toy harness are emulated
    on the host folders of the mounts. Each container is recorded (plan labels, variant, writable mounts, whether they
    were empty, the CPU time answered); `apres(self)` is called once each has ended."""

    image = "sha256:" + "0" * 64

    def __init__(self, after=None):
        self.containers, self.after = [], after

    def launch(self, command, mounts, pids=2, entry=None, timeout_seconds=3600):
        host = {target.replace(container.LINK, ""): source for source, target, _ in mounts}  # the image's link, followed
        token, _, *plan = entry.decode().splitlines()
        written_items = [source for source, _, read_only in mounts if not read_only]
        with open(os.path.join(host["/variante"], "execution"), encoding="ascii") as f:
            variant = f.read()
        c = {"etiquettes": [p.split("\t")[0] for p in plan], "variante": variant, "ecrits": written_items,
             "neuf": all(not os.listdir(d) for d in written_items), "tmpfs": all(os.path.ismount(os.path.dirname(d)) for d in written_items)}
        self.containers.append(c)
        lines = []
        for line_text in plan:
            label, parameters, *_ = line_text.split("\t")
            _, c_inputs, c_outputs = parameters.split()
            toy_harness(host[c_inputs], host[c_outputs])
            user, system = 0.001 * len(self.containers), 0.0005
            c["cpu"] = round(user + system, 6)
            lines.append(json.dumps({"jeton": token, "etiquette": label, "code": 0, "signal": 0, "utilisateur_s": user,
                                      "systeme_s": system, "mur_s": 0.01, "maxrss_ko": 1000, "instructions": 1000}))
        if self.after:
            self.after(self)
        return subprocess.CompletedProcess(command, 0, ("\n".join(lines) + "\n").encode(), b"")


def empty_open_folder(travail):
    """chrono's folder for DockerEmule (nothing is run): an empty folder."""
    return container.open_folder(os.path.join(travail, "chrono"))


def emulated_variant(build_step, folder):
    """/variante for DockerEmule: a harness file that names the variant (the last letter of the folder)."""
    os.makedirs(folder)
    with open(os.path.join(folder, "execution"), "w", encoding="ascii") as f:
        f.write(folder[-1])
    return folder


class TestOrderAndFingerprints(unittest.TestCase):
    """ruche-0036, without Docker: juge.main on the toy with two scenarios per side, conteneur.Docker emulated."""

    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.mkdtemp(prefix="bee-ordre-")
        cls.base = toy_with_four_scenarios(os.path.join(cls.workdir, "jouet"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workdir, ignore_errors=True)

    def run_the_judge(self, after=None, seed="00" * 16, graine_ordre=None, base=None):
        base, emulated, output_text = base or self.base, EmulatedDocker(after), io.StringIO()
        with mock.patch.object(judge.shutil, "which", return_value="/usr/bin/docker"), \
                mock.patch.object(judge.container, "build_image", return_value="image"), \
                mock.patch.object(judge.container, "image_id", return_value="sha256:" + "0" * 64), \
                mock.patch.object(judge, "variant", side_effect=emulated_variant), \
                mock.patch.object(judge.container, "Docker", return_value=emulated), \
                mock.patch.object(judge.container, "compile_stopwatch", side_effect=lambda docker, travail: empty_open_folder(travail)), \
                mock.patch.object(judge, "build", return_value=surveys()), \
                contextlib.redirect_stdout(output_text), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(judge.main(["--tooling", base, "--source-a", base, "--source-b", base, "--repetitions", "3"]
                                       + (["--seed", seed] if seed else []) + (["--order-seed", graine_ordre] if graine_ordre else [])), 0)
        return json.loads(output_text.getvalue()), emulated

    def test_both_contracts_same_judgement(self):
        """ruche-0148 (J2): the toy and its English twin, at the same seeds, get the same report but for the plugin's SHA-256 and
        the judge's duration."""
        english = toy_with_four_scenarios(os.path.join(self.workdir, "toy-4"), english_toy(os.path.join(self.workdir, "toy")))
        reports = [self.run_the_judge(graine_ordre="01" * 16, base=b)[0] for b in (self.base, english)]
        for r, path in zip(reports, (toy_file(self.base, "plugin"), toy_file(english, "plugin"))):
            with open(path, "rb") as f:
                self.assertEqual(r["judge"].pop("plugin"), hashlib.sha256(f.read()).hexdigest())
            self.assertIsInstance(r.pop("duration_s"), float)
        self.assertEqual(reports[1], reports[0])

    def test_judge_json_is_the_map_translation(self):
        """ruche-0148 (J2b), as proof P2 checks data: every key and closed value of judge.json is in names.yaml's judge_report (keys,
        domains, data-keyed places), so it reads back into French and again into the same English; read back, it has the keys juge.json
        had at juge-v3 (JUGE_V3_KEYS, from judge.py before J2b, on this toy at these seeds), the stopped judge's report too."""
        if yaml is None:
            self.skipTest("PyYAML required (pip install -r tools/requirements.txt)")
        sys.path[:0] = [os.path.join(os.path.dirname(HERE), "migration"), os.path.dirname(HERE)]
        try:
            import rename
        finally:
            del sys.path[:2]
        with open(os.path.join(os.path.dirname(HERE), "migration", "names.yaml"), encoding="utf-8") as f:
            names = rename.Names(f.read())
        english = self.run_the_judge(graine_ordre="01" * 16)[0]
        french = names.data("judge_report", english, True)
        self.assertEqual(names.data("judge_report", french, False), english)
        keys = set()

        def walk(o):
            [(keys.add(k), walk(v)) for k, v in o.items()] if isinstance(o, dict) else [walk(x) for x in o] if isinstance(o, list) else None
        walk(french)
        self.assertEqual(keys, set(JUGE_V3_KEYS.split()))
        self.assertEqual((french["juge"]["issue"], french["juge"]["origine_des_graines"]), ("juste", {"graine": "donnee", "graine_ordre": "donnee"}))
        stopped = os.path.join(self.workdir, "stopped.json")
        with mock.patch.dict(judge.FAILURE, json=stopped, judge={"version": 3, "common": "juge-v3", "source": None, "base": None, "head": None}), \
                contextlib.redirect_stderr(io.StringIO()):
            judge.stop_it(2, "juge : erreur : x", True)
        with open(stopped, encoding="utf-8") as f:
            self.assertEqual(names.data("judge_report", json.load(f), True), {"juge": {
                "version": 3, "commun": "juge-v3", "source": None, "base": None, "tete": None, "code": 2, "issue": "erreur_environnement",
                "panne_machine": True, "motif": "juge : erreur : x"}})

    def test_drawn_order_and_processor_time(self):
        """The order is drawn at each repetition, the same for A and B, from its own seed (secrets, independent of the
        inputs' seed) recorded in juge.json, and is the order run; each scenario's CPU time is the one chrono measured; one
        command and one fresh writable folder per container."""
        report, emulated = self.run_the_judge(graine_ordre="00" * 16)
        self.assertEqual(len(emulated.containers), 2 * 2 + 2 * 4 * 4 + 2 * 2)  # verification, 1 + 3 repetitions, instructions
        for c in emulated.containers:  # ruche-0117: its fresh writable folder on its own tmpfs, mounted for it
            self.assertEqual((len(c["etiquettes"]), len(c["ecrits"]), c["neuf"], c["tmpfs"]), (1, 1, True, True))
        unfolding = report["judge"]["scenarios"]["steps"]
        self.assertEqual([e["step"] for e in unfolding], ["warmup", "measurement", "measurement", "measurement", "instructions"])
        self.assertEqual([e["variants"] for e in unfolding], ["AB", "BA", "AB", "BA", "AB"])
        instructions_given = []
        for e in unfolding:
            expected_items = toy_plugin.Projet.INSTRUCTIONS if e["step"] == "instructions" else FOUR_SCENARIOS
            self.assertEqual(sorted(e["order"]), sorted(expected_items))
            instructions_given += [(v, s, e["cpu_time_s"][v][s]) for v in e["variants"] for s in e["order"]]
        runs_launched = [(c["variante"], c["etiquettes"][0], c["cpu"]) for c in emulated.containers if c["etiquettes"] != ["verifier"]]
        self.assertEqual(runs_launched, instructions_given)
        self.assertGreater(len({tuple(e["order"]) for e in unfolding[:4]}), 1)

        def orders(r):
            return [e["order"] for e in r["judge"]["scenarios"]["steps"]]

        def drawn(graine_ordre):  # the orders the recorded order seed alone gives
            draw = random.Random(bytes.fromhex(graine_ordre))
            return [draw.sample(list(FOUR_SCENARIOS), 4) for _ in range(4)] + [draw.sample(list(toy_plugin.Projet.INSTRUCTIONS), 2)]
        self.assertEqual((report["judge"]["scenarios"]["order_seed"], orders(report)), ("00" * 16, drawn("00" * 16)))
        self.assertEqual(orders(self.run_the_judge(seed="01" * 16, graine_ordre="00" * 16)[0]), orders(report))  # not from --graine
        seeds = {report["judge"]["scenarios"]["order_seed"]}
        for _ in range(2):  # same --graine, order seed from secrets: recorded, and it alone gives the orders
            other = self.run_the_judge()[0]
            graine_ordre = other["judge"]["scenarios"]["order_seed"]
            self.assertRegex(graine_ordre, r"\A[0-9a-f]{32}\Z")
            self.assertEqual(orders(other), drawn(graine_ordre))
            self.assertEqual((other["judge"]["seed"], other["judge"]["verification"]), (report["judge"]["seed"], report["judge"]["verification"]))
            seeds.add(graine_ordre)
        self.assertEqual(len(seeds), 3)

    def test_where_each_seed_came_from(self):
        """ruche-0136: juge.json says, for each seed (the inputs', the order's), whether the judge drew it or it was given on the
        command line (--seed, --order-seed: a local reproduction); only a report whose seeds were both drawn passes
        report.py --verify."""
        path = os.path.join(self.workdir, "graines.json")
        for seed, graine_ordre, origins in ((None, None, ("drawn", "drawn")), ("00" * 16, None, ("given", "drawn")),
                                               (None, "01" * 16, ("drawn", "given")), ("00" * 16, "01" * 16, ("given", "given"))):
            with self.subTest(seed=seed, graine_ordre=graine_ordre):
                j = self.run_the_judge(seed=seed, graine_ordre=graine_ordre)[0]
                j["judge"].update(base="2" * 40, head="3" * 40)
                self.assertEqual(j["judge"]["seed_origin"], dict(zip(("seed", "order_seed"), origins)))
                self.assertEqual((j["judge"]["seed"] == seed, j["judge"]["scenarios"]["order_seed"] == graine_ordre),
                                 (seed is not None, graine_ordre is not None))
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(j, f)
                if origins == ("drawn", "drawn"):
                    self.assertEqual(report.verifier(path, report.publish(path, "0"), "2" * 40, "3" * 40), j)
                else:
                    with self.assertRaisesRegex(report.Gap, "seed given"):
                        report.verifier(path, report.publish(path, "0"), "2" * 40, "3" * 40)

    def test_each_execution_on_its_own_tmpfs(self):
        """ruche-0117: each container's folders are on a tmpfs mounted for it alone, of fixed bounds: whatever the containers
        before it wrote, each finds the same free space and the same device, and nothing of it remains after the judge."""
        seen_items = []

        def after(emulated):
            written = emulated.containers[-1]["ecrits"][0]
            st, fs = os.stat(written), os.statvfs(written)
            seen_items.append((st.st_dev, fs.f_blocks * fs.f_frsize, fs.f_files, os.path.ismount(os.path.dirname(written))))
            self.assertEqual(sorted(os.listdir(os.path.dirname(written))), ["chrono", "entrees", "etc", "sorties", "variante"])
        _, emulated = self.run_the_judge(after)
        self.assertEqual(len(seen_items), len(emulated.containers))
        self.assertEqual(set(seen_items), {(seen_items[0][0], 4 << 30, 262144, True)})
        self.assertFalse(any(os.path.ismount(os.path.dirname(c["ecrits"][0])) for c in emulated.containers))

    def test_suspicious_most_serious_first(self):
        """ruche-0117: juge.json lists the most serious constructs first (GRAVITE), SUSPECTES_MAX at most, and counts each kind."""
        found_ones = [{"type": "source", "detail": f"pragma {i}"} for i in range(judge.SUSPICIOUS_MAX + 20)]
        found_ones += [{"type": "symbole", "detail": "s"}, {"type": "inconnu", "detail": "?"}, {"type": "appel_interdit", "detail": "g"}]
        with mock.patch.object(judge.analysis, "analyse", return_value=found_ones), \
                mock.patch.object(judge.platform, "machine", return_value="x86_64"):
            j = self.run_the_judge()[0]["judge"]
        self.assertEqual([s["type"] for s in j["suspicious_constructs"][:3]], ["appel_interdit", "symbole", "source"])
        self.assertEqual((len(j["suspicious_constructs"]), j["suspicious_constructs_omitted"]), (judge.SUSPICIOUS_MAX, 23))
        self.assertEqual(j["suspicious_constructs_by_type"], {"appel_interdit": 1, "inconnu": 1, "source": 120, "symbole": 1})

    def test_fixed_metric_read_on_verification_alone(self):
        """ruche-0117: a fixed metric that no scenario computes from its timed outputs (the ratio, here the base's scenario
        returns none) is flagged in juge.json and never beyond the noise, even where the sign test says so; the toy's own
        ratio, read on its timed outputs, is not flagged."""
        base = os.path.join(self.workdir, "sans-ratio")
        if not os.path.isdir(base):
            shutil.copytree(self.base, base)
            path = os.path.join(base, "bee", "juge", "projet.py")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(replace_with(text, ', ratio=sum(traites) / compresse if compresse else None)', ")"))
        true_one = stats.sign_test
        with mock.patch.object(judge.stats, "sign_test", side_effect=lambda a, b, direction: dict(true_one(a, b, direction), beyond_noise=True)):
            honest_one, without_ratio = self.run_the_judge()[0], self.run_the_judge(base=base)[0]
        self.assertEqual(honest_one["judge"]["verification"]["fixed_without_measurement"], [])
        self.assertEqual(without_ratio["judge"]["verification"]["fixed_without_measurement"], ["ratio"])
        for report_, only_this in ((honest_one, False), (without_ratio, True)):
            ratio = report_["metrics"]["ratio"]
            self.assertEqual((ratio["verification_only"], ratio["beyond_noise"]), (only_this, not only_this))
            self.assertTrue(report_["metrics"]["debit_compression"]["beyond_noise"])
            self.assertFalse(report_["metrics"]["debit_compression"]["verification_only"])

    def test_outputs_changed_after_fingerprint(self):
        """An output changed, added or removed after its container ended (here, while the next container runs) is refused."""
        def change(action):
            def after(emulated):
                before, last = emulated.containers[-2:] if len(emulated.containers) > 1 else (None, None)
                if emulated.changed_ones or not before or "verifier" in before["etiquettes"] + last["etiquettes"] \
                        or before["variante"] != last["variante"]:
                    return
                emulated.changed_ones = True
                travail = os.path.dirname(os.path.dirname(before["ecrits"][0]))  # <travail>/execution/sorties (ruche-0117)
                found_items = glob.glob(os.path.join(travail, "*", before["etiquettes"][0]))
                self.assertEqual(len(found_items), 1)  # the previous scenario's frozen folder, renamed <side>/<scenario>
                action(found_items[0])
            return after
        first = lambda d: sorted(os.path.join(r, n) for r, _, names in os.walk(d) for n in names)[0]  # noqa: E731
        for nom, action in (("modifiée", lambda d: add_to(first(d), b"x")), ("retirée", lambda d: os.remove(first(d))),
                            ("ajoutée", lambda d: add_to(os.path.join(d, "ajout"), b""))):
            with self.subTest(nom=nom), mock.patch.object(EmulatedDocker, "changed_ones", False, create=True), \
                    self.assertRaises(lecture.Refus) as e:
                self.run_the_judge(change(action))
            self.assertIn("après leur empreinte" if nom == "ajoutée" else "après son empreinte", str(e.exception))


# ------------------------------------------------------------------ juge.yml (ruche-0024): read and run its scripts

JUDGE_YML = os.path.join(os.path.dirname(os.path.dirname(HERE)), ".github", "workflows", "juge.yml")
try:
    import yaml
except ImportError:  # the registry's CI (validation.yml) installs PyYAML; the Docker meta-test job may not have it
    yaml = None

# Stand-in for the GitHub CLI (`gh api repos/O/R/compare/BASE...HEAD --jq .status`), put first on PATH as TestFailClosed
# does with its tools. It logs its arguments and whether it got a token; FAUX_GH_ETAT forces the answer, FAUX_GH_CODE
# its exit code, FAUX_GH_DELAI makes it slow; otherwise it answers from the ancestry in the repository FAUX_GH_DEPOT.
FAKE_GH = r'''#!/usr/bin/env python3
import os, re, subprocess, sys, time
with open(os.environ["FAUX_GH_JOURNAL"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + (" +jeton" if os.environ.get("GH_TOKEN") else "") + "\n")
time.sleep(float(os.environ.get("FAUX_GH_DELAI", "0")))
if os.environ.get("FAUX_GH_CODE", "0") != "0":
    sys.exit(int(os.environ["FAUX_GH_CODE"]))
if "FAUX_GH_OCTETS" in os.environ:  # bytes that are not UTF-8
    sys.stdout.buffer.write(b"\xff\xfebehind\n")
    sys.exit(0)
if "FAUX_GH_ETAT" in os.environ:
    print(os.environ["FAUX_GH_ETAT"])
    sys.exit(0)
base, tete = re.fullmatch(r"repos/[^/]+/[^/]+/compare/([^.]+)\.\.\.(.+)", sys.argv[2]).groups()
depot = ["git", "-C", os.environ["FAUX_GH_DEPOT"], "merge-base", "--is-ancestor"]
if base == tete:
    print("identical")
elif subprocess.run(depot + [tete, base]).returncode == 0:
    print("behind")
elif subprocess.run(depot + [base, tete]).returncode == 0:
    print("ahead")
else:
    sys.exit(1)
'''


def fake_gh(folder):
    """Writes the stand-in gh into dossier/bin; returns (PATH with it first, journal of its calls)."""
    os.makedirs(os.path.join(folder, "bin"), exist_ok=True)
    with open(os.path.join(folder, "bin", "gh"), "w", encoding="utf-8") as f:
        f.write(FAKE_GH)
    os.chmod(os.path.join(folder, "bin", "gh"), 0o755)
    return os.path.join(folder, "bin") + os.pathsep + os.environ["PATH"], os.path.join(folder, "gh.journal")


def judge_workflow():
    with open(JUDGE_YML, encoding="utf-8") as f:
        text = f.read()
    data = yaml.safe_load(text)
    data["on"] = data.pop(True)  # YAML 1.1: the key « on » reads as true
    return text, data


def step(data, nom):
    found_ones = [e for e in data["jobs"]["juge"]["steps"] if e.get("name") == nom]
    if len(found_ones) != 1:
        raise AssertionError(f"step {nom!r} not found exactly once in juge.yml")
    return found_ones[0]


PREPARATION = "Commit de ce workflow, sur la branche principale du registre (le code du juge y est lu)"
HISTORY = "Historique déclaré (ancêtres de la base ; seul appel de judge.py avec le jeton, avant le greffon et la PR)"
IMAGE = "Image du juge (avec réseau, avant tout fichier de la PR)"
INPUTS = "Entrées de l'appelant, avant tout usage (un appel qui ne laisse pas un jugement complet s'arrête ici)"
WORKDIR = "Dossier de travail du juge, borné (tmpfs ; tout ce que les conteneurs écrivent y reste)"
JOB_OUTPUTS = ["code"] + list(report.FORMATS)


def runner_commands(output_text):
    """Workflow commands the GitHub Actions runner would act on in a step's output (actions/runner,
    ActionCommandManager): « ::name properties::data » at the start of a line (leading blanks ignored) and
    « ##[name properties]data » anywhere in it; lines split at \\n, \\r\\n and lone \\r. After
    « ::stop-commands::TOKEN », none until a command named TOKEN, which resumes them."""
    views, token = [], None
    for line_text in re.split(r"\r\n|\r|\n", output_text):
        line_text = line_text.lstrip()
        m = re.match(r"::([^\s:]+)[^:]*::(.*)", line_text) or re.search(r"##\[([^\s\]]+)[^\]]*\](.*)", line_text)
        if not m:
            continue
        nom, data = m.group(1), m.group(2)
        if token is not None:
            if nom.lower() == token.lower():
                token = None
                views.append("<resume>")
            continue
        if nom == "stop-commands":
            token = data
        views.append(nom)
    return views


@unittest.skipUnless(yaml, "PyYAML required (pip install -r outils/requirements.txt)")
class TestJudgeWorkflow(unittest.TestCase):
    """juge.yml reads the judge at its own commit, a commit of the registry's main, and prints the journal without
    workflow commands (ruche-0024); its scripts are run here with bash, gh replaced by a stand-in."""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.wf = judge_workflow()

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bee-workflow-")
        self.path, self.gh_log = fake_gh(self.dir)
        self.output = os.path.join(self.dir, "sortie")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def launch(self, script, env):
        open(self.output, "w").close()
        environment = {"PATH": self.path, "HOME": self.dir, "GITHUB_OUTPUT": self.output,
                         "FAUX_GH_JOURNAL": self.gh_log, **env}
        r = subprocess.run(["bash", "-e", "-c", script], cwd=self.dir, env=environment, capture_output=True, text=True,
                           timeout=120)
        with open(self.output) as f:
            return r, f.read()

    def test_one_judging_job_whose_step_writes_the_code(self):
        self.assertEqual(list(self.wf["jobs"]), ["juge"])
        self.assertEqual(self.wf["on"]["workflow_call"]["outputs"]["code"]["value"], "${{ jobs.juge.outputs.code }}")
        # ruche-0038: the report's SHA-256 and key figures too, all written by the judging step
        # ruche-0148 (J2b): under their English names, and under their French ones until judge-v5
        french = {"empreinte": "fingerprint", "suspectes": "suspects", "sorties_comparees": "outputs_compared", "greffon": "plugin",
                  "graine": "seed", "tete": "head"}
        self.assertEqual({k: v["value"] for k, v in self.wf["on"]["workflow_call"]["outputs"].items()},
                         {k: "${{ jobs.juge.outputs.%s }}" % french.get(k, k) for k in JOB_OUTPUTS + list(french)})
        self.assertEqual(self.wf["jobs"]["juge"]["outputs"], {k: "${{ steps.juge.outputs.%s }}" % k for k in JOB_OUTPUTS})
        self.assertEqual(step(self.wf, "Juger")["id"], "juge")
        self.assertIn('report.py results/judge.json --code "$code" > results/outputs\n', step(self.wf, "Juger")["run"])
        self.assertIn('cat results/outputs >> "$GITHUB_OUTPUT"', step(self.wf, "Juger")["run"])

    def test_judge_code_read_at_the_workflow_commit(self):
        """No tag, no branch: the registry is checked out at the commit the preparation step checked."""
        self.assertNotIn("JUGE_COMMUN_REF", self.text)
        self.assertIn(judge.common_tag(), self.text)  # the version label stays named in the usage comment
        steps = self.wf["jobs"]["juge"]["steps"]
        self.assertEqual([steps[0]["name"], steps[1]["name"]], [INPUTS, PREPARATION])  # the caller's inputs first (ruche-0038)
        self.assertEqual(steps[1]["env"], {"DEPOT": "${{ job.workflow_repository }}", "COMMIT": "${{ job.workflow_sha }}",
                                            "GH_TOKEN": "${{ github.token }}"})
        extractions = [e for e in steps if str(e.get("uses", "")).startswith("actions/checkout@")]
        common_judge = [e for e in extractions if e["with"].get("path") == "juge-commun"]
        self.assertEqual(len(common_judge), 1)
        self.assertEqual(common_judge[0]["with"]["repository"], "Bee-ruche/registre")
        self.assertEqual(common_judge[0]["with"]["ref"], "${{ steps.preparation.outputs.commit }}")
        for e in extractions:
            if e is not common_judge[0]:
                self.assertNotIn("repository", e["with"], "only the judge comes from another repository")
        self.assertEqual(step(self.wf, "Juger")["env"]["SOURCE"], "Bee-ruche/registre@${{ steps.preparation.outputs.commit }}")

    def test_preparation_requires_a_commit_of_the_registry_main(self):
        """S2: the workflow must be Bee-ruche/registre's (owner/name compared without case) at a full commit that the
        compare API puts on main (identical or behind); anything else, an API error included, stops the judge."""
        script = step(self.wf, PREPARATION)["run"]
        self.assertIn('etat="$(timeout 60 gh api "repos/Bee-ruche/registre/compare/main...$COMMIT" --jq .status)"', script)
        good = "0123456789abcdef0123456789abcdef01234567"
        refused_items = [("", "", None), ("Bee-ruche/registre", "", None), ("Bee-ruche/registre", "juge-v2", None),
                   ("Bee-ruche/registre", "main", None), ("Bee-ruche/registre", good[:39], None), ("", good, None),
                   ("Bee-ruche/registre", good + "\nx", None), ("a/b;c", good, None), ("someone/registre", good, "identical"),
                   ("Bee-ruche/registre-test", good, "identical"), ("Bee-ruche/registre", good, "ahead"),
                   ("Bee-ruche/registre", good, "diverged"), ("Bee-ruche/registre", good, ""),
                   ("Bee-ruche/registre", good, "behind\nidentical"), ("Bee-ruche/registre", good, "erreur")]
        for repo, commit, state in refused_items:
            with self.subTest(repo=repo, commit=commit, state=state):
                env = {"DEPOT": repo, "COMMIT": commit, "GH_TOKEN": "t"}
                env.update({"FAUX_GH_CODE": "1"} if state == "erreur" else {"FAUX_GH_ETAT": "identical" if state is None else state})
                r, output_text = self.launch(script, env)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(output_text, "")
        for repo, state in (("Bee-ruche/registre", "identical"), ("bee-ruche/REGISTRE", "behind")):
            with self.subTest(repo=repo, state=state):
                open(self.gh_log, "w").close()
                r, output_text = self.launch(script, {"DEPOT": repo, "COMMIT": good, "GH_TOKEN": "t", "FAUX_GH_ETAT": state})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(output_text, f"commit={good}\n")
                with open(self.gh_log) as f:  # the canonical name, whatever the case it came in
                    self.assertEqual(f.read(), f"api repos/Bee-ruche/registre/compare/main...{good} --jq .status +jeton\n")

    def test_history_in_its_own_step_the_only_judge_call_with_the_token(self):
        """The declared history is checked and fetched in its own step, the only call of judge.py given GH_TOKEN, before
        the image (which loads the plugin) and before the PR; it is never interpolated into a script."""
        self.assertEqual([self.wf["on"]["workflow_call"]["inputs"][i]["type"] for i in ("history", "historique")], ["string", "string"])
        steps = self.wf["jobs"]["juge"]["steps"]
        names = [e.get("name") for e in steps]
        history, image = step(self.wf, HISTORY), step(self.wf, IMAGE)
        self.assertEqual(history["env"], {"HISTORIQUE": "${{ inputs.history || inputs.historique }}", "GH_TOKEN": "${{ github.token }}"})
        self.assertEqual(history["run"], "python3 juge-commun/tools/judge/judge.py --tooling base --history-only "
                                            '--history "$HISTORIQUE"')
        self.assertNotIn("env", image)
        self.assertEqual(image["run"], "python3 juge-commun/tools/judge/judge.py --tooling base --image-only")
        self.assertLess(names.index("Base de la PR (greffon, harnais, corpus)"), names.index(HISTORY))
        self.assertLess(names.index(HISTORY), names.index(IMAGE))
        self.assertLess(names.index(IMAGE), names.index("Tête de la PR (données ; rien n'en est exécuté hors conteneur)"))
        with_token = [e["name"] for e in steps if "GH_TOKEN" in (e.get("env") or {}) or "github.token" in str(e.get("with"))]
        self.assertEqual(with_token, [PREPARATION, HISTORY])  # the pin step runs gh alone, before the base exists
        self.assertNotIn("github.token", self.text.replace("GH_TOKEN: ${{ github.token }}", ""))
        for e in steps:
            self.assertNotIn("${{ inputs.", e.get("run", ""), "inputs reach scripts through env only")

    def test_log_cannot_issue_workflow_commands(self):
        """The judged PR fills the journal; printed between ::stop-commands::<token> and ::<token>::, with ##[ made
        # #[ (ruche-0025), none of its lines is a workflow command for the runner (a line ::error:: among others)."""
        script = step(self.wf, "Juger")["run"]
        hostile = ("juge : début\n::error::injected annotation\n  ::add-mask::abc\n::stop-commands::faux\n::faux::\n"
                   "::error::after a forged resume\n##[error]old syntax\nx\r::warning::after a carriage return\n"
                   "::set-output name=code::0\n::warning file=rle.c,line=1::props\nend ##[group]x")
        os.makedirs(os.path.join(self.dir, "juge-commun", "tools", "judge"))
        shutil.copy(os.path.join(HERE, "report.py"), os.path.join(self.dir, "juge-commun", "tools", "judge"))
        with open(os.path.join(self.dir, "juge-commun", "tools", "judge", "judge.py"), "w", encoding="utf-8") as f:
            f.write(f"import sys\nsys.stderr.write({hostile!r})\nsys.exit(1)\n")
        r, output_text = self.launch(script, {"OPTIONS": "sortie_compressee=identique", "REPETITIONS": "2",
                                         "SANS_INSTRUCTIONS": "false", "SOURCE": "Bee-ruche/registre@" + "0" * 40})
        self.assertEqual(r.returncode, 0, r.stderr)
        # the judging step itself writes the job's code, and the report's figures (none: no report)
        self.assertEqual(output_text, "code=1\n" + "".join(f"{k}=\n" for k in report.FORMATS))
        with open(os.path.join(self.dir, "results", "code")) as f:
            self.assertEqual(f.read().strip(), "1")
        with open(os.path.join(self.dir, "results", "log.txt"), newline="") as f:
            journal = f.read()
        self.assertEqual(journal, hostile)
        self.assertGreaterEqual(len([c for c in runner_commands(journal) if c != "<resume>"]), 6)  # the simulator sees them
        lines = r.stdout.splitlines()
        token = re.fullmatch(r"::stop-commands::([0-9a-f]{64})", lines[0]).group(1)
        self.assertEqual(lines[-2:], [f"::{token}::", "::warning title=Juge commun::code 1 : refus du code jugé (B)"])  # ruche-0136
        self.assertNotIn(token, journal)
        self.assertEqual(r.stdout.count(token), 2)
        self.assertNotIn("##[", r.stdout)
        self.assertEqual(r.stdout.count("# #["), 2)
        self.assertEqual(runner_commands(r.stdout), ["stop-commands", "<resume>", "warning"])

    def test_caller_inputs_checked_before_any_use(self):
        """ruche-0038, the call as workflow_call makes it (github.event is the caller's): the first step, which nothing
        precedes and after whose failure only the upload of results/ runs, accepts only the event's pull request as base
        and head (full commits), 10 to 50 repetitions and the instruction count; anything else ends the job, nothing judged."""
        steps = self.wf["jobs"]["juge"]["steps"]
        entrees = steps[0]
        self.assertEqual(entrees["name"], INPUTS)
        self.assertEqual(entrees["env"], {"BASE": "${{ inputs.base_sha }}", "HEAD_SHA": "${{ inputs.head_sha }}", "TETE": "${{ inputs.tete_sha }}",
                                          "BASE_EVENEMENT": "${{ github.event.pull_request.base.sha }}",
                                          "TETE_EVENEMENT": "${{ github.event.pull_request.head.sha }}",
                                          "HISTORY": "${{ inputs.history }}", "HISTORIQUE": "${{ inputs.historique }}",
                                          "REPETITIONS": "${{ inputs.repetitions }}", "NO_INSTRUCTIONS": "${{ inputs.no_instructions }}",
                                          "SANS_INSTRUCTIONS": "${{ inputs.sans_instructions }}"})
        # ruche-0148 (J2): after it, every step reads an input by its English name, else by its French one
        self.assertEqual(sorted(set(re.findall(r"inputs\.\w+(?: \|\| inputs\.\w+)?", json.dumps(steps[1:])))),
                         ["inputs.base_sha", "inputs.head_sha || inputs.tete_sha", "inputs.history || inputs.historique", "inputs.options",
                          "inputs.repetitions"])
        self.assertEqual([e["name"] for e in steps if "if" in e or "continue-on-error" in e], ["Conserver le rapport"])
        self.assertNotIn("continue-on-error", self.wf["jobs"]["juge"])
        self.assertNotIn("--no-instructions", self.text)  # the judging step never skips the instruction count
        base, head = "0123456789abcdef0123456789abcdef01234567", "89abcdef0123456789abcdef0123456789abcdef"
        call = {"BASE": base, "HEAD_SHA": "", "TETE": head, "BASE_EVENEMENT": base, "TETE_EVENEMENT": head, "HISTORY": "", "HISTORIQUE": "",
                "REPETITIONS": "10", "NO_INSTRUCTIONS": "false", "SANS_INSTRUCTIONS": "false"}
        english = dict(call, HEAD_SHA=head, TETE="")  # ruche-0148 (J2): each input by its English name or by its French one
        for env in (call, dict(call, REPETITIONS="27"), dict(call, REPETITIONS="50"), english, dict(english, HISTORY="1" * 40),
                    dict(call, HISTORIQUE="1" * 40), dict(english, HISTORIQUE="1" * 40)):
            with self.subTest(accepted=env):
                r, output_text = self.launch(entrees["run"], env)
                self.assertEqual((r.returncode, output_text, r.stderr), (0, "", ""))
        refused_ones = [dict(call, REPETITIONS=v) for v in ("9", "2", "0", "-10", "51", "100", "010", "10.5", "1e1", "", " 10", "10\n",
                                                          "a[$(touch injection)]")]
        refused_ones += [dict(call, SANS_INSTRUCTIONS=v) for v in ("true", "", "False", "0")]
        refused_ones += [dict(english, NO_INSTRUCTIONS=v) for v in ("true", "", "False", "0")]
        refused_ones += [dict(call, HEAD_SHA=head), dict(english, TETE=base), dict(call, HISTORY="1" * 40, HISTORIQUE="1" * 40),
                         dict(english, HISTORY="1" * 40, HISTORIQUE="2" * 40), dict(english, HEAD_SHA=""), dict(english, HEAD_SHA=base),
                         dict(english, HEAD_SHA=head[:39], TETE_EVENEMENT=head[:39])]
        refused_ones += [dict(call, BASE=v, BASE_EVENEMENT=v) for v in (base[:39], base.upper(), base + "\n", base + "0", "main", "HEAD", "")]
        refused_ones += [dict(call, TETE=v, TETE_EVENEMENT=v) for v in (head[:39], "v1.0", "refs/pull/1/head")]
        refused_ones += [dict(call, BASE_EVENEMENT=""), dict(call, TETE_EVENEMENT=""), dict(call, BASE_EVENEMENT="", TETE_EVENEMENT=""),
                     dict(call, BASE=head), dict(call, TETE=base), dict(call, BASE=head, TETE=base), dict(call, TETE_EVENEMENT=base)]
        for env in refused_ones:
            with self.subTest(refused=env):
                r, output_text = self.launch(entrees["run"], env)
                self.assertEqual((r.returncode, output_text), (1, ""))
                self.assertTrue(r.stderr.strip())
        self.assertFalse(os.path.exists(os.path.join(self.dir, "injection")))

    def test_code_published_once_the_report_is_checked(self):
        """ruche-0117: the judging step publishes the code only with the report's figures, once report.py has checked the
        report: a report that fails its check (none for a code 0, malformed) publishes code 2, in the job's outputs as in
        resultats/code; a refusal or an error without a report keeps its code. ruche-0136: with a report, only if the report says
        the same code; the step reports a code 2 as an error of the environment, never as a refusal of B."""
        common_judge = os.path.join(self.dir, "juge-commun", "tools", "judge")
        os.makedirs(common_judge)
        shutil.copy(os.path.join(HERE, "report.py"), common_judge)
        with open(os.path.join(common_judge, "judge.py"), "w", encoding="utf-8") as f:
            f.write("import os, sys\nif os.environ['FAUX_RAPPORT']:\n"
                    "    open(sys.argv[sys.argv.index('--json') + 1], 'w').write(os.environ['FAUX_RAPPORT'])\n"
                    "sys.exit(int(os.environ['FAUX_CODE']))\n")
        good = json.dumps(REPORT, indent=2)
        refusal, fault = ({"judge": dict(REPORT["judge"], code=c, outcome=i, reason="m")} for c, i in ((1, "refusal"), (2, "environment_error")))
        refusal, fault, fake = json.dumps(refusal), json.dumps(fault), json.dumps({"judge": dict(REPORT["judge"], code=1, outcome="correct")})
        announcements = {"0": "::notice title=Juge commun::code 0 :", "1": "::warning title=Juge commun::code 1 : refus du code jugé",
                    "2": "::error title=Juge commun::code 2 : erreur d'environnement"}
        for code, report_, expected in ((0, good, "0"), (0, "", "2"), (0, "{}", "2"), (0, good[:-1], "2"), (1, "", "1"), (2, "", "2"),
                                        (1, "{}", "1"), (1, refusal[:-9], "1"), (1, refusal, "1"), (2, fault, "2"), (1, fault, "2"), (2, refusal, "2"), (0, fault, "2"),
                                        (1, fake, "2"), (1, good, "2")):
            with self.subTest(code=code, report=report_[:20]):
                shutil.rmtree(os.path.join(self.dir, "results"), ignore_errors=True)
                r, output_text = self.launch(step(self.wf, "Juger")["run"], {"OPTIONS": "", "REPETITIONS": "10", "BASE": "2" * 40,
                                        "TETE": "3" * 40, "SOURCE": "x", "RUNNER_TEMP": "/rt", "FAUX_CODE": str(code),
                                        "FAUX_RAPPORT": report_})
                self.assertEqual(r.returncode, 0, r.stderr)
                published_ones = dict(line_text.split("=", 1) for line_text in output_text.splitlines())
                self.assertEqual(list(published_ones), JOB_OUTPUTS)
                self.assertEqual(published_ones["code"], expected)
                self.assertEqual(published_ones["fingerprint"] != "", expected == "0")
                with open(os.path.join(self.dir, "results", "code")) as f:
                    self.assertEqual(f.read(), expected + "\n")
                self.assertEqual([line_text for line_text in r.stdout.splitlines() if line_text.startswith("::") and "title=" in line_text][-1:],
                                 [l for l in r.stdout.splitlines() if l.startswith(announcements[expected])])

    def test_work_folder_bounded(self):
        """ruche-0038: the judge works in a size-bounded tmpfs that juge.yml mounts just before judging (executable: the
        harness runs from it)."""
        names = [e.get("name") for e in self.wf["jobs"]["juge"]["steps"]]
        self.assertEqual(names.index(WORKDIR) + 1, names.index("Juger"))
        script = step(self.wf, WORKDIR)["run"]
        self.assertIn('sudo mount -t tmpfs -o "size=4g,nr_inodes=262144,mode=0755,nosuid,nodev,uid=$(id -u),gid=$(id -g)" '
                      'tmpfs "$RUNNER_TEMP/juge"', script)
        self.assertNotIn("noexec", script)
        self.assertIn('--base "$BASE" --head "$TETE" --workdir "$RUNNER_TEMP/juge"', step(self.wf, "Juger")["run"])

    def test_report_tied_to_the_judging_job(self):
        """ruche-0038: the judging step publishes juge.json's SHA-256 and key figures as job outputs; on the verdict side,
        report.py --verify, given those outputs (toJSON(needs.<job>.outputs)), refuses a report changed in between."""
        common_judge = os.path.join(self.dir, "juge-commun", "tools", "judge")
        os.makedirs(common_judge)
        shutil.copy(os.path.join(HERE, "report.py"), common_judge)
        with open(os.path.join(common_judge, "judge.py"), "w", encoding="utf-8") as f:
            f.write("import json, sys\nopen('arguments.json', 'w').write(json.dumps(sys.argv[1:]))\n"
                    f"open(sys.argv[sys.argv.index('--json') + 1], 'w').write({json.dumps(REPORT, indent=2)!r})\n")
        r, output_text = self.launch(step(self.wf, "Juger")["run"], {"OPTIONS": "", "REPETITIONS": "10", "BASE": REPORT["judge"]["base"],
                                                                 "TETE": REPORT["judge"]["head"], "SOURCE": "x", "RUNNER_TEMP": "/rt"})
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.dir, "arguments.json")) as f:
            arguments = json.load(f)
        self.assertEqual(arguments[arguments.index("--base"):arguments.index("--workdir") + 2],
                         ["--base", REPORT["judge"]["base"], "--head", REPORT["judge"]["head"], "--workdir", "/rt/juge"])
        path = os.path.join(self.dir, "results", "judge.json")
        with open(path, "rb") as f:
            data = f.read()
        published_ones = dict(line_text.split("=", 1) for line_text in output_text.splitlines())
        self.assertEqual(published_ones, {"code": "0", "fingerprint": hashlib.sha256(data).hexdigest(), "suspects": "103",
                                    "outputs_compared": "57", "plugin": "ab" * 32, "seed": "cd" * 16,
                                    "base": REPORT["judge"]["base"], "head": REPORT["judge"]["head"]})
        with open(os.path.join(self.dir, "sorties.json"), "w") as f:
            json.dump(published_ones, f)  # what toJSON(needs.juge.outputs) gives the verdict job
        commits = [REPORT["judge"]["base"], REPORT["judge"]["head"]]  # ruche-0117: the pull request's, given to --verifier
        verifier = [sys.executable, os.path.join(HERE, "report.py"), path, "--verify", os.path.join(self.dir, "sorties.json"),
                    "--base", commits[0], "--head", commits[1]]
        self.assertEqual(subprocess.run(verifier, capture_output=True).returncode, 0)
        self.assertEqual(report.verifier(path, published_ones, *commits)["judge"]["plugin"], "ab" * 32)
        other = json.loads(json.dumps(REPORT))
        other["judge"]["verification"]["outputs_compared"] = 58
        without_suspects = dict(REPORT, judge=dict(REPORT["judge"], suspicious_constructs=[], suspicious_constructs_omitted=0))
        modified_items = [json.dumps(REPORT).encode(), data + b"\n", data.replace(b'"gain": 0.25', b'"gain": 0.35'),
                    json.dumps(other, indent=2).encode(), json.dumps(without_suspects, indent=2).encode(), b""]
        for changed_one in modified_items:
            with self.subTest(changed_one=changed_one[:60]):
                with open(path, "wb") as f:
                    f.write(changed_one)
                self.assertEqual(subprocess.run(verifier, capture_output=True).returncode, 1 if changed_one else 2)
                with self.assertRaises((report.Gap, ValueError)):
                    report.verifier(path, published_ones, *commits)
        with open(path, "wb") as f:
            f.write(data)
        for key, value in (("fingerprint", ""), ("fingerprint", "0" * 64), ("suspects", "100"), ("head", REPORT["judge"]["base"])):
            with self.subTest(output_text=key), self.assertRaises(report.Gap):
                report.verifier(path, dict(published_ones, **{key: value}), *commits)
        os.remove(path)
        os.symlink(os.path.join(self.dir, "sorties.json"), path)
        self.assertNotEqual(subprocess.run(verifier, capture_output=True).returncode, 0)
        os.remove(path)
        self.assertEqual(subprocess.run(verifier, capture_output=True).returncode, 1)


# A judge's report: as juge.py writes it, with 100 suspicious constructs listed and 3 left out.
REPORT = {"repetitions": 10, "metrics": {"debit_compression": {"gain": 0.25}}, "judge": {
    "version": 3, "common": "juge-v2", "source": "Bee-ruche/registre@" + "1" * 40, "base": "2" * 40, "head": "3" * 40,
    "project": "jouet", "plugin": "ab" * 32, "code": 0, "outcome": "correct", "seed": "cd" * 16,
    "seed_origin": {"seed": "drawn", "order_seed": "drawn"}, "image": "bee-juge-commun:0123456789abcdef",
    "image_id": "sha256:" + "ef" * 32, "suspicious_constructs_omitted": 3, "verification": {"outputs_compared": 57},
    "suspicious_constructs": [{"type": "source", "detail": f"pragma {i}"} for i in range(judge.SUSPICIOUS_MAX)]}}
# ruche-0148 (J2b): the same report as juge-v1 to juge-v3 wrote it, in French (juge.json), read until DATE_D.
FRENCH_REPORT = {"repetitions": 10, "metriques": {"debit_compression": {"gain": 0.25}}, "juge": {
    "version": 3, "commun": "juge-v2", "source": "Bee-ruche/registre@" + "1" * 40, "base": "2" * 40, "tete": "3" * 40,
    "projet": "jouet", "greffon": "ab" * 32, "code": 0, "issue": "juste", "graine": "cd" * 16,
    "origine_des_graines": {"graine": "tiree", "graine_ordre": "tiree"}, "image": "bee-juge-commun:0123456789abcdef",
    "image_id": "sha256:" + "ef" * 32, "constructions_suspectes_omises": 3, "verification": {"sorties_comparees": 57},
    "constructions_suspectes": [{"type": "source", "detail": f"pragma {i}"} for i in range(judge.SUSPICIOUS_MAX)]}}


class TestReport(unittest.TestCase):
    """report.py (ruche-0038): the report's figures are read strictly, and the report itself within bounds."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bee-rapport-")
        self.path = os.path.join(self.dir, "juge.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_figures(self):
        data = json.dumps(REPORT).encode()
        self.assertEqual(report.digits(data)["suspects"], str(judge.SUSPICIOUS_MAX + 3))
        local = dict(REPORT, judge=dict(REPORT["judge"], base=None, head=None))  # judge.py run by hand: no commits named
        self.assertEqual([report.digits(json.dumps(local).encode())[k] for k in ("base", "head")], ["", ""])
        judge_ = REPORT["judge"]
        wrong_one = [b"[]", b"{}", b"{\"judge\": []}", b"{\"juge\": []}", b"\xff", json.dumps(dict(REPORT, judge={})).encode()]
        wrong_one += [json.dumps(dict(REPORT, judge=dict(judge_, **{key: value}))).encode() for key, value in (
            ("suspicious_constructs_omitted", -1), ("suspicious_constructs_omitted", True), ("suspicious_constructs_omitted", "3"),
            ("suspicious_constructs", "abc"), ("suspicious_constructs", None), ("plugin", "x"), ("plugin", "AB" * 32),
            ("seed", ""), ("seed", 12), ("base", "main"), ("head", "3" * 39), ("verification", {"outputs_compared": -1}),
            ("verification", {"outputs_compared": 1.5}), ("verification", {"outputs_compared": True}), ("verification", {}))]
        for data in wrong_one:
            with self.subTest(data=data[:80]), self.assertRaises(ValueError):
                report.digits(data)

    def test_verify_requires_code_0_and_the_pull_request_commits(self):
        """ruche-0117: report.py --verify also checks the published code (0) and the report's base and head against the pull
        request's, given by the verdict job; any other exit than 0 blocks the verdict."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(REPORT, f)
        published_ones, commits = report.publish(self.path, "0"), (REPORT["judge"]["base"], REPORT["judge"]["head"])
        self.assertEqual(report.verifier(self.path, published_ones, *commits)["judge"]["plugin"], "ab" * 32)
        without_code = {k: v for k, v in published_ones.items() if k != "code"}
        for published_, base, head in ((dict(published_ones, code="1"), *commits), (dict(published_ones, code="2"), *commits), (without_code, *commits),
                                      (published_ones, commits[1], commits[0]), (published_ones, "0" * 40, commits[1]), (published_ones, commits[0], ""),
                                      (published_ones, "AB" * 20, commits[1]), (published_ones, None, commits[1]),
                                      (published_ones, commits[0], commits[1] + "\n")):
            with self.subTest(code=published_.get("code"), base=base, head=head), self.assertRaises(report.Gap):
                report.verifier(self.path, published_, base, head)
        outputs = os.path.join(self.dir, "sorties.json")
        with open(outputs, "w") as f:
            json.dump(published_ones, f)
        command = [sys.executable, os.path.join(HERE, "report.py"), self.path, "--verify", outputs]
        self.check_the_seeds(published_ones, commits)
        for arguments, code in ((["--base", commits[0], "--head", commits[1]], 0), (["--base", commits[0], "--head", commits[0]], 1),
                                ([], 2), (["--base", commits[0]], 2), (["--head", commits[1], "--base", commits[0]], 2)):
            with self.subTest(arguments=arguments):
                self.assertEqual(subprocess.run(command + arguments, capture_output=True).returncode, code)

    def check_the_seeds(self, published_ones, commits):
        """ruche-0136: a report with a seed given on the command line (a local reproduction), or that does not say where its
        seeds came from, is never taken for a judgement: --verify refuses it, its figures and SHA-256 published or not."""
        for origins in ({"seed": "given", "order_seed": "drawn"}, {"seed": "drawn", "order_seed": "given"},
                         {"seed": "drawn"}, None, "drawn", {"seed": "drawn", "order_seed": "drawn", "x": 1}):
            reproduction = dict(REPORT, judge=dict(REPORT["judge"], seed_origin=origins))
            if origins is None:
                del reproduction["judge"]["seed_origin"]
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(reproduction, f)
            with self.subTest(origins=origins), self.assertRaisesRegex(report.Gap, "seed"):
                report.verifier(self.path, report.publish(self.path, "0"), *commits)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(REPORT, f)

    def test_french_report_read_until_date_d_never_mixed(self):
        """ruche-0148 (J2b): juge.json as juge-v1 to juge-v3 wrote it (French) gives the same figures, code and check as judge.json,
        until DATE_D; from DATE_D on, or with keys of both vocabularies among those report.py reads, it is refused (code 2 published)."""
        english, french = json.dumps(REPORT).encode(), json.dumps(FRENCH_REPORT).encode()
        figures = report.digits(english)
        self.assertEqual(dict(report.digits(french), fingerprint=figures["fingerprint"]), figures)
        self.assertEqual((report.outcome(french), report.outcome(english)), ("0", "0"))
        with open(self.path, "wb") as f:
            f.write(french)
        self.assertEqual(report.verifier(self.path, report.publish(self.path, "0"), "2" * 40, "3" * 40), FRENCH_REPORT)
        judge_fr = FRENCH_REPORT["juge"]
        for mixed in (dict(FRENCH_REPORT, metrics={}), dict(REPORT, metriques={}), dict(REPORT, juge=judge_fr),
                      dict(REPORT, judge=dict(REPORT["judge"], tete="3" * 40)), dict(FRENCH_REPORT, juge=dict(judge_fr, head="3" * 40)),
                      dict(FRENCH_REPORT, juge=dict(judge_fr, verification={"outputs_compared": 57})),
                      dict(REPORT, judge=dict(REPORT["judge"], seed_origin={"graine": "tiree", "graine_ordre": "tiree"}))):
            with self.subTest(mixed=json.dumps(mixed)[:60]), self.assertRaisesRegex(ValueError, "one vocabulary per report"):
                report.digits(json.dumps(mixed).encode())
        # A plugin's own keys in verification stay as written: one that is spelled as a key of the judge's other vocabulary is data.
        for doc, key in ((REPORT, "motif"), (FRENCH_REPORT, "reason")):
            section = doc["judge" if doc is REPORT else "juge"]
            plugin_key = dict(doc, **{"judge" if doc is REPORT else "juge": dict(section, verification=dict(section["verification"], **{key: "x"}))})
            with self.subTest(plugin_key=key):
                self.assertEqual(dict(report.digits(json.dumps(plugin_key).encode()), fingerprint=figures["fingerprint"]), figures)
                self.assertEqual(report.judge_of(json.dumps(plugin_key).encode())["verification"], {"outputs_compared": 57, key: "x"})
        with mock.patch.object(report, "today", return_value=report.DATE_D), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(ValueError, f"read until {report.DATE_D} only"):
                report.digits(french)
            self.assertEqual(report.publish(self.path, "0")["code"], "2")
            self.assertEqual(report.digits(english), figures)

    def test_a_refusal_needs_no_report(self):
        """ruche-0136: a refusal (code 1) is published as 1 whatever state its report is in (none, cut short, malformed, not a
        regular file), unless the report states another code; a code 0 still needs its report, whole and checked."""
        def published(code):
            with contextlib.redirect_stderr(io.StringIO()):
                return report.publish(self.path, code)["code"]
        refusal = json.dumps({"judge": dict(REPORT["judge"], code=1, outcome="refusal", reason="m")})
        for content, expected in ((None, "1"), ("", "1"), (refusal[:-7], "1"), ("[1]", "1"), ('{"judge": 3}', "1"), (refusal, "1"),
                                 ("\xff", "1"), (json.dumps(REPORT), "2"), (refusal.replace('"refusal"', '"correct"'), "2"),
                                 (refusal.replace('"code": 1', '"code": 2'), "2"), (refusal.replace('"code": 1', '"code": true'), "2")):
            with contextlib.suppress(FileNotFoundError):
                os.remove(self.path)
            if content is not None:
                with open(self.path, "w", encoding="utf-8", errors="surrogateescape") as f:
                    f.write(content.replace("\xff", "\udcff"))
            with self.subTest(content=content and content[:40]):
                self.assertEqual(published("1"), expected)
        os.remove(self.path)
        os.mkfifo(self.path)
        self.assertEqual((published("1"), published("0"), published("2")), ("1", "2", "2"))
        os.remove(self.path)
        os.symlink(self.dir, self.path)
        self.assertEqual((published("1"), published("0")), ("1", "2"))

    def test_reading_bounded(self):
        self.assertIsNone(report.lire(self.path))
        with contextlib.redirect_stdout(io.StringIO()) as output_text:
            self.assertEqual(report.main([self.path]), 0)
        self.assertEqual(output_text.getvalue(), "".join(f"{k}=\n" for k in report.FORMATS))
        with open(self.path, "wb") as f:
            f.write(b"x" * 101)
        with mock.patch.object(report, "REPORT_MAX", 100), self.assertRaises(ValueError):
            report.lire(self.path)
        os.remove(self.path)
        os.mkfifo(self.path)
        with self.assertRaises(ValueError):  # not a regular file: never read, never waited for
            report.lire(self.path)
        os.remove(self.path)
        os.symlink("/etc/hostname", self.path)
        with self.assertRaises(OSError):
            report.lire(self.path)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(report.main([self.path]), 2)
            self.assertEqual(report.main([]), 2)


OCI = "docker: Error response from daemon: failed to create task for container: OCI runtime create failed: runc create failed\n"

# Stand-in for the docker client: logs its arguments; « image inspect » answers FAUX_DOCKER_ID; « run » writes FAUX_DOCKER_MIO
# MiB on each standard stream (stdout: A, B…; stderr: a, b…), then, with FAUX_DOCKER_SANS_FIN, writes on without end.
FAKE_DOCKER = r"""#!/usr/bin/env python3
import os, sys
with open(os.environ["FAUX_DOCKER_JOURNAL"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
if sys.argv[1:3] == ["image", "inspect"]:
    print(os.environ.get("FAUX_DOCKER_ID", ""))
if sys.argv[1] == "inspect":  # ruche-0136: Docker's record of the container (FAUX_DOCKER_ETAT, JSON), or none (no container)
    print(os.environ.get("FAUX_DOCKER_ETAT", '{"Status": "exited", "Error": "", "ExitCode": 0}'))
    sys.exit(int(os.environ.get("FAUX_DOCKER_INSPECT", "0")))
if sys.argv[1] != "run":
    sys.exit(0)
sys.stdin.read()
for i in range(int(os.environ.get("FAUX_DOCKER_MIO", "0"))):
    sys.stdout.buffer.write(bytes([65 + i % 26]) * (1 << 20))
    sys.stderr.buffer.write(bytes([97 + i % 26]) * (1 << 20))
while os.environ.get("FAUX_DOCKER_SANS_FIN"):
    sys.stderr.buffer.write(b"x" * 65536)
sys.stderr.write(os.environ.get("FAUX_DOCKER_ERREUR", ""))
sys.exit(int(os.environ.get("FAUX_DOCKER_CODE", "0")))
"""


class TestBounds(unittest.TestCase):
    """ruche-0038: what a container writes is bounded (file size, no log on the host's disk) and the host reads it within
    bounds (the start of its standard output, the end of its standard error; outputs never beyond TAILLE_MAX_SORTIE)."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bee-bornes-")
        os.makedirs(os.path.join(self.dir, "bin"))
        with open(os.path.join(self.dir, "bin", "docker"), "w", encoding="utf-8") as f:
            f.write(FAKE_DOCKER)
        os.chmod(os.path.join(self.dir, "bin", "docker"), 0o755)
        self.journal = os.path.join(self.dir, "docker.journal")
        self.env = mock.patch.dict(os.environ, {"PATH": os.path.join(self.dir, "bin") + os.pathsep + os.environ["PATH"],
                                                "FAUX_DOCKER_JOURNAL": self.journal})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_container_limits(self):
        self.assertEqual(container.Docker.BOUNDS, ["--ulimit", f"fsize={lecture.TAILLE_MAX_SORTIE}", "--log-driver", "none"])
        container.Docker("sha256:" + "0" * 64).launch(["true"], [(self.dir, "/sorties", False)])
        with open(self.journal) as f:
            arguments = f.readline().split()  # the run (ruche-0136: then inspect and rm)
        self.assertEqual(arguments[arguments.index("--ulimit"):arguments.index("--ulimit") + 4], container.Docker.BOUNDS)
        self.assertEqual(arguments[-2:], ["sha256:" + "0" * 64, "true"])  # the image by its id

    def test_streams_read_within_bounds(self):
        tracemalloc.start()
        try:
            with mock.patch.dict(os.environ, {"FAUX_DOCKER_MIO": "40"}):
                r = container.Docker("i").launch(["x"], [], entry=b"jeton\n", timeout_seconds=120)
            points_to = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, b"A" * (1 << 20), bytes([97 + 39 % 26]) * (1 << 20)))
        self.assertLess(points_to, 12 << 20)  # 80 MiB written, a few MiB held

    def test_endless_writer_stopped_at_its_deadline(self):
        beginning = time.monotonic()
        with mock.patch.dict(os.environ, {"FAUX_DOCKER_SANS_FIN": "1"}), self.assertRaises(lecture.Refus):
            container.Docker("i").launch(["x"], [], timeout_seconds=2)
        self.assertLess(time.monotonic() - beginning, 30)
        with open(self.journal) as f:
            self.assertRegex(f.read(), r"\nkill bee-juge-[0-9a-f]{12}\n")

    def test_deadline_without_a_started_container_is_a_machine_failure(self):
        """ruche-0136: at its deadline, Docker's record is read before the container is removed: never started (no record, or
        still created) is a failure of the machine; started, the deadline stays a refusal."""
        for env, expected_one in (({"FAUX_DOCKER_INSPECT": "1"}, lecture.Panne), ({"FAUX_DOCKER_ETAT": '{"Status": "created"}'}, lecture.Panne),
                              ({"FAUX_DOCKER_ETAT": '{"Status": "running"}'}, lecture.Refus), ({}, lecture.Refus)):
            with self.subTest(env=env), mock.patch.dict(os.environ, dict(env, FAUX_DOCKER_SANS_FIN="1")), self.assertRaises(expected_one):
                container.Docker("i").launch(["x"], [], timeout_seconds=1)
        with open(self.journal) as f:
            self.assertEqual(re.findall(r"^(inspect|kill|rm) ", f.read(), re.M), ["inspect", "kill", "rm"] * 4)

    def test_machine_failure_is_an_environment_error(self):
        """ruche-0136: Docker's own record of the container decides, never its code or error stream: a daemon out of reach, a
        runtime that cannot create the container (OCI), a container whose code is not its process's or whose record is
        unreadable is a failure of the machine (Panne, an Erreur: code 2), each container removed after it ends."""
        state = lambda status, code, error="": json.dumps({"Status": status, "Error": error, "ExitCode": code})  # noqa: E731
        for env in ({"FAUX_DOCKER_CODE": "125", "FAUX_DOCKER_ERREUR": OCI, "FAUX_DOCKER_INSPECT": "1", "FAUX_DOCKER_ETAT": ""},
                    {"FAUX_DOCKER_CODE": "127", "FAUX_DOCKER_ERREUR": OCI, "FAUX_DOCKER_ETAT": state("created", 127, OCI)},
                    {"FAUX_DOCKER_CODE": "1", "FAUX_DOCKER_ERREUR": "failed to connect to the docker API", "FAUX_DOCKER_INSPECT": "1"},
                    {"FAUX_DOCKER_CODE": "125", "FAUX_DOCKER_ETAT": state("exited", 0)}, {"FAUX_DOCKER_ETAT": "{"},
                    {"FAUX_DOCKER_ETAT": state("running", 0)}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaisesRegex(lecture.Panne, "^machine du juge en panne") as fault:
                container.Docker("i").launch(["x"], [])
            self.assertNotRegex(str(fault.exception), "runc|daemon|API")  # what the error stream holds stays out of the motif
        with open(self.journal) as f:
            self.assertEqual(len(re.findall(r"^rm -f bee-juge-[0-9a-f]{12}$", f.read(), re.M)), 6)
        self.assertTrue(issubclass(lecture.Panne, lecture.Erreur))

    def test_judged_code_that_mimics_a_failure_stays_a_refusal(self):
        """ruche-0136: a container that ran to its end, exiting 125 with a daemon's error on its stream (both of which the
        judged code can write), is no failure of the machine: its code is returned, and in an execution it is a refusal."""
        env = {"FAUX_DOCKER_CODE": "125", "FAUX_DOCKER_ERREUR": OCI, "FAUX_DOCKER_ETAT": json.dumps({"Status": "exited", "Error": "",
                                                                                                    "ExitCode": 125})}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(container.Docker("i").launch(["x"], []).returncode, 125)
            with self.assertRaises(lecture.Refus):
                container.Execution(container.Docker("i"), "/c", {"B": "/b"}, self.dir).launch(
                    "B", "/e", os.path.join(self.dir, "s"), [("verifier", [container.HARNESS, "verifier", "/entrees", "/sorties"])])

    def test_judge_json_says_the_environment_error(self):
        """ruche-0136: the judge stopped by a failure of the machine exits with 2, and its juge.json says so (code 2,
        erreur_environnement, panne_machine); stopped by a refusal, 1 and refus; report.py publishes the code only when the
        report agrees with it."""
        path = os.path.join(self.dir, "resultats", "juge.json")
        env = {"FAUX_DOCKER_ID": "sha256:" + "a" * 64, "FAUX_DOCKER_CODE": "125", "FAUX_DOCKER_ERREUR": OCI, "FAUX_DOCKER_INSPECT": "1"}
        r = subprocess.run([sys.executable, os.path.join(HERE, "judge.py"), "--tooling", TOY, "--source-a", TOY, "--source-b",
                            TOY, "--json", path, "--workdir", self.dir, "--head", "3" * 40], env=dict(os.environ, **env),
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 2, r.stderr)
        with open(path, encoding="utf-8") as f:
            j = json.load(f)["judge"]
        self.assertEqual((j["code"], j["outcome"], j["machine_failure"], j["head"], j["common"]),
                         (2, "environment_error", True, "3" * 40, judge.common_tag()))
        self.assertIn("machine du juge en panne", j["reason"])
        self.assertEqual([report.publish(path, c)["code"] for c in "012"], ["2", "2", "2"])
        with mock.patch.dict(judge.FAILURE, json=path, judge={}), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(judge.stop_it(1, "juge : REFUS : B"), 1)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["judge"], {"code": 1, "outcome": "refusal", "machine_failure": False, "reason": "juge : REFUS : B"})
        self.assertEqual([report.publish(path, c)["code"] for c in "012"], ["2", "1", "2"])

    def test_a_refusal_stays_a_refusal_whatever_its_message_holds(self):
        """ruche-0136: a refusal quoting a name that is not UTF-8 exits with 1, its juge.json whole and saying refus, and
        report.py publishes 1; a report that cannot be written leaves none, neither partial nor stale."""
        self.assertEqual(lecture.propre("a\udcffb\ud800"), "a?b?")
        path, source_b = os.path.join(self.dir, "resultats", "juge.json"), os.path.join(os.fsencode(self.dir), b"B\xff")
        os.mkdir(source_b)
        r = subprocess.run([sys.executable, os.path.join(HERE, "judge.py"), "--tooling", TOY, "--source-a", TOY, "--source-b",
                            source_b, "--json", path, "--workdir", self.dir], capture_output=True, timeout=300,
                           env=dict(os.environ, FAUX_DOCKER_ID="sha256:" + "a" * 64))
        self.assertEqual(r.returncode, 1, r.stderr)
        with open(path, encoding="utf-8") as f:
            self.assertEqual((lambda j: (j["code"], j["outcome"], j["machine_failure"]))(json.load(f)["judge"]), (1, "refusal", False))
        output_text = subprocess.run([sys.executable, os.path.join(HERE, "report.py"), path, "--code", "1"], capture_output=True, text=True)
        self.assertEqual(output_text.stdout.splitlines()[0], "code=1")
        with mock.patch.dict(judge.FAILURE, json=path, judge={}), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(os, "replace", side_effect=OSError("disque plein")):
            self.assertEqual(judge.stop_it(1, "juge : REFUS : B\udcff"), 1)
        self.assertEqual(os.listdir(os.path.dirname(path)), [])

    def test_image_id(self):
        with mock.patch.dict(os.environ, {"FAUX_DOCKER_ID": "sha256:" + "a" * 64}):
            self.assertEqual(container.image_id("bee-juge-commun:x"), "sha256:" + "a" * 64)
        for wrong_one in ("", "a" * 64, "sha256:" + "A" * 64, "sha256:" + "a" * 63, "sha256:" + "a" * 64 + "\nx"):
            with self.subTest(wrong_one=wrong_one), mock.patch.dict(os.environ, {"FAUX_DOCKER_ID": wrong_one}), \
                    self.assertRaises(lecture.Erreur):
                container.image_id("bee-juge-commun:x")

    def test_outputs_never_read_beyond_the_bound(self):
        with open(os.path.join(self.dir, "sortie"), "wb") as f:
            f.write(b"x" * 101)
        with mock.patch.object(lecture, "TAILLE_MAX_SORTIE", 100), self.assertRaises(lecture.Refus):
            lecture.lire_sortie(self.dir, "sortie", maximum=1 << 30)
        self.assertEqual(lecture.lire_sortie(self.dir, "sortie", maximum=1 << 30), b"x" * 101)

    def test_commits_named_in_full(self):
        for value in ("abc", "2" * 39, "2" * 40 + "\n", "main", "A" * 40):
            for option in ("--base", "--head"):
                with self.subTest(option=option, value=value), contextlib.redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit):
                    judge.main(["--tooling", TOY, option, value])


def git_test(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "protocol.file.allow=always"]
                          + list(args), capture_output=True, text=True, check=True).stdout.strip()


def toy_repo_with_history(travail, toy=TOY):
    """An origin whose older commit X has another rle.c, and a base cloned from it without history (as actions/checkout
    does): X's objects are not in the base. Returns (origin, base, X, rle.c at X, full repository, a commit off the
    base's ancestry)."""
    source, origin_of, base = (os.path.join(travail, n) for n in ("source", "origine.git", "base"))
    shutil.copytree(toy, source, ignore=shutil.ignore_patterns("__pycache__"))
    with open(os.path.join(source, "rle.c"), "a", encoding="utf-8") as f:
        f.write("/* rle.c as it was at the corpus commit */\n")
    subprocess.run(["git", "init", "-q", "-b", "main", source], check=True)
    git_test(source, "add", "-A")
    git_test(source, "commit", "-qm", "X")
    commit = git_test(source, "rev-parse", "HEAD")
    with open(os.path.join(source, "rle.c"), "rb") as f:
        old = f.read()
    git_test(source, "checkout", "-qb", "ailleurs")
    git_test(source, "commit", "-qm", "off the base's ancestry", "--allow-empty")
    elsewhere = git_test(source, "rev-parse", "HEAD")
    git_test(source, "checkout", "-q", "main")
    shutil.copyfile(os.path.join(TOY, "rle.c"), os.path.join(source, "rle.c"))
    git_test(source, "commit", "-qam", "Y")
    subprocess.run(["git", "clone", "-q", "--bare", source, origin_of], check=True)
    subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + origin_of, base], check=True)
    return origin_of, base, commit, old, source, elsewhere


@unittest.skipUnless(shutil.which("git"), "git required")
class TestHistory(unittest.TestCase):
    """juge.yml's `historique` input: commits of the base's ancestry only (compare API, gh replaced by a stand-in),
    checked before any fetch and before the plugin is loaded, fetched within one time budget; judging then runs
    without any git transport (ruche-0024)."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp(prefix="bee-historique-")
        self.origin_of, self.base, self.commit, self.old, source, self.elsewhere = toy_repo_with_history(self.workdir)
        path, self.gh_log = fake_gh(self.workdir)
        self.env = mock.patch.dict(os.environ, {"PATH": path, "FAUX_GH_JOURNAL": self.gh_log, "FAUX_GH_DEPOT": source,
                                                "GITHUB_REPOSITORY": "Bee-ruche/jouetBee"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.workdir, ignore_errors=True)

    def present(self, commit):
        return subprocess.run(["git", "-C", self.base, "cat-file", "-e", commit + "^{commit}"], capture_output=True).returncode == 0

    def test_declared_commit_is_read_without_network(self):
        self.assertEqual(judge.fetch_history(self.base, f" {self.commit}\n{self.commit} ", "jeton"), [self.commit])
        base = git_test(self.base, "rev-parse", "HEAD")
        with open(self.gh_log) as f:
            self.assertEqual(f.read(), f"api repos/Bee-ruche/jouetBee/compare/{base}...{self.commit} --jq .status +jeton\n")
        os.rename(self.origin_of, self.origin_of + ".parti")  # from now on, no origin to fetch from
        projet = toy_plugin.Projet({"commit_corpus": self.commit})
        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "none"}):
            corpus = projet.corpus(self.base)
        self.assertEqual(corpus[-1][1], self.old)
        self.assertEqual(projet.VERIFICATION["historique"], f"{self.commit}:rle.c ({len(self.old)} octets)")

    def test_undeclared_commit_fails_cleanly(self):
        with self.assertRaises(lecture.Erreur) as e:
            toy_plugin.Projet({"commit_corpus": self.commit}).corpus(self.base)
        self.assertIn("historique", str(e.exception))
        with self.assertRaises(lecture.Erreur):
            toy_plugin.Projet({"commit_corpus": "HEAD"})

    def test_only_the_base_ancestry_is_fetched(self):
        """S3: a commit off the base's ancestry, a commit of another repository, an API error: refused before any fetch."""
        for commits, env in (([self.elsewhere], {}), ([self.commit, self.elsewhere], {}),
                             (["0123456789abcdef0123456789abcdef01234567"], {}), ([self.commit], {"FAUX_GH_CODE": "1"}),
                             ([self.commit], {"FAUX_GH_ETAT": "ahead"}), ([self.commit], {"FAUX_GH_ETAT": "diverged"}),
                             ([self.commit], {"FAUX_GH_ETAT": ""}), ([self.commit], {"GITHUB_REPOSITORY": ""}),
                             ([self.commit], {"GITHUB_REPOSITORY": "a/.."}), ([self.commit], {"GITHUB_REPOSITORY": "../x/y"})):
            with self.subTest(commits=commits, env=env), mock.patch.dict(os.environ, env):
                with self.assertRaises(lecture.Erreur) as e:
                    judge.fetch_history(self.base, " ".join(commits))
                self.assertIn("historique", str(e.exception))
                self.assertFalse(any(self.present(c) for c in commits))

    def test_declared_history_is_checked(self):
        for text in ("abc", self.commit[:39], self.commit.upper(), "--upload-pack=touch /tmp/x", f"{self.commit}:refs/x",
                      " ".join(f"{i:040x}" for i in range(judge.HISTORY_MAX + 1))):
            with self.subTest(text=text):
                with mock.patch.object(judge.subprocess, "run") as run, self.assertRaises(lecture.Erreur):
                    judge.fetch_history(self.base, text)
                run.assert_not_called()
        with mock.patch.object(judge.subprocess, "run") as run:
            self.assertEqual(judge.fetch_history(self.base, ""), [])
        run.assert_not_called()

    def test_output_that_is_not_utf8(self):
        """A byte that is not UTF-8 from gh (or git) gives a clean judge error, not a decoding traceback."""
        with mock.patch.dict(os.environ, {"FAUX_GH_OCTETS": "1"}), self.assertRaises(lecture.Erreur) as e:
            judge.fetch_history(self.base, self.commit)
        self.assertIn("not in the ancestry", str(e.exception))
        self.assertFalse(self.present(self.commit))

    def test_time_budget(self):
        """One budget for every check and fetch: exceeded, a clean judge error, nothing fetched."""
        with mock.patch.dict(os.environ, {"FAUX_GH_DELAI": "5"}), self.assertRaises(lecture.Erreur) as e:
            judge.fetch_history(self.base, self.commit, budget=1)
        self.assertIn("budget of 1 s", str(e.exception))
        self.assertFalse(self.present(self.commit))
        with mock.patch.object(judge.subprocess, "run", side_effect=FileNotFoundError("gh")), self.assertRaises(lecture.Erreur):
            judge.fetch_history(self.base, self.commit)

    def test_history_step_from_the_command_line(self):
        """--history-only checks and fetches, without Docker and without loading the plugin; a refusal is a
        judge error (code 2) without traceback."""
        judge_py = [sys.executable, os.path.join(HERE, "judge.py"), "--tooling", self.base, "--history-only"]
        r = subprocess.run(judge_py + ["--history", self.elsewhere], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(r.stderr.startswith("juge : erreur : historique : "), r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        with open(os.path.join(self.base, "bee", "juge", "projet.py"), "a", encoding="utf-8") as f:
            f.write("\nraise SystemExit('the plugin was loaded')\n")
        r = subprocess.run(judge_py + ["--history", self.commit], capture_output=True, text=True, timeout=120)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, self.commit + "\n", ""))
        self.assertTrue(self.present(self.commit))

    def test_modes_history_image_judging(self):
        """--history-only checks and fetches the history with the token and never loads the plugin;
        --image-only neither reads the history nor needs a token, and refuses --history; judging refuses every
        git transport before the plugin is loaded. GH_TOKEN is out of os.environ before any plugin load (defence in
        depth: juge.yml gives the token to the history step alone)."""
        seen_items = []

        def load(tooling, options):
            seen_items.append(("greffon", os.environ.get("GIT_ALLOW_PROTOCOL"), os.environ.get("GH_TOKEN")))
            return toy_plugin.Projet({}), "empreinte"

        def history(tooling, text, token=None):
            seen_items.append(("historique", text, token))
            return text.split()
        case_of = [(["--history-only", "--history", self.commit], {"GH_TOKEN": "secret"},
                [("historique", self.commit, "secret")]),
               (["--image-only"], {}, [("greffon", None, None), ("image",)]),
               (["--image-only"], {"GH_TOKEN": "secret"}, [("greffon", None, None), ("image",)]),
               (["--source-a", "a", "--source-b", "b"], {"GH_TOKEN": "secret"}, [("greffon", "none", None)])]
        for options, env, expected in case_of:
            with self.subTest(options=options, env=env):
                seen_items.clear()
                with mock.patch.dict(os.environ, env), mock.patch.object(judge.shutil, "which", return_value="/usr/bin/docker"), \
                        mock.patch.object(judge, "load_plugin", side_effect=load), \
                        mock.patch.object(judge, "fetch_history", side_effect=history), \
                        mock.patch.object(judge.container, "build_image", side_effect=lambda *a: seen_items.append(("image",)) or "i"), \
                        mock.patch.object(judge.tempfile, "mkdtemp", side_effect=lecture.Erreur("stop")), \
                        contextlib.redirect_stdout(io.StringIO()):
                    os.environ.pop("GIT_ALLOW_PROTOCOL", None)
                    try:
                        judge.main(["--tooling", self.base] + options)
                    except lecture.Erreur:
                        pass
                self.assertEqual(seen_items, expected)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            judge.main(["--tooling", self.base, "--image-only", "--history", self.commit])
        with mock.patch.object(judge.shutil, "which", return_value=None), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(judge, "fetch_history", return_value=[]) as call:  # no Docker needed for it
            self.assertEqual(judge.main(["--tooling", self.base, "--history-only"]), 0)
        call.assert_called_once()
        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "none"}), self.assertRaises(lecture.Erreur):
            judge.fetch_history(self.base, self.commit)


# ------------------------------------------------------------------ meta-tests of the analysis (built on the host, no Docker)

LOCAL_TOOLS = all(shutil.which(o) for o in ("sh", "cc", "nm", "objdump"))


class DockerLocal:
    """Stand-in for conteneur.Docker: runs the judge's build and analysis commands on the host, each mount target
    replaced by its host path. Only the toy project and the fixtures below are built this way; nothing built is run."""

    def __init__(self, tools=None):
        self.tools = tools

    def launch(self, command, mounts, pids=2, entry=None, timeout_seconds=3600):
        targets = {target: host for host, target, _ in mounts}
        reason = re.compile("|".join(re.escape(c) for c in sorted(targets, key=len, reverse=True)))
        env = dict(os.environ)
        if self.tools:
            env["PATH"] = self.tools + os.pathsep + env["PATH"]
        return subprocess.run([reason.sub(lambda m: targets[m.group(0)], c) for c in command], capture_output=True,
                              env=env, timeout=timeout_seconds)


def build_toy(travail, label="B", addition="", docker=None):
    """The toy project, `ajout` appended to rle.c, built and surveyed as the judge does; returns (releves, sources)."""
    projet = toy_plugin.Projet({})
    os.makedirs(travail)
    repo = os.path.join(travail, "depot")
    shutil.copytree(TOY, repo, ignore=shutil.ignore_patterns("bee", "__pycache__"))
    with open(os.path.join(repo, "rle.c"), "a", encoding="utf-8") as f:
        f.write(addition)
    sources = judge.copy_sources(repo, os.path.join(travail, "sources"), projet.SOURCES, projet.SOURCES_REQUISES)
    tools = judge.copy_tooling(TOY, TOY, os.path.join(travail, "outillage"), projet)
    surveys = judge.build(docker or DockerLocal(), projet, sources, tools, os.path.join(travail, "construction"),
                              label, travail)
    return surveys, sources


def asm_bytes(hex_digits, section=".text", end="ret"):
    return '__asm__("%s\\n.p2align 4\\nrle_seeded_%s:\\n.byte %s\\n%s\\n.previous\\n");\n' % (
        section, hex_digits, ", ".join("0x" + hex_digits[i:i + 2] for i in range(0, len(hex_digits), 2)), end)


SEEDED_CONSTRUCTS = {
    "syscall": "0f05", "sysenter": "0f34", "int": "cd80", "rdtsc": "0f31", "rdtscp": "0f01f9", "rdpmc": "0f33",
    "cpuid": "0fa2", "xgetbv": "0f01d0", "rdrand": "0fc7f0", "rdseed": "0fc7f8", "rdpid": "f30fc7f8",
    "preambule_valgrind": "48c1c70348c1c70d48c1c73d48c1c733",
}
# Every x86-64 prefix byte: legacy prefixes, then REX.
BYTE_PREFIXES = ["26", "2e", "36", "3e", "64", "65", "66", "67", "f0", "f2", "f3"] + [f"{r:02x}" for r in range(0x40, 0x50)]
# variant: (bytes before the construct, length it is padded to, bytes after it, ending its own section)
VARIANTS = {"variant_a": ("", 0, None), "variant_b": ("06", 0, None), "variant_c": ("48b8", 8, None),
            "variant_d": ("b8", 4, None), "variant_e": ("", 0, "0f")}
VARIANTS.update({f"variant_{i:02d}": (p, 0, None) for i, p in enumerate(BYTE_PREFIXES)})
# f2 and f3 select other instructions for some of these opcodes.
SHOWN_BY_DISASSEMBLY = ["variant_a"] + [f"variant_{i:02d}" for i, p in enumerate(BYTE_PREFIXES) if p not in ("f2", "f3")]


@unittest.skipUnless(LOCAL_TOOLS, "sh, cc, nm and objdump required")
class TestSeededObjects(unittest.TestCase):
    """Constructs seeded into the object of the toy project, built and surveyed as the judge does; analysed, never run."""

    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.mkdtemp(prefix="bee-seeded-")
        cls.a, cls.sources_a = build_toy(os.path.join(cls.workdir, "A"), "A")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workdir, ignore_errors=True)

    def analysis_of(self, nom, addition):
        b, sources_b = build_toy(os.path.join(self.workdir, nom), "B", addition)
        return analysis.analyse(self.a, b, judge.texts_of(self.sources_a), judge.texts_of(sources_b), prefixes=("rle_",))

    def test_honest(self):
        self.assertEqual(self.analysis_of("honest", ""), [])

    def test_every_family_seeded(self):
        self.assertEqual(set(SEEDED_CONSTRUCTS), set(analysis.SEQUENCES))

    def test_seeded_constructs_found(self):
        def case_of(c, v):
            before, length, after = VARIANTS[v]
            hex_digits = before + SEEDED_CONSTRUCTS[c] + "90" * max(0, length - len(SEEDED_CONSTRUCTS[c]) // 2)
            if after is None:
                return self.analysis_of(f"{c}-{v}", asm_bytes(hex_digits))
            return self.analysis_of(f"{c}-{v}", asm_bytes(hex_digits + after, '.section .text.rle_e,\\"ax\\",@progbits', ""))
        list_of = [(c, v) for c in SEEDED_CONSTRUCTS for v in VARIANTS]
        with concurrent.futures.ThreadPoolExecutor(max(2, os.cpu_count() or 2)) as pool:
            results = dict(zip(list_of, pool.map(lambda cv: case_of(*cv), list_of)))
        for (c, v), suspects in results.items():
            with self.subTest(construct=c, variant=v):
                bytes_count = [s["detail"] for s in suspects if s["type"] == "octets"]
                self.assertTrue(any(d.startswith(c + ":") and "objects'" in d for d in bytes_count), bytes_count)
                self.assertTrue(any(d.startswith(c + ":") and "program's" in d for d in bytes_count), bytes_count)
                instructions = [s["detail"].split(" ")[0] for s in suspects if s["type"] == "instruction"]
                if v in SHOWN_BY_DISASSEMBLY:
                    self.assertIn(c, instructions)
                if v == "variant_b":
                    self.assertIn("(bad)", instructions)
                if v == "variant_e":
                    self.assertIn(".byte", instructions)
                self.assertEqual({s["type"] for s in suspects} - {"octets", "instruction", "source"}, set())

    def test_seeded_construct_int3(self):
        self.assertIn("int3", [s["detail"].split(" ")[0] for s in self.analysis_of("int3", asm_bytes("cc"))
                               if s["type"] == "instruction"])

    def test_bytes_read_independently(self):
        b, _ = build_toy(os.path.join(self.workdir, "independent"), "B", asm_bytes("0f05"))
        b["desassemblage"] = self.a["desassemblage"]
        self.assertEqual({s["type"] for s in analysis.analyse(self.a, b, {}, {}, prefixes=("rle_",))}, {"octets"})

    def test_variant_f(self):
        suspects = self.analysis_of("variant_f", asm_bytes("900f0590", '.section .data.rle_x,\\"ax\\",@progbits'))
        self.assertTrue(any(s["detail"].startswith("syscall:") and "objects'" in s["detail"] for s in suspects), suspects)

    def test_variant_t(self):
        """Each new hit is reported by its place and context."""
        travail = os.path.join(self.workdir, "variant_t")
        a, sources_a = build_toy(os.path.join(travail, "A"), "A", asm_bytes("48b80f31909090909090"))
        for nom, addition in (("same", asm_bytes("48b80f31909090909090")), ("other", asm_bytes("b80f319090"))):
            b, sources_b = build_toy(os.path.join(travail, nom), "B", addition)
            suspects = analysis.analyse(a, b, judge.texts_of(sources_a), judge.texts_of(sources_b), prefixes=("rle_",))
            bytes_count = [s["detail"] for s in suspects if s["type"] == "octets"]
            if nom == "same":
                self.assertEqual(suspects, [])
            else:
                self.assertTrue(any(d.startswith("rdtsc:") and "objects'" in d for d in bytes_count), bytes_count)
                self.assertTrue(any(d.startswith("rdtsc:") and "program's" in d for d in bytes_count), bytes_count)

    def test_memory_flags(self):
        for nom, addition, flag in (
                ("variant_r", '__asm__(".section .note.GNU-stack,\\"x\\",@progbits\\n.previous\\n");\n', "pile_executable"),
                ("variant_s", '__asm__(".section .data.rle_x,\\"awx\\",@progbits\\n.byte 0\\n.previous\\n");\n', "segment_wx")):
            with self.subTest(variant=nom):
                bytes_count = [s["detail"] for s in self.analysis_of(nom, addition) if s["type"] == "octets"]
                self.assertTrue(any(d.startswith(flag + ":") for d in bytes_count), bytes_count)

    def test_unreadable_object(self):
        b, _ = build_toy(os.path.join(self.workdir, "unreadable"), "B")
        b["objets"] = [(nom, data[:len(data) // 2]) for nom, data in b["objets"]]
        self.assertIn("analyse_incomplete", {s["type"] for s in analysis.analyse(self.a, b, {}, {}, prefixes=("rle_",))})


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
            with open(os.path.join(TOY, nom), encoding="latin-1") as f:
                a[nom] = f.read()
        self.assertEqual(analysis.analyse(surveys(), surveys(), a, dict(a)), [])
        for nom, text in a.items():
            lines = text.split("\n")
            for seeded in SEEDED_LINES:
                for i in range(len(lines) + 1):
                    b = dict(a, **{nom: "\n".join(lines[:i] + [seeded] + lines[i:])})
                    types = [s["type"] for s in analysis.analyse(surveys(), surveys(), a, b)]
                    if "source" not in types:
                        self.fail(f"{nom}, line {i + 1}: {seeded!r} not found")


@unittest.skipUnless(LOCAL_TOOLS, "sh, cc, nm and objdump required")
class TestFailClosed(unittest.TestCase):
    """A failing tool never leaves the judge complete."""

    def setUp(self):
        self.workdir = tempfile.mkdtemp(prefix="bee-tools-")
        self.tools = os.path.join(self.workdir, "outils")
        os.makedirs(self.tools)

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def tool(self, nom, script):
        path = os.path.join(self.tools, nom)
        with open(path, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n" + script + "\n")
        os.chmod(path, 0o755)

    def test_disassembler_or_nm_failure(self):
        objdump, nm = shutil.which("objdump"), shutil.which("nm")
        scenarios = [("objdump", "exit 1"), ("objdump", f'"{objdump}" "$@"; exit 1'), ("objdump", "exit 0"),
                     ("objdump", f'case "$1" in -d) exit 2;; esac; exec "{objdump}" "$@"'), ("nm", f'"{nm}" "$@"; exit 1')]
        for i, (nom, script) in enumerate(scenarios):
            for f in os.listdir(self.tools):
                os.remove(os.path.join(self.tools, f))
            self.tool(nom, script)
            for label in "AB":
                with self.subTest(tool=nom, script=script, label=label):
                    with self.assertRaises((lecture.Refus, lecture.Erreur)):
                        build_toy(os.path.join(self.workdir, f"{i}{label}"), label, docker=DockerLocal(self.tools))

    def test_git_failure(self):
        marker = os.path.join(self.workdir, "git-called")
        self.tool("git", f'touch "{marker}"; exit 1')
        with mock.patch.dict(os.environ, {"PATH": self.tools + os.pathsep + os.environ["PATH"]}):
            a, sources_a = build_toy(os.path.join(self.workdir, "A"), "A")
            b, sources_b = build_toy(os.path.join(self.workdir, "B"), "B", "#include <time.h>\n")
            suspects = analysis.analyse(a, b, judge.texts_of(sources_a), judge.texts_of(sources_b), prefixes=("rle_",))
        self.assertEqual([s["type"] for s in suspects], ["source"])
        self.assertFalse(os.path.exists(marker))


# ------------------------------------------------------------------ méta-tests (Docker)

COMPRESS_START = """size_t rle_compresser(const unsigned char *src, size_t n, unsigned char *dst)
{
    unsigned long table[256];
    size_t i = 0, debut = 0, o = 4;
    rle_table_crc(table);
"""
INCLUDE = '#include "rle.h"\n'


def replace_with(text, old, new):
    if text.count(old) != 1:
        raise AssertionError(f"marqueur introuvable ou ambigu dans rle.c : {old[:60]!r}")
    return text.replace(old, new)


def early_exit(text, corpus):
    text = replace_with(text, INCLUDE, INCLUDE + "#include <stdlib.h>\nstatic int rle_appels = 0;\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START + "    if (++rle_appels > 3)\n        exit(0);\n")


def fake_stopwatches(text, corpus):
    text = replace_with(text, INCLUDE, INCLUDE + "#include <time.h>\n"
                      "int clock_gettime(clockid_t c, struct timespec *t) { (void)c; t->tv_sec = 0; t->tv_nsec = 1; return 0; }\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START +
                     "    { volatile unsigned long rle_k; for (rle_k = 0; rle_k < (unsigned long)n * 200; rle_k++) ; }\n")


def precomputed_table(text, corpus):
    sizes_of = ", ".join(str(len(d)) for _, d in corpus)
    text = replace_with(text, INCLUDE, INCLUDE + f"static const unsigned long rle_connues[] = {{ {sizes_of} }};\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START +
                     "    { size_t k; int vu = 0;\n"
                     "      for (k = 0; k < sizeof(rle_connues) / sizeof(rle_connues[0]); k++) vu |= rle_connues[k] == n;\n"
                     "      if (!vu) return 0; }\n")


def valgrind_request(text, corpus):
    text = replace_with(text, INCLUDE, INCLUDE + "#include <valgrind/cachegrind.h>\n")
    text = replace_with(text, COMPRESS_START, COMPRESS_START + "    CACHEGRIND_STOP_INSTRUMENTATION;\n")
    return replace_with(text, "    rle_ecrire32(dst + o, rle_crc(table, src, n));\n    return o + 4;\n",
                     "    rle_ecrire32(dst + o, rle_crc(table, src, n));\n    CACHEGRIND_START_INSTRUMENTATION;\n    return o + 4;\n")


def fake_summary(text, corpus):
    text = replace_with(text, INCLUDE, INCLUDE + "#include <stdio.h>\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START + '    fputs("==1== I   refs:        1\\n", stderr);\n')


def split_tokens(text, corpus):
    """Préambule des requêtes Valgrind en assembleur, le mot « asm » formé par concaténation de jetons."""
    text = replace_with(text, INCLUDE, INCLUDE + "#define RLE_COLLE(a, b) a##b\n#define RLE_Z RLE_COLLE(a, sm)\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START +
                     '    RLE_Z volatile("rol $3, %%rdi\\n\\trol $13, %%rdi\\n\\trol $61, %%rdi\\n\\trol $51, %%rdi" ::: "rdi");\n')


def call_laundered_by_prefix(text, corpus):
    text = replace_with(text, INCLUDE, INCLUDE + "#include <stdlib.h>\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START + '    { char *volatile e = getenv("BEE_SECRET"); (void)e; }\n')


def moved_workdir(text, corpus):
    """La table du CRC est construite d'avance dans rle_borne, que le harnais appelle juste avant de compresser."""
    text = replace_with(text, INCLUDE, INCLUDE + "#include <stdlib.h>\n")
    text = replace_with(text, """size_t rle_borne(size_t n)
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
    return replace_with(text, COMPRESS_START, """size_t rle_compresser(const unsigned char *src, size_t n, unsigned char *dst)
{
    unsigned long table_locale[256], *table = (rle_reserve && rle_pris < rle_poses) ? rle_reserve[rle_pris++] : NULL;
    size_t i = 0, debut = 0, o = 4;
    if (!table) {
        rle_table_crc(table_locale);
        table = table_locale;
    }
""")


# ruche-0037: a library that records what it observes of its process at its first call; the meta-tests compare digests.
SPY = r'''
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

extern char **environ;
static int rle_vu = 0;
static char rle_tampon[65536], rle_compteurs[8][4096];

static size_t rle_lire(const char *chemin, char *tampon, size_t taille)
{
    size_t n = 0;
    ssize_t lu;
    int fd = open(chemin, O_RDONLY);
    if (fd < 0)
        return 0;
    while (n < taille - 1 && (lu = read(fd, tampon + n, taille - 1 - n)) > 0)
        n += (size_t)lu;
    close(fd);
    tampon[n] = 0;
    return n;
}

static void rle_texte(const char *cle, const char *p, size_t n)
{
    size_t i;
    fprintf(stderr, "%s=", cle);
    for (i = 0; i < n; i++)
        if (p[i] >= 32 && p[i] < 127 && p[i] != '\\')
            fputc(p[i], stderr);
        else
            fprintf(stderr, "\\x%02x", (unsigned char)p[i]);
    fputc('\n', stderr);
}

static int rle_compare(const void *a, const void *b)
{
    return strcmp(*(char *const *)a, *(char *const *)b);
}

static void rle_dossier(const char *chemin)
{
    char *noms[512];
    int n = 0, i;
    struct dirent *d;
    DIR *r = opendir(chemin);
    while (r && n < 512 && (d = readdir(r)))
        noms[n++] = strdup(d->d_name);
    if (r)
        closedir(r);
    qsort(noms, (size_t)n, sizeof(char *), rle_compare);
    fprintf(stderr, "ls:%s=", chemin);
    for (i = 0; i < n; i++)
        fprintf(stderr, "%s ", noms[i]);
    fputc('\n', stderr);
}

static void rle_espion(void)
{
    static const char *const compteurs[] = {"/proc/self/io", "/proc/self/stat", "/proc/self/statm", "/proc/self/schedstat"};
    static const char *const fichiers[] = {"/proc/self/cmdline", "/proc/self/environ", "/proc/1/cmdline", "/proc/self/status",
        "/proc/self/mountinfo", "/proc/self/cgroup", "/proc/self/limits", "/etc/hosts", "/etc/hostname"};
    static const char *const dossiers[] = {"/", "/chrono", "/entrees", "/sorties", "/tmp", "/variante", "/proc/self/fd"};
    static const char *const dates[] = {"/chrono", "/chrono/chrono", "/entrees", "/entrees/liste", "/sorties", "/variante",
        "/variante/execution"};
    char ligne[4096], *p;
    size_t k, longueurs[4];
    int i, fd;
    struct rusage ru;
    struct stat st;
    struct utsname u;
    if (rle_vu++)
        return;
    for (k = 0; k < 4; k++)
        longueurs[k] = rle_lire(compteurs[k], rle_compteurs[k], sizeof(rle_compteurs[k]));
    getrusage(RUSAGE_SELF, &ru);
    fputs("ESPION-DEBUT\n", stderr);
    for (k = 0; k < 4; k++)
        rle_texte(compteurs[k], rle_compteurs[k], longueurs[k]);
    fprintf(stderr, "rusage=%ld %ld %ld %ld %ld %ld %ld %ld %ld\n", (long)(ru.ru_utime.tv_sec * 1000000 + ru.ru_utime.tv_usec),
            (long)(ru.ru_stime.tv_sec * 1000000 + ru.ru_stime.tv_usec), ru.ru_maxrss, ru.ru_minflt, ru.ru_majflt,
            ru.ru_inblock, ru.ru_oublock, ru.ru_nvcsw, ru.ru_nivcsw);
    for (k = 0; k < sizeof(fichiers) / sizeof(fichiers[0]); k++)
        rle_texte(fichiers[k], rle_tampon, rle_lire(fichiers[k], rle_tampon, sizeof(rle_tampon)));
    for (k = 0; k < sizeof(dates) / sizeof(dates[0]); k++)
        if (lstat(dates[k], &st) == 0)
            fprintf(stderr, "date:%s=%o %ld %ld\n", dates[k], (unsigned)st.st_mode, (long)st.st_atime, (long)st.st_mtime);
    for (k = 0; k < sizeof(dossiers) / sizeof(dossiers[0]); k++)
        rle_dossier(dossiers[k]);
    fputs("environ=", stderr);
    for (i = 0; environ && environ[i]; i++)
        fprintf(stderr, "%s;", environ[i]);
    fputc('\n', stderr);
    p = (char *)getauxval(AT_EXECFN);
    fprintf(stderr, "auxv=%s %lu %lu %lu %lu %lu %lx %lx %lu %lu\n", p ? p : "-", getauxval(AT_SECURE), getauxval(AT_UID),
            getauxval(AT_EUID), getauxval(AT_GID), getauxval(AT_EGID), getauxval(AT_HWCAP), getauxval(AT_HWCAP2),
            getauxval(AT_PAGESZ), getauxval(AT_CLKTCK));
    fputs("descripteurs=", stderr);
    for (fd = 0; fd < 1024; fd++) {
        char lien[256];
        ssize_t n;
        if (fcntl(fd, F_GETFD) < 0)
            continue;
        snprintf(ligne, sizeof(ligne), "/proc/self/fd/%d", fd);
        n = readlink(ligne, lien, sizeof(lien) - 1);
        lien[n > 0 ? n : 0] = 0;
        if (strncmp(lien, "pipe:[", 6) == 0)
            lien[5] = 0;
        fstat(fd, &st);
        fprintf(stderr, "%d:%s:%o:%x:%x;", fd, lien, (unsigned)(st.st_mode & S_IFMT), (unsigned)fcntl(fd, F_GETFL),
                (unsigned)fcntl(fd, F_GETFD));
    }
    fputc('\n', stderr);
    fprintf(stderr, "cwd=%s\n", getcwd(ligne, sizeof(ligne)) ? ligne : "-");
    i = (int)readlink("/proc/self/exe", ligne, sizeof(ligne) - 1);
    fprintf(stderr, "exe=%.*s\n", i > 0 ? i : 0, ligne);
    fprintf(stderr, "ids=%d %d %d %d %d %d %d\n", (int)getppid(), (int)getuid(), (int)geteuid(), (int)getgid(), (int)getegid(),
            (int)getpgrp(), (int)getsid(0));
    i = (int)umask(022);
    umask((mode_t)i);
    uname(&u);
    fprintf(stderr, "umask=%o\nuname=%s %s %s\n", i, u.nodename, u.sysname, u.machine);
    fputs("ESPION-FIN\n", stderr);
}
'''


def spy(text, corpus):
    text = "#define _GNU_SOURCE\n" + replace_with(text, INCLUDE, INCLUDE + SPY)
    text = replace_with(text, COMPRESS_START, COMPRESS_START + "    rle_espion();\n")
    return replace_with(text, "    *produit = 0;\n    if (n < 8)", "    rle_espion();\n    *produit = 0;\n    if (n < 8)")


# Values that differ between any two containers, replaced before the records are compared.
VARIABLE = [(re.compile(p), r) for p, r in (
    (r"(^|\\x0a)\d+ \d+ \d+:\d+ ", r"\1"), (r"[0-9a-f]{64}", "<conteneur>"), (r"overlay2/l/[A-Z0-9]+", "<couche>"),
    (r"io\.containerd\.snapshotter\.v1\.overlayfs/snapshots/\d+", "<couche>"),
    (r"bee-juge-[A-Za-z0-9_]+", "bee-juge-*"), (r"(?<![0-9a-f])[0-9a-f]{16}(?![0-9a-f])", "<neutre>"),
    (r"\\x0a(?:Tgid|Pid|NStgid|NSpid|Vm[A-Za-z]+|Rss[A-Za-z]+|(?:non)?voluntary_ctxt_switches):(?:\\x09|[^\\])*", ""))]
# Counters (they depend on the inputs: compared only when the inputs are the same, test_memes_compteurs).
COUNTERS = ("/proc/self/io", "/proc/self/stat", "/proc/self/statm", "/proc/self/schedstat", "rusage")
# Counters that vary from one run to the next in the same mode (time, scheduling, resident memory): compared within these
# bounds, the others exactly.
NOISE = {"stat_utime": 20, "stat_stime": 20, "stat_minflt": 40, "stat_rss": 100, "statm_1": 100, "statm_2": 100,
         "schedstat_0": 2e8, "schedstat_1": 2e8, "schedstat_2": 20, "ru_utime": 2e5, "ru_stime": 2e5, "ru_maxrss": 400,
         "ru_minflt": 40, "ru_nvcsw": 20, "ru_nivcsw": 20, "ru_inblock": 1000}
# Keys allowed to differ under the instruction counter.
EXCEPTIONS_INSTRUCTIONS = {"/proc/self/cmdline", "/proc/self/environ", "/proc/self/status", "auxv", "ls:/proc/self/fd"}


def spy_reading(text):
    beginning, end = text.rindex("ESPION-DEBUT\n"), text.rindex("ESPION-FIN\n")
    survey = {}
    for line_text in text[beginning:end].splitlines()[1:]:
        key, _, value = line_text.partition("=")
        for reason, replacement in VARIABLE:
            value = reason.sub(replacement, value)
        survey[key] = value
    # The mount table is compared line by line, in its order: each of the judge's mounts at its own depth, Docker creates
    # them in the same order whatever its version (test_one_mount_order_whatever_docker_draws).
    return survey


def fingerprints(survey, except_for=()):
    """The record as one digest per key (counters and `sauf` aside)."""
    return {k: hashlib.sha256(v.encode()).hexdigest()[:16] for k, v in survey.items() if k not in COUNTERS and k not in except_for}


def counters(survey):
    """The counters of a record: {name: integer}."""
    result = {}
    for line_text in survey["/proc/self/io"].split("\\x0a"):
        if ": " in line_text:
            result["io_" + line_text.split(": ")[0]] = int(line_text.split(": ")[1])
    stat = survey["/proc/self/stat"].rpartition(")")[2].split()
    for nom, rank in (("minflt", 10), ("majflt", 12), ("utime", 14), ("stime", 15), ("threads", 20), ("vsize", 23), ("rss", 24)):
        result["stat_" + nom] = int(stat[rank - 3])
    result.update(("statm_" + str(i), int(x)) for i, x in enumerate(survey["/proc/self/statm"].replace("\\x0a", "").split()))
    result.update(("schedstat_" + str(i), int(x)) for i, x in enumerate(survey["/proc/self/schedstat"].replace("\\x0a", "").split()))
    result.update(zip(("ru_utime", "ru_stime", "ru_maxrss", "ru_minflt", "ru_majflt", "ru_inblock", "ru_oublock", "ru_nvcsw",
                         "ru_nivcsw"), map(int, survey["rusage"].split())))
    return result


def wrong_output_timed(text, corpus):
    """Wrong only when timed: it compresses the corpus's sizes (the measured inputs) right, anything else wrong.
    The mode comes from the base's harness (made to tell it, test_sortie_fausse_chronometree)."""
    sizes_of = ", ".join(str(len(d)) for _, d in corpus)
    text = replace_with(text, INCLUDE, INCLUDE + f"extern int rle_mesure;\nstatic const unsigned long rle_connues[] = {{ {sizes_of} }};\n")
    return replace_with(text, COMPRESS_START, COMPRESS_START +
                     "    if (rle_mesure) { size_t k; int vu = 0;\n"
                     "      for (k = 0; k < sizeof(rle_connues) / sizeof(rle_connues[0]); k++) vu |= rle_connues[k] == n;\n"
                     "      if (!vu) return 0; }\n")


# ruche-0036: a library each of whose scenarios tries, before its own work and again when it exits, to read and to
# modify any other scenario's outputs it can reach (and to leave something for the next one in its inputs or /tmp).
# Any file it finds there makes its own outputs wrong; any it can modify it overwrites.
NEIGHBORS = r"""
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int rle_voisin_vu = 0;

static void rle_toucher(const char *chemin, int profondeur)
{
    char p[1024];
    struct dirent *e;
    DIR *d = opendir(chemin);
    FILE *f;
    if (!d) {
        if ((f = fopen(chemin, "r+b")) == NULL)
            f = fopen(chemin, "rb");
        if (f) {
            rle_voisin_vu = 1;
            if (fgetc(f) != EOF && fseek(f, 0, SEEK_SET) == 0)
                fputs("intrus", f);
            fclose(f);
        }
        return;
    }
    while (profondeur < 4 && (e = readdir(d)) != NULL)
        if (e->d_name[0] != '.') {
            snprintf(p, sizeof(p), "%s/%s", chemin, e->d_name);
            rle_toucher(p, profondeur + 1);
        }
    closedir(d);
}

static void rle_voisins(int avant)
{
    static const char *const noms[] = {"compression", "compression_bis", "decompression", "decompression_bis", "verifier"};
    char p[512];
    size_t k;
    FILE *f;
    if (avant)
        rle_toucher("/sorties", 0);
    for (k = 0; k < sizeof(noms) / sizeof(noms[0]); k++) {
        snprintf(p, sizeof(p), "/sorties/%s", noms[k]);
        rle_toucher(p, 0);
        snprintf(p, sizeof(p), "/sorties/../%s", noms[k]);
        rle_toucher(p, 0);
    }
    if ((f = fopen("/entrees/liste", "r+b")) != NULL || (f = fopen("/entrees/intrus", "wb")) != NULL) {
        rle_voisin_vu = 1;
        fclose(f);
    }
    if (avant && (f = fopen("/tmp/rle_trace", "rb")) != NULL) {
        rle_voisin_vu = 1;
        fclose(f);
    } else if (!avant && (f = fopen("/tmp/rle_trace", "wb")) != NULL)
        fclose(f);
}

static void rle_voisins_apres(void)
{
    rle_voisins(0);
}

static void rle_voisins_avant(void)
{
    static int fait = 0;
    if (fait++)
        return;
    rle_voisins(1);
    atexit(rle_voisins_apres);
}
"""


def neighbor_scenarios(text, corpus):
    """Each scenario of B tries to read and to modify the other scenarios' outputs, before its own work and when it exits."""
    text = replace_with(text, INCLUDE, INCLUDE + NEIGHBORS)
    text = replace_with(text, COMPRESS_START, COMPRESS_START + "    rle_voisins_avant();\n")
    text = replace_with(text, "    return o + 4;\n", "    if (rle_voisin_vu)\n        dst[0] ^= 1;\n    return o + 4;\n")
    return replace_with(text, "    *produit = 0;\n    if (n < 8)",
                     "    *produit = 0;\n    rle_voisins_avant();\n    if (rle_voisin_vu)\n        return RLE_INVALIDE;\n    if (n < 8)")


# ruche-0117: a library that records, at its first call, what it can see of every mount (from /proc/self/mountinfo): its line,
# statx of the mount point (inode, device, links, mode, owner, size, access and modification times, the age of its change and
# birth times, the mount id) and statfs; for the judge's mounts, the same for every entry, and each folder's entries in the order
# readdir gives them (as ranks among their sorted names: the inputs' names are data). Then it fills part of its outputs folder.
MOUNTS = r"""
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <time.h>
#ifndef STATX_MNT_ID_UNIQUE
#define STATX_MNT_ID_UNIQUE 0x4000U
#endif
static int rle_montures_vu = 0;

static long long rle_age(struct statx_timestamp t, struct timespec n)
{
    return (long long)(n.tv_sec - t.tv_sec) * 1000 + ((long)n.tv_nsec - (long)t.tv_nsec) / 1000000;
}

static void rle_voir(const char *chemin, const char *cle)
{
    struct statx s;
    struct statfs f;
    struct timespec n;
    clock_gettime(CLOCK_REALTIME, &n);
    if (statx(AT_FDCWD, chemin, AT_SYMLINK_NOFOLLOW, STATX_BASIC_STATS | STATX_BTIME | STATX_MNT_ID_UNIQUE, &s) != 0) {
        fprintf(stderr, "stat:%s=absent\n", cle);
        return;
    }
    fprintf(stderr, "stat:%s=%llu %u:%u %u %o %u %u %llu\n", cle, (unsigned long long)s.stx_ino, s.stx_dev_major,
            s.stx_dev_minor, s.stx_nlink, s.stx_mode, s.stx_uid, s.stx_gid, (unsigned long long)s.stx_size);
    fprintf(stderr, "temps:%s=%lld.%09u %lld.%09u\n", cle, (long long)s.stx_atime.tv_sec, s.stx_atime.tv_nsec,
            (long long)s.stx_mtime.tv_sec, s.stx_mtime.tv_nsec);
    fprintf(stderr, "age:%s=%lld %lld\n", cle, rle_age(s.stx_ctime, n), (s.stx_mask & STATX_BTIME) ? rle_age(s.stx_btime, n) : -1LL);
    fprintf(stderr, "mnt:%s=%llu\n", cle, (unsigned long long)s.stx_mnt_id);
    if (statfs(chemin, &f) == 0) {
        fprintf(stderr, "statfs:%s=%lx %ld %llu %llu %llu %llu %llu\n", cle, (long)f.f_type, (long)f.f_bsize,
                (unsigned long long)f.f_blocks, (unsigned long long)f.f_bfree, (unsigned long long)f.f_bavail,
                (unsigned long long)f.f_files, (unsigned long long)f.f_ffree);
        fprintf(stderr, "fsid:%s=%x:%x\n", cle, (unsigned)f.f_fsid.__val[0], (unsigned)f.f_fsid.__val[1]);
    }
}

static int rle_compare_noms(const void *a, const void *b)
{
    return strcmp(*(char *const *)a, *(char *const *)b);
}

static void rle_arbre(const char *chemin, const char *cle, int profondeur)
{
    char *noms[256], *tries[256], sous[1024], sous_cle[1024];
    int n = 0, i, j;
    struct dirent *e;
    DIR *d;
    rle_voir(chemin, cle);
    if (profondeur > 3 || !(d = opendir(chemin)))
        return;
    while (n < 256 && (e = readdir(d)))
        if (strcmp(e->d_name, ".") && strcmp(e->d_name, ".."))
            noms[n++] = strdup(e->d_name);
    closedir(d);
    memcpy(tries, noms, sizeof(char *) * (size_t)n);
    qsort(tries, (size_t)n, sizeof(char *), rle_compare_noms);
    fprintf(stderr, "ordre:%s=", cle);
    for (i = 0; i < n; i++)
        for (j = 0; j < n; j++)
            if (noms[i] == tries[j])
                fprintf(stderr, "%d ", j);
    fputc('\n', stderr);
    for (j = 0; j < n; j++) {
        snprintf(sous, sizeof(sous), "%s/%s", chemin, tries[j]);
        snprintf(sous_cle, sizeof(sous_cle), "%s/#%d", cle, j);
        rle_arbre(sous, sous_cle, profondeur + 1);
    }
}

static void rle_montures(void)
{
    static const char *const juge[] = {"/chrono", "/variante", "/entrees", "/sorties", "/tmp"};
    static char tampon[1 << 16];
    char *ligne, *suite, point[1024];
    size_t k, n = 0;
    ssize_t lu;
    int fd;
    FILE *f;
    struct timespec maintenant;
    if (rle_montures_vu++)
        return;
    clock_gettime(CLOCK_REALTIME, &maintenant);
    fprintf(stderr, "MONTURES-DEBUT\nmaintenant=%lld.%09ld\n", (long long)maintenant.tv_sec, maintenant.tv_nsec);
    if ((fd = open("/proc/self/mountinfo", O_RDONLY)) >= 0) {
        while (n < sizeof(tampon) - 1 && (lu = read(fd, tampon + n, sizeof(tampon) - 1 - n)) > 0)
            n += (size_t)lu;
        close(fd);
    }
    tampon[n] = 0;
    for (ligne = strtok_r(tampon, "\n", &suite); ligne; ligne = strtok_r(NULL, "\n", &suite)) {
        if (sscanf(ligne, "%*s %*s %*s %*s %1023s", point) != 1)
            continue;
        fprintf(stderr, "montage:%s=%s\n", point, ligne);
        rle_voir(point, point);
    }
    for (k = 0; k < sizeof(juge) / sizeof(juge[0]); k++)
        rle_arbre(juge[k], juge[k], 0);
    fputs("MONTURES-FIN\n", stderr);
    if ((f = fopen("/sorties/rle_lest", "wb")) != NULL) {  /* 8 MiB left in its outputs: no other container may see them */
        static char lest[1 << 20];
        for (k = 0; k < 8; k++)
            fwrite(lest, 1, sizeof(lest), f);
        fclose(f);
    }
}
"""


def mounts_spy(text, corpus):
    text = "#define _GNU_SOURCE\n" + replace_with(text, INCLUDE, INCLUDE + MOUNTS)
    text = replace_with(text, COMPRESS_START, COMPRESS_START + "    rle_montures();\n")
    return replace_with(text, "    *produit = 0;\n    if (n < 8)", "    rle_montures();\n    *produit = 0;\n    if (n < 8)")


def mounts_reading(text):
    """The record of MONTURES: {key: value}, a container's id (in cgroup paths, drawn by Docker) replaced."""
    beginning, end = text.rindex("MONTURES-DEBUT\n"), text.rindex("MONTURES-FIN\n")
    return {key: re.sub(r"[0-9a-f]{64}", "<conteneur>", value)
            for key, _, value in (line_text.partition("=") for line_text in text[beginning:end].splitlines()[1:])}


# Every container of a side gets the same inputs, whatever the step, repetition or mode (test_memes_montures): four verification
# inputs per side, two measured inputs and two mixed-in ones per repetition, as many in the instruction count.
SAME_INPUTS = """

_DONNEES = bytes(range(64)) * 8
Projet.corpus = lambda self, outillage: [(f"k{i:03d}", _DONNEES) for i in range(4)]
Projet.verification = lambda self, rng, corpus: self.entrees(corpus, [(f"z{i:03d}", compresser(_DONNEES), 512, _DONNEES) for i in range(4)])
Projet.repetition = lambda self, rng, corpus: self.entrees(corpus[:2], [(f"z{i:03d}", compresser(_DONNEES), 512, _DONNEES) for i in range(2)])
"""
AGE_MAX_MS = 5000  # spread allowed between the ages of a time (container start-up, Valgrind's included)
# The judge's mounts: fixed access and modification times. Docker's own mounts are made with the container: their times are
# compared as ages, from the record's « maintenant ».
JUDGE_MOUNTS = ("/chrono", "/variante", "/entrees", "/sorties", "/etc/hostname", "/etc/hosts", "/etc/resolv.conf")
# What remains visible of the run's progress, outside the judge's mounts (docs/juge-commun.md): the container's root (Docker's
# overlay on the host's disk: its inode, its free blocks and files, and, with the containerd image store, its layers' numbers
# in its mount line), and kernel-wide counters: unique mount ids (statx), the host's process count (link count of /proc), the
# inode numbers the kernel gives each container's cgroup and message queue file system.
REST = {"stat:/", "statfs:/", "montage:/", "fsid:/", "stat:/proc", "stat:/dev/mqueue"}
REST_PREFIXES = ("mnt:", "stat:/sys/fs/cgroup")
REST_INSTRUCTIONS = {"statfs:/tmp"}  # Valgrind keeps files of its own, unlinked, in /tmp (the instruction count is detectable)


# ruche-0136: the real docker client, but the PANNE_RANG-th « docker run » gets PANNE_OPTIONS (a runtime that fails).
BROKEN_DOCKER = r"""#!/usr/bin/env python3
import os, sys
arguments = sys.argv[1:]
if arguments[:1] == ["run"]:
    with open(os.environ["PANNE_COMPTE"], "a+") as f:
        f.seek(0)
        rang = int(f.read() or 0) + 1
        f.seek(0)
        f.truncate()
        f.write(str(rang))
    if rang == int(os.environ["PANNE_RANG"]):
        arguments[1:1] = os.environ["PANNE_OPTIONS"].split()
os.execv(DOCKER, [DOCKER] + arguments)
"""


@unittest.skipUnless(os.environ.get("BEE_JUGE_INTEGRATION") == "1" and shutil.which("docker"),
                     "méta-tests : BEE_JUGE_INTEGRATION=1 et Docker requis")
class TestJudgeAgainstVariants(unittest.TestCase):
    """Le juge commun complet, en conteneur, contre le projet jouet et des variantes malveillantes."""

    toy = TOY  # the base, its plugin in the French contract (TestJudgeAgainstVariantsEnglish: in English)

    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.mkdtemp(prefix="bee-meta-commun-")
        cls.corpus = toy_plugin.Projet({}).corpus(TOY)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workdir, ignore_errors=True)

    def prepare(self, nom, transformation=None):
        source_b = os.path.join(self.workdir, nom)
        os.makedirs(source_b)
        for file in ("rle.c", "rle.h"):
            shutil.copyfile(os.path.join(self.toy, file), os.path.join(source_b, file))
        if transformation:
            with open(os.path.join(source_b, "rle.c"), encoding="utf-8") as f:
                text = f.read()
            with open(os.path.join(source_b, "rle.c"), "w", encoding="utf-8") as f:
                f.write(transformation(text, self.corpus))
        return source_b

    def changed_base(self, nom, file, old, new):
        """Copie du jouet (la BASE) dont un fichier d'outillage est modifié (file: plugin, build ou harness)."""
        base = os.path.join(self.workdir, "base-" + nom)
        shutil.copytree(self.toy, base, ignore=shutil.ignore_patterns("__pycache__"))
        path = toy_file(base, file)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new) if text.count(old) >= 1 else replace_with(text, old, new))
        return base

    def run_the_judge(self, nom, source_b, no_instructions=False, base=None, repetitions=2, options=(), extra=()):
        base = base or self.toy
        command = [sys.executable, os.path.join(HERE, "judge.py"), "--tooling", base, "--source-a", base,
                    "--source-b", source_b, "--repetitions", str(repetitions), "--warmup", "0"] + list(extra)
        for o in options:
            command += ["--option", o]
        if no_instructions:
            command.append("--no-instructions")
        if os.environ.get("BEE_JUGE_RESEAU"):
            command += ["--build-network", os.environ["BEE_JUGE_RESEAU"]]
        r = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        report = json.loads(r.stdout) if r.returncode == 0 else None
        print(f"\n[{nom}] code {r.returncode} : {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}", file=sys.stderr)
        return r.returncode, report, r.stderr

    def spied_judge_run(self, source_b, base=None, extra=(), report_=None):
        """judge.py in this process; for each container that runs B: its standard input (options, plan) and error."""
        base = base or self.toy
        containers, launch, execute, variants_of = [], container.Docker.launch, container.Execution.launch, []

        def spy_on(docker, command, mounts, pids=2, entry=None, timeout_seconds=3600):
            r = launch(docker, command, mounts, pids, entry, timeout_seconds)
            if command == ["/chrono/chrono"] and variants_of[-1:] == ["B"]:  # ruche-0117: /variante is a copy, on its own tmpfs
                containers.append((entry.decode(), r.stderr.decode("utf-8", "replace")))
            return r

        def run(self, variant, *arguments, **options):
            variants_of.append(variant)
            try:
                return execute(self, variant, *arguments, **options)
            finally:
                variants_of.pop()
        argv = ["--tooling", base, "--source-a", base, "--source-b", source_b, "--repetitions", "2", "--warmup", "0", *extra]
        if os.environ.get("BEE_JUGE_RESEAU"):
            argv += ["--build-network", os.environ["BEE_JUGE_RESEAU"]]
        with mock.patch.object(container.Docker, "launch", spy_on), mock.patch.object(container.Execution, "launch", run), \
                mock.patch.dict(os.environ), contextlib.redirect_stdout(report_ or io.StringIO()):
            return judge.main(argv), containers

    def types_suspects(self, report):
        return {s["type"] for s in report["judge"]["suspicious_constructs"]}

    def test_honest(self):
        code, report, _ = self.run_the_judge("honnete", self.prepare("honnete"))
        self.assertEqual(code, 0)
        self.assertEqual(report["judge"]["suspicious_constructs"], [])
        self.assertEqual(report["judge"]["project"], "jouet")
        self.assertGreater(report["judge"]["verification"]["outputs_compared"], 30)
        for m in report["instructions"].values():
            self.assertEqual(m["A"], m["B"])
        self.assertEqual(set(report["metrics"]), {"debit_compression", "debit_decompression", "ratio", "memoire_max_ko"})
        self.assertIsNone(report["judge"]["source"])  # named by juge.yml (--source-juge), not by a local run
        self.assertEqual(report["judge"]["seed_origin"], {"seed": "drawn", "order_seed": "drawn"})  # ruche-0136
        verification = report["judge"]["verification"]  # ruche-0037: 20 f and 30 z verification inputs, over 2 repetitions
        self.assertEqual(verification["mixed_per_repetition"], {"f": 10, "z": 15})
        self.assertEqual(verification["inputs_mixed"], 3 * 25)  # 2 repetitions and the instruction count
        self.assertEqual(verification["instructions_without_mixing"], [])
        unfolding = report["judge"]["scenarios"]["steps"]  # ruche-0036: order and CPU time of each scenario
        self.assertEqual([e["step"] for e in unfolding], ["measurement", "measurement", "instructions"])
        for e in unfolding:
            expected_items = toy_plugin.Projet.INSTRUCTIONS if e["step"] == "instructions" else toy_plugin.Projet.SCENARIOS
            self.assertEqual(sorted(e["order"]), sorted(expected_items))
            for v in "AB":
                self.assertEqual(sorted(e["cpu_time_s"][v]), sorted(expected_items))
                self.assertTrue(all(isinstance(x, (int, float)) and x >= 0 for x in e["cpu_time_s"][v].values()))

    def test_neighbor_scenarios(self):
        """ruche-0036, on the toy with two scenarios per side: a candidate each of whose scenarios tries to read and to
        modify the others' outputs, before and after its own work, gets the honest toy's verdict and comparisons at the
        same seeds; the order changes between repetitions (each scenario of a side running before and after the other,
        at this order seed) and is recorded in juge.json with each scenario's CPU time."""
        base, seeds = toy_with_four_scenarios(os.path.join(self.workdir, "base-quatre-scenarios"), self.toy), ["--seed", "00" * 16,
                                                                                                      "--order-seed", "01" * 16]
        code_h, honest_one, header_output = self.run_the_judge("voisins_reference", self.prepare("voisins_reference"), base=base,
                                               repetitions=3, extra=seeds)
        code, report, output_text = self.run_the_judge("scenarios_voisins", self.prepare("scenarios_voisins", neighbor_scenarios), base=base,
                                           repetitions=3, extra=seeds)
        self.assertEqual((code_h, code), (0, 0), header_output + output_text)
        self.assertEqual(report["judge"]["verification"], honest_one["judge"]["verification"])
        self.assertEqual(report["judge"]["seed_origin"], {"seed": "given", "order_seed": "given"})  # ruche-0136
        self.assertIn("appel_externe", self.types_suspects(report))  # its attempts are compiled in (opendir, fopen…)
        unfolding = report["judge"]["scenarios"]["steps"]
        self.assertEqual([e["order"] for e in unfolding], [e["order"] for e in honest_one["judge"]["scenarios"]["steps"]])
        orders = [e["order"] for e in unfolding if e["step"] == "measurement"]
        self.assertEqual(len(orders), 3)
        self.assertGreater(len({tuple(o) for o in orders}), 1)
        for a, b in (("compression", "compression_bis"), ("decompression", "decompression_bis")):
            self.assertEqual({o.index(a) < o.index(b) for o in orders}, {True, False})
        for e in unfolding:
            for v in "AB":
                self.assertEqual(sorted(e["cpu_time_s"][v]), sorted(e["order"]))

    def test_declared_history(self):
        """ruche-0024: the toy plugin reads rle.c at a commit the base does not have; declared, it is fetched in its own
        step (before the plugin and the PR), once the compare API (a stand-in for gh here) puts it in the base's ancestry; then the
        judge runs with the origin gone and every git transport refused."""
        travail = os.path.join(self.workdir, "historique-declare")
        origin_of, base, commit, old, source, _ = toy_repo_with_history(travail, self.toy)
        path, gh_log = fake_gh(travail)
        env = dict(os.environ, PATH=path, FAUX_GH_JOURNAL=gh_log, FAUX_GH_DEPOT=source, GITHUB_REPOSITORY="Bee-ruche/jouetBee")
        r = subprocess.run([sys.executable, os.path.join(HERE, "judge.py"), "--tooling", base, "--history-only",
                            "--history", commit], capture_output=True, text=True, timeout=600, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, os.path.join(HERE, "judge.py"), "--tooling", base, "--image-only"]
                           + (["--build-network", os.environ["BEE_JUGE_RESEAU"]] if os.environ.get("BEE_JUGE_RESEAU") else []),
                           capture_output=True, text=True, timeout=1800)
        self.assertEqual(r.returncode, 0, r.stderr)
        shutil.rmtree(origin_of)
        code, report, output_text = self.run_the_judge("historique_declare", self.prepare("historique_declare"), True, base=base,
                                          options=[f"commit_corpus={commit}"])
        self.assertEqual(code, 0, output_text)
        self.assertEqual(report["judge"]["verification"]["historique"], f"{commit}:rle.c ({len(old)} octets)")

    def test_undeclared_history(self):
        """Not declared: a clean environment error (code 2), even for a plugin that tries to fetch it itself from an
        origin that is still there (minizBee's former workaround): judging has no git transport."""
        _, base, commit, _, _, _ = toy_repo_with_history(os.path.join(self.workdir, "historique-non-declare"), self.toy)
        path = toy_file(base, "plugin")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(replace_with(text, '        r = subprocess.run(["git", "-C", outillage, "cat-file"',
                              '        subprocess.run(["git", "-C", outillage, "fetch", "-q", "--depth=1", "origin", '
                              'self.commit_corpus], capture_output=True, timeout=60)\n'
                              '        r = subprocess.run(["git", "-C", outillage, "cat-file"'))
        code, _, output_text = self.run_the_judge("historique_non_declare", self.prepare("historique_non_declare"), True, base=base,
                                     options=[f"commit_corpus={commit}"])
        self.assertEqual(code, 2)
        self.assertIn("historique", output_text)

    def test_depths(self):
        """ruche-0136, with Docker: every mount Docker makes itself in a container of the judge (/proc, /dev, /sys and cgroups,
        /dev/shm, /tmp, /etc's files, masked paths) is shallower than conteneur.PROFONDEUR, from which each folder of the judge
        is given (test_one_mount_order_whatever_docker_draws), and each folder lands where it is named."""
        image = container.build_image([], os.environ.get("BEE_JUGE_RESEAU"))
        folders = [container.open_folder(os.path.join(self.workdir, "profondeur-" + n)) for n in ("a", "b")]
        r = container.Docker(container.image_id(image)).launch(
            ["cat", "/proc/self/mountinfo"], [(folders[0], "/sources", True), (folders[1], "/sortie", False)], pids=8, timeout_seconds=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        points = [line_text.split()[4] for line_text in r.stdout.decode().splitlines()]
        self.assertTrue({"/sources", "/sortie", "/tmp", "/dev/shm", "/etc/hosts"} <= set(points), points)
        self.assertLess(max(p.count("/") for p in points if p not in ("/sources", "/sortie")), container.DEPTH)
        self.assertFalse(set(points) - set(DOCKER_MOUNTS) - {"/", "/sources", "/sortie", "/tmp", "/etc/hostname", "/etc/hosts",
                                                                 "/etc/resolv.conf", "/proc/fs", "/proc/irq", "/proc/sysrq-trigger",
                                                                 "/proc/interrupts", "/proc/keys", "/proc/timer_list",
                                                                 "/proc/kcore", "/proc/latency_stats", "/proc/timer_stats",
                                                                 "/proc/sched_debug", "/proc/scsi"}
                         - {p for p in points if p.startswith("/sys/fs/cgroup/")})

    def test_machine_failure(self):
        """ruche-0136, with Docker: the container of B's build created with a runtime Docker does not have, then the one of
        B's verification that the runtime fails to start (OCI): each time the judge ends with code 2, and its juge.json says
        an error of the environment, a failure of the machine; before ruche-0136, both were refusals of B."""
        folder = os.path.join(self.workdir, "docker-en-panne")
        os.makedirs(folder)
        with open(os.path.join(folder, "docker"), "w", encoding="utf-8") as f:
            f.write(BROKEN_DOCKER.replace("DOCKER", repr(shutil.which("docker"))))
        os.chmod(os.path.join(folder, "docker"), 0o755)
        for rank, options in ((4, "--runtime bee-panne"), (8, "--entrypoint /bee-panne")):
            path, account = (os.path.join(folder, f"{n}-{rank}") for n in ("juge.json", "compte"))
            with self.subTest(rank=rank), mock.patch.dict(os.environ, {"PATH": folder + os.pathsep + os.environ["PATH"],
                                                                      "PANNE_RANG": str(rank), "PANNE_OPTIONS": options, "PANNE_COMPTE": account}):
                code, _, output_text = self.run_the_judge(f"panne-{rank}", self.prepare(f"panne-{rank}"), True, extra=["--json", path])
                self.assertEqual(code, 2, output_text)
                with open(path, encoding="utf-8") as f:
                    j = json.load(f)["judge"]
                self.assertEqual((j["code"], j["outcome"], j["machine_failure"]), (2, "environment_error", True))
                with open(account) as f:
                    self.assertEqual(f.read(), str(rank))

    def test_simulated_failure(self):
        """ruche-0136, with Docker: B's code writes a daemon's error and exits with 125, as a failing runtime would: the
        container ran to its end, so it is a refusal of B (code 1, « refus » in juge.json), never an error of the environment."""
        def simulate(text, corpus):
            text = replace_with(text, INCLUDE, INCLUDE + "#include <stdio.h>\n#include <stdlib.h>\n")
            return replace_with(text, COMPRESS_START, COMPRESS_START + f"    fputs({json.dumps(OCI)}, stderr); exit(125);\n")
        path = os.path.join(self.workdir, "panne_simulee.json")
        code, _, output_text = self.run_the_judge("panne_simulee", self.prepare("panne_simulee", simulate), True, extra=["--json", path])
        self.assertEqual(code, 1, output_text)
        with open(path, encoding="utf-8") as f:
            j = json.load(f)["judge"]
        self.assertEqual((j["code"], j["outcome"], j["machine_failure"]), (1, "refusal", False))

    def test_early_exit(self):
        code, _, output_text = self.run_the_judge("sortie_anticipee", self.prepare("sortie_anticipee", early_exit), True)
        self.assertEqual(code, 1)
        self.assertIn("REFUS", output_text)

    def test_fake_stopwatches(self):
        code, report, _ = self.run_the_judge("faux_chronos", self.prepare("faux_chronos", fake_stopwatches), True)
        self.assertEqual(code, 0)
        self.assertIn("symbole_interdit", self.types_suspects(report))
        m = report["metrics"]["debit_compression"]
        self.assertLess(m["B"]["median"], m["A"]["median"])

    def test_precomputed_table(self):
        code, _, output_text = self.run_the_judge("table_precalculee", self.prepare("table_precalculee", precomputed_table), True)
        self.assertEqual(code, 1)
        self.assertIn("REFUS", output_text)

    def test_valgrind_request(self):
        code, report, _ = self.run_the_judge("requete_valgrind", self.prepare("requete_valgrind", valgrind_request))
        self.assertEqual(code, 0)
        self.assertIn("preambule_valgrind", " ".join(s["detail"] for s in report["judge"]["suspicious_constructs"]))

    def test_fake_summary(self):
        code, report, _ = self.run_the_judge("faux_resume", self.prepare("faux_resume", fake_summary))
        self.assertEqual(code, 0)
        self.assertIn("appel_externe", self.types_suspects(report))
        m = report["instructions"]["instructions_compression"]
        self.assertGreater(m["B"], 0.99 * m["A"])

    def test_moved_workdir(self):
        code, report, _ = self.run_the_judge("travail_deplace", self.prepare("travail_deplace", moved_workdir))
        self.assertEqual(code, 0)
        self.assertEqual(report["judge"]["suspicious_constructs"], [])
        m = report["instructions"]["instructions_compression"]
        self.assertLess(m["gain"], 0.002, "le travail déplacé dans rle_borne doit rester compté")

    def test_plugin_of_the_pr(self):
        """B est faux (sortie compressée tronquée) mais apporte un greffon et un harnais qui acceptent tout."""
        source_b = self.prepare("greffon_de_la_pr", lambda t, c: replace_with(t, "    return o + 4;\n", "    return o > 8 ? o - 1 : o + 4;\n"))
        shutil.copytree(os.path.join(self.toy, "bee"), os.path.join(source_b, "bee"))
        with open(toy_file(source_b, "plugin"), "a", encoding="utf-8") as f:
            f.write(contract(source_b, "\nProjet.verifier = lambda self, a, b, e: 1\nProjet.compressee = lambda self, a, b, r, o: 0\n"))
        code, _, output_text = self.run_the_judge("greffon_de_la_pr", source_b, True)
        self.assertEqual(code, 1)
        self.assertIn("REFUS", output_text)

    def test_empty_readings(self):
        base = self.changed_base("releves_vides", "build", 'echo "construction terminée"',
                                  ': > "$sortie/desassemblage.txt"\necho "construction terminée"')
        code, report, _ = self.run_the_judge("releves_vides", self.prepare("releves_vides", valgrind_request), True, base=base)
        self.assertEqual(code, 0)
        self.assertIn("preambule_valgrind", " ".join(s["detail"] for s in report["judge"]["suspicious_constructs"]))

    def test_forgotten_object(self):
        """L'objet du projet est compilé hors de obj/ : il échapperait à l'analyse, le juge s'arrête."""
        base = self.changed_base("objet_oublie", "build", '"$sortie/obj/rle.o"', '"$sortie/rle.o"')
        code, _, output_text = self.run_the_judge("objet_oublie", self.prepare("objet_oublie"), True, base=base)
        self.assertEqual(code, 2)
        self.assertIn("sans objet", output_text)

    def test_split_tokens(self):
        code, report, _ = self.run_the_judge("jetons_scindes", self.prepare("jetons_scindes", split_tokens), True)
        self.assertEqual(code, 0)
        self.assertIn("preambule_valgrind", " ".join(s["detail"] for s in report["judge"]["suspicious_constructs"]))

    def test_distracted_plugin(self):
        """Le greffon de la base oublie de lire les sorties de B d'un scénario : erreur, jamais une acceptation."""
        base = self.changed_base("greffon_distrait", "plugin",
                                  'self.juste(a, b, e, f"{s}/")', 'self.juste(a, a, e, f"{s}/")')
        code, _, output_text = self.run_the_judge("greffon_distrait", self.prepare("greffon_distrait"), True, base=base)
        self.assertEqual(code, 2)
        self.assertIn("aucune sortie de B", output_text)

    def test_forbidden_call(self):
        """Revue adverse n° 2 : getenv est signalé par son nom, quel que soit l'espace de noms déclaré."""
        code, report, _ = self.run_the_judge("appel_interdit", self.prepare("appel_interdit", call_laundered_by_prefix), True)
        self.assertEqual(code, 0)
        self.assertIn("getenv", " ".join(s["detail"] for s in report["judge"]["suspicious_constructs"]))

    def test_seeded_bytes(self):
        code, report, _ = self.run_the_judge("seeded_bytes", self.prepare("seeded_bytes", lambda t, c: t + asm_bytes("48b80f05909090909090")), True)
        self.assertEqual(code, 0)
        self.assertIn("octets", self.types_suspects(report))

    def test_same_conditions(self):
        """ruche-0037: B records everything it can observe of its process at its first call: the same digests in every
        mode (counters aside, the inputs differing; EXCEPTIONS_INSTRUCTIONS aside under the instruction counter)."""
        code, containers = self.spied_judge_run(self.prepare("memes_conditions", spy))
        self.assertEqual(code, 0)
        surveys = {}
        for entry, error in containers:
            _, options, line_text = entry.splitlines()
            surveys.setdefault((options.split()[1] == "1", line_text.split("\t")[0]), []).append(spy_reading(error))
        self.assertEqual(sorted(surveys), [(False, "compression"), (False, "decompression"), (False, "verifier"),
                                           (True, "compression"), (True, "decompression")])
        natives = [r for (valgrind, _), list_of in sorted(surveys.items()) if not valgrind for r in list_of]
        self.assertEqual(len(natives), 6)  # verification (2 sides), 2 repetitions × 2 scenarios
        for r in natives:
            self.assertEqual(fingerprints(r), fingerprints(natives[0]))
        for r in surveys[(True, "compression")] + surveys[(True, "decompression")]:
            self.assertEqual(fingerprints(r, EXCEPTIONS_INSTRUCTIONS), fingerprints(natives[0], EXCEPTIONS_INSTRUCTIONS))

    def test_same_mounts(self):
        """ruche-0117 (points 3, 6 and 7): every container of a side gets the same inputs; B, run at different positions (orders
        drawn so that each scenario changes place), in both variant passes (A first, then B first), at both repetitions and in
        every mode (verification, timed, instruction count), sees the same thing, mount by mount: mount lines, inode, device,
        links, mode, owner, size, access and modification times, directory order, statfs; the ages of its change and birth
        times within AGE_MAX_MS; each tmpfs's f_fsid the same or drawn anew; RESTE aside (outside the judge's mounts). The
        8 MiB each container leaves in its outputs are seen by none of the others."""
        base = toy_with_four_scenarios(os.path.join(self.workdir, "base-memes-montures"), self.toy)
        with open(toy_file(base, "plugin"), "a", encoding="utf-8") as f:
            f.write(contract(base, SAME_INPUTS))
        seed = next(g for g in (f"{i:02x}" * 16 for i in range(256)) if (lambda t: (lambda o, p: all(
            o.index(s) != p.index(s) for s in FOUR_SCENARIOS))(t.sample(list(FOUR_SCENARIOS), 4), t.sample(list(FOUR_SCENARIOS), 4)))(
            random.Random(bytes.fromhex(g))))
        output_text = io.StringIO()
        code, containers = self.spied_judge_run(self.prepare("memes_montures", mounts_spy), base,
                                               ["--order-seed", seed], output_text)
        self.assertEqual(code, 0)
        unfolding = json.loads(output_text.getvalue())["judge"]["scenarios"]["steps"]
        self.assertEqual([(e["step"], e["variants"]) for e in unfolding], [("measurement", "AB"), ("measurement", "BA"), ("instructions", "AB")])
        by_side = {}
        for entry, error in containers:
            survey = mounts_reading(error)
            if entry.splitlines()[1].split()[1] == "1":
                survey = {k: v for k, v in survey.items() if k not in REST_INSTRUCTIONS}
            now_instant = float(survey.pop("maintenant"))
            for key in [k for k in survey if k.startswith("temps:") and not k[6:].startswith(JUDGE_MOUNTS)]:
                survey["age" + key] = " ".join(str(round(1000 * (now_instant - float(x)))) for x in survey.pop(key).split())
            by_side.setdefault("f" if "stat:/entrees/#0/#0" in survey else "z", []).append(survey)
        self.assertEqual({c: len(l) for c, l in by_side.items()}, {"f": 6, "z": 6})  # verification, 2 × 2 timed, instructions
        for quoted_side, list_of in by_side.items():
            self.assertIn(f"stat:/entrees/#{'0' if quoted_side == 'f' else '2'}/#3", list_of[0])  # four inputs on the side's folder
            for key in sorted(set().union(*list_of)):
                values_of = [r.get(key) for r in list_of if key in r or key not in REST_INSTRUCTIONS]
                with self.subTest(quoted_side=quoted_side, key=key):
                    if key in REST or key.startswith(REST_PREFIXES):
                        continue
                    if key.startswith(("age:", "agetemps:")):
                        for ages in zip(*(map(int, v.split()) for v in values_of)):
                            self.assertLessEqual(max(ages) - min(ages), AGE_MAX_MS, values_of)
                    elif key.startswith("fsid:"):
                        self.assertIn(len(set(values_of)), (1, len(values_of)), values_of)
                    else:
                        self.assertEqual(len(set(values_of)), 1, values_of)

    def run_modes(self, source_b, modes):
        """B built and run by the judge's own containers on one /entrees (the f side of a repetition), once per mode:
        [(mode, valgrind)]. Returns its records, in order."""
        projet, travail = judge.load_plugin(self.toy, {})[0], tempfile.mkdtemp(dir=self.workdir)
        os.chmod(travail, 0o755)
        docker = container.Docker(container.build_image(projet.PAQUETS, os.environ.get("BEE_JUGE_RESEAU")))
        sources = judge.copy_sources(source_b, os.path.join(travail, "sources-B"), projet.SOURCES, projet.SOURCES_REQUISES)
        tools = judge.copy_tooling(self.toy, self.toy, os.path.join(travail, "outillage"), projet)
        judge.build(docker, projet, sources, tools, os.path.join(travail, "construction-B"), "B", travail)
        run = container.Execution(docker, container.compile_stopwatch(docker, travail),
                                        {"B": judge.variant(os.path.join(travail, "construction-B"), os.path.join(travail, "variante-B"))},
                                        travail)
        entrees = [e for e in projet.repetition(random.Random(1), projet.corpus(self.toy)) if e.cote == "f"]
        folder = judge.prepare(travail, "", judge.rename(random.Random(1), entrees)[0], ("f", "z"))["f"]
        errors, launch = [], docker.launch

        def spy_on(*a, **k):
            r = launch(*a, **k)
            errors.append(r.stderr.decode("utf-8", "replace"))
            return r
        docker.launch = spy_on
        for mode, valgrind in modes:
            command = (judge.VALGRIND if valgrind else []) + [container.HARNESS, mode, "/entrees", "/sorties"]
            run.launch("B", folder, judge.outputs_of(travail, "", ("f",))["f"], [(mode, command)], valgrind=valgrind, timeout_seconds=600)
        return [spy_reading(e) for e in errors]

    def test_same_counters(self):
        """ruche-0037: on the same /entrees, B observes the same thing in every mode, the counters it can read about itself
        included (exactly, or within BRUIT); under the instruction counter, EXCEPTIONS_INSTRUCTIONS and the counters aside."""
        modes = [("verifier", False), ("compression", False), ("decompression", False), ("compression", True)]
        surveys = self.run_modes(self.prepare("memes_compteurs", spy), modes)
        natives, under_valgrind = surveys[:3], surveys[3]
        values_of = [counters(r) for r in natives]
        for r, c in zip(natives[1:], values_of[1:]):
            self.assertEqual(fingerprints(r), fingerprints(natives[0]))
            self.assertEqual({k: v for k, v in c.items() if k not in NOISE}, {k: v for k, v in values_of[0].items() if k not in NOISE})
        for nom, gap in NOISE.items():
            self.assertLessEqual(max(c[nom] for c in values_of) - min(c[nom] for c in values_of), gap, nom)
        self.assertEqual(fingerprints(under_valgrind, EXCEPTIONS_INSTRUCTIONS), fingerprints(natives[0], EXCEPTIONS_INSTRUCTIONS))

    def base_that_states_the_mode(self, nom):
        """A copy of the toy whose harness tells the library the mode (int rle_mesure): the case mixing must catch."""
        base = os.path.join(self.workdir, "base-" + nom)
        shutil.copytree(self.toy, base, ignore=shutil.ignore_patterns("__pycache__"))
        path = toy_file(base, "harness")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text = replace_with(text, "static char entrees[256], sorties[256];\n", "static char entrees[256], sorties[256];\nint rle_mesure = 0;\n")
        text = replace_with(text, "    explicit_bzero(mode, sizeof(mode));\n",
                          '    rle_mesure = strcmp(mode, "verifier") != 0;\n    explicit_bzero(mode, sizeof(mode));\n')
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return base

    def test_wrong_output_timed(self):
        """ruche-0037: B is right whenever it is verified, and wrong when timed on inputs other than the corpus's (the
        base's harness is made to tell it the mode): the verification inputs mixed into the timed inputs refuse it."""
        code, report, output_text = self.run_the_judge("sortie_fausse_chronometree",
                                           self.prepare("sortie_fausse_chronometree", wrong_output_timed), True,
                                           base=self.base_that_states_the_mode("sortie_fausse_chronometree"))
        self.assertEqual(code, 1, output_text)
        self.assertIn("REFUS", output_text)
        self.assertIn("compression/c/e", output_text)  # a timed output of a mixed-in input, not the verification step

    def test_changing_output_timed(self):
        """ruche-0037: with outputs allowed to differ from the base's, B gives a valid but different output when timed:
        its output of a mixed-in input differs from its own in verification, refused."""
        source_b = self.prepare("sortie_changeante_chronometree", lambda t, c: replace_with(
            replace_with(t, INCLUDE, INCLUDE + "extern int rle_mesure;\n"), "        if (plage >= 3) {", "        if (plage >= 3 && !rle_mesure) {"))
        code, _, output_text = self.run_the_judge("sortie_changeante_chronometree", source_b, True, options=["sortie_compressee=peut_changer"],
                                     base=self.base_that_states_the_mode("sortie_changeante_chronometree"))
        self.assertEqual(code, 1, output_text)
        self.assertIn("différente de sa sortie en vérification", output_text)

    def test_side_without_shuffle(self):
        """ruche-0037: a measured side without verification inputs to mix in is an error of the plugin, never a pass."""
        base = self.changed_base("cote_sans_melange", "plugin", "return self.entrees(fichiers, self.flux(rng, fichiers))",
                                  "return self.entrees(fichiers, [])")
        code, _, output_text = self.run_the_judge("cote_sans_melange", self.prepare("cote_sans_melange"), True, base=base)
        self.assertEqual(code, 2, output_text)
        self.assertIn("aucune entrée de vérification", output_text)

    def test_instructions_without_shuffle(self):
        """ruche-0037: an instruction-count scenario that got no verification input (none within the prefix) is flagged."""
        code, report, output_text = self.run_the_judge("instructions_sans_melange", self.prepare("instructions_sans_melange"),
                                           extra=["--instructions-prefix", "1"])
        self.assertEqual(code, 0, output_text)
        self.assertEqual(report["judge"]["verification"]["instructions_without_mixing"], ["decompression"])

    def test_symbolic_link(self):
        source_b = self.prepare("lien_symbolique")
        os.remove(os.path.join(source_b, "rle.c"))
        os.symlink(os.path.join(self.toy, "rle.c"), os.path.join(source_b, "rle.c"))
        code, _, output_text = self.run_the_judge("lien_symbolique", source_b, True)
        self.assertEqual(code, 1)
        self.assertIn("lien symbolique", output_text)

    def bounded_judge(self, nom, source_b, *options):
        """judge.py against the toy base, with the options given (ruche-0038); returns (code, report, journal, seconds)."""
        command = [sys.executable, os.path.join(HERE, "judge.py"), "--tooling", self.toy, "--source-a", self.toy, "--source-b", source_b,
                    "--repetitions", "2", "--warmup", "0", "--no-instructions", *options]
        command += ["--build-network", os.environ["BEE_JUGE_RESEAU"]] if os.environ.get("BEE_JUGE_RESEAU") else []
        beginning = time.monotonic()
        r = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        print(f"\n[{nom}] code {r.returncode} : {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}", file=sys.stderr)
        return r.returncode, json.loads(r.stdout) if r.returncode == 0 else None, r.stderr, time.monotonic() - beginning

    def test_job_report(self):
        """ruche-0038: juge.json names the commits judged and the image's id, lists SUSPECTES_MAX suspicious constructs and
        counts the rest; its figures are those report.py publishes, and a report changed afterwards is refused. ruche-0117: the
        most serious first, a forbidden call and a global symbol of 2,000 characters added after 125 pragmas, each kind counted,
        each detail cut to DETAIL_MAX; report.py --verify wants the code 0 and the pull request's commits."""
        lines = "".join(f"#pragma rle_marque_{i:03d}\n" for i in range(judge.SUSPICIOUS_MAX + 25))
        lines += '#include <stdlib.h>\nchar *rle_env(void) { return getenv("BEE"); }\nint bee_' + "x" * 2000 + " = 1;\n"
        path, base, head = os.path.join(self.workdir, "rapport_du_job.json"), "4" * 40, "5" * 40
        code, report_, log_, _ = self.bounded_judge("rapport_du_job", self.prepare("rapport_du_job", lambda t, c: t + lines),
                                                       "--base", base, "--head", head, "--json", path)
        self.assertEqual(code, 0, log_)
        j = report_["judge"]
        self.assertEqual((j["base"], j["head"], len(j["suspicious_constructs"]), j["suspicious_constructs_omitted"]),
                         (base, head, judge.SUSPICIOUS_MAX, 28))
        self.assertEqual([s["type"] for s in j["suspicious_constructs"][:3]], ["appel_interdit", "symbole_defini", "source"])
        self.assertEqual(j["suspicious_constructs_by_type"], {"appel_interdit": 1, "source": 126, "symbole_defini": 1})
        self.assertLessEqual(max(len(s["detail"]) for s in j["suspicious_constructs"]), analysis.DETAIL_MAX)
        self.assertEqual(log_.count("suspicious construct:"), judge.SUSPICIOUS_MAX)
        self.assertRegex(j["image_id"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(j["image_id"], container.image_id(j["image"]))
        published_ones = report.digits(report.lire(path))
        self.assertEqual((published_ones["suspects"], published_ones["outputs_compared"], published_ones["base"], published_ones["head"]),
                         (str(judge.SUSPICIOUS_MAX + 28), str(j["verification"]["outputs_compared"]), base, head))
        published_ones = report.publish(path, "0")
        self.assertEqual(report.verifier(path, published_ones, base, head), report_)
        for others in ((head, base), (base, "6" * 40)):
            with self.assertRaises(report.Gap):
                report.verifier(path, published_ones, *others)
        j["suspicious_constructs"].pop()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report_, f, ensure_ascii=False, indent=2)
        with self.assertRaises(report.Gap):
            report.verifier(path, published_ones, base, head)

    def test_endless_writing(self):
        """ruche-0038: a judged code that writes without end is stopped at the file size bound of every container (SIGXFSZ):
        a refusal, in bounded time."""
        def endless(text, corpus):
            text = replace_with(text, INCLUDE, INCLUDE + "#include <stdio.h>\n")
            return replace_with(text, COMPRESS_START, COMPRESS_START +
                             '    { static unsigned char rle_bloc[1 << 16]; FILE *rle_f = fopen("/sorties/rle_sans_fin", "wb");\n'
                             "      while (rle_f) fwrite(rle_bloc, 1, sizeof rle_bloc, rle_f); }\n")
        code, _, log_, duration = self.bounded_judge("ecriture_sans_fin", self.prepare("ecriture_sans_fin", endless))
        self.assertEqual(code, 1, log_)
        self.assertIn("signal 25", log_)
        self.assertLess(duration, 600)

    def test_full_disk(self):
        """ruche-0038: a judged code that fills the work folder (a small tmpfs here, as juge.yml mounts a larger one): a
        refusal, in bounded time, and the folder left empty."""
        folder, sudo = os.path.join(self.workdir, "tmpfs-borne"), ([] if os.geteuid() == 0 else ["sudo", "-n"])
        os.makedirs(folder)
        options = f"size=96m,nr_inodes=4096,mode=0755,nosuid,nodev,uid={os.getuid()},gid={os.getgid()}"
        if subprocess.run(sudo + ["mount", "-t", "tmpfs", "-o", options, "tmpfs", folder], capture_output=True).returncode != 0:
            self.skipTest("mounting a tmpfs needs root or sudo without a password")
        self.addCleanup(subprocess.run, sudo + ["umount", folder], capture_output=True)

        def fill_in(text, corpus):  # files of 32 MiB, 2 GiB at most, until the folder is full
            text = replace_with(text, INCLUDE, INCLUDE + "#include <stdio.h>\n")
            return replace_with(text, COMPRESS_START, COMPRESS_START +
                             "    { static unsigned char rle_bloc[1 << 16]; static int rle_fait; char rle_p[64]; int k, j = 512;\n"
                             "      for (k = 0; !rle_fait && k < 64 && j == 512; k++) {\n"
                             '        FILE *rle_f; snprintf(rle_p, sizeof rle_p, "/sorties/rle_plein_%d", k);\n'
                             '        if (!(rle_f = fopen(rle_p, "wb"))) break;\n'
                             "        for (j = 0; j < 512 && fwrite(rle_bloc, 1, sizeof rle_bloc, rle_f) == sizeof rle_bloc; j++) ;\n"
                             "        if (fclose(rle_f) != 0) j = 0; }\n"
                             "      rle_fait = 1; }\n")
        code, _, log_, duration = self.bounded_judge("disque_plein", self.prepare("disque_plein", fill_in), "--workdir", folder)
        self.assertEqual(code, 1, log_)
        self.assertLess(duration, 600)
        self.assertEqual(os.listdir(folder), [])


class TestJudgeAgainstVariantsEnglish(TestJudgeAgainstVariants):
    """ruche-0148 (J2): every meta-test again, the base's plugin in the English contract (the toy's twin, bee/judge/project.py)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.toy = english_toy(os.path.join(cls.workdir, "toy"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
