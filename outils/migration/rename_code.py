#!/usr/bin/env python3
"""English names, step 1b (ruche-0142; docs/english-migration.md, sections 9, 12 and 13): the Python code renamer
(CodeMap.rename_python) and proofs P1, P1b and P3, dormant. Run it isolated, from the base's own checkout:
    python3 -I outils/migration/rename_code.py lint | check --base REV --head REV [--repo DIR]
lint: identifiers.yaml against the code. check reads both maps and the files from git, runs only as the base's own code
(this script, rename.py, bee.py): P1 and P1b (a) per Python code file, then, if P1 holds for bee.py, P3 and P1b (b).
Exit 0: proven, as the last line says; 1: problems, listed. Shell scripts and workflows are not renamed here.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("rename_code.py: run it isolated, python3 -I outils/migration/rename_code.py …, so that nothing shadows a module")

import argparse, ast, collections, importlib.util, io, keyword, pathlib, re, subprocess, tempfile, tokenize  # noqa: E401, E402
import yaml  # noqa: E402

SELF = pathlib.Path(__file__).resolve()
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import bee, rename  # noqa: E402, E401

IDS = ("outils/migration/identifiers.yaml", "tools/migration/identifiers.yaml")
WORD = re.compile(r"((?<!\\)[\w.-]+)")  # the tokens P1 compares inside a text (never the letter of an escape: \\n)
LINE = re.compile(r"([ \t]*(?:- )*)([A-Za-z_][\w-]*)(:)((?=[ \t]).*|)")  # a YAML key at a line start, and the rest
VALUE = re.compile(r"( +)([\"']?)([\w.-]+(?:/[\w.-]+)*)(\2)([ \t]*(?:#.*)?)")  # its one-token value
words = lambda name: [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-zà-ÿ]+", name)]  # noqa: E731
idents = lambda tree: ((n, f, v) for n in ast.walk(tree) if not isinstance(n, ast.Constant) for f, v in ast.iter_fields(n)  # noqa: E731
                       for v in (v if isinstance(v, list) else [v]) if isinstance(v, str) and f not in ("kind", "type_comment"))


class CodeMap:
    """identifiers.yaml with the name map. ids: French identifier -> English (attrs: for x.name, attribute-name strings and
    destinations); tokens: every name a string may hold (the name map's keys, values, commands, options, path segments and
    stems, the extra tokens, the French identifiers); hand: two English names, by hand (P1 accepts both)."""

    def __init__(self, names, text):
        self.names, m = names, bee.charger_texte_yaml(text, "identifiers.yaml")
        self.m, self.ids, self.english, nm = m, m["identifiers"], set(m["english"]), names.m
        self.attrs, pairs = {**self.ids, **m["attributes"]}, collections.defaultdict(set)
        for d in [*(f["keys"] for f in nm["families"].values()), *(f.get("schema_strings") or {} for f in nm["families"].values()),
                  *nm["domains"].values(), *nm["open_domains"].values(), nm["cli"]["commands"], nm["cli"]["options"],
                  *nm["cli"]["scripts"].values(), nm["tree"]["segments"]]:
            [pairs[str(a)].add(str(b)) for a, b in d.items()]
        for a, b in nm["cli"]["commands"].items():  # a subcommand's own name: « invitation accord-conseil » -> council-approval
            [pairs[a.split(" ")[1]].add(b.split(" ")[1]) for _ in [1] if " " in a]
        for a, b in nm["paths"].items():  # each folder and file name of the path map, and a file's stem (a schema's name)
            for x, y in zip(a.strip("/").split("/"), b.strip("/").split("/")):
                pairs[x].add(y)
                [pairs[x.split(".")[0]].add(y.split(".")[0]) for _ in [1] if "." in x and x.partition(".")[2] == y.partition(".")[2]]
        self.from_names = {t: next(iter(v)) for t, v in pairs.items() if len(v) == 1}
        self.dests = {a[2:].replace("-", "_"): b[2:].replace("-", "_") for d in [nm["cli"]["options"], *nm["cli"]["scripts"].values(),
                                                                                 m["tokens"]] for a, b in d.items() if a.startswith("--")}
        for a, b in m["tokens"].items():
            pairs[a] = {b} if pairs[a] <= {b} else pairs[a] | {b}
        self.hand = {t: pairs.get(t, set()) | set(m["hand"].get(t, {}).get("english", ())) for t in {t for t, v in pairs.items() if len(v) > 1} | set(m["hand"])}
        self.named = {t: next(iter(v)) for t, v in pairs.items() if t not in self.hand}
        self.tokens = {**{t: e for t, e in self.ids.items() if t not in pairs and not self.covered(t, False)}, **self.named}  # never an English word
        self.targets = set(self.tokens.values()) | set(self.attrs.values())
        self.keep = [(rename.glob_re(k["files"]), set(k.get("scopes") or ()), set(k.get("tokens") or ())) for k in m["keep"]]

    def covered(self, name, mapped=True):
        return mapped and name in self.attrs or all(len(w) < 2 or w in self.english for w in words(name))

    def kept(self, path):
        """In one code file (French path): the top-level scopes whose strings stay as written, and the tokens kept anywhere."""
        k = [(s, t) for r, s, t in self.keep if r.match(path)]
        return set().union(*(s for s, _ in k)), set().union(*(t for _, t in k))

    def lint(self, code):
        """The map against the code ({path: text}): each identifier mapped or English; a destination as its option, a name of
        the name map as it says (unless a keyword); one English name per identifier in each scope; a pending file: one line."""
        problems = [f"identifier {a} -> {b}: not an identifier, a keyword, or not made of English words" for a, b in [*self.ids.items(),
                    *self.m["attributes"].items()] if not (isinstance(b, str) and b.isidentifier() and not keyword.iskeyword(b) and a != b and self.covered(b, False))]
        problems += [f"token {t}: two English names {sorted(v)}, not declared in hand" for t, v in self.hand.items() if t not in self.m["hand"]]
        for path, text in sorted(code.items()):
            tree, seen, missing = ast.parse(text), set(), 0
            for _, f, v in [*idents(tree), *((c, "attr", c.value) for c in identifier_strings(tree) if isinstance(getattr(c, "value", None), str))]:
                for x in set(v.split(".") if f == "module" else [v]) - seen:
                    seen.add(x)
                    if not self.covered(x):
                        missing += 1
                        problems += [] if path in self.m["pending"] else [f"{path}: identifier {x} is neither mapped nor made of English words"]
                    elif x in self.dests and self.attrs.get(x, x) != self.dests[x]:
                        problems.append(f"{path}: attribute {x} -> {self.attrs.get(x, x)}, its option says {self.dests[x]}")
                    elif x not in self.m["hand"] and (e := self.from_names.get(x, "")).isidentifier() and self.ids.get(x, x) != e and not keyword.iskeyword(e):
                        problems.append(f"{path}: identifier {x} -> {self.ids.get(x, x)}, the name map says {e}")
            problems += [f"{path}: {missing} identifiers not mapped yet (pending)"] if path in self.m["pending"] else []
            problems += [f"{path}: {p}" for p in self.collisions(tree)]
        return problems

    def collisions(self, tree):
        """Two identifiers of one scope (module, function, lambda, class, a class's self attributes) mapped to one name, unless
        declared shared (never live at once)."""
        def names(scope):
            todo, found = list(ast.iter_child_nodes(scope)), set()
            while todo:
                n = todo.pop()
                found |= {n.id} if isinstance(n, ast.Name) else {n.arg} if isinstance(n, ast.arg) else set(n.names) \
                    if isinstance(n, (ast.Global, ast.Nonlocal)) else {getattr(n, "name", None)} - {None}
                todo += [] if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)) else list(ast.iter_child_nodes(n))
            return found
        scopes = [(s, names(s), self.ids) for s in ast.walk(tree) if isinstance(s, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))]
        scopes += [(c, {a.attr for a in ast.walk(c) if isinstance(a, ast.Attribute) and getattr(a.value, "id", None) == "self"}, self.attrs)
                   for c in ast.walk(tree) if isinstance(c, ast.ClassDef)]
        shared, out = {(k["scope"], frozenset(k["names"])) for k in self.m["shared"]}, []
        for s, found, d in scopes:
            by = collections.defaultdict(set)
            [by[d.get(x, x)].add(x) for x in found]
            out += [f"line {getattr(s, 'lineno', 1)}: {' and '.join(sorted(v))} both become {e}" for e, v in by.items()
                    if len(v) > 1 and (getattr(s, "name", None), frozenset(v)) not in shared]
        return out

    # --- the renamer ---

    def whole(self, s):
        """The English of a whole literal shaped as a name: a token, a node id, a path, or names joined by / or a dot."""
        if s in self.tokens or s in self.hand or not re.fullmatch(r"[\w./*{}<>~-]+", s):
            return self.tokens.get(s, s)
        seg = self.names.m["tree"]["segments"]
        if "/" in s and s.split("/")[0] in ("racine", "roles", "projets") and all(x in seg for x in s.split("/")):
            return "/".join(seg[x] for x in s.split("/"))
        return "".join(self.tokens.get(x, x) for x in re.split(r"([/.])", self.names.path(s)))

    def text(self, t):
        """The names in a text: a YAML key at a line start and its one-token value, options, regex group names, paths and node
        ids (never in an address), commands after « bee », constants, bee.<name>; prose stays (translated after the switch)."""
        parts = re.split(r"(\n|\\n)", t)
        for i in range(0, len(parts), 2):
            if x := LINE.fullmatch(parts[i]):
                v = VALUE.fullmatch(x[4])
                parts[i] = x[1] + self.tokens.get(x[2], x[2]) + x[3] + (f"{v[1]}{v[2]}{self.whole(v[3])}{v[4]}{v[5]}" if v and
                                                                        isinstance(yaml.safe_load(v[3]), str) else x[4])
        t = re.sub(r"(?<![\w-])--[a-z][\w-]*", lambda x: self.tokens.get(x[0], x[0]), "".join(parts))
        t = re.sub(r"(\(\?P[<=]|\\g<)(\w+)(?=[>)])", lambda x: x[1] + self.tokens.get(x[2], x[2]), t)  # as m["name"] is renamed
        t = re.sub(r"(?<![\w.:/@-])[\w.-]+(?:/[\w.*{}<>~-]*)+|(?<![\w.:/-])[A-Z]+\.md\b", lambda x: self.whole(x[0]), t)
        t = re.sub(r"(?<![\w/.-])(bee(?:\.py)? +)([a-z][\w-]*)( +[a-z][\w-]*)?", lambda x: x[1] + self.command(x[2], x[3] or ""), t)
        t = re.sub(r"(?<![\w.-])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", lambda x: self.tokens.get(x[0], x[0]), t)
        return re.sub(r"(?<![\w.])bee\.([A-Za-z_]\w*)", lambda x: "bee." + self.ids.get(x[1], x[1]), t)

    def command(self, a, b):
        c = self.names.m["cli"]["commands"]
        return c[f"{a} {b.strip()}"].replace(" ", b[:len(b) - len(b.lstrip())], 1) if b and f"{a} {b.strip()}" in c else c.get(a, a) + b

    def string(self, raw):
        """One string token renamed, its quoting kept: a whole literal by whole(), any other text by text()."""
        prefix = re.match(r"[rRbBuU]*", raw)[0]
        q = raw[len(prefix):len(prefix) + 3] if raw[len(prefix):len(prefix) + 3] in ('"""', "'''") else raw[len(prefix)]
        body, value = raw[len(prefix) + len(q):-len(q)], ast.literal_eval(raw)
        value = value.decode("utf-8", "surrogateescape") if isinstance(value, bytes) else value
        if (new := self.whole(value)) != value and body != value:
            raise rename.Problem(f"« {raw[:40]} » is written in a form the renamer does not edit")
        return prefix + q + (new if new != value else self.text(body)) + q

    def rename_python(self, source, path=""):
        """A Python file renamed: identifiers (attrs after a dot), the names in strings and f-string parts (outside kept scopes
        and tokens); the rest as written, comments included. Returns (text, [(line, old token, new token)])."""
        scopes, kept = self.kept(path)
        lines, starts, tree = source.split("\n"), [0], ast.parse(source)  # lines as the tokenizer counts them (not at U+2028)
        [starts.append(starts[-1] + len(x) + 1) for x in lines]
        frozen = [range(n.lineno, n.end_lineno + 1) for n in tree.body if scopes & ({getattr(n, "name", None)} | {
            t.id for t in getattr(n, "targets", [getattr(n, "target", None)]) if isinstance(t, ast.Name)})]
        roles = {(c.lineno, len(lines[c.lineno - 1].encode()[:c.col_offset].decode())) for c in identifier_strings(tree)}  # bytes -> characters
        edits, changes, prev = {}, [], None
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            a, b = starts[tok.start[0] - 1] + tok.start[1], starts[tok.end[0] - 1] + tok.end[1]
            d, prev = self.attrs if prev == "." else self.ids, tok.string if tok.type not in (tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE) else prev
            if tok.type == tokenize.NAME and tok.string in d:
                new = d[tok.string]
            elif tok.type in (tokenize.STRING, tokenize.FSTRING_MIDDLE) and not any(tok.start[0] in r for r in frozen):
                if source[a:b] != tok.string:
                    raise rename.Problem(f"{path}:{tok.start[0]}: a string part the tokenizer does not place")
                new = self.string(tok.string) if tok.type == tokenize.STRING else self.whole(tok.string) if \
                    re.fullmatch(r"[\w./*<>~-]+", tok.string) else self.text(tok.string)  # an f-string part: f"{x}_max_par_pr"
                if tok.start in roles and (v := ast.literal_eval(tok.string)) in self.attrs:
                    new = tok.string.replace(v, self.attrs[v])
                if kept and len(WORD.split(new)) == len(WORD.split(tok.string)):
                    new = "".join(o if o in kept else n for o, n in zip(WORD.split(tok.string), WORD.split(new)))
            else:
                continue
            if new != tok.string:
                edits[a, b] = new
                changes.append((tok.start[0], tok.string, new))
        cuts = [0, *(x for e in sorted(edits) for x in e), len(source)]  # one pass: 20 000 edits on 1 MB stay linear
        return "".join(source[cuts[i]:cuts[i + 1]] + edits.get((cuts[i + 1], cuts[i + 2]), "") for i in range(0, len(cuts) - 2, 2)) + source[cuts[-2]:], changes

    # --- P1 ---

    def allowed(self, a, b):
        """A token of a text changes only to its English name (either, for a role-dependent token), dot by dot if need be."""
        return b == self.tokens.get(a) or b in self.hand.get(a, ()) or \
            "." in a and a.count(".") == b.count(".") and all(x == y or self.allowed(x, y) for x, y in zip(a.split("."), b.split(".")))

    def string_change(self, a, b):
        """The (old, new) names by which string a became b, or None if it changed otherwise."""
        if a == b or self.whole(a) == b or self.attrs.get(a) == b:
            return [(a, b)] if a != b else []
        x, y = WORD.split(a), WORD.split(b)
        pairs = [(s, t) for s, t in zip(x[1::2], y[1::2]) if s != t]
        return pairs if len(x) == len(y) and x[0::2] == y[0::2] and all(self.allowed(s, t) for s, t in pairs) else None

    def same_python(self, old, new, counts):
        """P1 for one file: equal syntax trees once identifiers go through the map and strings (f-string parts included) through
        whole() or token by token; numbers, operators, structure identical; no two dict keys merge. counts: each mapping."""
        problems = []

        def same(a, b, line):
            if type(a) is not type(b):
                return problems.append(f"line {line}: {type(a).__name__} {a!r:.40} became {type(b).__name__} {b!r:.40}")
            if isinstance(a, list):
                return problems.append(f"line {line}: {len(a)} elements became {len(b)}") if len(a) != len(b) else [same(x, y, line) for x, y in zip(a, b)]
            if not isinstance(a, ast.AST):  # a name of global or nonlocal, or a number
                e = self.ids.get(a, a) if isinstance(a, str) else a
                return problems.append(f"line {line}: {a!r:.40} became {b!r:.40}, the map says {e!r:.40}") if b != e else counts.update(
                    [("identifier", a, b)] if a != b else [])
            line = getattr(a, "lineno", line)
            if isinstance(a, (ast.Dict, ast.Set)) and len({getattr(e, "value", e) for e in getattr(a, "keys", getattr(a, "elts", []))}) != \
                    len({getattr(e, "value", e) for e in getattr(b, "keys", getattr(b, "elts", []))}):
                problems.append(f"line {line}: two strings of one literal became one")
            for f in (f for f in a._fields if f not in ("kind", "type_comment")):
                x, y = getattr(a, f, None), getattr(b, f, None)
                if isinstance(a, ast.Constant) and isinstance(x, (str, bytes)) and type(x) is type(y):
                    s, t = (x.decode("utf-8", "surrogateescape"), y.decode("utf-8", "surrogateescape")) if isinstance(x, bytes) else (x, y)
                    if (pairs := self.string_change(s, t)) is None:
                        problems.append(f"line {line}: the string « {s[:60]} » became « {t[:60]} », not through the map")
                    counts.update(("string", p, q) for p, q in pairs or [])
                elif isinstance(x, str) and isinstance(y, str):
                    e = ".".join(self.ids.get(p, p) for p in x.split(".")) if f == "module" else (self.attrs if f == "attr" else self.ids).get(x, x)
                    problems.extend([f"line {line}: the identifier {x} became {y}, the map says {e}"] if y != e else [])
                    counts.update([("identifier", x, y)] if x != y else [])
                else:
                    same(x, y, line)
        same(ast.parse(old), ast.parse(new), 1)
        return problems

    # --- P1b ---

    def residue(self, path, new):
        """P1b (a): renaming the new file again changes nothing, but kept tokens and English names (« voter »: blind spots)."""
        return [f"line {n}: « {a[:50]} » is still French (it would become « {b[:50]} »)" for n, a, b in self.rename_python(new, path)[1]
                if a not in self.targets and (len(WORD.split(a)) != len(WORD.split(b)) or any(
                    x != y and x not in self.targets for x, y in zip(WORD.split(a), WORD.split(b))))]

    def attribute_names(self, tree, dests):
        """P1b (b): each attribute-name string and args.<name> names an attribute of the new code or (for args) a destination."""
        defined = {v for _, _, v in idents(tree)} | dests
        found = [((getattr(n, "args", None) or [None])[0], c) for n in ast.walk(tree) for c in identifier_strings(n, False)]
        found += [(n.value, ast.Constant(n.attr, lineno=n.lineno)) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and getattr(n.value, "id", None) == "args"]
        bad = lambda s, r: s not in dests if getattr(r, "id", None) == "args" else s not in defined and (  # noqa: E731
            s in self.attrs or self.tokens.get(s, s) != s or not self.covered(s))
        return [f"line {s.lineno}: « {s.value} » names no attribute of the new code" + (" and no parser destination" if getattr(r, "id", None) == "args" else "")
                for r, s in found if isinstance(s, ast.Constant) and isinstance(s.value, str) and bad(s.value, r)]

    # --- P3 ---

    def mapped_tree(self, t):
        """A parser tree as the map makes it (destinations by attrs, functions and set_defaults keys by ids)."""
        v = lambda x: (x[0], self.ids.get(x[1], x[1])) if isinstance(x, tuple) else self.whole(x) if isinstance(x, str) else \
            [v(y) for y in x] if isinstance(x, list) else x  # noqa: E731
        return {"defaults": {self.ids.get(k, k): v(x) for k, x in t["defaults"].items()}, "actions": [
            {**a, "options": [self.tokens.get(o, o) for o in a["options"]], "dest": self.attrs.get(a["dest"], a["dest"]), "default": v(a["default"]),
             "const": v(a["const"]), "type": v(a["type"]), "metavar": v(a["metavar"]), "choices": {self.whole(k): self.mapped_tree(c) for k, c in
                                                                                                   a["choices"].items()} if isinstance(a["choices"], dict) else
             v(a["choices"]) if a["choices"] is None else sorted(v(a["choices"]))} for a in t["actions"]]}


def identifier_strings(tree, deep=True):
    """The string constants that are attribute names: given to getattr, setattr, hasattr or delattr, or a key of vars(x);
    the first argument of add_argument without dashes, and every dest= (argparse destinations)."""
    of = lambda e: isinstance(e, ast.Call) and getattr(e.func, "id", None) == "vars"  # noqa: E731
    for n in ast.walk(tree) if deep else [tree]:
        if isinstance(n, ast.Call):
            name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            yield from [n.args[1]] if name in ("getattr", "setattr", "hasattr", "delattr") and len(n.args) > 1 else \
                [n.args[0]] if name == "add_argument" and n.args and not str(getattr(n.args[0], "value", "-")).startswith("-") else []
            yield from (k.value for k in n.keywords if k.arg == "dest")
            yield from n.args[:1] if isinstance(n.func, ast.Attribute) and of(n.func.value) else []
        yield from [n.slice] if isinstance(n, ast.Subscript) and of(n.value) else [n.left] if isinstance(n, ast.Compare) and of(n.comparators[0]) else []


def parser_tree(parser):
    """An argparse parser as a comparable tree, help texts aside (prose): each action's class, option strings, destination,
    nargs, required, default, const, type, metavar and choices (sorted), each subcommand's own tree; set_defaults."""
    v = lambda x: ("function", x.__name__) if callable(x) and hasattr(x, "__name__") else list(x) if isinstance(x, (list, tuple)) else x  # noqa: E731
    return {"defaults": {k: v(x) for k, x in parser._defaults.items()}, "actions": [
        {"class": type(a).__name__, "options": list(a.option_strings), "dest": a.dest, "nargs": a.nargs, "required": a.required, "default": v(a.default),
         "const": v(a.const), "type": v(a.type), "metavar": v(a.metavar), "choices": {k: parser_tree(p) for k, p in a.choices.items()}
         if isinstance(a, argparse._SubParsersAction) else None if a.choices is None else sorted(v(a.choices))} for a in parser._actions]}


def tree_diff(a, b, where="bee"):
    """Where two parser trees differ, one line each."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [f"{where} {k}: only {'before' if k in a else 'after'} the move" for k in a.keys() ^ b.keys()] + \
            [x for k in a.keys() & b.keys() for x in tree_diff(a[k], b[k], f"{where} {k}" if k not in ("actions", "choices") else where)]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(isinstance(x, dict) for x in a + b):
        return [x for p, q in zip(a, b) for x in tree_diff(p, q, f"{where} {'/'.join(p.get('options') or [p.get('dest')])}")]
    return [] if a == b else [f"{where}: the map gives {a!r:.80}, the new parser has {b!r:.80}"]


def walk_trees(t):
    yield t
    for a in t["actions"]:
        yield from (y for c in (a["choices"].values() if isinstance(a["choices"], dict) else []) for y in walk_trees(c))


def check(repo, base, head):
    """P1, P1b (a, b) and P3 (plan, sections 9 and 12, change 2); P1b (c), the scans on the fixture, is step 1c's, with P6.
    Returns (problems, counts of each mapping)."""
    files, after, none = rename.tree_files(repo, base), rename.tree_files(repo, head), collections.Counter()
    if (at := next((c for c in rename.MAPS if c in files), None)) is None or IDS[rename.MAPS.index(at)] not in files:
        return [f"no {rename.MAP} and {IDS[0]} at the base {base}"], none
    tools_dir = at.rpartition("/migration/")[0]
    for path, live in ((f"{tools_dir}/migration/rename_code.py", SELF), (f"{tools_dir}/migration/rename.py", rename.SELF),
                       (f"{tools_dir}/bee.py", pathlib.Path(bee.__file__).resolve())):
        if files.get(path) != live.read_bytes():
            return [f"{live} is not the base's {path}: run the base's own checker, python3 -I, from its checkout"], none
    names = rename.Names(files[at].decode("utf-8"))
    cm, code = CodeMap(names, files[IDS[rename.MAPS.index(at)]].decode("utf-8")), {p: files[p].decode("utf-8") for p in names.code if p.endswith(".py")}
    problems, counts, tool = [f"the map: {x}" for x in cm.lint(code)], collections.Counter(), names.path(f"{tools_dir}/bee.py")
    for p, text in code.items():
        try:
            new = after[q := names.path(p)].decode("utf-8")
            problems += [f"{q}: {x}" for x in cm.same_python(text, new, counts)] or [f"P1b: {q}: {x}" for x in cm.residue(p, new)]
        except (KeyError, SyntaxError, UnicodeDecodeError, rename.Problem) as e:
            problems.append(f"{q}: {'not in the head' if isinstance(e, KeyError) else f'{type(e).__name__}: {e}'}")
    if any(x.startswith(f"{tool}: ") for x in problems):
        return problems + [f"P3 and P1b (b) not run: P1 does not hold for {tool}"], counts
    with tempfile.TemporaryDirectory() as tmp:  # P1 holds: the new tool is the base's code modulo the map, it may run
        (path := pathlib.Path(tmp) / tool).parent.mkdir(parents=True)
        path.write_bytes(after[tool])
        spec = importlib.util.spec_from_file_location("bee_after_the_move", path)
        spec.loader.exec_module(new := importlib.util.module_from_spec(spec))
        trees = parser_tree(bee.construire_analyseur()), parser_tree(getattr(new, cm.ids.get("construire_analyseur", "construire_analyseur"))())
        problems += [f"P3: {x}" for x in tree_diff(cm.mapped_tree(trees[0]), trees[1])]
        dests = {a["dest"] for t in walk_trees(trees[1]) for a in t["actions"]} | {k for t in walk_trees(trees[1]) for k in t["defaults"]}
    return problems + [f"P1b: {tool}: {x}" for x in cm.attribute_names(ast.parse(after[tool].decode("utf-8")), dests)], counts


def main(argv=None):
    p = argparse.ArgumentParser(prog="rename_code.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("lint")
    s = sub.add_parser("check")
    [s.add_argument(o, required=o != "--repo", default=str(SELF.parents[2]) if o == "--repo" else None) for o in ("--base", "--head", "--repo")]
    a, counts = p.parse_args(argv), collections.Counter()
    try:
        if a.action == "check":
            problems, counts = check(a.repo, a.base, a.head)
        else:
            names, read = rename.Names((SELF.parents[2] / rename.MAP).read_text(encoding="utf-8")), lambda q: (SELF.parents[2] / q).read_text(encoding="utf-8")
            problems = CodeMap(names, read(IDS[0])).lint({q: read(q) for q in names.code if q.endswith(".py")})
    except (rename.Problem, bee.ErreurBee, yaml.YAMLError, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems = [f"{type(e).__name__}: {e}"]
    if a.action == "check":
        print("".join(f"{k}: {x} -> {y}: {n}\n" for (k, x, y), n in sorted(counts.items(), key=lambda c: (-c[1], c[0]))), end="")
    print("".join(f"✗ {x}\n" for x in problems) + f"{len(problems)} problem(s)." if problems else
          f"✓ P1, P1b and P3 hold at {a.base} for the head {a.head}: {len({x for k, x, _ in counts if k == 'identifier'})} identifiers and "
          f"{len({x for k, x, _ in counts if k == 'string'})} names in strings renamed through the map ({sum(counts.values())} places), nothing "
          "else changed; no French name left, every attribute name resolves, the parser is the same." if a.action == "check" else
          "✓ the identifier map covers the code, one English name per identifier in each scope.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
