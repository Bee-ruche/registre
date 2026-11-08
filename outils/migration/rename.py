#!/usr/bin/env python3
"""English names, step 1a (ruche-0141; docs/english-migration.md, sections 12 and 13): the scoped map's lint, the data and
schema translator and proof P2. Dormant: bee never calls it. Run it isolated (-I), from the base's own checkout:
    python3 -I outils/migration/rename.py lint | apply SOURCE DEST | inverse SOURCE DEST  [--map FILE]
    python3 -I outils/migration/rename.py check --base REV [--head REV] [--repo DIR]
check (P2) reads the map and the files from the base commit, and runs only if this script and bee.py are the base's own:
data files and schemas translate and back byte for byte; every other file stays byte-identical, moved, replaced or removed
as the map says, except the code it lists (step 1b's proofs). With --head, the head must be exactly that. Exit 0: proven,
as the last line says; 1: problems, listed.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("rename.py: run it isolated, python3 -I outils/migration/rename.py …, so that nothing shadows a module")

import argparse, collections, functools, json, pathlib, re, subprocess  # noqa: E401, E402  (nothing imported before the check)
import yaml  # noqa: E402

SELF = pathlib.Path(__file__).resolve()
sys.path.append(str(SELF.parent.parent))  # last: a module of the tool's folder never shadows the standard library or PyYAML
import bee  # noqa: E402  the tool's own reader (no timestamp, alias or duplicate key) and canonical writer

MAPS = ("outils/migration/names.yaml", "tools/migration/names.yaml")  # the map at the base, before and after the switch
MAP, STR, REMOVED = MAPS[0], "tag:yaml.org,2002:str", object()
join = lambda path, seg: f"{path}/{seg}" if path else seg  # noqa: E731
edited = lambda text, edits: functools.reduce(lambda t, e: t[:e[0][0]] + e[1] + t[e[0][1]:], sorted(edits.items(), reverse=True), text)  # noqa: E731


class Problem(Exception):
    pass


def glob_re(motif):
    """A file glob of the map: * stays inside one folder, ** crosses folders."""
    return re.compile("".join({"**": ".*", "*": "[^/]*"}.get(t, re.escape(t)) for t in re.split(r"(\*\*|\*)", motif)) + r"\Z")


def edit(text, edits, n, new):
    """Records the replacement of one scalar token, in its own quoting; refuses a token written in another form."""
    raw = text[n.start_mark.index:n.end_mark.index]
    q = raw[:1] if raw[:1] in "'\"" else ""
    if new != n.value and raw != q + n.value + q:
        raise Problem(f"« {raw[:40]} » (line {n.start_mark.line + 1}) is written in a form the translator does not edit")
    if new != n.value and edits.setdefault((n.start_mark.index, n.end_mark.index), q + new + q) != q + new + q:
        raise Problem(f"line {n.start_mark.line + 1}: one token, two translations")


class Names:
    """The map read from names.yaml, seen from the French side (inv=False) or from the English side (inv=True)."""

    def __init__(self, text):
        self.m = m = bee.charger_texte_yaml(text, "names.yaml")  # a key written twice is refused
        self.fam = m["families"]
        flip = lambda d: {b: a for a, b in d.items()}  # noqa: E731
        self.dom = {n: ({False: d, True: flip(d)}, n in m["open_domains"]) for n, d in {**m["domains"], **m["open_domains"]}.items()}
        self.seg = {False: m["tree"]["segments"], True: flip(m["tree"]["segments"])}
        self.paths = {inv: sorted((flip if inv else dict)(m["paths"]).items(), key=lambda p: -len(p[0])) for inv in (False, True)}
        self.files = {n: [glob_re(g) for g in f["files"]] for n, f in self.fam.items()}
        self.schemas = {f"schemas/{f['schema']}": n for n, f in self.fam.items() if f.get("schema")}
        self.hand, self.code = [(glob_re(h["files"]), h) for h in m["hand"]], set(m["code"])
        self.new, self.sides = [glob_re(g) for g in m.get("new") or []], {}

    def side(self, name, inv):
        """A family's keys, value rules, key_values and schema strings, with their paths written on one side."""
        if (name, inv) not in self.sides:
            f, keys = self.fam[name], self.fam[name]["keys"]
            p = (lambda s: "/".join(re.sub(r"^[^\[*]+", lambda x: keys.get(x.group(0), x.group(0)), g) for g in s.split("/"))) \
                if inv else (lambda s: s)
            strings = f.get("schema_strings") or {}
            self.sides[name, inv] = {"name": name, "inv": inv, "keys": {b: a for a, b in keys.items()} if inv else keys,
                                     "values": {p(k): v for k, v in (f.get("values") or {}).items()},
                                     "kv": {p(k): v for k, v in (f.get("key_values") or {}).items()},
                                     "strings": {b: a for a, b in strings.items()} if inv else strings}
        return self.sides[name, inv]

    def value(self, domain, v, inv):
        if domain in ("path", "node"):
            if domain == "node" and not all(s in self.seg[inv] for s in v.split("/")):
                raise Problem(f"node id « {v} » has a segment outside the tree map")
            return self.path(v, inv) if domain == "path" else "/".join(self.seg[inv][s] for s in v.split("/"))
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

    def rule(self, side, path):  # the domain of the value at this path, or None for a leaf
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
        side, doc, edits = self.side(name, inv), bee.charger_texte_yaml(text), {}

        def walk(n, path):
            if isinstance(n, yaml.MappingNode):
                for kn, vn in n.value:
                    k = kn.value if kn.tag == STR else bee.charger_texte_yaml(text[kn.start_mark.index:kn.end_mark.index])
                    new = self.key(side, path, k)
                    if kn.tag == STR:
                        edit(text, edits, kn, new)
                    walk(vn, join(path, "*" if path in side["kv"] else k))
            elif isinstance(n, yaml.SequenceNode):
                [walk(x, path + "[]") for x in n.value]
            elif n.tag == STR and (d := self.rule(side, path)):
                edit(text, edits, n, self.value(d, n.value, inv))
        if (root := yaml.compose(text, Loader=bee.ChargeurBee)) is not None:
            walk(root, "")
        if bee.charger_texte_yaml(text := edited(text, edits)) != self.data(name, doc, inv):
            raise Problem("the text edits do not give the map applied to the values")
        return text

    def schema(self, name, text, inv):
        """A family's JSON schema, its names translated in place: properties, required, dependentRequired, enum and const
        by the family's keys and domains, and the map's exact strings ($id, patterns); the rest stays byte for byte."""
        side, edits, pending, seen = self.side(name, inv), {}, set(), set()
        root = yaml.compose(text, Loader=bee.ChargeurBee)  # JSON read as YAML, for the tokens' places
        defs = {k.value: v for k, v in next((v.value for k, v in root.value if k.value == "$defs"), [])}

        def walk(n, path):
            for kn, vn in n.value if isinstance(n, yaml.MappingNode) else [(None, x) for x in n.value] if isinstance(n, yaml.SequenceNode) else []:
                k, kv, items = kn and kn.value, path in side["kv"], vn.value if not isinstance(vn, yaml.ScalarNode) else []
                if k is None or k in ("allOf", "anyOf", "oneOf", "if", "then", "else", "not"):
                    walk(vn, path)
                elif k == "properties":
                    for pk, pv in items:
                        edit(text, edits, pk, self.key(side, path, pk.value))
                        walk(pv, join(path, "*" if kv else pk.value))
                elif k in ("required", "dependentRequired"):
                    for y in (x for i in items for x in ([i] if k == "required" else [i[0], *i[1].value])):
                        edit(text, edits, y, self.key(side, path, y.value))
                elif k in ("enum", "const"):
                    for x in [x for x in (items if k == "enum" else [vn]) if x.tag == STR and x.value]:
                        if not (d := self.rule(side, path)):
                            raise Problem(f"« {x.value} » at {path} has no domain")
                        edit(text, edits, x, self.value(d, x.value, inv))
                elif k in ("items", "additionalProperties", "patternProperties"):
                    [walk(x, path + "[]" if k == "items" else join(path, "*")) for x in ([vn] if k != "patternProperties" else [v for _, v in items])]
                elif k == "$ref":
                    pending.add((vn.value.rpartition("/")[2], path))
                elif vn.tag == STR and vn.value in side["strings"]:
                    edit(text, edits, vn, side["strings"][vn.value])
        walk(root, "")
        while pending - seen:  # a definition is translated where it is used; two uses must agree (edit refuses otherwise)
            seen.add(ref := (pending - seen).pop())
            walk(defs.get(ref[0]), ref[1])
        json.loads(text := edited(text, edits))
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
        return (bee.charger_texte_yaml("\n".join(lines[1:fin]) + "\n") if fin else None), [c.group(1) for _, c in kids], \
            "\n".join(lines[fin + 1 if fin else 0:])

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
        """Every name a text; one-to-one inside each family; every domain known; English values that read back as text;
        each family's schema translatable; the hand entries, the retired names, date D. read(path): a text or None."""
        m, problems = self.m, []
        maps = {"paths": m["paths"], "tree segments": m["tree"]["segments"], "commands": m["cli"]["commands"],
                "options": m["cli"]["options"], **{f"options of {s}": o for s, o in m["cli"]["scripts"].items()},
                **{f"keys of the family {n}": f["keys"] for n, f in self.fam.items()},
                **{f"schema strings of the family {n}": f.get("schema_strings") or {} for n, f in self.fam.items()},
                **{f"domain {n}": d for n, d in {**m["domains"], **m["open_domains"]}.items()}}
        for label, d in maps.items():
            seen = {}
            for fr, en in d.items():
                if not (isinstance(fr, str) and isinstance(en, str)):
                    problems.append(f"{label}: « {fr} » -> « {en} »: every name is a text")
                elif en in seen:
                    problems.append(f"{label}: « {seen[en]} » and « {fr} » share the English name « {en} »")
                seen.setdefault(str(en), fr)
        for n, (d, _) in self.dom.items():
            problems += [f"domain {n}: « {en} » reads back as {type(lu).__name__}, not as a text" for en in d[False].values()
                         if isinstance(en, str) and re.fullmatch(r"[\w.-]+", en) and not isinstance(lu := yaml.safe_load(en), str)]
        for n, f in self.fam.items():
            problems += [f"family {n}: unknown domain {d}" for d in [*(f.get("values") or {}).values(), *(f.get("key_values") or {}).values()]
                         if d and d not in set(self.dom) | {"path", "node"}]
        for chemin, n in self.schemas.items():
            try:
                self.schema(n, read(chemin) or "", False)
            except (Problem, bee.ErreurBee, yaml.YAMLError, ValueError, AttributeError, KeyError) as e:
                problems.append(f"family {n}: {chemin}: {'unknown domain ' if isinstance(e, KeyError) else ''}{e}")
        problems += [f"hand entry {h['files']}: one of same, becomes, removed" for _, h in self.hand
                     if sum(bool(h.get(k)) for k in ("same", "becomes", "removed")) != 1]
        removed = {h["files"] for h in m["hand"] if h.get("removed")}
        problems += [f"retired name {r}: neither a French path of the map nor a removed file" for r in m["retired"]
                     if r not in m["paths"] and r not in removed or r in m["paths"].values()]
        if len(self.schemas) != sum(bool(f.get("schema")) for f in self.fam.values()) or self.path(MAPS[0]) != MAPS[1]:
            problems.append(f"a schema serves two families, or the map does not move {MAPS[0]} to {MAPS[1]}")
        if not (re.fullmatch(r"\d{4}-\d\d-\d\d", str(m["date_d"])) and str(m["date_d"]) >= "2027-01-01"):
            problems.append(f"date_d {m['date_d']}: a date, 2027-01-01 at the earliest")
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
    """Proof P2 (plan, section 4.2 point 2, section 12 change 6, section 13). Returns (problems, files per kind)."""
    modes, after_modes = {}, {}
    files = tree_files(repo, base, modes)
    if (carte := next((c for c in MAPS if c in files), None)) is None:
        return [f"no {MAPS[0]} at the base {base}"], {}
    outil = carte.rpartition("/migration/")[0]
    for chemin, vivant in ((f"{outil}/migration/rename.py", SELF), (f"{outil}/bee.py", pathlib.Path(bee.__file__).resolve())):
        if files.get(chemin) != vivant.read_bytes():
            return [f"{vivant} is not the base's {chemin}: run the base's own checker, python3 -I, from its checkout"], {}
    names = Names(files[carte].decode("utf-8"))
    problems = names.lint(lambda p: files[p].decode("utf-8") if p in files else None)
    images, counts = {}, collections.Counter()
    for p in sorted(modes):
        fams, schema, code = names.families_of(p), names.schemas.get(p), p in names.code
        hand = [h for r, h in names.hand if r.match(p)][:1] if not (fams or schema or code) else []
        if p not in files or len(fams) + bool(schema) + code + bool(hand) != 1:
            quoi = fams + [x for x in (schema, code and "code") if x] or "no family, no schema, no code and no hand-change entry"
            problems.append(f"{p}: " + ("not a file" if p not in files else f"matched by {quoi}"))
            continue
        if names.path(q := names.path(p), True) != p or q in images:
            problems.append(f"{p}: the path map gives {q}, which does not translate back to it alone")
        if hand or code:
            h = hand[0] if hand else {}
            if (source := h.get("becomes", p)) not in files:
                problems.append(f"{p}: becomes {source}, which is not a file of the base")
            counts[kind := "code" if code else "removed" if h.get("removed") else "same"] += 1
            images[q] = (p, {"code": None, "removed": REMOVED}.get(kind, files.get(source)), f"byte-identical to {source}")
            continue
        fait = (lambda t, inv=False: names.schema(schema, t, inv)) if schema else (lambda t, inv=False: names.translate(fams[0], t, inv))
        try:
            if fait(new := fait(text := files[p].decode("utf-8")), True) != text:
                problems.append(f"{p}: inverse(apply(f)) is not byte-identical to f")
            problems += [f"{p}: {x}" for x in ([] if schema else names.same_values(fams[0], text, new))]
        except (Problem, bee.ErreurBee, yaml.YAMLError, UnicodeDecodeError, ValueError, KeyError) as e:
            problems.append(f"{p}: {'unknown domain ' if isinstance(e, KeyError) else ''}{e}")
            continue
        images[q] = (p, new.encode("utf-8"), f"the translation of {p}")
        counts["schema" if schema else "data"] += 1
    if head is not None:
        after = tree_files(repo, head, after_modes)
        for q, (p, new, quoi) in images.items():
            if q in after_modes and new is not REMOVED and after_modes[q] != modes[p]:
                problems.append(f"{q}: mode {after_modes[q].decode()}, {p} had {modes[p].decode()}")
            if new is REMOVED:
                problems += [f"{q}: listed as removed, still in the head"] if q in after_modes else []
            elif q not in after_modes:
                problems.append(f"{p}: dropped (no {q} in the head)")
            elif new is not None and after.get(q) != new:
                problems.append(f"{q}: not {quoi}")
        problems += [f"{q}: added (the translation of no file of the base)" for q in after_modes
                     if q not in images and not any(r.match(q) for r in names.new)]
    return problems, counts


def translate_tree(names, source, dest, inv):
    """apply / inverse: every data file and schema of a tree, translated, at its translated path; returns how many."""
    n = 0
    for f in sorted(pathlib.Path(source).rglob("*")):
        rel = f.relative_to(source).as_posix()
        fr = names.path(rel, True) if inv else rel
        if f.is_file() and not rel.startswith(".git/") and (len(fams := names.families_of(fr)) == 1 or fr in names.schemas):
            out, texte = pathlib.Path(dest) / (fr if inv else names.path(rel)), f.read_text(encoding="utf-8")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((names.schema(names.schemas[fr], texte, inv) if fr in names.schemas else names.translate(fams[0], texte, inv)).encode())
            n += 1
    return n


def main(argv=None):
    p = argparse.ArgumentParser(prog="rename.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("lint", "apply", "inverse"):
        s = sub.add_parser(action)
        [s.add_argument(x) for x in (("source", "dest") if action != "lint" else ())]
        s.add_argument("--map", default=str(SELF.parent / "names.yaml"))
    s = sub.add_parser("check")
    [s.add_argument(o, required=o == "--base", default=str(SELF.parents[2]) if o == "--repo" else None) for o in ("--base", "--head", "--repo")]
    a, n, ecrits = p.parse_args(argv), collections.Counter(), None
    try:
        if a.action == "check":
            problems, n = check(a.repo, a.base, a.head)
        else:
            names, racine = Names(pathlib.Path(a.map).read_text(encoding="utf-8")), pathlib.Path(a.map).resolve().parents[2]
            problems = names.lint(lambda q: (racine / q).read_text(encoding="utf-8") if (racine / q).is_file() else None)
            if not problems and a.action != "lint":
                ecrits = translate_tree(names, a.source, a.dest, a.action == "inverse")
    except (Problem, bee.ErreurBee, yaml.YAMLError, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems = [f"{type(e).__name__}: {e}"]
    print("".join(f"✗ {x}\n" for x in problems) + f"{len(problems)} problem(s)." if problems else
          f"✓ P2 holds at {a.base}" + (f" for the head {a.head}: {n['data']} data files and {n['schema']} schemas are their translation "
                                       f"byte for byte, {n['same']} files are byte-identical (moved or replaced), {n['removed']} removed"
                                       if a.head else f" (no head): {n['data']} data files and {n['schema']} schemas translate and back "
                                       f"byte for byte, {n['same']} files are to stay byte-identical, {n['removed']} to be removed")
          + f"; {n['code']} code files are left to step 1b (P1, P1b, P3), checked here for their place and mode only." if a.action == "check"
          else "✓ the map is one-to-one in every family, and its schemas translate." if a.action == "lint" else f"✓ {ecrits} file(s) written.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
