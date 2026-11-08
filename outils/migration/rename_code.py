#!/usr/bin/env python3
"""English names, step 1b (ruche-0142; docs/english-migration.md, sections 9, 12 and 13): the Python code renamer and the
proofs P1, P1b and P3, dormant: bee never calls it. Run it isolated (-I), from the base's own checkout:
    python3 -I outils/migration/rename_code.py lint | apply SOURCE DEST
    python3 -I outils/migration/rename_code.py check --base REV --head REV [--repo DIR]
lint checks the identifier map (identifiers.yaml) against the code; apply writes the Python code files of the checkout
SOURCE, renamed, at their English paths under DEST. check reads both maps and the files from git and runs only as the
base's own code (this script, rename.py and bee.py): P1 for each Python code file; then, if P1 holds for bee.py, P3 and
P1b on the head. Exit 0: proven, as the last line says; 1: problems, listed. The shell scripts and workflows: not here.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("rename_code.py: run it isolated, python3 -I outils/migration/rename_code.py …, so that nothing shadows a module")

import argparse, ast, builtins, collections, contextlib, importlib.util, io, keyword, os, pathlib, re, subprocess, tempfile, tokenize  # noqa: E401, E402
import yaml  # noqa: E402

SELF = pathlib.Path(__file__).resolve()
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import bee, rename  # noqa: E402, E401

IDS = ("outils/migration/identifiers.yaml", "tools/migration/identifiers.yaml")
WORD = re.compile(r"([\w.-]+)")  # the tokens P1 compares inside a text
LINE = re.compile(r"([ \t]*(?:- )*)([A-Za-z_][\w-]*)(:)((?=[ \t]).*|)")  # a YAML key at a line start, and the rest
VALUE = re.compile(r"( +)([\"']?)([\w.-]+(?:/[\w.-]+)*)(\2)([ \t]*(?:#.*)?)")  # its one-token value
words = lambda name: [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-zà-ÿ]+", name)]  # noqa: E731
idents = lambda tree: ((n, f, v) for n in ast.walk(tree) if not isinstance(n, ast.Constant) for f, v in ast.iter_fields(n)  # noqa: E731
                       for v in (v if isinstance(v, list) else [v]) if isinstance(v, str) and f not in ("kind", "type_comment"))


class CodeMap:
    """identifiers.yaml with the name map: ids (French identifier -> English), attrs (the same, for attributes); named (every name of the name map a string
    may hold, and the extra tokens: keys, values, commands, options, segments and stems of its paths); tokens (named, then
    the identifiers); hand (a token with two English names: left to the hand-made part, both accepted by P1)."""

    def __init__(self, names, text):
        self.names, m = names, bee.charger_texte_yaml(text, "identifiers.yaml")
        self.m, self.ids, self.english, nm = m, m["identifiers"], set(m["english"]), names.m
        self.attrs = {**self.ids, **m["attributes"]}  # an attribute (x.name, an attribute-name string, a destination) may differ
        pairs = collections.defaultdict(set)
        for d in [*(f["keys"] for f in nm["families"].values()), *(f.get("schema_strings") or {} for f in nm["families"].values()),
                  *nm["domains"].values(), *nm["open_domains"].values(), nm["cli"]["commands"], nm["cli"]["options"],
                  *nm["cli"]["scripts"].values(), nm["tree"]["segments"]]:
            [pairs[str(a)].add(str(b)) for a, b in d.items()]
        for a, b in nm["cli"]["commands"].items():  # a subcommand's own name: « invitation accord-conseil » -> council-approval
            [pairs[a.split(" ")[1]].add(b.split(" ")[1]) for _ in [1] if " " in a]
        for a, b in nm["paths"].items():  # every folder and file name of the path map, and a file name's stem (a schema's name)
            for x, y in zip(a.strip("/").split("/"), b.strip("/").split("/")):
                pairs[x].add(y)
                [pairs[x.split(".")[0]].add(y.split(".")[0]) for _ in [1] if "." in x and x.partition(".")[2] == y.partition(".")[2]]
        self.from_names = {t: next(iter(v)) for t, v in pairs.items() if len(v) == 1}
        self.dests = {a[2:].replace("-", "_"): b[2:].replace("-", "_") for d in [nm["cli"]["options"], *nm["cli"]["scripts"].values(), m["tokens"]]
                      for a, b in d.items() if a.startswith("--")}  # an option's destination follows the option
        for a, b in m["tokens"].items():
            pairs[a] = {b} if pairs[a] <= {b} or a in m["hand"] else pairs[a] | {b}
        self.hand = {t: v | set(m["hand"].get(t, {}).get("english", ())) for t, v in pairs.items() if len(v) > 1 or t in m["hand"]}
        self.named = {t: next(iter(v)) for t, v in pairs.items() if t not in self.hand}
        self.tokens = {**{t: e for t, e in self.ids.items() if t not in pairs and not self.covered(t, False)}, **self.named}  # never an English word
        self.targets = set(self.tokens.values()) | set(self.ids.values())
        self.keep = [(rename.glob_re(k["files"]), set(k.get("scopes") or ()), set(k.get("tokens") or ())) for k in m["keep"]]

    def covered(self, name, mapped=True):
        return mapped and name in self.attrs or all(len(w) < 2 or w in self.english for w in words(name))

    def kept(self, path):
        """The top-level scopes whose strings stay as written, and the tokens kept anywhere, in one code file (French path)."""
        k = [(s, t) for r, s, t in self.keep if r.match(path)]
        return set().union(*(s for s, _ in k)), set().union(*(t for _, t in k))

    def lint(self, code):
        """The map against the base's Python code ({path: text}): every identifier mapped or made of English words; an
        identifier that is an option's destination or a name of the name map gets its English (another one if that is a keyword); one English name per
        identifier inside each scope; every role-dependent token declared."""
        problems = [f"identifier {a} -> {b}: not an identifier, a keyword, or not made of English words" for a, b in [*self.ids.items(), *self.m["attributes"].items()]
                    if not (isinstance(b, str) and b.isidentifier() and not keyword.iskeyword(b) and a != b and self.covered(b, False))]
        problems += [f"token {t}: two English names {sorted(v)}, not declared in hand" for t, v in self.hand.items() if t not in self.m["hand"]]
        for path, text in sorted(code.items()):
            tree, seen = ast.parse(text), set()
            for n, f, v in [*idents(tree), *((c, "attr", c.value) for c in identifier_strings(tree) if isinstance(getattr(c, "value", None), str))]:
                for x in (v.split(".") if f == "module" else [v]):
                    if x in seen:
                        continue
                    seen.add(x)
                    if not self.covered(x):
                        problems.append(f"{path}: identifier {x} is neither mapped nor made of English words ({' '.join(words(x))})")
                    elif x in self.dests and self.attrs.get(x, x) != self.dests[x]:
                        problems.append(f"{path}: attribute {x} -> {self.attrs.get(x, x)}, its option says {self.dests[x]}")
                    elif x not in self.m["hand"] and (e := self.from_names.get(x, "")).isidentifier() and self.ids.get(x, x) != e and not keyword.iskeyword(e):
                        problems.append(f"{path}: identifier {x} -> {self.ids.get(x, x)}, the name map says {e}")
            problems += [f"{path}: {p}" for p in self.collisions(tree)]
        return problems

    def collisions(self, tree):
        """Two identifiers of one scope (module, function, lambda, class body, a class's attributes) mapped to one name."""
        out = []

        def names(scope):
            todo, found = list(ast.iter_child_nodes(scope)), set()
            while todo:
                n = todo.pop()
                found |= {n.id} if isinstance(n, ast.Name) else {n.arg} if isinstance(n, ast.arg) else set(n.names) \
                    if isinstance(n, (ast.Global, ast.Nonlocal)) else {getattr(n, "name", None)} - {None}
                todo += [] if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)) else list(ast.iter_child_nodes(n))
            return found
        scopes = [(s, names(s)) for s in ast.walk(tree) if isinstance(s, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))]
        scopes += [((c,), {a.attr for a in ast.walk(c) if isinstance(a, ast.Attribute) and getattr(a.value, "id", None) == "self"})
                   for c in ast.walk(tree) if isinstance(c, ast.ClassDef)]
        shared = {(k["scope"], frozenset(k["names"])) for k in self.m["shared"]}
        for s, found in scopes:
            by = collections.defaultdict(set)
            [by[(self.attrs if isinstance(s, tuple) else self.ids).get(x, x)].add(x) for x in found]
            line = s[0].lineno if isinstance(s, tuple) else getattr(s, "lineno", 1)
            out += [f"line {line}: {' and '.join(sorted(v))} both become {e}" for e, v in by.items()
                    if len(v) > 1 and (getattr(s, "name", None), frozenset(v)) not in shared]
        return out

    # --- the renamer ---

    def whole(self, s):
        """The English of a whole literal that is a name: a token, a node id, a path, or names joined by / or a dot."""
        if s in self.tokens or s in self.hand or not re.fullmatch(r"[\w./*{}<>~-]+", s):
            return self.tokens.get(s, s)
        seg = self.names.m["tree"]["segments"]
        if "/" in s and s.split("/")[0] in ("racine", "roles", "projets") and all(x in seg for x in s.split("/")):
            return "/".join(seg[x] for x in s.split("/"))
        return "".join(self.tokens.get(x, x) for x in re.split(r"([/.])", self.names.path(s)))

    def text(self, t):
        """The names inside a text, as they are written: a YAML key at a line start and its one-token value, options, paths
        and node ids (never in an address), commands after « bee », regex group names, constants and environment variables, bee.<attribute>;
        every other word stays (prose is translated after the switch)."""
        parts = re.split(r"(\n|\\n)", t)
        for i in range(0, len(parts), 2):
            if x := LINE.fullmatch(parts[i]):
                v = VALUE.fullmatch(x[4])
                rest = f"{v[1]}{v[2]}{self.whole(v[3])}{v[4]}{v[5]}" if v and isinstance(yaml.safe_load(v[3]), str) else x[4]
                parts[i] = x[1] + self.tokens.get(x[2], x[2]) + x[3] + rest
        t = re.sub(r"(?<![\w-])--[a-z][\w-]*", lambda x: self.tokens.get(x[0], x[0]), "".join(parts))
        t = re.sub(r"(\(\?P[<=]|\\g<)(\w+)(?=[>)])", lambda x: x[1] + self.tokens.get(x[2], x[2]), t)  # a regex group's name, as m["name"]
        t = re.sub(r"(?<![\w.:/@-])[\w.-]+(?:/[\w.*{}<>~-]*)+|(?<![\w.:/-])[A-Z]+\.md\b", lambda x: self.whole(x[0]), t)
        t = re.sub(r"(?<![\w/.-])(bee(?:\.py)? +)([a-z][\w-]*)( +[a-z][\w-]*)?", lambda x: x[1] + self.command(x[2], x[3] or ""), t)
        t = re.sub(r"(?<![\w.-])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", lambda x: self.tokens.get(x[0], x[0]), t)
        return re.sub(r"(?<![\w.])bee\.([A-Za-z_]\w*)", lambda x: "bee." + self.ids.get(x[1], x[1]), t)

    def command(self, a, b):
        c = self.names.m["cli"]["commands"]
        if b and f"{a} {b.strip()}" in c:
            return c[f"{a} {b.strip()}"].replace(" ", b[:len(b) - len(b.lstrip())], 1)
        return c.get(a, a) + b

    def string(self, raw, kind):
        """One string token, renamed: a whole literal by whole(), any other text by text(); its quoting kept."""
        if kind != tokenize.STRING:
            return self.text(raw)
        prefix = re.match(r"[rRbBuU]*", raw)[0]
        q = raw[len(prefix):len(prefix) + 3] if raw[len(prefix):len(prefix) + 3] in ('"""', "'''") else raw[len(prefix)]
        body, value = raw[len(prefix) + len(q):-len(q)], ast.literal_eval(raw)
        value = value.decode("utf-8", "surrogateescape") if isinstance(value, bytes) else value
        if (new := self.whole(value)) != value:
            if body != value:
                raise rename.Problem(f"« {raw[:40]} » is written in a form the renamer does not edit")
            return prefix + q + new + q
        return prefix + q + self.text(body) + q

    def rename_python(self, source, path=""):
        """A Python file renamed: every identifier of the map, and the names in its strings and f-string parts outside the
        kept scopes and tokens; comments, layout and every other token as written. Returns (text, [(line, old, new)])."""
        scopes, kept = self.kept(path)
        text, starts = source.split("\n"), [0]  # lines as the tokenizer counts them (never at U+2028 or U+0085)
        [starts.append(starts[-1] + len(x) + 1) for x in text]
        tree = ast.parse(source)
        frozen = [range(n.lineno, n.end_lineno + 1) for n in tree.body if scopes & ({getattr(n, "name", None)} | {
            t.id for t in getattr(n, "targets", [getattr(n, "target", None)]) if isinstance(t, ast.Name)})]
        roles = {(c.lineno, len(text[c.lineno - 1].encode()[:c.col_offset].decode())) for c in identifier_strings(tree)}  # bytes -> characters
        edits, changes, prev = {}, [], None
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            a, b = starts[tok.start[0] - 1] + tok.start[1], starts[tok.end[0] - 1] + tok.end[1]
            dot, prev = prev == ".", tok.string if tok.type not in (tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE) else prev
            if tok.type == tokenize.NAME and tok.string in (self.attrs if dot else self.ids):
                new = (self.attrs if dot else self.ids)[tok.string]
            elif tok.type in (tokenize.STRING, tokenize.FSTRING_MIDDLE) and not any(tok.start[0] in r for r in frozen):
                if source[a:b] != tok.string:
                    raise rename.Problem(f"{path}:{tok.start[0]}: a string part the tokenizer does not place")
                new, old_words = self.string(tok.string, tok.type), WORD.split(tok.string)
                if tok.start in roles and (v := ast.literal_eval(tok.string)) in self.attrs:  # an attribute or destination name
                    new = tok.string.replace(v, self.attrs[v])
                if kept and len(WORD.split(new)) == len(old_words):
                    new = "".join(o if o in kept else n for o, n in zip(old_words, WORD.split(new)))
            else:
                continue
            if new != tok.string:
                edits[a, b] = new
                changes.append((tok.start[0], tok.string, new))
        return rename.edited(source, edits), changes

    # --- P1 ---

    def allowed(self, a, b):
        """A token of a text may change only to its English name (both, for a role-dependent token), dot by dot if need be."""
        return b == self.tokens.get(a) or b in self.hand.get(a, ()) or \
            "." in a and a.count(".") == b.count(".") and all(x == y or self.allowed(x, y) for x, y in zip(a.split("."), b.split(".")))

    def string_change(self, a, b):
        """The (old, new) names by which string a became b, or None if it changed otherwise."""
        if a == b or self.whole(a) == b or self.attrs.get(a) == b:
            return [(a, b)] if a != b else []
        x, y = WORD.split(a), WORD.split(b)
        if len(x) != len(y) or x[0::2] != y[0::2]:
            return None
        pairs = [(s, t) for s, t in zip(x[1::2], y[1::2]) if s != t]
        return pairs if all(self.allowed(s, t) for s, t in pairs) else None

    def same_python(self, old, new, counts):
        """P1 for one file: the old and new syntax trees are equal once identifiers go through the map and string constants
        (f-string parts included) through whole() or token by token; numbers, operators and structure identical."""
        problems = []

        def same(a, b, line):
            if type(a) is not type(b):
                return problems.append(f"line {line}: {type(a).__name__} {a!r:.40} became {type(b).__name__} {b!r:.40}")
            if isinstance(a, list):
                return problems.append(f"line {line}: {len(a)} elements became {len(b)}") if len(a) != len(b) else \
                    [same(x, y, line) for x, y in zip(a, b)]
            if isinstance(a, str):  # a name of global, nonlocal: an identifier
                return problems.append(f"line {line}: the identifier {a} became {b}, the map says {self.ids.get(a, a)}") \
                    if b != self.ids.get(a, a) else counts.update([("identifier", a, b)] if a != b else [])
            if not isinstance(a, ast.AST):
                return problems.append(f"line {line}: {a!r:.40} became {b!r:.40}") if a != b else None
            line = getattr(a, "lineno", line)
            for f in (f for f in a._fields if f not in ("kind", "type_comment")):
                x, y = getattr(a, f, None), getattr(b, f, None)
                if isinstance(a, ast.Constant) and isinstance(x, (str, bytes)) and type(x) is type(y):
                    s, t = (x.decode("utf-8", "surrogateescape"), y.decode("utf-8", "surrogateescape")) if isinstance(x, bytes) else (x, y)
                    if (pairs := self.string_change(s, t)) is None:
                        problems.append(f"line {line}: the string « {s[:60]} » became « {t[:60]} », not through the map")
                    counts.update(("string", p, q) for p, q in pairs or [])
                elif isinstance(x, str) and isinstance(y, str):
                    e = ".".join(self.ids.get(p, p) for p in x.split(".")) if f == "module" else (self.attrs if f == "attr" else self.ids).get(x, x)
                    if y != e:
                        problems.append(f"line {line}: the identifier {x} became {y}, the map says {e}")
                    counts.update([("identifier", x, y)] if x != y else [])
                else:
                    same(x, y, line)
        same(ast.parse(old), ast.parse(new), 1)
        return problems

    # --- P1b ---

    def residue(self, path, new):
        """P1b (a) for one file of the new tree: the renamer would change nothing, outside the keep-list (path: French) and
        the words that are also an English name of the map (« voter », « status »: blind spots, listed by the lint)."""
        left = [(n, a, b) for n, a, b in self.rename_python(new, path)[1] if a not in self.targets and (len(WORD.split(a)) != len(WORD.split(b))
                or any(x != y and x not in self.targets for x, y in zip(WORD.split(a), WORD.split(b))))]
        return [f"line {n}: « {a[:50]} » is still French (it would become « {b[:50]} »)" for n, a, b in left]

    def attribute_names(self, tree, dests):
        """P1b (b): every string given to getattr, setattr, hasattr, delattr or vars() as an attribute name, and every
        args.<name>, names an attribute of the new code or a parser destination (always one for args)."""
        defined = {v for _, _, v in idents(tree)} | dests
        found = [(n.args[0], n.args[1]) for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) in
                 ("getattr", "setattr", "hasattr", "delattr") and len(n.args) > 1 and isinstance(n.args[1], ast.Constant)]
        of = lambda e: e.args[0] if isinstance(e, ast.Call) and getattr(e.func, "id", None) == "vars" and e.args else None  # noqa: E731
        for n in ast.walk(tree):  # vars(x)["k"], vars(x).get("k") and the like, "k" in vars(x)
            found += [(of(n.value), n.slice)] if isinstance(n, ast.Subscript) and of(n.value) else [(of(n.func.value), n.args[0])] if \
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and of(n.func.value) and n.args else [(of(n.comparators[0]), n.left)] \
                if isinstance(n, ast.Compare) and of(n.comparators[0]) else []
        found = [(r, s) for r, s in found if isinstance(s, ast.Constant)]
        found += [(n.value, ast.Constant(n.attr, lineno=n.lineno)) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and getattr(n.value, "id", None) == "args"]
        bad = lambda s, r: s not in dests if getattr(r, "id", None) == "args" else s not in defined and (  # noqa: E731
            s in self.attrs or self.tokens.get(s, s) != s or not self.covered(s))
        return [f"line {s.lineno}: « {s.value} » names no attribute of the new code" + (" and no parser destination" if getattr(r, "id", None) == "args" else "")
                for r, s in found if isinstance(s.value, str) and bad(s.value, r)]

    def scanners(self, tools, roots, argvs):
        """P1b (c): the old tool on the base's frozen fixture and the new tool on the head's (tools, roots: (old, new)) scan
        alike: each glob, rglob and iterdir, its folder and pattern mapped, finds as many files; each collection of the
        registry holds as many; each read-only command of argvs (old names) ends with the same exit code."""
        env = {"BEE_MAINTENANT": "2026-11-08T12:00:00Z", "BEE_REGISTRE": None}
        old = scan_run(tools[0], roots[0], [["--registre", str(roots[0]), *a] for a in argvs], env)
        new = scan_run(tools[1], roots[1], [[str(roots[1]) if x == "<root>" else self.whole(x) for x in ["--registre", "<root>", *a]] for a in argvs],
                  {self.tokens.get(k, k): v for k, v in env.items()}, lambda x: self.ids.get(x, x))
        expected = [(self.names.path(r) if r != "." else r, self.whole(p), n) for r, p, n in old[0]]
        problems = [f"{r}/{p}: found {n} file(s) before the move, {m} after" for (r, p, n), (_, _, m) in zip(expected, new[0]) if n != m]
        if [x[:2] for x in expected] != [x[:2] for x in new[0]]:
            problems += [f"scan {x[0]}/{x[1]} made before the move, not after" for x in expected if x[:2] not in [y[:2] for y in new[0]]]
            problems += [f"scan {x[0]}/{x[1]} made after the move only" for x in new[0] if x[:2] not in [y[:2] for y in expected]]
        problems += [f"registry.{k}: {n} item(s) before the move, {new[1].get(self.attrs.get(k, k))} after" for k, n in old[1].items()
                     if new[1].get(self.attrs.get(k, k)) != n]
        problems += [f"bee {' '.join(a)}: exit code {x} before the move, {y} after" for a, x, y in zip(argvs, old[2], new[2]) if x != y]
        problems += [] if sum(n for _, _, n in old[0]) else ["no scan finds a file on the fixture: the proof would prove nothing"]
        return problems, len(old[0]), sum(n for _, _, n in old[0])

    # --- P3 ---

    def mapped_tree(self, t):
        """A parser tree as the map makes it: options, choices, defaults and subcommands by their names, destinations and
        functions by the identifier map."""
        v = lambda x: (x[0], self.ids.get(x[1], x[1])) if isinstance(x, tuple) and x[:1] == ("function",) else self.whole(x) \
            if isinstance(x, str) else [v(y) for y in x] if isinstance(x, list) else x  # noqa: E731
        return {"defaults": {self.ids.get(k, k): v(x) for k, x in t["defaults"].items()}, "actions": [
            {**a, "options": [self.tokens.get(o, o) for o in a["options"]], "dest": self.attrs.get(a["dest"], a["dest"]), "default": v(a["default"]),
             "const": v(a["const"]), "type": v(a["type"]), "metavar": v(a["metavar"]), "choices": {self.whole(k): self.mapped_tree(c) for k, c in
                                                                                                   a["choices"].items()} if isinstance(a["choices"], dict) else
             v(a["choices"]) if a["choices"] is None else sorted(v(a["choices"]))}
            for a in t["actions"]]}


def scan_run(tool, root, argvs, env, n=lambda x: x):
    """The tool on one registry: each glob, rglob and iterdir it makes (folder, pattern, files found), the size of each
    collection of its Registre, and each command's exit code (n: a name of the tool as it is spelled in it)."""
    seen, real = [], {m: getattr(pathlib.Path, m) for m in ("glob", "rglob", "iterdir")}

    def spy(m):
        def scan(path, *a, **k):
            found = list(real[m](path, *a, **k))
            seen.append((os.path.relpath(path, root), a[0] if a else "", len(found)))
            return iter(found)
        return scan
    codes, out = [], io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), mock_env(env), patched(pathlib.Path, {m: spy(m) for m in real}):
        registry = getattr(tool, n("Registre"))(root)
        sizes = {k: len(v) for k, v in vars(registry).items() if isinstance(v, (list, dict, set, tuple))}
        for argv in argvs:
            try:
                codes.append(getattr(tool, n("principal"))(argv) or 0)
            except SystemExit as e:
                codes.append(e.code)
    return seen, sizes, codes


def identifier_strings(tree):
    """The string constants that are attribute names: given to getattr, setattr, hasattr or delattr, or as a key of vars(x);
    the first argument of add_argument without dashes, and every dest= (argparse destinations)."""
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            yield from [n.args[1]] if name in ("getattr", "setattr", "hasattr", "delattr") and len(n.args) > 1 else \
                [n.args[0]] if name == "add_argument" and n.args and not str(getattr(n.args[0], "value", "-")).startswith("-") else []
            yield from (k.value for k in n.keywords if k.arg == "dest")
        of = lambda e: isinstance(e, ast.Call) and getattr(e.func, "id", None) == "vars"  # noqa: E731
        yield from [n.slice] if isinstance(n, ast.Subscript) and of(n.value) else n.args[:1] if isinstance(n, ast.Call) and \
            isinstance(n.func, ast.Attribute) and of(n.func.value) else [n.left] if isinstance(n, ast.Compare) and of(n.comparators[0]) else []


def parser_tree(parser):
    """An argparse parser as a comparable tree, help texts aside (prose): each action's class, option strings, destination,
    nargs, required, default, const, type, metavar and choices, each subcommand's own tree; set_defaults."""
    v = lambda x: ("function", x.__name__) if callable(x) and hasattr(x, "__name__") else list(x) if isinstance(x, (list, tuple)) else x  # noqa: E731
    sub = lambda a: {k: parser_tree(p) for k, p in a.choices.items()} if isinstance(a, argparse._SubParsersAction) else v(a.choices)  # noqa: E731
    return {"defaults": {k: v(x) for k, x in parser._defaults.items()}, "actions": [
        {"class": type(a).__name__, "options": list(a.option_strings), "dest": a.dest, "nargs": a.nargs, "required": a.required,
         "default": v(a.default), "const": v(a.const), "type": v(a.type), "metavar": v(a.metavar), "choices": sub(a) if isinstance(a.choices, dict) or a.choices is None else sorted(v(a.choices))} for a in parser._actions]}


def tree_diff(a, b, where="bee"):
    """Where two parser trees differ, one line each."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [f"{where} {k}: only before the move" if k not in b else f"{where} {k}: only after the move" for k in a.keys() ^ b.keys()] + \
            [x for k in a.keys() & b.keys() for x in tree_diff(a[k], b[k], f"{where} {k}" if k not in ("actions", "choices") else where)]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(isinstance(x, dict) for x in a + b):
        return [x for p, q in zip(a, b) for x in tree_diff(p, q, f"{where} {'/'.join(p.get('options') or [p.get('dest')])}")]
    return [] if a == b else [f"{where}: the map gives {a!r:.80}, the new parser has {b!r:.80}"]


@contextlib.contextmanager
def patched(owner, attributes):
    saved = {k: getattr(owner, k) for k in attributes}
    try:
        [setattr(owner, k, f) for k, f in attributes.items()]
        yield
    finally:
        [setattr(owner, k, f) for k, f in saved.items()]


@contextlib.contextmanager
def mock_env(changes):
    saved = {k: os.environ.get(k) for k in changes}
    try:
        [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in changes.items()]
        yield
    finally:
        [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in saved.items()]


def checkout(files, dest, data, fixture):
    """A commit's files written as a registry whose data is the frozen fixture (data: the data folders, fixture: its
    folder, if the commit has one), committed, so that the tool reads its history as on a clone."""
    data = data if any(p.startswith(fixture) for p in files) else set()
    for p, content in files.items():
        for q in [p[len(fixture):]] * p.startswith(fixture) + [p] * (p.split("/")[0] + "/" not in data):
            (dest / q).parent.mkdir(parents=True, exist_ok=True)
            (dest / q).write_bytes(content)
    env = {**os.environ, "GIT_AUTHOR_NAME": "x", "GIT_AUTHOR_EMAIL": "x@x", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@x",
           "GIT_AUTHOR_DATE": "2026-11-08T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-08T00:00:00Z"}
    for argv in (["init", "-q"], ["add", "-A", "-f", "."], ["commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(dest), *argv], check=True, capture_output=True, env=env)


READ_ONLY = (["valider"], ["lister", "--statut", "toutes", "--json"], ["cap", "--json"], ["essaim", "--json"], ["niveaux", "--json"],
             ["classement", "--json"], ["debats", "--json"], ["en-attente"])


def check(repo, base, head):
    """P1, P1b and P3 (plan, sections 9 and 12, change 2). Returns (problems, counts of each mapping, scans made)."""
    files, after = rename.tree_files(repo, base), rename.tree_files(repo, head)
    if (carte := next((c for c in rename.MAPS if c in files), None)) is None or IDS[rename.MAPS.index(carte)] not in files:
        return [f"no {rename.MAP} and {IDS[0]} at the base {base}"], collections.Counter(), None
    outil = carte.rpartition("/migration/")[0]
    for chemin, vivant in ((f"{outil}/migration/rename_code.py", SELF), (f"{outil}/migration/rename.py", rename.SELF),
                           (f"{outil}/bee.py", pathlib.Path(bee.__file__).resolve())):
        if files.get(chemin) != vivant.read_bytes():
            return [f"{vivant} is not the base's {chemin}: run the base's own checker, python3 -I, from its checkout"], collections.Counter(), None
    names = rename.Names(files[carte].decode("utf-8"))
    cm = CodeMap(names, files[IDS[rename.MAPS.index(carte)]].decode("utf-8"))
    code = {p: files[p].decode("utf-8") for p in names.code if p.endswith(".py")}
    problems, counts, scans = [f"the map: {x}" for x in cm.lint(code)], collections.Counter(), None
    for p, text in code.items():
        if (q := names.path(p)) not in after:
            problems.append(f"{q}: not in the head")
            continue
        try:
            found = cm.same_python(text, after[q].decode("utf-8"), counts)
            found = found or cm.residue(p, after[q].decode("utf-8"))
        except (SyntaxError, UnicodeDecodeError, rename.Problem) as e:
            found = [f"{type(e).__name__}: {e}"]
        problems += [f"{q}: {x}" for x in found]
    tool = names.path(f"{outil}/bee.py")
    if any(x.startswith(f"{tool}: ") for x in problems) or tool not in after:
        return problems + [f"P3 and P1b (b, c) not run: P1 does not hold for {tool}"], counts, scans
    with tempfile.TemporaryDirectory() as tmp:  # P1 holds: the new tool is the base's code modulo the map, it may run
        roots = (pathlib.Path(tmp) / "base", pathlib.Path(tmp) / "head")
        data = set(bee.DOSSIERS_LIBRE_SERVICE)
        fixture = f"{outil}/tests/registre/"
        checkout(files, roots[0], data, fixture)
        checkout(after, roots[1], {names.path(d) for d in data}, names.path(fixture))
        spec = importlib.util.spec_from_file_location("bee_after_the_move", roots[1] / tool)
        new = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(new)
        trees = parser_tree(bee.construire_analyseur()), parser_tree(getattr(new, cm.ids.get("construire_analyseur", "construire_analyseur"))())
        problems += [f"P3: {x}" for x in tree_diff(cm.mapped_tree(trees[0]), trees[1])]
        dests = {a["dest"] for t in walk_trees(trees[1]) for a in t["actions"]} | {k for t in walk_trees(trees[1]) for k in t["defaults"]}
        problems += [f"P1b: {tool}: {x}" for x in cm.attribute_names(ast.parse(after[tool].decode("utf-8")), dests)]
        try:
            found, n, total = cm.scanners((bee, new), roots, READ_ONLY)
        except Exception as e:  # noqa: BLE001 - whatever breaks in the new tool is a problem, never a pass
            found, n, total = [f"a tool failed on the fixture: {type(e).__name__}: {e}"], 0, 0
        problems, scans = problems + [f"P1b: {x}" for x in found], (n, total)
    return problems, counts, scans


def walk_trees(t):
    yield t
    for a in t["actions"]:
        for c in (a["choices"].values() if isinstance(a["choices"], dict) else []):
            yield from walk_trees(c)


def main(argv=None):
    p = argparse.ArgumentParser(prog="rename_code.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("lint")
    s = sub.add_parser("apply")
    [s.add_argument(x) for x in ("source", "dest")]
    s = sub.add_parser("check")
    [s.add_argument(o, required=o != "--repo", default=str(SELF.parents[2]) if o == "--repo" else None) for o in ("--base", "--head", "--repo")]
    a = p.parse_args(argv)
    try:
        if a.action == "check":
            problems, counts, scans = check(a.repo, a.base, a.head)
        else:
            racine = SELF.parents[2]
            names = rename.Names((racine / rename.MAP).read_text(encoding="utf-8"))
            cm = CodeMap(names, (racine / IDS[0]).read_text(encoding="utf-8"))
            source = pathlib.Path(a.source if a.action == "apply" else racine)
            code = {q: (source / q).read_text(encoding="utf-8") for q in names.code if q.endswith(".py")}
            problems, counts = cm.lint(code), collections.Counter()
            for q, text in code.items() if a.action == "apply" and not problems else []:
                out, changes = cm.rename_python(text, q)
                (dest := pathlib.Path(a.dest) / names.path(q)).parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(out, encoding="utf-8")
                counts.update(("file", q) for _ in changes)
    except (rename.Problem, bee.ErreurBee, yaml.YAMLError, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems, counts, scans = [f"{type(e).__name__}: {e}"], collections.Counter(), None
    if a.action == "check":
        print("".join(f"{k}: {x} -> {y}: {n}\n" for (k, x, y), n in sorted(counts.items(), key=lambda c: (-c[1], c[0]))), end="")
    print("".join(f"✗ {x}\n" for x in problems) + f"{len(problems)} problem(s)." if problems else
          f"✓ P1, P1b and P3 hold at {a.base} for the head {a.head}: {len({x for k, x, _ in counts if k == 'identifier'})} identifiers and "
          f"{len({x for k, x, _ in counts if k == 'string'})} string names renamed through the map ({sum(counts.values())} places), "
          f"nothing else changed; no French name left; {scans[0]} scans find the same {scans[1]} files." if a.action == "check" else
          "✓ the identifier map covers the code, one English name per identifier in each scope." if a.action == "lint" else
          f"✓ {len(code)} Python file(s) written, {sum(counts.values())} name(s) renamed.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
