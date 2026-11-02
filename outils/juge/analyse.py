#!/usr/bin/env python3
"""Juge commun Bee : analyse statique des objets compilés du projet jugé.

Le juge vérifie de l'extérieur que les SORTIES du projet sont justes. Ce qu'il ne peut pas voir de
l'extérieur, c'est un code qui s'en prend à la mesure elle-même : appels système directs, lancement
d'autres programmes, requêtes client de Valgrind (qui suspendent le décompte d'instructions), lecture de
l'horloge, constructeurs exécutés avant le harnais, symboles qui remplacent ceux du harnais ou de la libc
(memcmp, clock_gettime…). Ces constructions n'ont rien à faire dans une bibliothèque de calcul (compression,
analyse, codage) ; elles se voient dans les objets compilés. Ce module compare les relevés de la PR (B)
à ceux de la base (A), produits dans le conteneur par le script de construction du greffon (nm, objdump),
et liste ce que B ajoute. Le greffon fournit l'espace de noms du projet (PREFIXES) et les fonctions
externes qu'il peut appeler en plus de la liste commune (PERMIS).

Une construction suspecte n'est pas une faute : elle retire seulement la confiance dans les mesures, et
le registre exige alors la relecture d'un gardien (R3). This module reads only text and bytes; it executes nothing.
"""

import re
import struct
from collections import Counter

# Fonctions qui servent à tromper la mesure (horloge, processus, environnement, signaux, appels système), pas à
# compresser ni à analyser : jamais permises, et signalées par leur nom exact AVANT toute exemption par l'espace de
# noms du projet ou par la liste PERMIS du greffon (revue adverse n° 2 du 28/10 : un préfixe « ge » couvrait getenv).
JAMAIS_PERMIS = frozenset({
    "syscall", "clock_gettime", "clock_getres", "gettimeofday", "time", "times", "getrusage", "fork", "vfork",
    "clone", "execve", "execv", "execvp", "execl", "execlp", "system", "popen", "posix_spawn", "dlopen", "dlsym",
    "getenv", "secure_getenv", "ptrace", "prctl", "signal", "sigaction", "raise", "kill", "alarm", "setitimer",
    "sched_setaffinity", "mprotect",
})

# Fonctions de la libc qu'une bibliothèque de calcul peut appeler sans rien changer à la mesure : mémoire et chaînes.
INDEFINIS_PERMIS = frozenset({
    "memcpy", "memmove", "memset", "memcmp", "malloc", "calloc", "realloc", "free", "strlen",
    "abort", "__assert_fail", "__stack_chk_fail", "__memcpy_chk", "__memmove_chk", "__memset_chk",
    "_GLOBAL_OFFSET_TABLE_",
})

# Instructions sans usage dans une bibliothèque de calcul, mais utiles pour tromper une mesure ou en sortir.
MNEMONIQUES_SUSPECTS = {
    "syscall": "appel système direct",
    "sysenter": "appel système direct",
    "int": "interruption logicielle (appel système 32 bits ou point d'arrêt)",
    "int3": "point d'arrêt",
    "rdtsc": "lecture du compteur de cycles",
    "rdtscp": "lecture du compteur de cycles",
    "rdpmc": "reading a performance counter",
    "rdpid": "lecture de l'identifiant de processeur",
    "rdrand": "nombre aléatoire matériel",
    "rdseed": "nombre aléatoire matériel",
    "cpuid": "identification du processeur (détection d'un émulateur ou de Valgrind)",
    "xgetbv": "lecture d'état du processeur",
    "(bad)": "bytes the disassembler cannot decode",
    ".byte": "bytes the disassembler cannot decode",
    "preambule_valgrind": "préambule de requête client Valgrind (suspend le décompte d'instructions)",
    "segment_wx": "memory both writable and executable in the linked program",
    "pile_executable": "executable stack in the linked program",
}
# Préambule des requêtes client de Valgrind sur x86-64 : rol $3, $13, $61, $51 sur %rdi.
PREAMBULE_VALGRIND = re.compile(r"\brol\s+\$0x(?:3|d|3d|33),%rdi\b")
SEQUENCES = {nom: re.compile(b"(?=(" + motif + b"))") for nom, motif in (
    ("syscall", rb"\x0f\x05"), ("sysenter", rb"\x0f\x34"), ("int", rb"\xcd\x80"), ("rdtsc", rb"\x0f\x31"),
    ("rdtscp", rb"\x0f\x01\xf9"), ("rdpmc", rb"\x0f\x33"), ("cpuid", rb"\x0f\xa2"), ("xgetbv", rb"\x0f\x01\xd0"),
    ("rdrand", rb"\x0f\xc7[\xf0-\xf7]"), ("rdseed", rb"\x0f\xc7[\xf8-\xff]"), ("rdpid", rb"\xf3[\x40-\x4f]?\x0f\xc7[\xf8-\xff]"),
    ("preambule_valgrind", rb"\x48\xc1\xc7\x03\x48\xc1\xc7\x0d\x48\xc1\xc7\x3d\x48\xc1\xc7\x33"))}

DETAIL_MAX = 300  # characters of a detail: names, paths and extracts come from the judged code (ruche-0117)
SECTIONS_PERMISES = re.compile(
    r"^\.(?:text(?:\.(?:unlikely|hot|cold)(?:\..*)?)?|text\.[A-Za-z0-9_]+|rodata(?:\..*)?|data(?:\..*)?|bss(?:\..*)?"
    r"|debug_.*|note(?:\..*)?|comment|eh_frame|group|rela?\..*)$")
SECTIONS_INTERDITES = re.compile(r"^\.(?:init_array|fini_array|preinit_array|ctors|dtors|init|fini|text\.startup|text\.exit)(?:\..*)?$")

# Judged files, read whole (each file of B against the same file of A): words with no business in the project.
MOTS_SOURCE = [
    (re.compile(r"\b(?:__asm__|__asm|asm)\b"), "assembleur en ligne"),
    (re.compile(r"__attribute(?:__)?\s*\(\s*\((?:[^()]|\([^()]*\))*?(?:constructor|destructor|ifunc|section|weak|alias)"),
     "attribut de lien ou d'initialisation"),
    (re.compile(r"(?:#|%:)\s*(?:include(?:_next)?|import)\s*(?:[<\"](?:sys/|unistd\.h|dlfcn\.h|signal\.h|time\.h|sched\.h|pthread\.h"
                r"|fcntl\.h|cpuid\.h|valgrind/)|[^\s<\"])"),
     "en-tête système (processus, horloge, signaux, Valgrind)"),
    (re.compile(r"\b(?:getenv|RUNNING_ON_VALGRIND|VALGRIND_\w+|CACHEGRIND_\w+|CALLGRIND_\w+|dlsym|dlopen)\b"),
     "détection de l'environnement de mesure"),
    (re.compile(r"\b(?:__builtin_ia32_(?:rdtscp?|rdpmc|rdrand\w*|rdseed\w*|rdpid|xgetbv)|__?rdtscp?|__rdpmc|_xgetbv|_rd(?:rand|seed)\w*"
                r"|__cpuid\w*|__get_cpuid\w*|__builtin_cpu_(?:supports|init|is))\b"),
     "lecture du processeur ou de l'horloge"),
    # Ce balayage du texte n'est qu'un filet : la concaténation de jetons (« a##sm ») ou _Pragma peuvent
    # former un mot interdit que les motifs ci-dessus ne voient pas (revue adverse du 28/10). L'analyse
    # des objets, elle, voit le code produit.
    (re.compile(r"##|%:%:|\b_Pragma\b|(?:#|%:)\s*pragma\b"), "concaténation de jetons ou pragma (peut former un mot interdit)"),
]


def symboles(texte):
    """nm -P -A : « fichier.o: nom type valeur [taille] ». Renvoie {nom: (type, fichier)}."""
    resultat = {}
    for ligne in texte.splitlines():
        if ": " not in ligne:
            continue
        fichier, reste = ligne.split(": ", 1)
        morceaux = reste.split()
        if len(morceaux) < 2:
            continue
        nom, type_ = morceaux[0], morceaux[1]
        fichier = fichier.rsplit("/", 1)[-1]
        resultat.setdefault((nom, type_), fichier)
    return resultat


def sections(texte):
    """objdump -h : noms de section par fichier."""
    noms = set()
    for ligne in texte.splitlines():
        morceaux = ligne.split()
        if len(morceaux) >= 2 and morceaux[0].isdigit() and morceaux[1].startswith("."):
            noms.add(morceaux[1])
    return noms


def mnemoniques(texte):
    """objdump -d --no-show-raw-insn : suspicious mnemonics among the words of each instruction, « (bad) », Valgrind preamble."""
    comptes = {}
    for ligne in texte.splitlines():
        if "\t" not in ligne:
            continue
        instruction = ligne.split("\t", 1)[1].strip()
        if not instruction:
            continue
        for mot in re.sub(r"<[^>]*>|#.*", " ", instruction).replace(",", " ").split():
            if mot in MNEMONIQUES_SUSPECTS:
                comptes[mot] = comptes.get(mot, 0) + 1
        if PREAMBULE_VALGRIND.search(instruction):
            comptes["preambule_valgrind"] = comptes.get("preambule_valgrind", 0) + 1
    return comptes


def octets_executables(donnees):
    """Executable bytes of an x86-64 ELF file read from its headers: an object's sections marked executable or named
    .text*, a program's executable segments and memory flags. ValueError if any of it cannot be read."""
    if donnees[:7] != b"\x7fELF\x02\x01\x01" or struct.unpack_from("<H", donnees, 18)[0] != 62:
        raise ValueError("not an x86-64 ELF file")
    genre_fichier, = struct.unpack_from("<H", donnees, 16)
    ph, sh = struct.unpack_from("<QQ", donnees, 32)
    ph_taille, ph_nombre, sh_taille, sh_nombre, sh_noms = struct.unpack_from("<HHHHH", donnees, 54)

    def tranche(debut, taille):
        if debut + taille > len(donnees):
            raise ValueError("header or contents beyond the end of the file")
        return donnees[debut:debut + taille]
    morceaux, drapeaux = [], []
    if genre_fichier == 1:  # relocatable object: its sections
        if sh_nombre == 0 or sh_noms >= sh_nombre or sh_taille < 64:
            raise ValueError("unreadable section table")
        noms = struct.unpack_from("<IIQQQQ", tranche(sh + sh_noms * sh_taille, 64))[4]
        for i in range(sh_nombre):
            nom, genre, attributs, _, debut, taille = struct.unpack_from("<IIQQQQ", tranche(sh + i * sh_taille, 64))
            if genre != 8 and (attributs & 4 or donnees[noms + nom:noms + nom + 5] == b".text"):
                if attributs & 0x800:
                    raise ValueError("compressed executable section")
                morceaux.append(tranche(debut, taille))
    else:  # linked program: what is mapped at run time
        if ph_nombre == 0 or ph_taille < 56:
            raise ValueError("unreadable program header table")
        pile = None
        for i in range(ph_nombre):
            genre, attributs, debut, _, _, taille = struct.unpack_from("<IIQQQQ", tranche(ph + i * ph_taille, 56))
            if genre == 1 and attributs & 1:
                morceaux.append(tranche(debut, taille))
                drapeaux += ["segment_wx"] if attributs & 2 else []
            pile = attributs if genre == 0x6474E551 else pile
        if pile is None or pile & 1:
            drapeaux.append("pile_executable")
    return morceaux, drapeaux


def occurrences(fichiers):
    """Hits of SEQUENCES and memory flags in [(name, ELF bytes)], keyed by (file, name, bytes around); unreadable files."""
    comptes, illisibles = Counter(), []
    for nom, donnees in fichiers:
        try:
            morceaux, drapeaux = octets_executables(donnees)
        except (ValueError, struct.error) as e:
            illisibles.append(f"{nom}: executable bytes unreadable ({e}): analysis incomplete")
            continue
        comptes.update((nom, d, b"") for d in drapeaux)
        for mot, motif in SEQUENCES.items():
            comptes.update((nom, mot, m[max(0, t.start() - 6):t.end(1) + 6]) for m in morceaux for t in motif.finditer(m))
    return comptes, illisibles


def analyser(releves_a, releves_b, textes_a, textes_b, prefixes=(), permis=()):
    """releves_* : {"symboles": texte nm, "sections": texte objdump -h, "desassemblage": texte objdump -d}.
    Also "objets" and "programme": [(name, ELF bytes)]; textes_*: the judged files of A and B, {path: text}.

    prefixes : espace de noms du projet (noms qu'il définit et appelle entre ses fichiers) ;
    permis   : fonctions externes permises en plus d'INDEFINIS_PERMIS.
    Renvoie la liste des constructions suspectes que B ajoute par rapport à A (liste de dicts), chaque détail coupé à DETAIL_MAX."""
    prefixes = tuple(prefixes)
    tous_permis = INDEFINIS_PERMIS | frozenset(permis)
    suspects = []
    sym_a, sym_b = symboles(releves_a["symboles"]), symboles(releves_b["symboles"])
    definis_a = {nom for (nom, t) in sym_a if t not in "Uuvw" and t.isupper()}
    indefinis_a = {nom for (nom, t) in sym_a if t in ("U", "w", "v")}
    for (nom, t), fichier in sorted(sym_b.items()):
        if nom in JAMAIS_PERMIS and (nom, t) not in sym_a:
            suspects.append({"type": "appel_interdit" if t in ("U", "w", "v") else "symbole_interdit",
                             "detail": f"{nom} ({fichier}) : fonction qui sert à tromper la mesure (jamais permise)"})
        elif t in ("i", "u") and (nom, t) not in sym_a:
            suspects.append({"type": "symbole", "detail": f"{nom} ({fichier}) : fonction indirecte ou symbole unique (type {t})"})
        elif t in ("U", "w", "v"):
            if nom not in tous_permis and nom not in indefinis_a and not (prefixes and nom.startswith(prefixes)):
                suspects.append({"type": "appel_externe", "detail": f"{nom} ({fichier}) : fonction externe hors de la liste permise"})
        elif t.isupper() and nom not in definis_a and not (prefixes and nom.startswith(prefixes)):
            suspects.append({"type": "symbole_defini", "detail": f"{nom} ({fichier}) : symbole global hors de l'espace de noms du projet "
                                                                 "(il pourrait remplacer une fonction du harnais ou de la libc)"})
    sec_a, sec_b = sections(releves_a["sections"]), sections(releves_b["sections"])
    for nom in sorted(sec_b - sec_a):
        if SECTIONS_INTERDITES.match(nom) or not SECTIONS_PERMISES.match(nom):
            suspects.append({"type": "section", "detail": f"{nom} : section exécutée avant le programme ou inhabituelle"})
    mn_a, mn_b = mnemoniques(releves_a["desassemblage"]), mnemoniques(releves_b["desassemblage"])
    for mot, n in sorted(mn_b.items()):
        if n > mn_a.get(mot, 0):
            raison = "préambule de requête client Valgrind (suspend le décompte d'instructions)" if mot == "preambule_valgrind" \
                else MNEMONIQUES_SUSPECTS[mot]
            suspects.append({"type": "instruction", "detail": f"{mot} : {n} occurrence(s) contre {mn_a.get(mot, 0)} dans la base ({raison})"})
    for releve, ou in (("objets", "the objects' executable sections"), ("programme", "the linked program's executable segments")):
        (oc_a, illisibles_a), (oc_b, illisibles_b) = occurrences(releves_a[releve]), occurrences(releves_b[releve])
        suspects += [{"type": "analyse_incomplete", "detail": d} for d in illisibles_a + illisibles_b]
        for (nom, mot, autour), n in sorted(oc_b.items()):
            if n > oc_a[(nom, mot, autour)]:
                suspects.append({"type": "octets", "detail": f"{mot}: {n} occurrence(s) at {autour.hex()} in {nom} ({ou}), "
                                                             f"against {oc_a[(nom, mot, autour)]} in the base ({MNEMONIQUES_SUSPECTS[mot]})"})
    vus_a = constructions_du_texte(textes_a)
    for (chemin, raison, extrait), n in sorted(constructions_du_texte(textes_b).items()):
        if n > vus_a[(chemin, raison, extrait)]:
            suspects.append({"type": "source", "detail": f"{raison} : « {extrait[:160]} » ({chemin})"})
    return [dict(s, detail=s["detail"] if len(s["detail"]) <= DETAIL_MAX else s["detail"][:DETAIL_MAX - 1] + "…") for s in suspects]


def constructions_du_texte(textes):
    """{(file, reason, extract): n} for MOTS_SOURCE over whole files {path: text}, line splices joined as the preprocessor
    does, across line breaks; the extract is the text of the lines a match spans, whitespace collapsed."""
    comptes = Counter()
    for chemin, texte in textes.items():
        texte = re.sub(r"\\[ \t\f\v\0]*(?:\r\n?|\n)", "", texte)
        for motif, raison in MOTS_SOURCE:
            for m in motif.finditer(texte):
                debut, fin = texte.rfind("\n", 0, m.start()) + 1, texte.find("\n", m.end())
                comptes[(chemin, raison, " ".join(texte[debut:fin if fin >= 0 else None].split()))] += 1
    return comptes
