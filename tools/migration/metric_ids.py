#!/usr/bin/env python3
"""ruche-0149, step 5 (docs/english-migration.md, section 6): the metric ids in English in the registry's data, written by this
script and proven by P2: the switch's translator (rename.py) on the families' English side, the domain metric_id alone.
    python3 -I tools/migration/metric_ids.py write|check --base REV [--head REV]
The map is names.yaml at REV (domain metric_id, metric_step), read from git; this script, rename.py and bee.py must be REV's own.
write: each file of REV that metric_step lists, translated, in this checkout: a data file's metric ids at its family's places, at the
text level (order, quoting, comments, wrapping kept), and in a live task (metric_step: prose) the ids written as whole words in its
prose keys' texts; a code file's ids written as whole words in its strings and comments. check: each data file translates back to
itself byte for byte, its values are the map applied and every other scalar the same; a code file changes only strings and
comments, each by the map; with --head, the head holds exactly that, every other file of REV byte for byte, none added. Exit 0:
proven, as the last line says; 1: problems, listed.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("metric_ids.py: run it isolated, python3 -I tools/migration/metric_ids.py …, so that nothing shadows a module")

import argparse, collections, io, itertools, pathlib, re, subprocess, tokenize  # noqa: E401, E402

SELF = pathlib.Path(__file__).resolve()
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import yaml  # noqa: E402
import bee, rename  # noqa: E402, E401

MAP, DOMAIN = "tools/migration/names.yaml", "metric_id"
WORDS = (tokenize.STRING, tokenize.COMMENT, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING))


class Step:
    """The step's map: a rename.Names whose families are metric_step's, on their English side (their keys as they are, their paths
    written in English), with the domain metric_id alone at its places; every other scalar is a leaf."""

    def __init__(self, text):
        full = rename.Names(text)
        self.step, self.ids = full.m["metric_step"], full.m["domains"][DOMAIN]
        families = {}
        for name, globs in self.step["families"].items():
            side = full.side(name, True)  # keys: English -> French; places written in English
            families[name] = {"files": globs, "writer": "text", "keys": {k: k for k in side["keys"]},
                              "values": {p: d for p, d in side["values"].items() if d == DOMAIN},
                              "key_values": {p: d if d == DOMAIN else None for p, d in side["kv"].items()}}
        self.names = rename.Names(yaml.safe_dump({"families": families, "domains": {DOMAIN: self.ids}, "open_domains": {},
                                                  "tree": {"segments": {}, "dir": ["tree", "tree"]}, "paths": {}, "hand": [],
                                                  "code": [], "new": []}, allow_unicode=True))
        self.code = [rename.glob_re(g) for g in self.step["code"]]
        renamed = {a: b for a, b in self.ids.items() if a != b}
        self.word = {inv: (re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(map(re.escape, sorted(d, key=len, reverse=True))) + r")(?![A-Za-z0-9_])"), d)
                     for inv, d in ((False, renamed), (True, {b: a for a, b in renamed.items()}))}

    def problems(self):
        """The domain one-to-one, between metric ids; the prose rule on a family of the step."""
        english = list(self.ids.values())
        return ([f"metric_id: « {a} » -> « {b} »: not two metric ids" for a, b in self.ids.items()
                 if not all(isinstance(x, str) and re.fullmatch(r"[a-z0-9_]{1,60}", x) for x in (a, b))]
                + [f"metric_id: two French ids share the English id « {b} »" for b in sorted({str(b) for b in english if english.count(b) > 1})]
                + ["metric_step: prose: not a family of the step"] * (self.step["prose"]["family"] not in self.step["families"]))

    def words(self, s, inv=False):
        pattern, d = self.word[inv]
        return pattern.sub(lambda m: d[m[1]], s)

    def kind(self, path):
        fams = self.names.families_of(path)
        return ("data", fams[0]) if len(fams) == 1 else ("code", None) if any(r.match(path) for r in self.code) else (None, None)

    def live(self, name, doc):
        p = self.step["prose"]
        return name == p["family"] and isinstance(doc, dict) and doc.get("status") in p["status"]

    def prose_doc(self, name, doc, inv=False):
        """A document's values with the prose rule applied: its prose keys' texts, whole words."""
        if not self.live(name, doc):
            return doc
        w = lambda o: self.words(o, inv) if isinstance(o, str) else [w(x) for x in o] if isinstance(o, list) else o  # noqa: E731
        return {k: w(v) if k in self.step["prose"]["keys"] else v for k, v in doc.items()}

    def prose_text(self, name, text, inv=False):
        """The prose rule at the text level: each scalar token under a prose key, edited in place; it must give prose_doc."""
        doc = bee.load_yaml_text(text)
        if not self.live(name, doc):
            return text
        edits, root = {}, yaml.compose(text, Loader=bee.BeeLoader)
        for kn, vn in root.value:
            if kn.value in self.step["prose"]["keys"]:
                for n in [vn] if isinstance(vn, yaml.ScalarNode) else vn.value if isinstance(vn, yaml.SequenceNode) else []:
                    raw = text[n.start_mark.index:n.end_mark.index]
                    if isinstance(n, yaml.ScalarNode) and n.tag == rename.STR and (new := self.words(raw, inv)) != raw:
                        edits[(n.start_mark.index, n.end_mark.index)] = new
        out = rename.edited(text, edits)
        if bee.load_yaml_text(out) != self.prose_doc(name, doc, inv):
            raise rename.Problem("the prose rule's text edits do not give the map applied to the prose keys' texts")
        return out

    def data(self, name, text, inv=False):
        """apply (inv=False) or inverse: the places, then the prose rule (in that order both ways: neither touches the other's)."""
        return self.prose_text(name, self.names.translate(name, text, inv), inv)

    def python(self, source, inv=False):
        """A code file: the metric ids written as whole words in its string and comment tokens; every other byte as it is."""
        out, last, starts = [], 0, [0, *itertools.accumulate(len(line) + 1 for line in source.split("\n"))]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in WORDS and (new := self.words(tok.string, inv)) != tok.string:
                a, b = starts[tok.start[0] - 1] + tok.start[1], starts[tok.end[0] - 1] + tok.end[1]
                assert source[a:b] == tok.string, f"line {tok.start[0]}: a token the tokenizer does not place"
                out, last = out + [source[last:a], new], b
        return "".join(out) + source[last:]

    def same_code(self, old, new):
        """P1 for a code file: the same tokens, each one equal, or a string or comment equal to the map applied to the old one."""
        before, after = (list(tokenize.generate_tokens(io.StringIO(s).readline)) for s in (old, new))
        if len(before) != len(after):
            return ["not the same number of tokens"]
        return [f"line {a.start[0]}: « {a.string[:40]} » -> « {b.string[:40]} »: not the map applied to a string or a comment"
                for a, b in zip(before, after) if (a.type, a.string) != (b.type, b.string)
                and not (a.type == b.type and a.type in WORDS and self.words(a.string) == b.string)]

    def file(self, path, data):
        """(new bytes, problems) for one file of the base: its translation, proven (P2 for data, the token check for code)."""
        kind, name = self.kind(path)
        if kind is None:
            return data, []
        text = data.decode("utf-8")
        if kind == "code":
            new = self.python(text)
            return new.encode("utf-8"), [f"{path}: {p}" for p in self.same_code(text, new)]
        try:
            new = self.data(name, text)
            problems = [] if self.data(name, new, True) == text else ["inverse(apply(f)) is not byte-identical to f"]
            old_doc, new_doc = bee.load_yaml_text(text), bee.load_yaml_text(new)
            if self.names.data(name, self.prose_doc(name, old_doc), False) != new_doc:
                problems.append("the values differ once the metric ids (and the prose rule) are mapped")
            if self.names.leaves(name, self.prose_doc(name, old_doc), False) != self.names.leaves(name, new_doc, True):
                problems.append("a leaf changed (a number, a date, a login or a free text outside the prose rule)")
        except (rename.Problem, bee.BeeError, yaml.YAMLError, ValueError, KeyError) as e:
            return data, [f"{path}: {e}"]
        return new.encode("utf-8"), [f"{path}: {p}" for p in problems]


def base_step(repo, base, files):
    """The base's map, once this script, rename.py and bee.py are checked to be the base's own."""
    for path, alive in ((f"tools/migration/{SELF.name}", SELF), ("tools/migration/rename.py", pathlib.Path(rename.__file__).resolve()),
                        ("tools/bee.py", pathlib.Path(bee.__file__).resolve()), (MAP, None)):
        if path not in files or alive and files[path] != alive.read_bytes():
            raise rename.Problem(f"{alive or path} is not the base's {path}: run the base's own script, python3 -I, from its checkout")
    return Step(files[MAP].decode("utf-8"))


def check(repo, base, head=None):
    """Returns (problems, counts, {path: new bytes} of the files the step changes)."""
    modes, after_modes = {}, {}
    files = rename.tree_files(repo, base, modes)
    step = base_step(repo, base, files)
    problems, counts, changed = step.problems(), collections.Counter(), {}
    for p in sorted(files):
        kind = step.kind(p)[0]
        new, found = step.file(p, files[p])
        problems += found
        counts[kind or "other"] += 1
        if new != files[p]:
            changed[p] = new
            counts[f"{kind} changed"] += 1
    if head is not None:
        after = rename.tree_files(repo, head, after_modes)
        for p in sorted(files):
            if p not in after:
                problems.append(f"{p}: dropped (not in the head)")
            elif after[p] != changed.get(p, files[p]):
                problems.append(f"{p}: not " + ("its translation" if p in changed else "byte-identical to the base"))
            elif after_modes[p] != modes[p]:
                problems.append(f"{p}: mode {after_modes[p].decode()}, the base had {modes[p].decode()}")
        problems += [f"{p}: added (no file of the base)" for p in sorted(set(after) - set(files))]
    return problems, counts, changed


def main(argv=None):
    p = argparse.ArgumentParser(prog="metric_ids.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("write", "check"):
        s = sub.add_parser(action)
        [s.add_argument(o, required=o == "--base", default=str(SELF.parents[2]) if o == "--repo" else None)
         for o in ("--base", "--repo", "--head")[:3 if action == "check" else 2]]
    a = p.parse_args(argv)
    try:
        problems, n, changed = check(a.repo, a.base, getattr(a, "head", None))
        [(pathlib.Path(a.repo) / path).write_bytes(data) for path, data in changed.items() if a.action == "write" and not problems]
    except (rename.Problem, bee.BeeError, yaml.YAMLError, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems, n, changed = [f"{type(e).__name__}: {e}"], collections.Counter(), {}
    summary = f"{n['data']} data files ({n['data changed']} with metric ids), {n['code']} code files ({n['code changed']}), {n['other']} others"
    print("".join(f"✗ {x}\n" for x in problems) + f"{len(problems)} problem(s)." if problems else
          f"✓ {len(changed)} file(s) written from {a.base}: {summary}." if a.action == "write" else
          f"✓ P2 (metric ids) holds at {a.base}" + (f" for the head {a.head}: the {len(changed)} changed files are their translation, "
                                                   "every other file byte for byte" if a.head else ": every data file translates and back "
                                                   "byte for byte") + f"; {summary}.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
