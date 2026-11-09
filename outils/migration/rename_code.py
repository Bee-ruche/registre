#!/usr/bin/env python3
"""English names, steps 1b and 1b-2 (ruche-0142, ruche-0152; docs/english-migration.md, sections 9, 12 and 13): the code
renamers (CodeMap.rename_python; CodeMap.rename_shell for shell scripts and workflows) and proofs P1, P1b and P3, dormant.
Run it isolated, from the base's own checkout:
    python3 -I outils/migration/rename_code.py lint | check --base REV --head REV [--repo DIR]
lint: identifiers.yaml against the code. check reads both maps and the files from git, runs only as the base's own code
(this script, rename.py, bee.py): P1 and P1b (a) per code file, the workflows' links, then, if P1 holds for bee.py, P3 and
P1b (b). Exit 0: proven, as the last line says; 1: problems, listed.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("rename_code.py: run it isolated, python3 -I outils/migration/rename_code.py …, so that nothing shadows a module")

import argparse, ast, collections, importlib.util, io, itertools, json, keyword, pathlib, re, subprocess, tempfile, tokenize, unittest  # noqa: E401, E402
import yaml  # noqa: E402

SELF = pathlib.Path(__file__).resolve()
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import bee, rename  # noqa: E402, E401

IDS = ("outils/migration/identifiers.yaml", "tools/migration/identifiers.yaml")
NAME_SHAPE = r"[\w./*{}<>~#@\[\]-]+"  # a whole literal shaped as a name (a path, a key path, a glob, an address)
RUN = re.compile(r"((?:[\w\[\]<>@#/-]|\.(?=[\w\[\]<>@#/-]))+)")  # a run of name characters (a sentence's final period aside)
WORD = re.compile(r"((?<!\\)[\w.-]+)")  # the tokens P1 compares inside a text (never the letter of an escape: \\n)
LINE = re.compile(r"([ \t]*(?:\| )?[ \t]*(?:- )*(\\?[\"']|))([A-Za-z_][\w-]*)(\2:)((?=[ \t]).*|)")  # a YAML key at a line start (quoted, in a data frame's « | »)
VALUE = re.compile(r"( +)([\"']?)([\w.-]+(?:/[\w.-]+)*)(\2)([ \t]*(?:#.*)?)")  # its one-token value
TAG = re.compile(r"(</?(?:a|b|body|br|code|dd|details|div|dl|dt|em|footer|h[1-6]|head|header|html|input|label|li|main|meta|nav|ol|option|p|"
                 r"pre|section|select|small|span|strong|summary|table|tbody|td|th|thead|title|tr|ul)\b[^<>]*>)")  # HTML: its text is prose
KEY = re.compile(r"(\s*(?:- )*)([\w-]+)(:)(?=\s|$)\s*")  # a workflow's YAML key at a line start, and the blanks after it
TESTS = re.compile(r"(?:^|/)test_\w+(?:\.py)?\Z")  # a test file (outils/test_bee.py), or a test module in a dotted name
TEST_CASE = frozenset(dir(unittest.TestCase))  # what a test class's method must never become (ruche-0153: execution -> run)
HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)(\w+)\1\s*$")  # a here-document starts at this line's end
BLOCK = re.compile(r"[ \t>]*(`{3,}|~{3,})")  # Markdown: a fenced code block opens or closes (in a list or a quote too)
SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)  # Markdown: a code span, inside one paragraph
BEE = re.compile(r"(?<![\w.-])(?:[\w.-]+/)*bee(?:\.py)?(?=\s)")  # change 10: bee, or a path to bee.py, then a blank
ARG = re.compile(r"(?:'[^'\n]*'|\"[^\"\n]*\"|[^\s'\"|;&)]|(?<=[^\s|])\|(?=[^\s|]))+")  # a word of a command line (a|b: alternatives)
words = lambda name: [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-zà-ÿ]+", name)]  # noqa: E731
idents = lambda tree: ((n, f, v) for n in ast.walk(tree) if not isinstance(n, ast.Constant) for f, v in ast.iter_fields(n)  # noqa: E731
                       for v in (v if isinstance(v, list) else [v]) if isinstance(v, str) and f not in ("kind", "type_comment"))


class CodeMap:
    """identifiers.yaml with the name map. ids: French identifier -> English (attrs: for x.name, attribute-name strings and
    destinations); tokens: every name a string may hold (the name map's keys, values, commands, options, path segments and
    stems, the extra tokens, the French identifiers but a test's local variables); hand: two English names, by hand (P1
    accepts both); phrases: the workflows' names of several words, renamed whole in texts; keeping: the file's kept tokens."""

    def __init__(self, names, text):
        self.names, m = names, bee.charger_texte_yaml(text, "identifiers.yaml")
        self.m, self.ids, self.english, nm = m, {**m["identifiers"], **(m.get("test_identifiers") or {})}, set(m["english"]), names.m
        self.attrs, pairs = {**self.ids, **m["attributes"]}, collections.defaultdict(set)
        for d in [*(f["keys"] for f in nm["families"].values()), *(f.get("schema_strings") or {} for f in nm["families"].values()),
                  *nm["domains"].values(), *nm["open_domains"].values(), nm["cli"]["commands"], nm["cli"]["options"],
                  *nm["cli"]["scripts"].values(), nm["tree"]["segments"], nm.get("env") or {}, *(nm.get("workflows") or {}).values()]:
            [pairs[str(a)].add(str(b)) for a, b in d.items()]
        for a, b in nm["cli"]["commands"].items():  # a subcommand's own name: « invitation accord-conseil » -> council-approval
            [pairs[a.split(" ")[1]].add(b.split(" ")[1]) for _ in [1] if " " in a]
        for a, b in ((a, b) for a, b in nm["paths"].items() if a != b):  # each folder and file name the path map moves, and a file's stem
            for x, y in zip(a.strip("/").split("/"), b.strip("/").split("/")):
                pairs[x].add(y)
                [pairs[x.split(".")[0]].add(y.split(".")[0]) for _ in [1] if "." in x and x.partition(".")[2] == y.partition(".")[2]]
        self.from_names = {t: next(iter(v)) for t, v in pairs.items() if len(v) == 1}
        self.dests = {a[2:].replace("-", "_"): b[2:].replace("-", "_") for d in [nm["cli"]["options"], *nm["cli"]["scripts"].values(),
                                                                                 m["tokens"]] for a, b in d.items() if a.startswith("--")}
        for a, b in {**m["tokens"], **(m.get("shell") or {})}.items():
            pairs[a] = {b} if pairs[a] <= {b} else pairs[a] | {b}
        self.hand = {t: pairs.get(t, set()) | set(m["hand"].get(t, {}).get("english", ())) for t in {t for t, v in pairs.items() if len(v) > 1} | set(m["hand"])}
        self.named = {t: next(iter(v)) for t, v in pairs.items() if t not in self.hand}
        mine = lambda d, skip=(): {t: e for t, e in d.items() if t not in pairs and t not in skip and not self.covered(t, False)}  # noqa: E731
        self.tokens = {**mine(m["identifiers"]), **self.named}  # never an English word
        self.test_tokens = mine(m.get("test_identifiers") or {}, set(m.get("locals") or ()))  # in a test file, a unittest name only
        self.targets, self.inverse = set(self.tokens.values()) | set(self.attrs.values()), {e: f for f, e in self.ids.items()}
        self.tokens = self.base_tokens = collections.ChainMap({}, self.tokens)
        self.keep = [(rename.glob_re(k["files"]), set(k.get("scopes") or ()), set(k.get("tokens") or ())) for k in m["keep"]]
        self.in_scopes = [(rename.glob_re(k["files"]), set(k["scopes"]), set(k["tokens"])) for k in m.get("kept_in_scopes") or ()]  # ruche-0153
        self.declared = [(rename.glob_re(k["files"]), set(k["tokens"])) for k in m.get("strings") or ()]  # on purpose, in strings
        phrases = sorted({t for d in (nm.get("workflows") or {}).values() for t in d if " " in t}, key=len, reverse=True)  # workflows, steps, robots
        self.subcommands = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(k).replace(r"\ ", r"\s+") for k in nm["cli"]["commands"] if " " in k) + r")(?![\w-])")
        self.in_tests, self.test_ids = False, set(m.get("test_identifiers") or {})
        self.key_names = {k for f in nm["families"].values() for k in f["keys"] if k in self.named and k not in self.hand}  # printed()
        self.value_names = {v for d in (*nm["domains"].values(), *nm["open_domains"].values()) for v in d if isinstance(v, str) and v in self.named
                            and v not in self.hand}
        self.displayed = self.kept(next((c for c in sorted(names.code) if re.fullmatch(r"[^/]+/bee\.py", c)), ""))[1]  # bee's kept words
        self.phrases, self.keeping = re.compile(r"(?<![\w-])(?:" + "|".join(map(re.escape, phrases)) + r")(?![\w-])"), set()  # keeping: the file's kept

    def phrased(self, s):
        """s with each whole phrase renamed, a kept one aside (P1 compares a text so, then token by token)."""
        return self.phrases.sub(lambda x: x[0] if x[0] in self.keeping else self.named[x[0]], s)

    def scoped(self, path, scope, literal=""):
        """tokens, each hand token resolved by the role table of its file and scope (and literal), else by its default; a token kept
        in this scope (kept_in_scopes: logins) as written."""
        scope = self.inverse.get(scope, scope)  # the new tree's scopes are English
        self.tokens, self.in_tests = collections.ChainMap({**{t: (h.get("roles") or {}).get(f"{path}:{scope}:{literal}", (h.get("roles") or {}).get(
            f"{path}:{scope}", h.get("default", t))) for t, h in self.m["hand"].items()}, **dict.fromkeys(self.kept_here(path, scope), None)},
            self.test_tokens if TESTS.search(path) else {}, self.base_tokens), bool(TESTS.search(path))
        self.tokens.maps[0].update({t: t for t in self.kept_here(path, scope)})

    def kept_here(self, path, scope):
        """The tokens kept as written in one scope of one file (kept_in_scopes; the scope as the base names it)."""
        scope = self.inverse.get(scope, scope)
        return set().union(*(t for r, s, t in self.in_scopes if r.match(path) and scope in s))

    def covered(self, name, mapped=True):
        return mapped and name in self.attrs or all(len(w) < 2 or w in self.english for w in words(name))

    def frozen(self, tree, scopes):
        """The lines of the top-level scopes named in the keep-list: their strings stay as written."""
        return {i for n in tree.body if scopes & {y for x in [getattr(n, "name", None), *(t.id for t in getattr(n, "targets", [getattr(n, "target", None)])
                                                              if isinstance(t, ast.Name))] for y in (x, self.inverse.get(x))} for i in range(n.lineno, n.end_lineno + 1)}

    def kept(self, path):
        """In one code file (French path): the top-level scopes whose strings stay as written, and the tokens kept anywhere."""
        return tuple(set().union(*(e[i] for r, *e in self.keep if r.match(path))) for i in (0, 1))

    def lint(self, code):
        """The map against the code ({path: text}): each identifier mapped or English; a destination as its option, a name of
        the name map as it says (unless a keyword); one English name per name in each scope; a pending file: one line."""
        problems = [f"identifier {a} -> {b}: not an identifier, a keyword, or not made of English words" for a, b in [*self.ids.items(),
                    *self.m["attributes"].items(), *(self.m.get("shell") or {}).items()] if not (isinstance(b, str) and b.isidentifier() and
                                                                                                  not keyword.iskeyword(b) and a != b and self.covered(b, False))]
        problems += [f"token {t}: two English names {sorted(v)}, not declared in hand with a default" for t, v in self.hand.items() if "default" not in self.m["hand"].get(t, {})]
        problems += [f"token {t}: an option or environment variable, its English belongs in names.yaml" for t in {**self.m["tokens"], **(self.m.get(
            "shell") or {})} if re.match(r"-|BEE_", t)] + [f"local {t}: not a test identifier" for t in self.m.get("locals") or () if t not in self.test_ids]
        used = set()  # the names the code but the tests uses
        for path, text in sorted(code.items()):
            if not path.endswith(".py"):
                problems += [f"{path}: {p}" for p in self.lint_shell(text, path, used)]
                continue
            tree, seen, missing = ast.parse(text), set(), 0
            for _, f, v in [*idents(tree), *((c, "attr", w) for c in identifier_strings(tree) for w in re.findall(r"\w+", str(getattr(c, "value", ""))))]:
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
            problems += [] if TESTS.search(path) else [f"{path}: identifier {x} is in test_identifiers: a name of the code belongs in identifiers"
                                                       for x in sorted(seen & self.test_ids)] + self.stray(text, path, seen)
            used |= set() if TESTS.search(path) else seen
            problems += [f"{path}: {x} is defined as {self.ids.get(x, x)} and read as an attribute as {self.attrs[x]}" for x in sorted({n.name for n in ast.walk(
                tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}) if self.attrs.get(x, self.ids.get(x, x)) != self.ids.get(x, x)]
            problems += [f"{path}: {p}" for p in self.collisions(tree, path)]
            problems += [f"{path}: line {f.lineno}: the method {f.name} becomes {e}, an attribute of unittest.TestCase it would hide (ruche-0153)"
                         for c in ast.walk(tree) if isinstance(c, ast.ClassDef) and TESTS.search(path) for f in c.body
                         if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and (e := self.ids.get(f.name, f.name)) != f.name and e in TEST_CASE]
        return problems + [f"identifier {x}: only a test uses it, it belongs in test_identifiers (never a string token elsewhere)"
                           for x in self.m["identifiers"] if x not in used and x in self.base_tokens and x not in self.named and self.names.code <= set(code)]

    def stray(self, text, path, own):
        """In a file but the tests: each token of identifiers.yaml (not of names.yaml) the renamer changes in a string though
        the file's code does not name it, unless declared on purpose (strings): a value that only looks like a name (a hashed
        literal, a CSS class) would change with it."""
        declared = set().union(*(t for r, t in self.declared if r.match(path)))
        return [f"{path}: the token {x} -> {y} changes in a string, though this file's code does not name it: keep it, or declare it on purpose "
                "(identifiers.yaml, strings)" for x, y in sorted({(x, y) for _, a, b in (self.rename_python if path.endswith(".py") else self.rename_shell)(
                    text, path)[1] for x, y in zip(WORD.split(self.phrased(a))[1::2], WORD.split(b)[1::2]) if x != y and x in self.base_tokens and x not in self.named})
                if x not in own | declared]

    def collisions(self, tree, path):
        """Two names of one scope (module, function, lambda, class with its bases in the file, a class's self attributes) that
        become one, unless declared shared (never live at once): one would hide the other (a test method, a variable)."""
        def names(scope):
            todo, found = list(ast.iter_child_nodes(scope)), set()
            while todo:
                n = todo.pop()
                found |= {n.id} if isinstance(n, ast.Name) else {n.arg} if isinstance(n, ast.arg) else set(n.names) \
                    if isinstance(n, (ast.Global, ast.Nonlocal)) else {getattr(n, "name", None)} - {None}
                todo += [] if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)) else list(ast.iter_child_nodes(n))
            return found
        classes = {c.name: c for c in ast.walk(tree) if isinstance(c, ast.ClassDef)}
        lineage = lambda c, seen: names(c).union(*(lineage(classes[b.id], seen | {b.id}) for b in c.bases if getattr(b, "id", None) in set(classes) - seen))  # noqa: E731
        scopes = [(s, lineage(s, {s.name}) if isinstance(s, ast.ClassDef) else names(s), self.ids) for s in ast.walk(tree)
                  if isinstance(s, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))]
        scopes += [(c, {a.attr for a in ast.walk(c) if isinstance(a, ast.Attribute) and getattr(a.value, "id", None) == "self"}, self.attrs)
                   for c in classes.values()]
        return self.clashes(((getattr(s, "lineno", 1), getattr(s, "name", None) or path, found, d) for s, found, d in scopes))

    def clashes(self, scopes):
        """(line, scope, names, map) -> one problem per English name two names of one scope share, unless declared shared."""
        shared, out = {(k["scope"], frozenset(k["names"])) for k in self.m["shared"]}, []
        for n, s, found, d in scopes:
            by = collections.defaultdict(set)
            [by[d.get(x, x)].add(x) for x in found]
            out += [f"line {n}: {' and '.join(sorted(v))} both become {e}" for e, v in by.items() if len(v) > 1 and (s, frozenset(v)) not in shared]
        return out

    # --- the renamer ---

    def whole(self, s):
        """The English of a whole literal shaped as a name: a token, a node id, a path, or names joined by / or a dot."""
        if s in self.tokens or s in self.hand or not re.fullmatch(NAME_SHAPE, s):
            return self.tokens.get(s, s)
        if (n := re.fullmatch(r"([A-Za-z_]\w*_)(\d+)", s)) and self.tokens.get(n[1], n[1]) != n[1]:  # cle_refusee_0: f"{prefix}{n}" (ruche-0153)
            return self.tokens[n[1]] + n[2]
        if self.names.kept_path(s):  # ruche-0153: a path the switch leaves as it is (the common judge), every segment as written
            return s
        seg = self.names.m["tree"]["segments"]
        if "/" in s and s.split("/")[0] in ("racine", "roles", "projets") and all(x in seg for x in s.split("/")):
            return "/".join(seg[x] for x in s.split("/"))
        x = re.split(r"([/.#@<>\[\]])", self.names.path(s))  # after a test module (outils.test_bee.TestX.test_y), the tests' names
        t = next((i for i, y in enumerate(x) if TESTS.search(y)), len(x))
        return "".join((self.tokens if i <= t else collections.ChainMap(self.test_tokens, self.tokens)).get(y, y) for i, y in enumerate(x))

    def text(self, t):
        """The names in a text: a YAML key at a line start and its one-token value; every compound word (with _ . / [ ] < > @ #
        inside, or a hyphen between letters: options, paths, keys, constants); placeholders; a folder group (a|b)/; k=; commands
        after « bee » and a subcommand after its command; bee.<name>; $variable; a workflow's or step's name. A plain word stays:
        prose is translated after the switch (HTML's text too, cut from its tags)."""
        parts = re.split(r"(\n|\\n)", t)
        for i in range(0, len(parts), 2):
            if x := LINE.fullmatch(parts[i]):
                v = VALUE.fullmatch(x[5])
                parts[i] = x[1] + self.tokens.get(x[3], x[3]) + x[4] + (f"{v[1]}{v[2]}{self.whole(v[3])}{v[4]}{v[5]}" if v and
                                                                        isinstance(yaml.safe_load(v[3]), str) else x[5])
        parts = self.phrased("".join(parts))
        parts = self.printed(parts)
        c = self.names.m["cli"]["commands"]  # a subcommand after its command, wherever (a fake bee's « BEE passe-fusion preparer »)
        t = self.subcommands.sub(lambda x: (lambda a, s, b: s.join(c[f"{a} {b}"].split(" ")))(*re.fullmatch(r"(\S+)(\s+)(\S+)", x[0]).groups()), parts)
        t = "".join(RUN.sub(lambda x: self.whole(x[0]) if re.search(r"[_.\[\]<>@#/]|\w-\w|^--", x[0]) else x[0], p)
                    for p in TAG.split(t))
        t = re.sub(r"(?<=\{)[A-Za-z_]\w*(?=[}!:.\[])|(?<=%\()[A-Za-z_]\w*(?=\))", lambda x: self.ids.get(x[0], x[0]), t)  # as .format(name=)
        t = re.sub(r"(?<=\(\?P=)\w+(?=\))|(?<=\\g<)\w+(?=>)", lambda x: self.tokens.get(x[0], x[0]), t)  # regex back-references, as m["name"]
        t = re.sub(r"(?<=\()(\?:)?([\w-]+(?:\|[\w-]+)+)(?=\)/)", lambda x: (x[1] or "") + "|".join(map(self.name, x[2].split("|"))), t)  # (a|b)/
        t = re.sub(r"(?<![\w-])[a-z_][\w-]*(?=\]?=)|(?<=\^)[a-z_][\w-]*(?=:)", lambda x: self.name(x[0]), t)
        t = re.sub(r"(?<=\^)([ \t]*- )([a-z_][\w-]*)(?=:)", lambda x: x[1] + self.name(x[2]), t)  # a pattern's ^  - key: (ruche-0153)  # k=, x[k]=, a pattern's ^key:
        t = re.sub(r"((?<![\w/.-])bee +|(?<![\w.-])bee\.py +)([a-z][\w-]*)( +[a-z][\w-]*)?", lambda x: x[1] + self.command(x[2], x[3] or ""), t)
        t = re.sub(r"(?<=\$)\{?([A-Za-z_]\w*)", lambda x: x[0].replace(x[1], self.whole(x[1])), t)  # a shell's $variable
        t = re.sub(r"(?<=\bread -r )[A-Za-z_][\w ]*|\A ?(?!(?:for|while|until|if)\b)(?:(?!in\b)[a-z_]\w* )+[a-z_]\w*(?=; do\b)", lambda x: re.sub(r"\w+", lambda w: self.whole(w[0]), x[0]),
                   t)  # a shell's read -r names, and a text going on with such a list until « ; do » (ruche-0153)
        t = re.sub(r"(?<![\w$-])[a-z_]\w*(?==\$\()", lambda x: self.whole(x[0]), t)  # a shell's x=$( … ) (ruche-0153)
        return re.sub(r"(?<![\w.])bee\.([A-Za-z_]\w*)", lambda x: "bee." + self.ids.get(x[1], x[1]), t)

    def printed(self, t):
        """ruche-0153: the plain words of a text in the places where bee's messages print names, renamed as the tool's output is:
        a key before French typography's « : » (« motif : ») or ending a label (« f.yaml : motif »), or before « de N caractères »;
        a value after « : » then the end, a mark or an id (« statut : refusee) »), unless bee.py keeps it as a word of its messages; a
        key or a value between « and »
        (« proposee »), a node id after
        « nœud » or around « > » (« racine > roles/relire »). Any other plain word stays (prose, logins)."""
        here = {w for w, e in self.tokens.maps[0].items() if w == e}  # kept in this scope
        t = re.sub(r"(?<![\w/.<>@#\[\]$«-])[a-z_][\w-]*(?= : )|(?<=[\w.] : )[a-z_][\w-]*\Z", lambda x: self.named.get(x[0], x[0]) if x[0] in self.key_names - here
                   else x[0], t)  # « motif : », and a label « f.yaml : motif » the tool prints so
        t = re.sub(r"(?<=« )[a-z_][\w-]*(?= »)", lambda x: self.named.get(x[0], x[0]) if x[0] in (self.key_names | self.value_names) - here else x[0], t)
        t = re.sub(r"(?<![\w/.<>@#\[\]$«-])[a-z_][\w-]*(?= de \d+ caractères)", lambda x: self.named.get(x[0], x[0]) if x[0] not in here | self.hand.keys()
                   else x[0], t)  # « motif de 1516 caractères », « corps de … »: a field's or an option's name
        t = re.sub(r"(?<=[\w)] : )[a-z_][\w-]*(?=\Z|[),;.\n]| [\w-]*\d)", lambda x: self.named.get(x[0], x[0]) if x[0] in self.value_names - here - self.displayed
                   else x[0], t)  # a value after « : », then the end, a mark or an id (« statut : refusee) », « close : tache ruche-0008 »)
        t = re.sub(r"""((?:\[|\.get\()\\?(["']))([\w.-]+)(?=\\?\2[\]),])""", lambda x: x[1] + self.whole(x[3]), t)  # x["k"], .get("k"), escaped too
        seg = self.names.m["tree"]["segments"]
        return re.sub(r"(?<=nœud )[a-z_]+\b(?![/.-])|(?<![\w/.$-])[a-z_]+(?= > )|(?<= > )[a-z_]+\b(?![/.-])", lambda x: seg.get(x[0], x[0]), t)

    def name(self, x):
        """A name of the name map (or of the role table), never an identifier: for patterns that hold French words."""
        return self.tokens.maps[0].get(x) or self.named.get(x, x)

    def command(self, a, b):
        c = self.names.m["cli"]["commands"]
        return c[f"{a} {b.strip()}"].replace(" ", b[:len(b) - len(b.lstrip())], 1) if b and f"{a} {b.strip()}" in c else c.get(a, a) + b

    # --- change 10 (ruche-0153; plan, section 12): `bee <command>` and its options in the code of Markdown ---

    def cli(self, inv):
        """The command line's names on one side: (commands, options, {(command, option): {choice: its other name}}), the
        choices of the base's own parser (bee.construire_analyseur) named as P3 maps them (whole, in that function's scope)."""
        if not hasattr(self, "_cli"):
            nm, tool = self.names.m["cli"], next(p for p in sorted(self.names.code) if re.fullmatch(r"[^/]+/bee\.py", p))
            self.scoped(tool, "construire_analyseur")
            choices = {}
            for r in parser_rows(bee.construire_analyseur()):
                for o in (o for o in (r[1] if r[1] != "defaults" and r[0] and r[9] else ()) if o.startswith("--")):
                    choices[" ".join(r[0]), o] = {v: self.whole(v) for v in r[9] if isinstance(v, str)}
            self.tokens = self.base_tokens
            flip = lambda d: {b: a for a, b in d.items()}  # noqa: E731
            options = {a: b for a, b in nm["options"].items() if a.startswith("--")}
            self._cli = {False: (nm["commands"], options, choices),
                         True: (flip(nm["commands"]), flip(options), {(" ".join(nm["commands"].get(c, c) for c in [k]), options.get(o, o)): flip(d)
                                                                   for (k, o), d in choices.items()})}
        return self._cli[inv]

    def commands(self, text, inv=False):
        """Change 10: a Markdown text with each `bee <command>` (or a path to bee.py) inside its code, fenced blocks and code
        spans, renamed with its options and their choices (inv: back to French); prose, and everything else, as written."""
        out, pos = [], 0
        for a, b, span in code_regions(text):
            out += [text[pos:a], self.calls(text[a:b], inv, span)]
            pos = b
        return "".join(out) + text[pos:]

    def calls(self, code, inv, span=False):
        """One region of code: each invocation of bee renamed (up to a line's end, unless continued, a pipe, ;, &, ), a comment
        or the next bee; in a code span, a line's end is a blank), its global options, its command (a subcommand too), then
        each option and the choice it is given (each of a|b too)."""
        commands, options, choices = self.cli(inv)
        edits, found, space = {}, list(BEE.finditer(code)), " \t\n" if span else " \t"
        for k, m in enumerate(found):
            words, j, stop = [], m.end(), found[k + 1].start() if k + 1 < len(found) else len(code)
            while j < stop:
                if code[j] in space or code.startswith("\\\n", j):
                    j += 1 + (code[j] == "\\")
                    continue
                if code[j] in "\n|;&)" or code[j] == "#" and code[j - 1] in space:
                    break
                if not (w := ARG.match(code, j)):
                    break
                words.append((j, j + len(w[0]), w[0]))
                j += len(w[0])
            n = 0
            while n < len(words) and words[n][2].startswith("--"):  # the global options: --registre takes a value
                n += 1 + (words[n][2] in ("--registre", "--registry"))
            words[n:n + 2] = [(a, a + len(c), c) for a, _, w in words[n:n + 2] for c in [name_of(w)]]  # « relire, », « prendre──▶ »
            if n >= len(words) or words[n][2] not in commands and " ".join(x[2] for x in words[n:n + 2]) not in commands:
                continue
            command = " ".join(x[2] for x in words[n:n + 2]) if " ".join(x[2] for x in words[n:n + 2]) in commands else words[n][2]
            new = commands[command].split(" ")
            edits.update({words[n + x][:2]: y for x, y in enumerate(new) if words[n + x][2] != y})
            edits.update({w[:2]: options[w[2]] for w in words[:n] if w[2] in options})
            for x, (a, b, w) in enumerate(words[n + len(new):], n + len(new)):
                a += len(w) - len(w := w.lstrip("["))  # an optional option, written [--name value]
                name, equal, value = w.partition("=")
                given = choices.get((command, name), {})
                if name in options:
                    edits[a, a + len(name)] = options[name]
                at = (a + len(name) + 1, b) if equal else words[x + 1][:2] if name.startswith("--") and x + 1 < len(words) else None
                if at and given and all(v in given for v in code[at[0]:at[1]].split("|")):
                    edits[at] = "|".join(given[v] for v in code[at[0]:at[1]].split("|"))
        return rename.edited(code, {k: v for k, v in edits.items() if code[k[0]:k[1]] != v})

    def old_commands(self, text, path):
        """The scan of change 10: each old command name left after bee in the code of a file of the new tree (Markdown: its
        fenced blocks and code spans; a shell script or workflow: every region but its comments). [(line, text)]."""
        commands = self.names.m["cli"]["commands"]
        old = {k for k in commands if " " not in k and k not in commands.values()}
        subcommands = {(v.split(" ")[0], k.split(" ")[1]) for k, v in commands.items() if " " in k and k.split(" ")[1] != v.split(" ")[1]}
        regions = code_regions(text) if path.endswith(".md") else [(a, b, False) for a, b, k in self.regions(text, path) if k != "comment"]
        found = []
        for a, b, span in regions:
            for m in BEE.finditer(code := text[a:b]):
                s = r"\s" if span else r"[ \t]"
                if (w := re.match(rf"{s}+(?:--registr[ey]{s}+\S+{s}+)?([a-z][\w-]*)(?:{s}+([a-z][\w-]*))?", code[m.end():])) and (
                        w[1] in old or (w[1], w[2]) in subcommands):
                    found.append((text.count("\n", 0, a + m.start()) + 1, (m[0] + w[0])[:80]))
        return found

    def string(self, raw, path=""):
        """One string token renamed, its quoting kept: a program in Python as Python (if written as its value), a whole literal
        by whole(), any other text by text()."""
        prefix, q, body = re.fullmatch(r"([rRbBuU]*)('''|\"\"\"|'|\")(.*)\2", raw, re.S).groups()
        value = ast.literal_eval(raw)
        value = value.decode("utf-8", "surrogateescape") if isinstance(value, bytes) else value
        if is_python(value, raw):  # a fake tool's program, written to a file: its names as Python's (ruche-0152)
            return prefix + q + self.rename_python(value, path)[0] + q
        if (new := self.whole(value)) != value and body != value:
            raise rename.Problem(f"« {raw[:40]} » is written in a form the renamer does not edit")
        return prefix + q + (new if new != value else self.pieces(body) if not re.search(r"\s", value) else self.text(body)) + q

    def pieces(self, t):
        """A text without a blank: each piece between : and = renamed as a whole literal if shaped as one (HEAD:taches,
        soumission:refs/pull/1/head, sortie_compressee=identique) and each quoted value, else as a text (a pattern)."""
        t = re.sub(r"(?<=([\"']))[\w.-]+(?=\1)", lambda x: self.whole(x[0]), self.text(t))  # a quoted value: '"refus"' (a JSON's)
        return "".join(self.whole(x) if re.fullmatch(NAME_SHAPE, x) else x for x in re.split(r"([:=])", t))

    def rename_python(self, source, path=""):
        """A Python file renamed: identifiers (attrs after a dot), the names in strings and f-string parts (outside kept scopes
        and tokens); the rest as written, comments included. Returns (text, [(line, old token, new token)])."""
        (scopes, kept), keeping = self.kept(path), self.keeping
        lines, starts, tree, self.keeping = source.split("\n"), [0], ast.parse(source), kept  # lines as the tokenizer counts them (not at U+2028)
        [starts.append(starts[-1] + len(x) + 1) for x in lines]
        frozen = self.frozen(tree, scopes)
        roles = {(c.lineno, len(lines[c.lineno - 1].encode()[:c.col_offset].decode())) for c in identifier_strings(tree)}  # bytes -> characters
        data = {(k.lineno, len(lines[k.lineno - 1].encode()[:k.col_offset].decode())) for k in data_keywords(tree)}  # ruche-0153
        edits, changes, prev, where = {}, [], None, scopes_of(tree)
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            a, b = starts[tok.start[0] - 1] + tok.start[1], starts[tok.end[0] - 1] + tok.end[1]
            d, prev = self.attrs if prev == "." else self.ids, tok.string if tok.type not in (tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE) else prev
            if tok.type == tokenize.NAME and tok.start in data:  # a keyword argument that is a data key (**kwargs): as a key
                new = w if (w := self.whole(tok.string)).isidentifier() and not keyword.iskeyword(w) else tok.string
            elif tok.type == tokenize.NAME and tok.string in d:
                new = d[tok.string]
            elif tok.type in (tokenize.STRING, tokenize.FSTRING_MIDDLE) and tok.start[0] not in frozen:
                if source[a:b] != tok.string:
                    raise rename.Problem(f"{path}:{tok.start[0]}: a string part the tokenizer does not place")
                self.scoped(path, where[tok.start[0]], value := tok.string if tok.type != tokenize.STRING else str(ast.literal_eval(tok.string)))
                new = tok.string if value in kept else self.string(tok.string, path) if tok.type == tokenize.STRING else self.whole(tok.string) if \
                    re.fullmatch(NAME_SHAPE, tok.string) else self.pieces(tok.string) if not re.search(r"\s", tok.string) else self.text(tok.string)
                new = re.sub(r"\w+", lambda x: self.attrs.get(x[0], x[0]), tok.string) if tok.start in roles else new  # attributes, fields
                if kept and len(WORD.split(new)) == len(WORD.split(tok.string)):
                    new = "".join(o if o in kept else n for o, n in zip(WORD.split(tok.string), WORD.split(new)))
            else:
                continue
            if new != tok.string:
                edits[a, b] = new
                changes.append((tok.start[0], tok.string, new))
        cuts, self.tokens, self.keeping = [0, *(x for e in sorted(edits) for x in e), len(source)], self.base_tokens, keeping  # linear
        return "".join(source[cuts[i]:cuts[i + 1]] + edits.get((cuts[i + 1], cuts[i + 2]), "") for i in range(0, len(cuts) - 2, 2)) + source[cuts[-2]:], changes

    # --- shell scripts and workflows (ruche-0152): every name through the same map, region by region ---

    def regions(self, text, path):
        """(start, end, kind) of a shell script or workflow: comment (as written), key (a workflow's YAML key), code (every name),
        text (prose: compound names, $variables and whole phrases only), python (python3 -c '…', python3 - <<'X' documents). A
        here-document's quotes are characters: its lines are prose, a script's (#!…sh) shell, line by line."""
        out, pos, block, here, q, yml = [], 0, None, None, None, path.endswith((".yml", ".yaml"))
        for line in text.split("\n"):
            end, indent, sh = pos + len(line), len(line) - len(line.lstrip()), False
            block = None if block is not None and line.strip() and indent <= block[0] and here is None else block
            if here is not None and line.strip() == here[0]:  # the end of a here-document
                out += [(here[2], pos, "python")] * (here[1] == "python") + [(pos, end, "code")]
                here = None
            elif here is not None:
                here[1] = here[1] or ("sh" if re.match(r"#!.*\b(?:ba|da)?sh\b", line) else "text")  # a script a script writes: shell
                self.shell(line, pos, None, out) if here[1] == "sh" else None if here[1] == "python" else out.append((pos, end, "text"))
            elif block is not None or not yml:
                q, sh = (self.shell(line, pos, q, out), True) if block is None or block[1] else (out.append((pos, end, "text")), False)
            elif line.lstrip().startswith("#"):
                out.append((pos, end, "comment"))
            elif k := KEY.match(line):
                v, at = line[k.end():], pos + k.end()
                c = next((i for i, x in enumerate(v) if x == "#" and (i == 0 or v[i - 1] in " \t") and v[:i].count('"') % 2 == 0), len(v))
                out.append((pos, at, "key"))
                if re.fullmatch(r"[|>][-+]?\s*", v[:c]):
                    block = (indent, k[2] == "run")
                elif k[2] == "run" or v[:1] in "[{":  # a step's script; a flow collection, whose quotes are YAML's
                    self.shell(v if k[2] == "run" else v[:c], at, None, out)
                else:
                    out.append((at, at + c, "text" if re.search(r"\s", v[:c].strip().strip("\"'")) else "code"))
                out += [(at + c, end, "comment")] if c < len(v) and k[2] != "run" else []
            else:
                out.append((pos, end, "text"))
            if sh and here is None and q is None and (h := HEREDOC.search(line)):
                here = [h[2], "python" if re.search(r"\bpython3 -(?:\s|$)", line) else None, end + 1]
            pos = end + 1
        return out

    @staticmethod
    def shell(s, at, q, out):
        """One line of shell (at: its offset; q: the quote open at its start) cut into regions: a quote holds code if its text
        has no blank, prose otherwise, Python after python3 -c; # starting a word, unquoted, starts a comment. Returns the
        quote still open at its end."""
        i, start = 0, 0
        while i < len(s):
            c = s[i]
            if q is None and c == "#" and (i == 0 or s[i - 1] in " \t"):
                out += [(at + start, at + i, "code"), (at + i, at + len(s), "comment")]
                return None
            if c == "\\" and (q is None or q[0] == '"'):
                i += 2
                continue
            if q is None and c in "'\"":
                out.append((at + start, at + i + 1, "code"))
                q, start = (c, True, c == "'" and re.search(r"\bpython3 -c\s*$", s[:i]) is not None), i + 1
            elif q is not None and c == q[0]:
                out.append((at + start, at + i, "python" if q[2] else "code" if q[1] and not re.search(r"\s", s[start:i]) else "text"))
                q, start = None, i
            i += 1
        out.append((at + start, at + len(s), "code" if q is None else "text"))
        return q and (q[0], False, q[2])

    def rename_shell(self, text, path):
        """A shell script or workflow renamed by regions: code and keys by whole(), each run of name characters; text by text(),
        whole phrases and $variables; python by rename_python; comments and kept tokens as written. Returns (text, [(line,
        old, new)])."""
        kept, edits, changes = self.kept(path)[1], {}, []
        for a, b, kind in self.regions(text, path):
            self.scoped(path, "")
            self.keeping = kept
            x = text[a:b]
            new = self.rename_python(x, path)[0] if kind == "python" else RUN.sub(lambda m: self.whole(m[0]), x) if kind in ("code", "key") else \
                self.text(x) if kind == "text" else x
            if kind != "python" and kept and len(WORD.split(new)) == len(WORD.split(x)):
                new = "".join(o if o in kept else n for o, n in zip(WORD.split(x), WORD.split(new)))
            if new != x:
                edits[a, b] = new
                changes.append((text.count("\n", 0, a) + 1, x, new))
        self.tokens, self.keeping = self.base_tokens, set()
        return rename.edited(text, edits), changes

    def lint_shell(self, text, path, used=None):
        """A shell script or workflow against the map: each name it defines or reads (variables, functions, YAML keys, step and
        job ids, expression names, the embedded Python's identifiers) mapped or English; one English name per name in each of
        its namespaces (the shell's and the Python's variables and functions with the environment; the workflow's keys and ids);
        no program in python3 -c "…" (read as prose), no name of the map in a quoted jq filter (its keys and values are one text)."""
        sh, keys = set(), set(re.findall(r"^\s*(?:- )*id: *([\w-]+)", text, re.M)) if path.endswith(".yml") else set()  # step ids
        self.scoped(path, "")
        problems = []
        for a, b, kind in self.regions(text, path):
            x, before = text[a:b], text[text.rfind("\n", 0, a) + 1:a]
            problems += [f"line {text.count(chr(10), 0, a) + 1}: python3 -c with its program in double quotes: write it in single quotes or a "
                         "here-document (python3 - <<'X'), as the renamer reads Python"] if kind == "code" and re.search(r'\bpython3\s+-c\s*"', x) else []
            problems += [f"line {text.count(chr(10), 0, a) + 1}: a quoted jq filter holds {w}, a name of the map: its keys and values cannot be told "
                         "apart, read the JSON in Python" for w in sorted(set(re.findall(r"[A-Za-z_][\w-]*", x))) if (self.tokens.get(w, w) != w or w in self.hand)
                         and kind != "comment" and (re.search(r"\bjq\b(?:[^'\"|>;)&]|\"[^\"]*\")*['\"]$", before) or "select(" in x)]
            if kind == "python":
                sh |= {w for _, f, v in idents(ast.parse(x)) for w in (v.split(".") if f == "module" else [v])}
            elif kind != "comment":
                found = [(i, w) for m in re.finditer(r"\$\{?([A-Za-z_]\w*)|\b(?:steps|needs|inputs|jobs|env)\.([\w-]+)(?:\.outputs\.([\w-]+))?" + (
                    r"|(?:^|[\s;(])([A-Za-z_]\w*)\+?=|\b(?:read(?: -r)?|local|export)((?: +[A-Za-z_]\w*)+)|\bfor +([A-Za-z_]\w*) +in\b|\b([A-Za-z_]\w*)\(\) *\{"
                    r"|^[\s-]*([\w-]+):" if kind != "text" else ""), x) for i, g in enumerate(m.groups()) if g for w in g.split()]
                sh |= {w for i, w in found if i in (0, 3, 4, 5, 6) or i == 7 and w.isupper()}  # the environment's variables are keys too
                keys |= {w for i, w in found if i in (1, 2, 7)}
        lines = text.split("\n")  # a here-document read as prose (no shebang, not Python) whose $variables the renamer would rename alone
        problems += [f"line {n + 2}: a here-document without a shebang names ${v}, a name of the map: it is read as prose, its $variables renamed and "
                     "its words not; start it with #!/bin/sh, or leave the variable out" for n, line in enumerate(lines) if (h := HEREDOC.search(line))
                     and not re.search(r"\bpython3 -(?:\s|$)", line) and not re.match(r"#!.*\b(?:ba|da)?sh\b", lines[n + 1] if n + 1 < len(lines) else "")
                     for v in sorted(set(re.findall(r"\$\{?([A-Za-z_]\w*)", "\n".join(itertools.takewhile(lambda x: x.strip() != h[2], lines[n + 1:])))))
                     if self.tokens.get(v, v) != v or v in self.hand]
        problems += [f"identifier {x} is neither mapped nor made of English words" for x in sorted((sh | keys) - self.kept(path)[1])
                     if self.tokens.get(x, x) == x and not self.covered(x, False)]
        problems += self.clashes([(1, path, sh, self.tokens), (1, path, keys, self.tokens)]) + [
            f"identifier {x} is in test_identifiers: a name of the code belongs in identifiers" for x in sorted((sh | keys) & self.test_ids)]
        self.tokens = self.base_tokens
        (used if used is not None else set()).update(sh | keys)
        return problems + [p.partition(": ")[2] for p in self.stray(text, path, sh | keys)]

    def links(self, texts, path_of, defined):
        """P1b (b) for workflows and scripts ({path: text}): each job's needs and needs.<job>.outputs.<name>, each steps.<id>,
        each jobs.<id> of a reusable workflow's outputs, each workflow_run listener (a workflow's name), each workflow file
        named, and in the embedded Python each bee.<name> and test resolve. path_of: the file's path at the base. Returns
        {(path, what, name)} of those that do not."""
        out, flows = set(), {p: f for p, t in texts.items() if p.endswith(".yml") and isinstance(f := yaml.safe_load(t), dict)}
        names, files = {f.get("name") for f in flows.values()}, {p.rsplit("/", 1)[-1] for p in flows}
        for p, f in flows.items():
            jobs, on = f.get("jobs") or {}, f.get(True, f.get("on")) or {}
            for job in jobs.values():
                needs, ids, s = [job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs") or [], {x.get("id") for x in job.get("steps") or []}, json.dumps(job)
                out |= {(p, "needs", x) for x in needs if x not in jobs} | {(p, "steps", x) for x in re.findall(r"steps\.([\w-]+)\.outputs", s) if x not in ids}
                out |= {(p, "needs", f"{x}.outputs.{y}") for x, y in re.findall(r"needs\.([\w-]+)\.outputs\.([\w-]+)", s) if x not in needs or y not in (jobs.get(x) or {}).get("outputs", {})}
            out |= {(p, "jobs", x) for x in re.findall(r"jobs\.([\w-]+)\.outputs", json.dumps(on)) if x not in jobs}
            out |= {(p, "workflow_run", w) for w in ((on.get("workflow_run") if isinstance(on, dict) else None) or {}).get("workflows") or [] if w not in names}
        for p, t in texts.items():  # comments aside
            parts = [(k, t[a:b]) for a, b, k in self.regions(t, path_of(p)) if k != "comment"]
            out |= {(p, "workflow file", w) for _, x in parts for w in re.findall(r"workflows/([\w.-]+\.ya?ml)", x) if w not in files}
            out |= {(p, "bee", w) for k, x in parts if k == "python" for w in re.findall(r"(?<![\w.])bee\.([A-Za-z_]\w*)", x) if w not in defined}
            out |= {(p, "test", w) for _, x in parts for w in re.findall(r"\b[\w-]+\.test_bee\.(\w+(?:\.\w+)?)", x) if w not in defined}
        return out

    # --- the proofs: P1, P3, P1b ---

    def allowed(self, a, b):
        """A token of a text changes only to its English name (a hand token: as its role says), dot by dot if need be."""
        return b == self.tokens.get(a) or a not in self.hand and (self.in_tests or a not in self.test_ids) and b in (self.ids.get(a), self.attrs.get(a)) or \
            "." in a and a.count(".") == b.count(".") and all(x == y or self.allowed(x, y) for x, y in zip(a.split("."), b.split(".")))

    def string_change(self, a, b, role=False):
        """The (old, new) names by which string a became b, or None if it changed otherwise (role: an attribute-name string)."""
        if a == b or (re.sub(r"\w+", lambda x: self.attrs.get(x[0], x[0]), a) if role else self.whole(a)) == b:
            return [(a, b)] if a != b else []
        for x, y in ((p.split(a), p.split(b)) for p in (WORD, RUN)):  # word by word, else name run by name run
            changed, c = [i for i in range(1, min(len(x), len(y)), 2) if x[i] != y[i]], self.names.m["cli"]["commands"]  # a command after « bee »: a command
            if len(x) == len(y) and x[0::2] == y[0::2] and all(self.allowed(x[i], y[i]) or self.whole(x[i]) == y[i] or i > 1 and x[i - 1].isspace()
                                                                and y[i] == c.get(x[i]) and re.fullmatch(r"(?:.*/)?bee(?:\.py)?", x[i - 2]) for i in changed):
                return [(x[i], y[i]) for i in changed]

    def through(self, a, b, role=False):
        """string_change once a's whole phrases are renamed, else as it is (a phrase cut by a literal's end stays)."""
        x = self.string_change(self.phrased(a), b, role)
        return self.string_change(a, b, role) if x is None else x

    def same_python(self, old, new, counts, path=""):
        """P1 for one file: equal syntax trees once identifiers go through the map and strings (f-string parts included) through
        whole() or token by token; numbers, operators, structure identical; no two dict keys merge. counts: each mapping."""
        problems, tree, (scopes, kept), keeping = [], ast.parse(old), self.kept(path), self.keeping
        where, roles, frozen = scopes_of(tree), {(c.lineno, c.col_offset) for c in identifier_strings(tree)}, self.frozen(tree, scopes)
        data = data_keywords(tree)  # ruche-0153: keyword arguments that are data keys, renamed as keys
        self.keeping = kept

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
                    self.scoped(path, where[line], s)
                    if line not in frozen and s != t and "\n" in s.strip() and is_python(s, ast.get_source_segment(old, a)):  # a program: P1
                        problems.extend(f"line {line}: in its program, {p}" for p in self.same_python(s, t, counts, path))
                        self.scoped(path, where[line], s)
                        pairs = []
                    elif (pairs := [] if line in frozen else self.through(s, t, (a.lineno, a.col_offset) in roles)) is None:
                        problems.append(f"line {line}: the string « {s[:60]} » became « {t[:60]} », not through the map")
                    elif s != t and (line in frozen or any(p in kept for p, _ in pairs + [(s, t)])):  # a kept scope, a kept name
                        problems.append(f"line {line}: the string « {s[:60]} » became « {t[:60]} »: kept as written (identifiers.yaml, keep)")
                    counts.update(("string", p, q) for p, q in pairs or [])
                elif isinstance(x, str) and isinstance(y, str):
                    e = ".".join(self.ids.get(p, p) for p in x.split(".")) if f == "module" else (self.attrs if f == "attr" else self.ids).get(x, x)
                    if a in data and f == "arg":
                        e = w if (w := self.whole(x)).isidentifier() and not keyword.iskeyword(w) else x
                    problems.extend([f"line {line}: the identifier {x} became {y}, the map says {e}"] if y != e else [])
                    counts.update([("identifier", x, y)] if x != y else [])
                else:
                    same(x, y, line)
        same(tree, ast.parse(new), 1)
        self.tokens, self.keeping = self.base_tokens, keeping
        return problems

    def same_shell(self, old, new, counts, path):
        """P1 for a shell script or workflow: the same regions (quoting, comments, embedded Python); each comment as written;
        the Python by P1; elsewhere each token changed only to its English name (a whole phrase as one), a kept one never."""
        ra, rb, problems, kept = self.regions(old, path), self.regions(new, path), [], self.kept(path)[1]
        if [k in ("comment", "python") and k for *_, k in ra] != [k in ("comment", "python") and k for *_, k in rb]:  # a phrase may lose its blanks
            return ["its regions differ (quoting, comments or embedded Python moved): not a renaming"]
        for (a0, a1, kind), (b0, b1, _) in zip(ra, rb):
            x, y, n = old[a0:a1], new[b0:b1], old.count("\n", 0, a0)
            self.scoped(path, "")
            self.keeping = kept
            if kind == "python":
                problems += [re.sub(r"^line (\d+)", lambda m: f"line {int(m[1]) + n}", p) for p in self.same_python(x, y, counts, path)]
            elif x != y and (kind == "comment" or (pairs := self.through(x, y)) is None or
                             any(p in kept for p, _ in pairs)):
                problems.append(f"line {n + 1}: « {x.strip()[:60]} » became « {y.strip()[:60]} », " + (
                    "but a comment stays as written" if kind == "comment" else "not through the map" if pairs is None else "but it is kept as written"))
            elif x != y:
                counts.update(("string", p, q) for p, q in pairs)
        self.tokens, self.keeping = self.base_tokens, set()
        return problems

    def residue_shell(self, path, new):
        """P1b (a) for a shell script or workflow: renaming it again changes nothing (no French name left where names are)."""
        return [f"line {n}: « {a.strip()[:50]} » is still French (it would become « {b.strip()[:50]} »)" for n, a, b in self.rename_shell(new, path)[1]
                if a not in self.targets and (len(WORD.split(a)) != len(WORD.split(b)) or any(x != y and x not in self.targets for x, y in zip(WORD.split(a), WORD.split(b))))]

    def mapped_rows(self, rows):
        """P3: the old parser's rows as the map makes them (options by tokens, destinations by attrs, functions and set_defaults by ids)."""
        m = lambda x: (x[0], self.ids.get(x[1], x[1])) if isinstance(x, tuple) and x[:1] == ("function",) else self.whole(x) if isinstance(x, str) else \
            tuple(map(m, x)) if isinstance(x, tuple) else x  # noqa: E731
        return [(tuple(map(self.whole, r[0])), "defaults", tuple(sorted((self.ids.get(k, k), m(x)) for k, x in r[2]))) if r[1] == "defaults" else
                (tuple(map(self.whole, r[0])), tuple(self.tokens.get(o, o) for o in r[1]), self.attrs.get(r[2], r[2]), *r[3:5], *map(m, r[5:9]),
                 None if r[9] is None else tuple(sorted(m(r[9])))) for r in rows]

    def residue(self, path, new):
        """P1b (a): renaming the new file again changes nothing, and no string without a space holds a French name, but kept
        tokens, hand tokens and English names (« voter »: blind spots)."""
        tree, (scopes, kept) = ast.parse(new), self.kept(path)
        out = [f"line {n}: « {a[:50]} » is still French (it would become « {b[:50]} »)" for n, a, b in self.rename_python(new, path)[1]
               if a not in self.targets and (len(WORD.split(a)) != len(WORD.split(b)) or any(
                   x != y and x not in self.targets for x, y in zip(WORD.split(a), WORD.split(b))))]
        frozen, seen, where = self.frozen(tree, scopes), {int(x.split(":")[0][5:]) for x in out}, scopes_of(tree)
        return out + [f"line {c.lineno}: « {c.value[:50]} » holds the French name « {w} »" for c in ast.walk(tree) if isinstance(c, ast.Constant)
                      and isinstance(c.value, str) and not re.search(r"\s", c.value) and c.lineno not in frozen | seen and c.value not in kept and not self.names.kept_path(c.value) for w in dict.fromkeys(
                          re.findall(r"[\w-]+", c.value)) if self.named.get(w, w) != w and w not in self.hand.keys() | self.targets | kept | self.kept_here(path, where[c.lineno])]

    def attribute_names(self, tree, dests):
        """P1b (b): each attribute-name string and args.<name> (dests: the tool's) names an attribute of the new code or a
        destination; each placeholder of a template given to format() by keyword is one of its keywords."""
        consts = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(getattr(n.value, "value", None), str) for t in n.targets
                  if isinstance(t, ast.Name)}
        formats = [(n, n.func.value.value if isinstance(n.func.value, ast.Constant) else consts.get(getattr(n.func.value, "id", None))) for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "format" and n.keywords and not n.args and all(k.arg for k in n.keywords)]
        defined, dests = {v for _, _, v in idents(tree)} | (dests or set()), dests if dests is not None else ()
        found = [((getattr(n, "args", None) or [None])[0], c) for n in ast.walk(tree) for c in identifier_strings(n, False)]
        found += [(n.value, ast.Constant(n.attr, lineno=n.lineno)) for n in ast.walk(tree) if isinstance(n, ast.Attribute) and getattr(n.value, "id", None) == "args" and dests]
        bad = lambda s, r: s not in dests if getattr(r, "id", None) == "args" else s not in defined and (  # noqa: E731
            s in self.attrs or self.tokens.get(s, s) != s or not self.covered(s))
        return [f"line {s.lineno}: « {s.value} » names no attribute of the new code" + (" and no parser destination" if getattr(r, "id", None) == "args" else "")
                for r, s in found if isinstance(s, ast.Constant) and isinstance(s.value, str) and bad(s.value, r)] + [
            f"line {n.lineno}: the template's « {{{x}}} » is given by no keyword of format()" for n, t in formats if isinstance(t, str)
            for x in sorted(set(re.findall(r"(?<!\{)\{([A-Za-z_]\w*)", t)) - {k.arg for k in n.keywords})]

def data_keywords(tree):
    """ruche-0153: the keyword arguments that are data, not names of the code: given to dict(), patch.dict() or .update() (keys,
    environment variables), or to a function of this file, called by its name, that takes them in **kwargs (every def of that name
    lacks that parameter), as a fake API's fields (status="in_progress")."""
    defs = collections.defaultdict(list)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):  # (takes **kwargs, its parameters)
            defs[n.name].append((n.args.kwarg is not None, {x.arg for x in ast.walk(n.args) if isinstance(x, ast.arg)}))
    return {k for c in ast.walk(tree) if isinstance(c, ast.Call) for k in c.keywords if k.arg and (
        (n := c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, "attr", None)) in ("dict", "update") and n not in defs or
        defs.get(n) and all(takes and k.arg not in p for takes, p in defs[n]))}


def identifier_strings(tree, deep=True):
    """The string constants that are attribute names: given to getattr, setattr, hasattr or delattr, a key of vars(x), the
    fields of a namedtuple or __slots__; the first argument of add_argument without dashes, and every dest= (destinations)."""
    of = lambda e: isinstance(e, ast.Call) and getattr(e.func, "id", None) == "vars"  # noqa: E731
    for n in ast.walk(tree) if deep else [tree]:
        if isinstance(n, ast.Call):
            name = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
            yield from [n.args[1]] if name in ("getattr", "setattr", "hasattr", "delattr") and len(n.args) > 1 else \
                [n.args[0]] if name == "add_argument" and n.args and not str(getattr(n.args[0], "value", "-")).startswith("-") else []
            yield from (k.value for k in n.keywords if k.arg == "dest")
            yield from n.args[:1] if isinstance(n.func, ast.Attribute) and of(n.func.value) else n.args[1:2] if name == "namedtuple" else []
        yield from n.value.elts if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "__slots__" and hasattr(n.value, "elts") else []
        yield from [n.slice] if isinstance(n, ast.Subscript) and of(n.value) else [n.left] if isinstance(n, ast.Compare) and of(n.comparators[0]) else []


def name_of(word):
    """A command line's word as a command's name: its leading name when the rest holds no letter (« relire, », « prendre──▶ »)."""
    m = re.match(r"[a-z][\w-]*", word)
    return m[0] if m and not re.search(r"\w", word[m.end():]) else word


def code_regions(text):
    """(start, end, span) of a Markdown text's code: each fenced block's lines, together (not its fences: a command continued by « \\ »
    on the next line), each code span's content (spans stay inside one paragraph; span: True); the rest is prose."""
    out, pos, opening, paragraph, inside = [], 0, None, [], False

    def flush():
        if paragraph:
            out.extend((paragraph[0] + m.start(2), paragraph[0] + m.end(2), True) for m in SPAN.finditer(text[paragraph[0]:paragraph[1]]))
        paragraph.clear()
    for line in text.split("\n"):
        end, m = pos + len(line), BLOCK.match(line)
        if opening is not None:
            if m and m[1][0] == opening[0] and len(m[1]) >= len(opening) and not line[m.end():].strip():
                opening = None
            elif out and not out[-1][2] and out[-1][1] == pos - 1 and inside:  # the block's next line
                out[-1] = (out[-1][0], end, False)
            else:
                out.append((pos, end, False))
                inside = True
        elif m:
            flush()
            opening, inside = m[1], False
        elif not line.strip():
            flush()
        else:
            paragraph[:] = [paragraph[0] if paragraph else pos, end]
        pos = end + 1
    flush()
    return out


def is_python(text, raw):
    """A program in Python inside a string, written as its value in one literal (raw): lines, at least one import, def or
    assignment, and no syntax error."""
    try:
        return "\n" in text.strip() and re.fullmatch(r"[rRuU]*('\'\'|\"\"\"|'|\")(.*)\1", raw or "", re.S)[2] == text and any(isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign)) for n in ast.parse(text).body)
    except (SyntaxError, ValueError, TypeError):
        return False


def scopes_of(tree):
    """The innermost def or class, or top-level assignment, of each line: the role table's scope."""
    out, top = collections.defaultdict(str), {id(n) for n in tree.body}
    for n in ast.walk(tree):  # breadth first: an inner scope overrides its outer one
        name = n.name if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else \
            getattr((getattr(n, "targets", None) or [getattr(n, "target", None)])[0], "id", None) if id(n) in top else None
        out.update(dict.fromkeys(range(n.lineno, n.end_lineno + 1), name) if name else {})
    return out


def check(repo, base, head, new_rows=None):
    """P1, P1b (a, b) and P3 (plan, sections 9 and 12, change 2); P1b (c), the migrated fixture's scans and data, is ruche-0143's.
    new_rows(path, builder): the new tool's parser rows (default: rows_here; bee check-migration reads them in a worker, so that
    the process that decides loads no code of the head). Returns (problems, counts of each mapping)."""
    files, after, none = rename.tree_files(repo, base), rename.tree_files(repo, head), collections.Counter()
    if (at := next((c for c in rename.MAPS if c in files), None)) is None or IDS[rename.MAPS.index(at)] not in files:
        return [f"no {rename.MAP} and {IDS[0]} at the base {base}"], none
    tools_dir = at.rpartition("/migration/")[0]
    for path, live in ((f"{tools_dir}/migration/rename_code.py", SELF), (f"{tools_dir}/migration/rename.py", rename.SELF),
                       (f"{tools_dir}/bee.py", pathlib.Path(bee.__file__).resolve())):
        if files.get(path) != live.read_bytes():
            return [f"{live} is not the base's {path}: run the base's own checker, python3 -I, from its checkout"], none
    names = rename.Names(files[at].decode("utf-8"))
    cm, code = CodeMap(names, files[IDS[rename.MAPS.index(at)]].decode("utf-8")), {p: files[p].decode("utf-8") for p in names.code}
    problems, counts, tool, trees, heads = [f"the map: {x}" for x in cm.lint(code)], collections.Counter(), names.path(f"{tools_dir}/bee.py"), {}, {}
    for p, text in code.items():
        try:
            if re.match(r"\ufeff|([^\n]*\n)?[ \t\f]*#.*?coding[:=]", new := after[q := names.path(p)].decode("utf-8")):
                raise rename.Problem("a byte order mark or a coding declaration: the code is read as UTF-8, nothing else")
            if not p.endswith(".py"):  # a shell script or a workflow
                problems += [f"{q}: {x}" for x in cm.same_shell(text, new, counts, p)] or [f"P1b: {q}: {x}" for x in cm.residue_shell(p, new)]
                heads[q] = new
                continue
            problems += [f"{q}: {x}" for x in cm.same_python(text, new, counts, p)] or [f"P1b: {q}: {x}" for x in (
                [] if p in cm.m["pending"] else cm.residue(p, new))]  # a pending file: its own names are not mapped yet
            trees[q] = ast.parse(new)
        except (KeyError, SyntaxError, UnicodeDecodeError, rename.Problem) as e:
            problems.append(f"{q}: {'not in the head' if isinstance(e, KeyError) else f'{type(e).__name__}: {e}'}")
    tests, empty = f"{tools_dir}/test_bee.py", ast.Module([], [])
    was = {(names.path(p), w, cm.whole(x)) for p, w, x in cm.links({p: t for p, t in code.items() if not p.endswith(".py")}, str, defined_names(
        ast.parse(code[f"{tools_dir}/bee.py"]), ast.parse(code[tests]) if tests in code else empty))}  # at the base: a fork's file
    problems += [f"P1b: {p}: the {w} « {x} » names nothing in the head" for p, w, x in sorted(cm.links(heads, str, defined_names(
        trees.get(tool, empty), trees.get(names.path(tests), empty))) - was)]
    if any(x.startswith(f"{tool}: ") for x in problems):
        return problems + [f"P3 and P1b (b) not run: P1 does not hold for {tool}"], counts
    with tempfile.TemporaryDirectory() as tmp:  # P1 holds: the new tool is the base's code modulo the map, it may run
        (path := pathlib.Path(tmp) / tool).parent.mkdir(parents=True)
        path.write_bytes(after[tool])
        try:
            rows = parser_rows(bee.construire_analyseur()), (new_rows or rows_here)(path, cm.ids.get("construire_analyseur", "construire_analyseur"))
        except Exception as e:  # noqa: BLE001 - a new tool that does not load is a refusal, never a crash
            return problems + [f"P3 and P1b (b) not run: {tool} does not load: {type(e).__name__}: {e}"], counts
    cm.scoped(f"{tools_dir}/bee.py", "construire_analyseur")  # the parser's names are that function's
    problems += [f"P3: bee {' '.join((a or b)[0])} {'/'.join((a or b)[1]) if (a or b)[1] != 'defaults' else 'defaults'}: the map gives {a!r:.160}, the "
                 f"new parser has {b!r:.160}" for a, b in itertools.zip_longest(cm.mapped_rows(rows[0]), rows[1]) if a != b]
    dests = {r[2] for r in rows[1] if r[1] != "defaults"} | {k for r in rows[1] if r[1] == "defaults" for k, _ in r[2]}
    return problems + [f"P1b: {q}: {x}" for q, t in trees.items() for x in cm.attribute_names(t, dests if q == tool else None)], counts


def rows_here(path, builder):
    """P3: the parser rows of the tool at path, loaded in this process."""
    spec = importlib.util.spec_from_file_location("bee_after_the_move", path)
    spec.loader.exec_module(new := importlib.util.module_from_spec(spec))
    return parser_rows(getattr(new, builder)())


def defined_names(tool, tests):
    """What a workflow's embedded Python and test runs may name: the tool's top-level names, the test classes and their
    methods (Class.method, inherited ones included)."""
    classes = {c.name: c for c in tests.body if isinstance(c, ast.ClassDef)}
    methods = lambda c: {m.name for m in c.body if isinstance(m, ast.FunctionDef)}.union(*(methods(classes[b.id]) for b in c.bases if getattr(b, "id", None) in classes))  # noqa: E731
    return {getattr(n, "name", None) for n in tool.body} | {x.id for n in tool.body if isinstance(n, (ast.Assign, ast.AnnAssign)) for x in ast.walk(n)
                                                             if isinstance(x, ast.Name)} | set(classes) | {f"{c}.{m}" for c, k in classes.items() for m in methods(k)}


def parser_rows(parser, path=()):
    """P3: an argparse parser as rows, help texts aside: (subcommand path, options, destination, nargs, required, default,
    const, type, metavar, sorted choices) per action, (path, "defaults", set_defaults) per parser."""
    v = lambda x: ("function", x.__name__) if callable(x) and hasattr(x, "__name__") else tuple(x) if isinstance(x, (list, tuple)) else x  # noqa: E731
    rows = [(path, "defaults", tuple(sorted((k, v(x)) for k, x in parser._defaults.items())))]
    for a in parser._actions:
        sub = a.choices if isinstance(a, argparse._SubParsersAction) else {}
        rows.append((path, tuple(a.option_strings), a.dest, a.nargs, a.required, v(a.default), v(a.const), v(a.type), v(a.metavar),
                     None if sub or a.choices is None else tuple(sorted(v(a.choices)))))
        rows += [r for k, p in sub.items() for r in parser_rows(p, path + (k,))]
    return rows


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
            problems = CodeMap(names, read(IDS[0])).lint({q: read(q) for q in names.code})
    except (rename.Problem, bee.ErreurBee, yaml.YAMLError, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems = [f"{type(e).__name__}: {e}"]
    print("".join(f"{k}: {x} -> {y}: {n}\n" for (k, x, y), n in sorted(counts.items(), key=lambda c: (-c[1], c[0]))), end="")  # lint: none
    print("".join(f"✗ {x}\n" for x in problems) + f"{len(problems)} problem(s)." if problems else
          f"✓ P1, P1b and P3 hold at {a.base} for the head {a.head}: {len({x for k, x, _ in counts if k == 'identifier'})} identifiers and "
          f"{len({x for k, x, _ in counts if k == 'string'})} names in strings renamed through the map ({sum(counts.values())} places), nothing "
          "else changed; no French name left, every attribute name resolves, the parser is the same." if a.action == "check" else
          "✓ the identifier map covers the code.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
