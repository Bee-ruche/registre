#!/usr/bin/env python3
"""Inventory of the French markers bee compares human-written text against (task ruche-0055).

    python3 tools/marker_inventory.py [--all | --names]

Reads tools/bee.py, tools/site_bee.py and outils/juge/*.py (tests excluded) with the ast module, and collects every
string literal that text is compared against: operands of ==, !=, in and not in; the first argument of (or the literal
calling) startswith, endswith, find, split, partition, replace, get…; patterns given to re.<function>, pattern= included;
indexes, the constant indexed or the keys of a dict literal indexed; match/case values; the iterable of a loop; literals
joined by +; and the literals of every module constant used there. Identifiers, paths and options (keys, statuses,
values, file, folder and attribute names; subcommands) are names: ruche-0070 (ruche-0069 for commands). Every other
literal that looks French (an accented letter or a French function word) must be classified below; exit code 1 if one
is not, or if the English form of a bilingual marker is missing from the code.
Limits: do not rely on it for what it cannot see. It misses a marker held in a local variable or a default parameter,
built from variables, or given to a function imported from re (from re import search). It takes a lowercase single word
or a token with a dot for a name. A literal with no accent and no French function word (« Enfants », « Contre ») goes
unchecked into the --all list: those two were found there by hand.
--names (ruche-0142): every name literal of tools/bee.py (a string constant shaped as NOM below, f-string parts included)
must be in the name map, its pieces between / and . each a name of tools/migration/names.yaml or identifiers.yaml (or a
path of the path map), or made of words identifiers.yaml declares English or language-neutral; exit code 1 otherwise.
"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
METHODS = {"startswith", "endswith", "find", "rfind", "index", "count", "split", "rsplit", "partition", "rpartition",
            "replace", "removeprefix", "removesuffix", "get", "setdefault", "pop"}
RE_FUNCTIONS = {"compile", "match", "search", "fullmatch", "findall", "finditer", "sub", "split"}
# Identifiers, and paths, domains or options with no space: names (folder and file names are ruche-0070's too).
NAME = re.compile(r"^(?:[a-z_][a-z0-9_-]*|[A-Z][A-Z0-9_]*|-[-a-z]+|[\w*<>{}~:@+-]*[./][\w./*<>{}~:@+-]*)$", re.ASCII)
FRENCH = re.compile(r"[À-ÖØ-öø-ÿŒœ]|\b(?:le|la|les|de|des|du|une?|et|ou|ce|cette|qui|que|qu|ici|pour|sur|avec|"
                      r"sans|dans|est|aux?|ne|pas|vous|son|sa|ses)\b", re.I)
CLASSES = {
    "bilingual": "read in human-written text: the English form is now accepted beside the French one",
    "already": "already bilingual: the check holds a French and an English form",
    "data": "a value the tool computes or writes into records itself, or a level, category or key name: ruche-0070",
    "message": "the tool's own message or display label, never compared with human-written text: ruche-0069",
}
# Literal prefix -> class, or (class, English form) for a bilingual marker; then module constant -> class.
BY_TEXT = {
    "À REMPLIR": ("bilingual", "TO FILL IN"), "^(?:Débat :": ("bilingual", "Debate:"),
    "Pourquoi cette branche existe": ("bilingual", "Why this branch exists"),
    "Ce qui compte ici": ("bilingual", "What matters here"),
    "Ce qu'on peut ignorer ici": ("bilingual", "What you can ignore here"),
    "Enfants": ("bilingual", "Children"), "- Une faille": ("bilingual", "- A vulnerability"),
    # Personal-data detectors (R13): French and English forms side by side.
    r"\b[\w.+-]+\s+(?:at|arobase)": "already", r"(?i)\s*[(\[{<]\s*(?:at|arobase)": "already",
    r"(?i)\s*[(\[{<]\s*(?:dot|point)": "already", r"(?i)(@[\w-]+(?:\.[\w-]+)*)\s*(?:\.|\bdot": "already",
    r"(?i:\b\d{1,5}\s*(?:bis|ter": "already",
    r"(?:com|org|net": "already", r")\b|(?i:\b\d{1,5}[a-z]?": "already", r"(?i)\b(?<!champ )": "already", r"(?i)\b(?:sick|": "already",
    "succès": "already",  # CI verdict written by the forks' CI: verte, vert, green, success, succes or succès
    "Confirmé": "data", "Contributeur": "data", "Nouveau": "data", "compression-sans-perte": "data", "en parallèle": "data",
    "caractères": "message", "propositions de règle": "message", "tâches proposées": "message", "la clé": "message",
    "invitations proposées": "message", " Elle passe en relecture": "message", "Un gardien nommé": "message",
    "Le conseil, après le gardien": "message", "Le conseil consigne": "message", "Le proposant, un gardien": "message",
    "Le conseil, à la demande": "message", "Le conseil renouvelle": "message", " (clé)": "message", "le titre": "message",
    # Refuses text that imitates bee's own frame (FIN_DONNEES): when ruche-0069 translates the frame, refuse both forms.
    "le résumé": "message", r"===\s*(?:fin\s+des": "message",
    r"(?is)((?:[dlcjmnst]|qu|jusqu": "already",  # ruche-0048: French elisions (d', qu'…) and the English possessive ('s)
}
BY_CONSTANT = {
    "MENTION_INVITATION": "already", "REQUEST_SENTENCE": "already", "FR_STREETS": "already", "EN_STREETS": "already",
    "REMOVED": "data", "VOTE_WEIGHT": "data", "SIZES_BY_LEVEL": "data",
    "FORMER_ENGAGEMENT_TITLES": "data",  # ruche-0155: titles bee wrote itself (bee-publish.json, branch hash), read until DATE_D
    "TYPES_JSON": "message", "SELF_SERVICE_FILES": "message", "SUITE_INVITATION": "message", "VERDICT_WAIT": "message",
    "MNEMONIQUES_SUSPECTS": "message", "MOTS_SOURCE": "message", "STATES": "message", "CONTRIBUTION_STATUSES": "message",
    "DEBATE_POSITIONS": "message", "DEBATE_OUTCOMES": "message", "SHORT_SECTIONS": "message", "MONTHS": "message",
    "SETTINGS": "message", "_POSITIVE": "message", "_FRACTION": "message",  # ruche-0144: the forms of bee.yaml's settings, in bee's messages
}


def literals(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        yield n
    elif isinstance(n, (ast.Tuple, ast.List, ast.Set, ast.Dict, ast.JoinedStr, ast.FormattedValue, ast.Call, ast.BinOp)):
        for e in ast.iter_child_nodes(n):
            if not isinstance(e, (ast.Name, ast.Attribute)):
                yield from literals(e)


def operands(n):
    """The expressions a node compares text against, if any."""
    if isinstance(n, ast.Compare):
        return [n.left] + n.comparators
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
        if isinstance(n.func.value, ast.Name) and n.func.value.id == "re" and n.func.attr in RE_FUNCTIONS:
            return n.args[:1] + [k.value for k in n.keywords if k.arg == "pattern"]
        return n.args[:1] + [n.func.value] if n.func.attr in METHODS else []
    if isinstance(n, ast.Subscript):  # an indexed dict literal compares its keys; an indexed constant, all of it
        return [n.slice] + ([k for k in n.value.keys if k] if isinstance(n.value, ast.Dict) else [n.value])
    return [n.iter] if isinstance(n, (ast.For, ast.comprehension)) else [n.value] if isinstance(n, ast.MatchValue) else []


def inventory(root=ROOT):
    """[(literal, class, English form or None, places)], data names, unclassified French-looking literals, missing
    English forms, other literals."""
    files = [root / "tools/bee.py", root / "tools/site_bee.py"] + sorted(
        p for p in (root / "outils/juge").glob("*.py") if not p.name.startswith("test_"))
    found_items, used_names, constants = {}, set(), []
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        constants += [(f, n.targets[0].id, n.value) for n in tree.body if isinstance(n, ast.Assign)
                       and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper()]
        for n in ast.walk(tree):
            for o in operands(n):
                used_names.update(names_of(o))
                for c in literals(o):
                    found_items.setdefault(c.value, (None, []))[1].append((f.relative_to(root), c.lineno))
    while True:  # a constant built from other constants (MARQUES_A_REMPLIR) uses them too
        before = len(used_names)
        used_names.update(x for _, name, value in constants if name in used_names for x in names_of(value))
        if len(used_names) == before:
            break
    for f, name, value in constants:
        for c in (literals(value) if name in used_names else []):
            found_items.setdefault(c.value, (name, []))[1].append((f.relative_to(root), c.lineno))
    lines, names, unknown_items, others = [], sorted(t for t in found_items if NAME.match(t)), [], []
    for text, (constant_name, places_found) in sorted(found_items.items(), key=lambda t: min(t[1][1])):
        places_found = [f"{f}:{line_text}" for f, line_text in sorted(places_found)]
        class_name = next((v for k, v in BY_TEXT.items() if text.startswith(k)), None)
        class_name = class_name or (None if NAME.match(text) else BY_CONSTANT.get(constant_name))
        if class_name is not None:
            class_name, english_form = class_name if isinstance(class_name, tuple) else (class_name, None)
            lines.append((text, class_name, english_form, places_found))
        elif not NAME.match(text):
            french = FRENCH.search(re.sub(r"\[[^\]]*\]", "", text))  # a character class is not a word
            (unknown_items if french else others).append((text, places_found))
    missing_items = [a for _, c, a, _ in lines if a and not any(a in t for t in found_items)]
    return lines, names, unknown_items, missing_items, others


def names_of(n):
    return {x.id if isinstance(x, ast.Name) else x.attr for x in ast.walk(n) if isinstance(x, (ast.Name, ast.Attribute))}


def bee_names(root=ROOT):
    """--names: (every name literal of bee.py with its first line, those neither in the map nor neutral)."""
    sys.path += [str(root / "tools"), str(root / "tools/migration")]
    import rename, rename_code  # noqa: E401
    name_map = rename_code.CodeMap(rename.Names((root / rename.MAP).read_text(encoding="utf-8")),
                                (root / rename_code.IDS[0]).read_text(encoding="utf-8"))
    kept_ones = name_map.kept("tools/bee.py")[1] | set(name_map.m["neutral"])  # kept on purpose, or declared language-neutral
    known_name = lambda x: x in name_map.tokens or x in name_map.hand or x in name_map.attrs or x in kept_ones or name_map.covered(x, False)  # noqa: E731
    read_items = {}  # each name literal, with its first line
    [read_items.setdefault(n.value, n.lineno) for n in ast.walk(ast.parse((root / "tools/bee.py").read_text(encoding="utf-8")))
     if isinstance(n, ast.Constant) and isinstance(n.value, str) and NAME.match(n.value)]
    return read_items, sorted((x for x in read_items if not (known_name(x) or name_map.names.path(x) != x or all(known_name(p) for p in re.split(r"[/.]", x) if p))), key=read_items.get)


def principal(arguments):
    if "--names" in arguments:
        read_items, unmapped_ones = bee_names(ROOT)
        print("".join(f"NAME NEITHER MAPPED NOR NEUTRAL tools/bee.py:{read_items[x]}: {x!r}\n" for x in unmapped_ones) +
              f"## names: {len(read_items)} name literals in tools/bee.py, {len(read_items) - len(unmapped_ones)} in the map or language-neutral, {len(unmapped_ones)} neither")
        return 1 if unmapped_ones else 0
    lines, names, unknown_items, missing_items, others = inventory()
    for class_name, cause in CLASSES.items():
        print(f"\n## {class_name}: {cause}")
        for text, c, english_form, places_found in (x for x in lines if x[1] == class_name):
            suite = f" -> {english_form!r}" if english_form else ""
            print(f"- {places_found[0]}{f' (+{len(places_found) - 1})' if len(places_found) > 1 else ''}: {text[:70]!r}{suite}")
    print(f"\n## names: {len(names)} identifiers, paths and options (keys, statuses, values, file, folder and attribute names; "
          "subcommands): ruche-0070, ruche-0069 for commands")
    if "--all" in arguments:
        print(" ".join(names))
        print(f"\n## other: {len(others)} literals with no French sign (patterns, addresses, English), read by hand")
        print("\n".join(f"- {places_found[0]}: {text[:70]!r}" for text, places_found in others))
    for text, places_found in unknown_items:
        print(f"UNCLASSIFIED {places_found[0]}: {text[:70]!r}")
    for english_form in missing_items:
        print(f"MISSING English form {english_form!r}")
    return 1 if unknown_items or missing_items else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
