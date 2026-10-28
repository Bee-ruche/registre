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
le registre exige alors la relecture d'un gardien (R3). Ce module ne lit que du texte ; il n'exécute rien.
"""

import re

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
    "rdpid": "lecture de l'identifiant de processeur",
    "rdrand": "nombre aléatoire matériel",
    "rdseed": "nombre aléatoire matériel",
    "cpuid": "identification du processeur (détection d'un émulateur ou de Valgrind)",
    "xgetbv": "lecture d'état du processeur",
}
# Préambule des requêtes client de Valgrind sur x86-64 : rol $3, $13, $61, $51 sur %rdi.
PREAMBULE_VALGRIND = re.compile(r"\brol\s+\$0x(?:3|d|3d|33),%rdi\b")

SECTIONS_PERMISES = re.compile(
    r"^\.(?:text(?:\.(?:unlikely|hot|cold)(?:\..*)?)?|text\.[A-Za-z0-9_]+|rodata(?:\..*)?|data(?:\..*)?|bss(?:\..*)?"
    r"|debug_.*|note(?:\..*)?|comment|eh_frame|group|rela?\..*)$")
SECTIONS_INTERDITES = re.compile(r"^\.(?:init_array|fini_array|preinit_array|ctors|dtors|init|fini|text\.startup|text\.exit)(?:\..*)?$")

# Lignes ajoutées par la PR (diff des sources C) : mots qui n'ont rien à faire dans le projet.
MOTS_SOURCE = [
    (re.compile(r"\b(?:__asm__|__asm|asm)\b"), "assembleur en ligne"),
    (re.compile(r"__attribute__\s*\(\(\s*(?:constructor|destructor|ifunc|section|weak|alias)\b"), "attribut de lien ou d'initialisation"),
    (re.compile(r"#\s*include\s*<(?:sys/|unistd\.h|dlfcn\.h|signal\.h|time\.h|sched\.h|pthread\.h|fcntl\.h|valgrind/)"),
     "en-tête système (processus, horloge, signaux, Valgrind)"),
    (re.compile(r"\b(?:getenv|RUNNING_ON_VALGRIND|VALGRIND_\w+|CACHEGRIND_\w+|CALLGRIND_\w+|dlsym|dlopen)\b"),
     "détection de l'environnement de mesure"),
    (re.compile(r"\b(?:__builtin_ia32_rdtscp?|__rdtsc|__builtin_cpu_supports|__builtin_cpu_init)\b"),
     "lecture du processeur ou de l'horloge"),
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
    """objdump -d --no-show-raw-insn : compte des mnémoniques suspects et du préambule Valgrind."""
    comptes = {}
    for ligne in texte.splitlines():
        if "\t" not in ligne:
            continue
        instruction = ligne.split("\t", 1)[1].strip()
        if not instruction:
            continue
        mot = instruction.split()[0]
        if mot in ("rep", "repz", "repnz", "lock", "notrack", "bnd", "data16", "cs", "ds"):
            morceaux = instruction.split()
            mot = morceaux[1] if len(morceaux) > 1 else mot
        if mot in MNEMONIQUES_SUSPECTS:
            comptes[mot] = comptes.get(mot, 0) + 1
        if PREAMBULE_VALGRIND.search(instruction):
            comptes["preambule_valgrind"] = comptes.get("preambule_valgrind", 0) + 1
    return comptes


def analyser(releves_a, releves_b, diff_sources="", prefixes=(), permis=()):
    """releves_* : {"symboles": texte nm, "sections": texte objdump -h, "desassemblage": texte objdump -d}.

    prefixes : espace de noms du projet (noms qu'il définit et appelle entre ses fichiers) ;
    permis   : fonctions externes permises en plus d'INDEFINIS_PERMIS.
    Renvoie la liste des constructions suspectes que B ajoute par rapport à A (liste de dicts)."""
    prefixes = tuple(prefixes)
    tous_permis = INDEFINIS_PERMIS | frozenset(permis)
    suspects = []
    sym_a, sym_b = symboles(releves_a["symboles"]), symboles(releves_b["symboles"])
    definis_a = {nom for (nom, t) in sym_a if t not in "Uuvw" and t.isupper()}
    indefinis_a = {nom for (nom, t) in sym_a if t in ("U", "w", "v")}
    for (nom, t), fichier in sorted(sym_b.items()):
        if t in ("i", "u") and (nom, t) not in sym_a:
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
    for ligne in diff_sources.splitlines():
        if not ligne.startswith("+") or ligne.startswith("+++"):
            continue
        for motif, raison in MOTS_SOURCE:
            if motif.search(ligne):
                extrait = ligne[1:].strip()[:120]
                suspects.append({"type": "source", "detail": f"{raison} : « {extrait} »"})
                break
    return suspects
