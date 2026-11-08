#!/usr/bin/env python3
"""English names, step 1a (ruche-0141; docs/english-migration.md, sections 12 and 13): the scoped map's lint, the data
translator and proof P2. Dormant: bee never calls it, and it renames nothing by itself.

    python3 outils/migration/rename.py lint    [--map FILE]
    python3 outils/migration/rename.py apply   SOURCE DEST [--map FILE]   # a tree's data files, at their English paths
    python3 outils/migration/rename.py inverse SOURCE DEST [--map FILE]   # and back
    python3 outils/migration/rename.py check   [--base REV] [--head REV] [--repo DIR]

check (P2) reads the map and the files from the base commit, never from the head nor the working tree: every data file
translates and back byte for byte, with the same values and leaves once mapped; every tracked file is in one family or on
the map's hand-change list; with --head, the head is exactly that translation. Exit 0: proven; 1: problems, listed.
"""
import argparse
import collections
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

import yaml

OUTILS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(OUTILS))
import bee  # noqa: E402  the tool's own reader (no timestamp, alias or duplicate key) and canonical writer

MAP = "outils/migration/names.yaml"
STR = "tag:yaml.org,2002:str"
REMOVED = object()


class Problem(Exception):
    pass


def glob_re(motif):
    """A file glob of the map: * stays inside one folder, ** crosses folders."""
    return re.compile("".join({"**": ".*", "*": "[^/]*"}.get(t, re.escape(t)) for t in re.split(r"(\*\*|\*)", motif)) + r"\Z")


def join(path, seg):
    return f"{path}/{seg}" if path else seg


class Names:
    """The map read from names.yaml, seen from the French side (inv=False) or from the English side (inv=True)."""

    def __init__(self, text):
        self.m = m = yaml.safe_load(text)
        self.fam = m["families"]
        flip = lambda d: {b: a for a, b in d.items()}  # noqa: E731
        self.dom = {n: ({False: d, True: flip(d)}, n in m["open_domains"]) for n, d in {**m["domains"], **m["open_domains"]}.items()}
        self.seg = {False: m["tree"]["segments"], True: flip(m["tree"]["segments"])}
        self.paths = {inv: sorted((flip if inv else dict)(m["paths"]).items(), key=lambda p: -len(p[0])) for inv in (False, True)}
        self.files = {n: [glob_re(g) for g in f["files"]] for n, f in self.fam.items()}
        self.hand = [(glob_re(h["files"]), h) for h in m["hand"]]
        self.new = [glob_re(g) for g in m.get("new") or []]
        self.sides = {}

    def side(self, name, inv):
        """A family's keys, value rules and key_values, with their paths written on one side."""
        if (name, inv) not in self.sides:
            f, keys = self.fam[name], self.fam[name]["keys"]
            p = (lambda s: "/".join(re.sub(r"^[^\[*]+", lambda x: keys.get(x.group(0), x.group(0)), g) for g in s.split("/"))) \
                if inv else (lambda s: s)
            self.sides[name, inv] = {"name": name, "inv": inv, "keys": {b: a for a, b in keys.items()} if inv else keys,
                                     "values": {p(k): v for k, v in (f.get("values") or {}).items()},
                                     "kv": {p(k): v for k, v in (f.get("key_values") or {}).items()}}
        return self.sides[name, inv]

    def value(self, domain, v, inv):
        if domain == "path":
            return self.path(v, inv)
        if domain == "node":
            seg = self.seg[inv]
            if not all(s in seg for s in v.split("/")):
                raise Problem(f"node id « {v} » has a segment outside the tree map")
            return "/".join(seg[s] for s in v.split("/"))
        d, ouvert = self.dom[domain]
        if v not in d[inv] and not ouvert:
            raise Problem(f"value « {v} » outside the domain {domain}")
        return d[inv].get(v, v)

    def path(self, p, inv=False):
        for a, b in self.paths[inv]:
            if p == a or a.endswith("/") and p.startswith(a):
                p = b + p[len(a):]
                break
        t = self.m["tree"]["dir"][0 if inv else 1] + "/"
        return t + "/".join(self.seg[inv].get(s, s) for s in p[len(t):].split("/")) if p.startswith(t) else p

    def families_of(self, path):
        return [n for n, res in self.files.items() if any(r.match(path) for r in res)]

    def rule(self, side, path):
        """The domain of the value at this path, or None for a leaf."""
        return side["values"].get(path) or side["values"].get("**/" + path.rsplit("/", 1)[-1])

    def key(self, side, path, k):
        if path in side["kv"]:
            d = side["kv"][path]
            return self.value(d, k, side["inv"]) if d and isinstance(k, str) else k
        if not isinstance(k, str) or k not in side["keys"]:
            raise Problem(f"key « {k} » (under {path or 'the top'}) is not in the map of the family {side['name']}")
        return side["keys"][k]

    def walk(self, name, doc, inv, leaf):
        """Rebuilds a document with keys and values translated; leaf(value, translated or None) sees every scalar."""
        side = self.side(name, inv)

        def walk(o, path):
            if isinstance(o, dict):
                if path in side["kv"] and not side["kv"][path]:
                    [leaf(k, None) for k in o]
                return {self.key(side, path, k): walk(v, join(path, "*" if path in side["kv"] else k)) for k, v in o.items()}
            if isinstance(o, list):
                return [walk(x, path + "[]") for x in o]
            d = self.rule(side, path) if isinstance(o, str) else None
            return leaf(o, self.value(d, o, inv) if d else None)
        return walk(doc, "")

    def data(self, name, doc, inv):
        """A document's values translated: keys by the family, values by their domain (also the text edits' cross-check)."""
        return self.walk(name, doc, inv, lambda v, new: v if new is None else new)

    def leaves(self, name, doc, inv):
        """The multiset of what never changes: every scalar outside a domain, and the keys that are data without a domain."""
        out = collections.Counter()
        self.walk(name, doc, inv, lambda v, new: out.update([(type(v).__name__, v)] if new is None else []) or v)
        return out

    def text(self, name, text, inv):
        """Text level: each key token, and each value token in a domain, is replaced in place; order, quoting, comments and
        wrapping stay, and free texts are never edited. The result must read as the map applied to the values."""
        side, doc, edits = self.side(name, inv), bee.charger_texte_yaml(text), []

        def edit(n, new):
            raw = text[n.start_mark.index:n.end_mark.index]
            q = raw[:1] if raw[:1] in "'\"" else ""
            if new != n.value and raw != q + n.value + q:
                raise Problem(f"« {raw[:40]} » (line {n.start_mark.line + 1}) is written in a form the translator does not edit")
            if new != n.value:
                edits.append((n.start_mark.index, n.end_mark.index, q + new + q))

        def walk(n, path):
            if isinstance(n, yaml.MappingNode):
                for kn, vn in n.value:
                    k = kn.value if kn.tag == STR else bee.charger_texte_yaml(text[kn.start_mark.index:kn.end_mark.index])
                    new = self.key(side, path, k)
                    if kn.tag == STR:
                        edit(kn, new)
                    walk(vn, join(path, "*" if path in side["kv"] else k))
            elif isinstance(n, yaml.SequenceNode):
                [walk(x, path + "[]") for x in n.value]
            elif n.tag == STR and (d := self.rule(side, path)):
                edit(n, self.value(d, n.value, inv))
        if (root := yaml.compose(text, Loader=bee.ChargeurBee)) is not None:
            walk(root, "")
        for a, b, s in sorted(edits, reverse=True):
            text = text[:a] + s + text[b:]
        if bee.charger_texte_yaml(text) != self.data(name, doc, inv):
            raise Problem("the text edits do not give the map applied to the values")
        return text

    def node_lines(self, text):
        """A tree node's lines, the end of its front matter (or None) and its children lines: [(index, match)]."""
        lines, section, kids = text.split("\n"), None, []
        fin = lines.index("---", 1) if lines[0] == "---" and "---" in lines[1:] else None
        for i, ligne in enumerate(lines[(fin or 0):], fin or 0):
            if ligne.startswith("## "):
                section = ligne[3:].strip()
            elif section in self.m["tree"]["children"] and (c := bee.ENFANT_NOEUD.match(ligne)):
                kids.append((i, c))
        return lines, fin, kids

    def parts(self, name, text):
        """What a file says: its values; for a tree node, its front matter, its children and the rest of its text."""
        if self.fam[name]["writer"] != "markdown":
            return bee.charger_texte_yaml(text)
        lines, fin, kids = self.node_lines(text)
        for i, c in kids:
            lines[i] = lines[i][:c.start(1)] + "\0" + lines[i][c.end(1):]
        front = bee.charger_texte_yaml("\n".join(lines[1:fin]) + "\n") if fin else None
        return front, [c.group(1) for _, c in kids], "\n".join(lines[fin + 1 if fin else 0:])

    def translate(self, name, text, inv=False):
        writer = self.fam[name]["writer"]
        if writer == "canonical":
            doc = bee.charger_texte_yaml(text)
            if bee._rendu_fidele(doc, name) != text:
                raise Problem("not in the canonical form the tool's writer gives")
            return bee._rendu_fidele(self.data(name, doc, inv), name)
        if writer != "markdown":
            return self.text(name, text, inv)
        lines, fin, kids = self.node_lines(text)
        for i, c in kids:
            lines[i] = lines[i][:c.start(1)] + self.value("node", c.group(1), inv) + lines[i][c.end(1):]
        if fin:
            lines[1:fin] = self.text(name, "\n".join(lines[1:fin]) + "\n", inv).split("\n")[:-1]
        return "\n".join(lines)

    def same_values(self, name, old, new):
        """P2 for one file: the values of new are those of old once mapped, and the leaves are the same multiset."""
        a, b, problems = self.parts(name, old), self.parts(name, new), []
        if self.fam[name]["writer"] == "markdown":
            if [self.value("node", k, False) for k in a[1]] != b[1] or a[2] != b[2]:
                problems.append("the children or the text outside the front matter differ once node ids are mapped")
            a, b = a[0], b[0]
        if self.data(name, a, False) != b:
            problems.append("the values differ once keys and values are mapped")
        if self.leaves(name, a, False) != self.leaves(name, b, True):
            problems.append("a leaf changed (number, date, sha, login or free text)")
        return problems

    def lint(self, read):
        """One-to-one inside each family; every domain known; English values that read back as text; the retired names;
        date D; every key and enumerated value of a family's schema in the map. read(path) gives a text or None."""
        m, problems = self.m, []
        maps = {"paths": m["paths"], "tree segments": m["tree"]["segments"], "commands": m["cli"]["commands"],
                "options": m["cli"]["options"], **{f"options of {s}": o for s, o in m["cli"]["scripts"].items()},
                **{f"keys of the family {n}": f["keys"] for n, f in self.fam.items()},
                **{f"domain {n}": d for n, d in {**m["domains"], **m["open_domains"]}.items()}}
        for label, d in maps.items():
            seen = {}
            for fr, en in d.items():
                if en in seen:
                    problems.append(f"{label}: « {seen[en]} » and « {fr} » share the English name « {en} »")
                seen.setdefault(en, fr)
        for n, (d, _) in self.dom.items():
            problems += [f"domain {n}: « {en} » reads back as {type(lu).__name__}, not as a text" for en in d[False].values()
                         if isinstance(en, str) and re.fullmatch(r"[\w.-]+", en) and not isinstance(lu := yaml.safe_load(en), str)]
        known = set(self.dom) | {"path", "node"}
        for n, f in self.fam.items():
            problems += [f"family {n}: unknown domain {d}" for d in [*(f.get("values") or {}).values(), *(f.get("key_values") or {}).values()]
                         if d and d not in known]
            if f.get("schema"):
                texte = read(f"schemas/{f['schema']}")
                problems += self.schema_problems(n, json.loads(texte)) if texte else [f"family {n}: schema {f['schema']} missing"]
        removed = {h["files"] for h in m["hand"] if h.get("removed")}
        problems += [f"retired name {r}: neither a French path of the map nor a removed file" for r in m["retired"]
                     if r not in m["paths"] and r not in removed or r in m["paths"].values()]
        if not dt.date.fromisoformat(str(m["date_d"])) >= dt.date(2027, 1, 1):
            problems.append(f"date_d {m['date_d']}: 2027-01-01 at the earliest")
        return problems

    def schema_problems(self, name, schema):
        side, problems = self.side(name, False), []

        def walk(node, path, refs=()):
            if isinstance(node, list):
                [walk(x, path, refs) for x in node]
            if not isinstance(node, dict):
                return
            if (ref := str(node.get("$ref", "")).rpartition("/")[2]) and ref not in refs:
                walk(schema.get("$defs", {}).get(ref), path, refs + (ref,))
            for v in [x for x in node.get("enum", []) + [node.get("const")] if isinstance(x, str) and x]:
                try:
                    self.value(self.rule(side, path) or "", v, False)
                except (Problem, KeyError) as e:
                    problems.append(f"family {name}: « {v} » at {path}: {e if isinstance(e, Problem) else 'no domain'}")
            for k, v in (node.get("properties") or {}).items():
                if path not in side["kv"] and k not in side["keys"]:
                    problems.append(f"family {name}: key « {k} » of the schema (under {path or 'the top'}) is not in the map")
                walk(v, join(path, "*" if path in side["kv"] else k), refs)
            for v in list((node.get("patternProperties") or {}).values()) + [node.get("additionalProperties")]:
                walk(v, join(path, "*"), refs)
            walk(node.get("items"), path + "[]", refs)
            [walk(node.get(k), path, refs) for k in ("allOf", "anyOf", "oneOf", "if", "then", "else")]
        walk(schema, "")
        return problems


def tree_files(repo, rev, modes=None):
    """{path: bytes} of every blob of a commit, read from git (never from the working tree); modes gets {path: mode}."""
    out = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", rev], capture_output=True, check=True).stdout
    entries = [(meta.split(), path.decode()) for meta, path in (e.split(b"\t", 1) for e in out.split(b"\0") if e)]
    (modes if modes is not None else {}).update((path, meta[0]) for meta, path in entries)
    blobs = [(meta[2], path) for meta, path in entries if meta[1] == b"blob"]
    data = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], input=b"".join(s + b"\n" for s, _ in blobs),
                          capture_output=True, check=True).stdout
    files, i = {}, 0
    for _, path in blobs:
        j = data.index(b"\n", i)
        taille = int(data[i:j].split()[2])
        files[path], i = data[j + 1:j + 1 + taille], j + 2 + taille
    return files


def check(repo, base, head=None):
    """Proof P2 (plan, section 4.2 point 2, section 12 change 6, section 13). Returns (problems, files per family)."""
    modes, after_modes = {}, {}
    files = tree_files(repo, base, modes)
    if MAP not in files:
        return [f"no {MAP} at the base {base}"], {}
    names = Names(files[MAP].decode("utf-8"))
    problems = names.lint(lambda p: files[p].decode("utf-8") if p in files else None)
    images, counts = {}, collections.Counter()
    for p in sorted(modes):
        fams, hand, blob = names.families_of(p), [h for r, h in names.hand if r.match(p)], files.get(p)
        if blob is None or len(fams) + bool(hand) != 1:
            quoi = fams + [h["files"] for h in hand] or "no family and no hand-change entry"
            problems.append(f"{p}: " + ("not a file" if blob is None else f"matched by {quoi}"))
            continue
        if names.path(q := names.path(p), True) != p or q in images:
            problems.append(f"{p}: the path map gives {q}, which does not translate back to it alone")
        if hand:
            images[q] = (p, REMOVED if any(h.get("removed") for h in hand) else None)
            continue
        try:
            new = names.translate(fams[0], text := blob.decode("utf-8"))
            if names.translate(fams[0], new, True) != text:
                problems.append(f"{p}: inverse(apply(f)) is not byte-identical to f")
            problems += [f"{p}: {x}" for x in names.same_values(fams[0], text, new)]
        except (Problem, bee.ErreurBee, yaml.YAMLError, UnicodeDecodeError) as e:
            problems.append(f"{p}: {e}")
            continue
        images[q] = (p, new.encode("utf-8"))
        counts[fams[0]] += 1
    if head is not None:
        after = tree_files(repo, head, after_modes)
        for q, (p, new) in images.items():
            if q in after_modes and new is not REMOVED and after_modes[q] != modes[p]:
                problems.append(f"{q}: mode {after_modes[q].decode()}, {p} had {modes[p].decode()}")
            if new is REMOVED:
                problems += [f"{q}: listed as removed, still in the head"] if q in after_modes else []
            elif q not in after_modes:
                problems.append(f"{p}: dropped (no {q} in the head)")
            elif new is not None and after.get(q) != new:
                problems.append(f"{q}: not the translation of {p}{leaf_changed(names, p, files[p], after.get(q, b''))}")
        problems += [f"{q}: added (the translation of no file of the base)" for q in after_modes
                     if q not in images and not any(r.match(q) for r in names.new)]
    return problems, counts


def leaf_changed(names, p, old, new):
    """Says why, when it can: the head's file has other leaves than the base's (a free text changed…), or does not read."""
    fam = names.families_of(p)[0]
    try:
        a, b = (x[0] if names.fam[fam]["writer"] == "markdown" else x for x in (names.parts(fam, y.decode()) for y in (old, new)))
        return " (a leaf changed: number, date, sha, login or free text)" if names.leaves(fam, a, False) != names.leaves(fam, b, True) else ""
    except (Problem, bee.ErreurBee, yaml.YAMLError, UnicodeDecodeError) as e:
        return f" ({e})"


def translate_tree(names, source, dest, inv):
    """apply / inverse: every data file of a tree, translated, at its translated path; returns how many were written."""
    n = 0
    for f in sorted(pathlib.Path(source).rglob("*")):
        rel = f.relative_to(source).as_posix()
        fr = names.path(rel, True) if inv else rel
        if f.is_file() and not rel.startswith(".git/") and len(fams := names.families_of(fr)) == 1:
            out = pathlib.Path(dest) / (fr if inv else names.path(rel))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(names.translate(fams[0], f.read_text(encoding="utf-8"), inv).encode("utf-8"))
            n += 1
    return n


def main(argv=None):
    p = argparse.ArgumentParser(prog="rename.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("lint", "apply", "inverse"):
        s = sub.add_parser(action)
        [s.add_argument(x) for x in (("source", "dest") if action != "lint" else ())]
        s.add_argument("--map", default=str(OUTILS.parent / MAP))
    s = sub.add_parser("check")
    s.add_argument("--base", default="HEAD")
    s.add_argument("--head")
    s.add_argument("--repo", default=str(OUTILS.parent))
    a, counts, ecrits = p.parse_args(argv), {}, None
    try:
        if a.action == "check":
            problems, counts = check(a.repo, a.base, a.head)
        else:
            names, racine = Names(pathlib.Path(a.map).read_text(encoding="utf-8")), pathlib.Path(a.map).resolve().parents[2]
            problems = names.lint(lambda q: (racine / q).read_text(encoding="utf-8") if (racine / q).is_file() else None)
            if not problems and a.action != "lint":
                ecrits = translate_tree(names, a.source, a.dest, a.action == "inverse")
    except (Problem, bee.ErreurBee, yaml.YAMLError, subprocess.CalledProcessError, OSError, UnicodeDecodeError) as e:
        problems = [str(e)]
    for x in problems:
        print(f"✗ {x}")
    if problems:
        print(f"{len(problems)} problem(s).")
        return 1
    print(f"✓ P2 holds at {a.base}" + (f" and the head {a.head}" if a.head else "") + ": " + ", ".join(
        f"{n} {k}" for k, n in sorted(counts.items())) + " file(s), translated and back byte for byte." if a.action == "check" else
          "✓ the map is one-to-one in every family, and covers its schemas." if a.action == "lint" else f"✓ {ecrits} file(s) written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
