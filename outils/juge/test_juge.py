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
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

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


def releves(nm=NM_A, sections=SECTIONS_A, desassemblage=DESASSEMBLAGE_A):
    return {"symboles": nm, "sections": sections, "desassemblage": desassemblage}


class TestAnalyse(unittest.TestCase):
    def test_base_contre_elle_meme(self):
        self.assertEqual(analyse.analyser(releves(), releves(), prefixes=("rle_",)), [])

    def test_prefixes_et_permis_du_greffon(self):
        b = releves(nm=NM_A + "/s/obj/rle.o: rle_aide T 0000000000000300 0000000000000010\n/s/obj/rle.o: qsort U\n")
        self.assertEqual([s["type"] for s in analyse.analyser(releves(), b, prefixes=("rle_",))], ["appel_externe"])
        self.assertEqual(analyse.analyser(releves(), b, prefixes=("rle_",), permis=("qsort",)), [])
        # Sans espace de noms, une nouvelle fonction globale est suspecte (elle pourrait en remplacer une autre).
        self.assertEqual(sorted(s["type"] for s in analyse.analyser(releves(), b, permis=("qsort",))), ["symbole_defini"])

    def test_symbole_qui_remplace_la_libc(self):
        b = releves(nm=NM_A + "/s/obj/rle.o: clock_gettime T 0000000000000300 0000000000000010\n"
                             "/s/obj/rle.o: memcmp T 0000000000000400 0000000000000010\n")
        self.assertEqual(sorted(s["type"] for s in analyse.analyser(releves(), b, prefixes=("rle_",))),
                         ["symbole_defini", "symbole_interdit"])

    def test_jamais_permis_malgre_prefixe_ou_permis(self):
        """Revue adverse n° 2 : un préfixe « ge » ou une entrée PERMIS ne blanchit pas getenv."""
        b = releves(nm=NM_A + "/s/obj/rle.o: getenv U\n/s/obj/rle.o: syscall U\n")
        types = [s["type"] for s in analyse.analyser(releves(), b, prefixes=("rle_", "ge", "sy"), permis=("getenv",))]
        self.assertEqual(types, ["appel_interdit", "appel_interdit"])
        a = releves(nm=NM_A + "/s/obj/rle.o: getenv U\n")
        self.assertEqual([s["type"] for s in analyse.analyser(a, b, prefixes=("rle_",))], ["appel_interdit"])  # syscall seul

    def test_continuation_de_ligne(self):
        diff = "+++ b/rle.c\n+    __as\\\n+m volatile(\"\");\n+    int x = 1;\n"
        self.assertEqual(analyse.lignes_ajoutees(diff), ["    __as" + "m volatile(\"\");", "    int x = 1;"])
        self.assertEqual(len(analyse.analyser(releves(), releves(), diff, prefixes=("rle_",))), 1)

    def test_constructeur_et_instructions(self):
        b = releves(sections=SECTIONS_A + "  1 .init_array   00000008  0000000000000000  0000000000000000  00001140  2**3\n",
                    desassemblage=DESASSEMBLAGE_A + "   9:\tsyscall\n  10:\trol    $0x3,%rdi\n")
        self.assertEqual(sorted(s["type"] for s in analyse.analyser(releves(), b, prefixes=("rle_",))),
                         ["instruction", "instruction", "section"])

    def test_source(self):
        diff = "+++ b/rle.c\n+    __asm__ volatile(\"\");\n+#include <time.h>\n+    int ordinaire = 1;\n"
        self.assertEqual(len(analyse.analyser(releves(), releves(), diff, prefixes=("rle_",))), 2)


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

    def test_workflow_epingle_sa_version(self):
        """Le workflow réutilisable lit le juge commun à sa propre étiquette, juge-v<VERSION_COMMUNE>."""
        chemin = os.path.join(os.path.dirname(os.path.dirname(ICI)), ".github", "workflows", "juge.yml")
        with open(chemin, encoding="utf-8") as f:
            texte = f.read()
        self.assertIn(f"JUGE_COMMUN_REF: juge-v{juge.VERSION_COMMUNE}\n", texte)


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

    def juger(self, nom, source_b, sans_instructions=False, base=JOUET):
        commande = [sys.executable, os.path.join(ICI, "juge.py"), "--outillage", base, "--source-a", base,
                    "--source-b", source_b, "--repetitions", "2", "--chauffe", "0"]
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

    def test_lien_symbolique(self):
        source_b = self.preparer("lien_symbolique")
        os.remove(os.path.join(source_b, "rle.c"))
        os.symlink(os.path.join(JOUET, "rle.c"), os.path.join(source_b, "rle.c"))
        code, _, sortie = self.juger("lien_symbolique", source_b, True)
        self.assertEqual(code, 1)
        self.assertIn("lien symbolique", sortie)


if __name__ == "__main__":
    unittest.main(verbosity=2)
