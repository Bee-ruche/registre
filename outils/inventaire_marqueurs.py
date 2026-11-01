#!/usr/bin/env python3
"""Inventory of the French markers bee compares human-written text against (task ruche-0055).

    python3 outils/inventaire_marqueurs.py [--all]

Reads outils/bee.py, outils/site_bee.py and outils/juge/*.py (tests excluded) with the ast module, and collects every
string literal that text is compared against: operands of ==, !=, in and not in; the first argument of (or the literal
calling) startswith, endswith, find, split, partition, replace, get…; patterns given to re; indexes; the iterable of a
loop; and the literals of every module constant used there. Identifiers, paths and options (keys, statuses, values, file,
folder and attribute names; subcommands) are names: ruche-0070 (ruche-0069 for commands). Every other literal that
looks French (an accented letter or a French function word) must be classified below; exit code 1 if one is not, or if
the English form of a bilingual marker is missing from the code. Limit: a French word with neither (« Enfants »,
« Contre ») is not detected; those were found by reading the --all list and are classified by hand.
"""
import ast
import pathlib
import re
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
METHODES = {"startswith", "endswith", "find", "rfind", "index", "count", "split", "rsplit", "partition", "rpartition",
            "replace", "removeprefix", "removesuffix", "get", "setdefault", "pop"}
FONCTIONS_RE = {"compile", "match", "search", "fullmatch", "findall", "finditer", "sub", "split"}
# Identifiers, and paths, domains or options with no space: names (folder and file names are ruche-0070's too).
NOM = re.compile(r"^(?:[a-z_][a-z0-9_-]*|[A-Z][A-Z0-9_]*|-[-a-z]+|[\w*<>{}~:@+-]*[./][\w./*<>{}~:@+-]*)$", re.ASCII)
FRANCAIS = re.compile(r"[À-ÖØ-öø-ÿŒœ]|\b(?:le|la|les|de|des|du|une?|et|ou|ce|cette|qui|que|qu|ici|on|pour|par|sur|avec|"
                      r"sans|dans|est|aux?|ne|pas|en|vous|son|sa|ses)\b", re.I)
CLASSES = {
    "bilingual": "read in human-written text: the English form is now accepted beside the French one",
    "already": "already bilingual: the check holds a French and an English form",
    "data": "a value the tool computes or writes into records itself, or a level, category or key name: ruche-0070",
    "message": "the tool's own message or display label, never compared with human-written text: ruche-0069",
}
# Literal prefix -> class, or (class, English form) for a bilingual marker; then module constant -> class.
PAR_TEXTE = {
    "À REMPLIR": ("bilingual", "TO FILL IN"), "^(?:Débat :": ("bilingual", "Debate:"),
    "Pourquoi cette branche existe": ("bilingual", "Why this branch exists"),
    "Ce qui compte ici": ("bilingual", "What matters here"),
    "Ce qu'on peut ignorer ici": ("bilingual", "What you can ignore here"),
    "Enfants": ("bilingual", "Children"), "Une faille": ("bilingual", "A vulnerability"),
    # Personal-data detectors (R13): French and English forms side by side.
    r"\b[\w.+-]+\s+(?:at|arobase)": "already", r"(?i)\s*[(\[{<]\s*(?:at|arobase)": "already",
    r"(?i)\s*[(\[{<]\s*(?:dot|point)": "already", r"(?i)(@[\w-]+(?:\.[\w-]+)*)\s*(?:\.|\bdot": "already",
    r"(?i:\b\d{1,5}\s*(?:bis|ter": "already",
    "succès": "already",  # CI verdict written by the forks' CI: verte, vert, green, success, succes or succès
    "Confirmé": "data", "Contributeur": "data", "Nouveau": "data", "compression-sans-perte": "data", "en parallèle": "data",
    "caractères": "message", "propositions de règle": "message", "tâches proposées": "message",
    "invitations proposées": "message", " Elle passe en relecture": "message", "Un gardien nommé": "message",
    "Le conseil, après le gardien": "message", "Le conseil consigne": "message", "Le proposant, un gardien": "message",
    "Le conseil, à la demande": "message", "Le conseil renouvelle": "message",
}
PAR_CONSTANTE = {
    "MENTION_INVITATION": "already", "PHRASE_DEMANDE": "already", "VOIES_FR": "already", "VOIES_EN": "already",
    "RETIRE": "data", "POIDS_VOTE": "data", "TAILLES_PAR_NIVEAU": "data",
    "TYPES_JSON": "message", "FICHIERS_LIBRE_SERVICE": "message", "SUITE_INVITATION": "message", "ATTENTE_VERDICT": "message",
    "MNEMONIQUES_SUSPECTS": "message", "MOTS_SOURCE": "message", "ETATS": "message", "STATUTS_CONTRIBUTION": "message",
    "POSITIONS_DEBAT": "message", "ISSUES_DEBAT": "message",
}


def litteraux(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        yield n
    elif isinstance(n, (ast.Tuple, ast.List, ast.Set, ast.Dict, ast.JoinedStr, ast.FormattedValue, ast.Call)):
        for e in ast.iter_child_nodes(n):
            if not isinstance(e, (ast.Name, ast.Attribute)):
                yield from litteraux(e)


def operandes(n):
    """The expressions a node compares text against, if any."""
    if isinstance(n, ast.Compare):
        return [n.left] + n.comparators
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        if isinstance(n.func.value, ast.Name) and n.func.value.id == "re" and n.func.attr in FONCTIONS_RE:
            return n.args[:1]
        return n.args[:1] + [n.func.value] if n.func.attr in METHODES else []
    return [n.slice] if isinstance(n, ast.Subscript) else [n.iter] if isinstance(n, (ast.For, ast.comprehension)) else []


def inventaire(racine=RACINE):
    """[(literal, class, English form or None, places)], data names, unclassified French-looking literals, missing
    English forms, other literals."""
    fichiers = [racine / "outils/bee.py", racine / "outils/site_bee.py"] + sorted(
        p for p in (racine / "outils/juge").glob("*.py") if not p.name.startswith("test_"))
    trouves, utilises, constantes = {}, set(), []
    for f in fichiers:
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        constantes += [(f, n.targets[0].id, n.value) for n in arbre.body if isinstance(n, ast.Assign)
                       and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper()]
        for n in ast.walk(arbre):
            for o in operandes(n):
                utilises.update(noms_de(o))
                for c in litteraux(o):
                    trouves.setdefault(c.value, (None, []))[1].append((f.relative_to(racine), c.lineno))
    while True:  # a constant built from other constants (MARQUES_A_REMPLIR) uses them too
        avant = len(utilises)
        utilises.update(x for _, nom, valeur in constantes if nom in utilises for x in noms_de(valeur))
        if len(utilises) == avant:
            break
    for f, nom, valeur in constantes:
        for c in (litteraux(valeur) if nom in utilises else []):
            trouves.setdefault(c.value, (nom, []))[1].append((f.relative_to(racine), c.lineno))
    lignes, noms, inconnus, autres = [], sorted(t for t in trouves if NOM.match(t)), [], []
    for texte, (constante, lieux) in sorted(trouves.items(), key=lambda t: min(t[1][1])):
        lieux = [f"{f}:{ligne}" for f, ligne in sorted(lieux)]
        classe = next((v for k, v in PAR_TEXTE.items() if texte.startswith(k)), None)
        classe = classe or (None if NOM.match(texte) else PAR_CONSTANTE.get(constante))
        if classe is not None:
            classe, anglais = classe if isinstance(classe, tuple) else (classe, None)
            lignes.append((texte, classe, anglais, lieux))
        elif not NOM.match(texte):
            francais = FRANCAIS.search(re.sub(r"\[[^\]]*\]", "", texte))  # a character class is not a word
            (inconnus if francais else autres).append((texte, lieux))
    manquants = [a for _, c, a, _ in lignes if a and not any(a in t for t in trouves)]
    return lignes, noms, inconnus, manquants, autres


def noms_de(n):
    return {x.id if isinstance(x, ast.Name) else x.attr for x in ast.walk(n) if isinstance(x, (ast.Name, ast.Attribute))}


def principal(arguments):
    lignes, noms, inconnus, manquants, autres = inventaire()
    for classe, raison in CLASSES.items():
        print(f"\n## {classe}: {raison}")
        for texte, c, anglais, lieux in (x for x in lignes if x[1] == classe):
            suite = f" -> {anglais!r}" if anglais else ""
            print(f"- {lieux[0]}{f' (+{len(lieux) - 1})' if len(lieux) > 1 else ''}: {texte[:70]!r}{suite}")
    print(f"\n## names: {len(noms)} identifiers, paths and options (keys, statuses, values, file, folder and attribute names; "
          "subcommands): ruche-0070, ruche-0069 for commands")
    if "--all" in arguments:
        print(" ".join(noms))
        print(f"\n## other: {len(autres)} literals with no French sign (patterns, addresses, English), read by hand")
        print("\n".join(f"- {lieux[0]}: {texte[:70]!r}" for texte, lieux in autres))
    for texte, lieux in inconnus:
        print(f"UNCLASSIFIED {lieux[0]}: {texte[:70]!r}")
    for anglais in manquants:
        print(f"MISSING English form {anglais!r}")
    return 1 if inconnus or manquants else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
