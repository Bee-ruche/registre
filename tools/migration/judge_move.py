#!/usr/bin/env python3
"""ruche-0148, J1 (docs/english-migration.md, section 6): the common judge moves from outils/juge/ to tools/judge/, its Python
identifiers and its CLI options in English, written by this script and proven by P1 (rename_code.py); what a fork reads from the
judge stays as written (J2 makes it dual).
    python3 -I tools/migration/judge_move.py write --base REV
    python3 -I tools/migration/judge_move.py check --base REV --head REV
write: the judge's files of REV at their paths in names.yaml (paths), written in this checkout. A Python file the map does not
keep (identifiers.yaml, judge: kept_files) is renamed: each identifier through identifiers.yaml (after a dot, as an attribute),
the plugin's names aside (judge: kept_names, kept_attributes, kept_data); in its strings, only the judge's options (names.yaml,
cli: scripts), the paths of its files and attribute names (getattr, mock.patch.object…). Every other file and string stays byte
for byte. The workflows that run the judge get the same options and paths.
check: writes again from the base, in memory: the head must hold exactly that; then P1 per renamed file (the syntax tree after is
the tree before modulo the map), every changed string an option, a path or an attribute name, the kept names derived from the code,
no two names of a scope merged, no name defined under one English name and read under another. Maps and code: this checkout's.
Exit 0: proven, as the last line says; 1: problems, listed.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("judge_move.py: run it isolated, python3 -I tools/migration/judge_move.py …, so that nothing shadows a module")

import argparse, ast, collections, io, keyword, pathlib, re, subprocess, tokenize  # noqa: E401, E402

SELF = pathlib.Path(__file__).resolve()
ROOT = SELF.parents[2]
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import rename, rename_code as rc  # noqa: E402, E401

OLD, WORKFLOWS = "outils/juge/", (".github/workflows/juge.yml", ".github/workflows/juge-commun.yml", ".github/workflows/suite.yml")
SCRIPTS = ("outils/juge/juge.py", "outils/juge/rapport.py")  # the judge's command lines (names.yaml, cli: scripts)


def git(*args, raw=False):
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout
    return out if raw else out.decode("utf-8")


def judge_map():
    """names.yaml and identifiers.yaml of this checkout, as the judge reads them: the code map minus the plugin's names."""
    names = rename.Names((ROOT / rename.MAP).read_text(encoding="utf-8"))
    cm = rc.CodeMap(names, (ROOT / rc.IDS[0]).read_text(encoding="utf-8"))
    j = cm.m["judge"]
    [cm.ids.pop(t, None) for t in j["kept_names"]]
    [cm.attrs.pop(t, None) for t in j["kept_attributes"]]
    [d.pop(t, None) for t in j["kept_data"] for d in (cm.base_tokens.maps[1], cm.test_tokens, cm.named, cm.hand, cm.m["hand"])]
    kept = [rename.glob_re(g) for g in j["kept_files"]]
    options = {a: b for s in SCRIPTS for a, b in names.m["cli"]["scripts"][s].items() if a != b}
    files = {a[len(OLD):]: b.rpartition("/")[2] for a, b in names.m["paths"].items() if a.startswith(OLD) and a != OLD}
    return names, cm, j, kept, options, files


class Judge:
    def __init__(self):
        self.names, self.cm, self.j, self.kept, self.options, self.files = judge_map()
        self.new_dir = self.names.path(OLD)
        self.option_re = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, sorted(self.options, key=len, reverse=True))) + r")(?![\w-])")
        self.dir_re = re.compile(r"(?<![\w.-])" + re.escape(OLD.rstrip("/")) + r"(?:/([\w.-]+))?(?![\w-])")
        self.file_re = re.compile(r"(?<![\w./-])(" + "|".join(map(re.escape, self.files)) + r")(?![\w-])")

    def texts(self, s):
        """A string's text: the judge's options, its folder and the paths and names of its renamed files; nothing else."""
        s = self.option_re.sub(lambda m: self.options[m[1]], s)
        s = self.dir_re.sub(lambda m: self.new_dir.rstrip("/") + (f"/{self.files.get(m[1], m[1])}" if m[1] else ""), s)
        return self.file_re.sub(lambda m: self.files[m[1]], s)

    def renamed(self, path):
        return path.endswith(".py") and not any(r.match(path) for r in self.kept)

    def rename_python(self, source, path):
        """One Python file: identifiers through the judge's map (attrs after a dot, the data keywords as P1 reads them), strings
        through texts(), attribute-name strings word by word as attributes, the path outils/juge given as two arguments."""
        cm, tree, lines = self.cm, ast.parse(source), source.split("\n")
        at = lambda n: (n.lineno, len(lines[n.lineno - 1].encode()[:n.col_offset].decode()))  # noqa: E731 (bytes -> characters)
        roles = {at(c) for c in rc.identifier_strings(tree)} | {at(n.args[1]) for n in ast.walk(tree) if isinstance(n, ast.Call)
                                                               and patched(n) and len(n.args) > 1 and isinstance(n.args[1], ast.Constant)}
        data, segments, where = {at(k) for k in rc.data_keywords(tree)}, {}, rc.scopes_of(tree)
        for n in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
            for x, y in zip(n.args, n.args[1:]):
                if [getattr(x, "value", None), getattr(y, "value", None)] == OLD.strip("/").split("/"):
                    segments.update(zip((at(x), at(y)), self.new_dir.strip("/").split("/")))
        starts, out, prev, last = [0], [], None, 0
        [starts.append(starts[-1] + len(x) + 1) for x in lines]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            a, b = starts[tok.start[0] - 1] + tok.start[1], starts[tok.end[0] - 1] + tok.end[1]
            new, d = tok.string, cm.attrs if prev == "." else cm.ids
            prev = tok.string if tok.type not in (tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE) else prev
            if tok.type == tokenize.NAME and tok.start in data:  # as P1 reads it: with the tokens of its scope
                cm.scoped(path, where[tok.start[0]])
                new = w if (w := cm.whole(tok.string)).isidentifier() and not keyword.iskeyword(w) else tok.string
                cm.tokens = cm.base_tokens
            elif tok.type == tokenize.NAME:
                new = d.get(tok.string, tok.string)
            elif tok.type == tokenize.STRING and tok.start in roles:
                new = re.sub(r"(?<=['\"])\w+(?=['\"])", lambda x: cm.attrs.get(x[0], x[0]), tok.string)
            elif tok.type == tokenize.STRING and tok.start in segments:
                new = tok.string.replace(tok.string.strip("'\""), segments[tok.start])
            elif tok.type in (tokenize.STRING, tokenize.FSTRING_MIDDLE):
                new = self.texts(tok.string)
            if new != tok.string:
                assert source[a:b] == tok.string, f"{path}:{tok.start[0]}: a token the tokenizer does not place"
                out += [source[last:a], new]
                last = b
        return "".join(out) + source[last:]

    def write(self, base):
        """{new path: bytes} of the judge's files at base, and the workflows that run it."""
        out = {}
        for p in git("ls-tree", "-r", "--name-only", base, OLD).split("\n"):
            if p:
                blob = git("show", f"{base}:{p}", raw=True)
                out[self.names.path(p)] = self.rename_python(blob.decode("utf-8"), p).encode("utf-8") if self.renamed(p) else blob
        for w in WORKFLOWS:
            out[w] = self.texts(git("show", f"{base}:{w}")).encode("utf-8")
        return out

    def contract(self, base):
        """The plugin's names, from the code: the modules a plugin imports (the kept files') and the names they define (module
        and class level, self attributes, namedtuple fields); in the renamed files, a kept module's name and each name imported
        from one (bare), each kept name read after a dot or in an attribute-name string, each keyword of a call to a kept name."""
        files = [p for p in git("ls-tree", "-r", "--name-only", base, OLD).split("\n") if p.endswith(".py")]
        trees = {p: ast.parse(git("show", f"{base}:{p}")) for p in files}
        modules = {p.rpartition("/")[2][:-3] for p in files if not self.renamed(p)}
        defined, mine = set(), set()
        for p in (p for p in files if not self.renamed(p)):
            defined |= top_level(trees[p])
            defined |= {n.attr for n in ast.walk(trees[p]) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                        and getattr(n.value, "id", None) == "self"}
            defined |= {f for n in ast.walk(trees[p]) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "namedtuple"
                        for f in n.args[1].value.split()}
        names, attrs = set(), set()
        for p in (p for p in files if self.renamed(p)):
            t = trees[p]
            mine |= top_level(t)
            imported = {a.asname or a.name for n in ast.walk(t) if isinstance(n, ast.ImportFrom) and n.module in modules for a in n.names}
            names |= imported | {a.name for n in ast.walk(t) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names if a.name in modules}
            roles = {w for c in rc.identifier_strings(t) for w in re.findall(r"\w+", str(getattr(c, "value", "")))}
            attrs |= ({n.attr for n in ast.walk(t) if isinstance(n, ast.Attribute)} | roles) & defined
            names |= {k.arg for n in ast.walk(t) if isinstance(n, ast.Call) and k_name(n.func) in defined and (
                isinstance(n.func, ast.Attribute) or k_name(n.func) in imported) for k in n.keywords if k.arg and k.arg != k_name(n.func)}
            names |= {k.arg for n in ast.walk(t) if isinstance(n, ast.Call) and k_name(n.func) == "_replace" for k in n.keywords
                      if k.arg in defined}  # a field of a kept namedtuple (Entree._replace(nom=…))
        return names | (mine & attrs), attrs  # a name of a renamed module read after a dot under a kept name (rapport.lire)

    def check(self, base, head):
        problems, counts, cm = [], collections.Counter(), self.cm
        expected, kept_names, kept_attrs = self.write(base), *self.contract(base)
        for what, declared, found in (("kept_names", self.j["kept_names"], kept_names), ("kept_attributes", self.j["kept_attributes"], kept_attrs)):
            found = {t for t in found if t in rc.CodeMap(self.names, (ROOT / rc.IDS[0]).read_text(encoding="utf-8")).attrs}  # those the map renames
            problems += [f"identifiers.yaml, judge: {what} is not what the code gives: missing {sorted(found - set(declared))}, "
                         f"extra {sorted(set(declared) - found)}"] if set(declared) != found else []
        at_head = {p for p in git("ls-tree", "-r", "--name-only", head, OLD.rstrip("/"), self.new_dir.rstrip("/")).split("\n") if p}
        problems += [f"{p}: in the head, not written from the base" for p in sorted(at_head - set(expected))]
        got = {}
        for p, blob in sorted(expected.items()):
            try:
                got[p] = git("show", f"{head}:{p}", raw=True)
            except subprocess.CalledProcessError:
                problems.append(f"{p}: not in the head")
                continue
            problems += [f"{p}: not what this script writes from the base"] if got[p] != blob else []
        for p in (p for p in git("ls-tree", "-r", "--name-only", base, OLD).split("\n") if p and self.renamed(p)):
            q = self.names.path(p)
            if q not in got:
                continue
            old, new = git("show", f"{base}:{p}"), got[q].decode("utf-8")  # P1 reads the head itself
            here = collections.Counter()
            problems += [f"P1: {q}: {x}" for x in cm.same_python(old, new, here, p)]
            allowed = {**self.options, **{OLD.rstrip("/"): self.new_dir.rstrip("/")}, **self.files}
            for (kind, a, b), n in here.items():
                if kind == "string" and not (allowed.get(a) == b or a in self.files and self.files[a] == b or self.texts(a) == b
                                             or cm.attrs.get(a) == b or a in OLD.split("/") + ["outils", "juge"] and b in self.new_dir.split("/")):
                    problems.append(f"{q}: the string « {a} » became « {b} »: not an option, a path or an attribute name")
            counts += here
            tree = ast.parse(old)
            problems += [f"{q}: {x}" for x in cm.collisions(tree, p)]
            problems += [f"{q}: {x} is defined as {cm.ids.get(x, x)} and read as an attribute as {cm.attrs.get(x, x)}" for x in sorted(top_level(tree))
                         if cm.attrs.get(x, x) != cm.ids.get(x, x)]
        return problems, counts


def top_level(tree):
    """The names a module defines that another reads after a dot: its functions, classes and assignments, a class's own."""
    out, todo = set(), list(tree.body)
    while todo:
        n = todo.pop()
        out |= {n.name} if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else {
            x.id for t in getattr(n, "targets", []) for x in ast.walk(t) if isinstance(x, ast.Name)}
        todo += n.body if isinstance(n, ast.ClassDef) else []
    return out


def patched(n):
    """mock.patch.object(target, "name", …): its name is an attribute name."""
    return isinstance(n.func, ast.Attribute) and n.func.attr == "object" and getattr(n.func.value, "attr", None) == "patch"


def k_name(f):
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def main(argv=None):
    p = argparse.ArgumentParser(prog="judge_move.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("write").add_argument("--base", required=True)
    c = sub.add_parser("check")
    [c.add_argument(o, required=True) for o in ("--base", "--head")]
    a, judge = p.parse_args(argv), Judge()
    a.base, a.head = (git("rev-parse", "--verify", f"{r}^{{commit}}").strip() if r else r for r in (a.base, getattr(a, "head", None)))
    if a.action == "write":
        for path, blob in judge.write(a.base).items():
            (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / path).write_bytes(blob)
        print(f"written from {a.base}: the judge at {judge.new_dir}, the workflows {', '.join(WORKFLOWS)}")
        return 0
    problems, counts = judge.check(a.base, a.head)
    print("".join(f"{k}: {x} -> {y}: {n}\n" for (k, x, y), n in sorted(counts.items(), key=lambda c: (-c[1], c[0]))), end="")
    ids, strings = {x for k, x, _ in counts if k == "identifier"}, {x for k, x, _ in counts if k == "string"}
    print("".join(f"✗ {x}\n" for x in problems) + f"{len(problems)} problem(s)." if problems else
          f"✓ the head {a.head} holds the judge this script writes from {a.base}; P1 holds: {len(ids)} identifiers and {len(strings)} "
          f"strings (options, paths, attribute names) renamed through the map ({sum(counts.values())} places), nothing else changed; "
          f"kept as written: {len(judge.j['kept_files'])} file globs, {len(judge.j['kept_names'])} names, {len(judge.j['kept_attributes'])} "
          f"attributes, {len(judge.j['kept_data'])} data keywords.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
