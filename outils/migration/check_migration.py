#!/usr/bin/env python3
"""English names, step 1c (ruche-0143; docs/english-migration.md, sections 3, 9, 12 and 13): proofs P1b (c), P4, P6 and section
13's list, run with P1, P1b (a, b), P2 and P3 by `bee check-migration`, from a copy of the base (the base's own code, isolated):
    python3 -I outils/migration/check_migration.py --base REV --head REV [--generated REV] [--repo DIR]
--generated: the commit the switch script wrote (default: the head), which P1, P1b (a, b), P2 and P3 prove is translate(base);
the head's later commits are the hand-made part, code only; the other proofs judge the head. Exit 0: proven; 1: problems.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("check_migration.py: run it isolated, python3 -I outils/migration/check_migration.py …, so that nothing shadows a module")

import argparse, ast, collections, contextlib, importlib.util, io, json, os, pathlib, re, subprocess, tempfile, types  # noqa: E401, E402
from unittest import mock  # noqa: E402

SELF = pathlib.Path(__file__).resolve()
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import bee, rename, rename_code  # noqa: E402, E401

NOW = dict.fromkeys(("BEE_MAINTENANT", "BEE_NOW"), "2026-11-08T12:00:00Z")  # the tools' clock, before and after the move
READ_ONLY = (["valider"], ["lister", "--statut", "toutes", "--json"], ["cap", "--json"], ["essaim", "--json"], ["niveaux", "--json"],
             ["classement", "--json"], ["debats", "--json"])
OUTPUTS = {"lister": "out_list", "cap": "out_balance", "essaim": "out_swarm", "classement": "out_ranking", "niveaux": "out_levels",
           "debats": "out_debates", "site": "site_api"}  # P6: each JSON output and its family of the map
WRITE_ONLY_SCANS = {"cmd_proposer_tache": "R-d", "cmd_proposer": "R-d", "cmd_inviter": "R-d", "verifier_pr_de": "R-b"}  # P4 covers them
KEY_GROUPS = ("CLES_LIBRE_SERVICE_TACHE", "CLES_NAISSANCE", "CLES_CONFIRMATION", "CLES_DEBAT", "CLES_ARGUMENT", "CLES_IMMUABLES_DEBAT",
            "CLES_SYNTHESE", "CLES_CLOTURE", "CLES_INVITATION", "GESTES_INVITATION", "VERS_LE_CONTACT", "NATURES_INVITATION", "CHAMPS_PSEUDO",
            "CHAMPS_DE_LA_PERSONNE", "LIENS", "CREES_PAR", "CLES_ENTETE_NOEUD", "DECLARE_MAX", "VERDICT_MAX", "LIBRE_SERVICE", "POIDS_GESTES",
            "POSTE_PAR_TYPE", "ROLE_PAR_TYPE", "DOSSIERS_LIBRE_SERVICE", "FICHIERS_LIBRE_SERVICE", "OCTETS_MAX", "CHAMPS_LONGS",
            "TEXTES_PROPRES", "SCHEMAS_TEXTES", "PARCOURS", "CHEMINS_OUTILLAGE", "LISTES_LIEES", "DOSSIERS_GESTES")  # sections 3.1, 3.3
SAMPLES = ("taches/miniz/miniz-0001.yaml", "contributions/miniz/miniz-0001-c1.yaml", "votes/miniz-0001-c1/alice.yaml", "votes/P-0001/alice.yaml",
           "mesures/miniz-0001-c1/alice.yaml", "membres/alice.yaml", "propositions/P-0001.yaml", "invitations/I-0001.yaml",
           "invitations/ne-plus-contacter.yaml", "signalements/S-0001.yaml", "debats/D-0001.yaml", "gouvernance/incidents.yaml",
           "gouvernance/retraits.yaml", "docs/decisions.md", "taches/ruche/ruche-9001.yaml")  # a positive example of each shape


def load(path, name):
    """A tool's module from its file, under its own name (two tools live side by side)."""
    spec = importlib.util.spec_from_file_location(name, path)
    spec.loader.exec_module(module := importlib.util.module_from_spec(spec))
    return module


def checkout(files, dest, data, fixture):
    """A commit's files as a committed registry whose data is the frozen fixture (if the commit holds one, in its folder)."""
    data = data if any(p.startswith(fixture) for p in files) else set()
    for p, content in files.items():
        for q in [p[len(fixture):]] * p.startswith(fixture) + [p] * (p.split("/")[0] + "/" not in data):
            (dest / q).parent.mkdir(parents=True, exist_ok=True)
            (dest / q).write_bytes(content)
    who = {f"GIT_{r}_{k}": v for r in ("AUTHOR", "COMMITTER") for k, v in (("NAME", "x"), ("EMAIL", "x@x"), ("DATE", "2026-11-08T00:00:00Z"))}
    for argv in (["init", "-q"], ["add", "-A", "-f", "."], ["commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(dest), *argv], check=True, capture_output=True, env={**os.environ, **who})
    return dest


class Move:
    """The two tools and the map: o, n (modules: the base's on its fixture, the head's on the migrated one) and roots. i: an
    identifier of the old tool as the new one spells it; w: a name it holds (a text: its names), as the new one holds it."""

    def __init__(self, names, cm, tools, roots, tool_dir):
        self.names, self.cm, (self.o, self.n), self.roots, self.dir, self.i = names, cm, tools, roots, tool_dir, lambda x: cm.ids.get(x, x)
        self.argv = lambda argv, new: [self.w(x) if new and not x.startswith("/") else x for x in argv]  # a path stays

    def w(self, s, scope=""):
        self.cm.scoped(f"{self.dir}/bee.py", scope)
        return self.cm.whole(s) if re.fullmatch(rename_code.NAME_SHAPE, s) else self.cm.text(s)

    def mapped(self, v, scope=None):
        """A constant with its names mapped in its own scope (None: the new tool's, as it is); a regular expression aside."""
        f = lambda x: self.mapped(x, scope)  # noqa: E731
        return (v if scope is None else self.w(v, scope)) if isinstance(v, str) else {f(k): f(x) for k, x in v.items()} if isinstance(v, dict) \
            else type(v)(map(f, v)) if isinstance(v, (tuple, list, set, frozenset)) else "<re>" if isinstance(v, re.Pattern) else v

    def scans(self, t, root, new):
        """The tool on its registry: each glob, rglob and iterdir (caller, folder, pattern, files found), its Registre's sizes,
        the exit code of bee valider and each read-only command, and the removal scan (balayer)."""
        seen, real, inside = [], {m: getattr(pathlib.Path, m) for m in ("glob", "rglob", "iterdir")}, []

        def spy(m):
            def scan(path, *a, **k):
                if inside:  # rglob may glob: one scan
                    return real[m](path, *a, **k)
                inside.append(f := sys._getframe(1))
                found = list(real[m](path, *a, **k))
                inside.pop()
                while f and (f.f_code.co_filename != t.__file__ or f.f_code.co_name.startswith("<")):
                    f = f.f_back
                seen.append((f.f_code.co_name if f else "?", os.path.relpath(path, root), a[0] if a else "", len(found)))
                return iter(found)
            return scan
        n, codes = (self.i if new else str), []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), mock.patch.dict(os.environ, NOW), \
                mock.patch.multiple(pathlib.Path, **{m: spy(m) for m in real}):
            reg = getattr(t, n("Registre"))(root)
            sizes = {k: len(v) for k, v in vars(reg).items() if isinstance(v, (list, dict, set, tuple))}
            for argv in READ_ONLY:
                try:
                    codes.append(getattr(t, n("principal"))(self.argv(["--registre", str(root), *argv], new)) or 0)
                except SystemExit as e:
                    codes.append(e.code)
            getattr(t, n("balayer"))(reg, {self.w("empreintes") if new else "empreintes": []})
        return seen, sizes, codes

    def p1b_c(self):
        """validate, the loaders, the council files' check (R-u), the removal scan (R-g) and every glob literal find the same files."""
        (old, so, co), (new, sn, cn) = self.scans(self.o, self.roots[0], False), self.scans(self.n, self.roots[1], True)
        want = collections.Counter((self.i(c), self.names.path(d + "/")[:-1], self.w(p), k) for c, d, p, k in old)
        got, problems = collections.Counter(new), []
        problems += [f"P1b (c): {c} scans {d}/{p} and finds {k} file(s) only {w} the move" for x, w in ((want - got, "before"), (got - want, "after"))
                     for c, d, p, k in x]
        problems += [f"P1b (c): the registry's {k}: {v} before the move, {sn.get(self.cm.attrs.get(k, k))} after" for k, v in so.items()
                     if sn.get(self.cm.attrs.get(k, k)) != v]
        problems += [f"P1b (c): bee {' '.join(a)}: exit code {x} before the move, {y} after" for a, x, y in zip(READ_ONLY, co, cn) if x != y]
        callers = {c for c, *_ in old}
        data = sum(k for _, d, p, k in old if f"{d}/{p}".removeprefix("./").split("/")[0] + "/" in self.o.DOSSIERS_LIBRE_SERVICE)
        problems += [f"P1b (c): {c} finds no file: the check would prove nothing" for c, n in (("problemes_textes_du_conseil", None), ("balayer", None),
                     ("data folders", data)) if not (n if n is not None else sum(k for x, _, _, k in old if x == c))]
        sites = {f.name for f in ast.walk(ast.parse(pathlib.Path(self.o.__file__).read_text(encoding="utf-8"))) if isinstance(f, ast.FunctionDef)
                 for c in ast.walk(f) if isinstance(c, ast.Call) and getattr(c.func, "attr", None) in ("glob", "rglob", "iterdir")}
        problems += [f"P1b (c): the scan in {s} is not run here, nor covered by P4" for s in sorted(sites - callers - set(WRITE_ONLY_SCANS))]
        return problems, f"{len(old)} scans in {len(callers)} functions find the same {sum(k for *_, k in old)} files, {len(so)} collections"

    def classify(self, t, p, new):
        """What the path rules of the gate (plan, section 3.1) answer for one path, folder names as the old tool spells them."""
        g, back = (lambda x: getattr(t, self.i(x) if new else x)), (lambda k: k and self.names.path(k + "/" * ("/" not in k), True).rstrip("/") if new else k)
        raw = lambda s, a, b: f":{a} {b} {'0' * 40} {'1' * 40} {s}\0{p}\0"  # noqa: E731
        ci = tuple(g("ci_scope")(None, None, None, raw(*m))[0] for m in (("A", "000000", "100644"), ("A", "000000", "100755"), ("A", "000000", "120000"),
                                                                           ("M", "100644", "100644"), ("D", "100644", "000000")))
        with mock.patch.object(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, f"A\0{p}\0".encode(), b"")):
            date = g("date_compte_requise")(None, "b", "h")
        return {"self-service kind (R-e)": back(g("sorte_libre_service")(p)), "byte bound (R-e)": g("borne_octets")(p),
                "self-service folder (R-a)": p.startswith(tuple(g("DOSSIERS_LIBRE_SERVICE"))), "ci-scope (R-b, R-c, R-n)": ci,
                "data commit (R-o)": g("commit_de_donnees")(["p"], [(raw("M", "100644", "100644").split("\0")[0], p)], {p: 1}),
                "numbering (R-d)": tuple(m.groups() if (m := g(r).match(p)) else None for r in
                                         ("CHEMIN_TACHE", "CHEMIN_PROPOSITION", "CHEMIN_INVITATION", "CHEMIN_SIGNALEMENT", "CHEMIN_DEBAT")),
                "history (R-r)": bool(g("CHEMIN_HISTORIQUE").match(p)) and p.split("/")[0] in g("DOSSIERS_GESTES"),
                "removal scan (R-g)": back(g("sorte_parcourue")(p)), "tooling (R-h)": g("correspond")(p, g("CHEMINS_OUTILLAGE")),
                "authority (R-i)": p.casefold().startswith(tuple(a.casefold() for a in g("AUTHORITY_FILES"))),
                "linked list (R-j)": p in g("LISTES_LIEES"), "removals file (R-l)": p == g("CHEMIN_RETRAITS"), "account date (R-p)": date}

    def council_reads(self, t, corpus, new):
        """R-u: the paths the council files' check reads, on a tree that holds the corpus."""
        with tempfile.TemporaryDirectory() as tmp:
            for p in corpus:
                (pathlib.Path(tmp) / p).parent.mkdir(parents=True, exist_ok=True)
                (pathlib.Path(tmp) / p).write_text("a: 1\n", encoding="utf-8")
            read, real = [], pathlib.Path.read_text
            with mock.patch.object(pathlib.Path, "read_text", lambda s, *a, **k: read.append(s.relative_to(tmp).as_posix()) or real(s, *a, **k)):
                reg = types.SimpleNamespace(**{self.cm.attrs.get(k, k) if new else k: v for k, v in (
                    ("racine", pathlib.Path(tmp)), ("rel", lambda c: pathlib.Path(c).relative_to(tmp).as_posix()))})
                list(getattr(t, self.i("problemes_textes_du_conseil") if new else "problemes_textes_du_conseil")(reg))
            return set(read)

    def corpus(self, tracked):
        """{old path: its image}: every tracked path, the constants' own paths and a positive example of each shape, and their
        negative neighbours, made alike on both sides: the first folder capitalised, a folder more, another extension, a
        number of the tests' reserve."""
        o = self.o
        seeds = {*tracked, *SAMPLES, *(c.replace("*", "x.md") for c in o.CHEMINS_OUTILLAGE), *o.AUTHORITY_FILES, *o.LISTES_LIEES,
                 o.CHEMIN_RETRAITS, *(d.rstrip("/") + "/x.yaml" for d in (*o.DOSSIERS_LIBRE_SERVICE, *o.DOSSIERS_GESTES, *o.PARCOURS))}
        out = {p: self.names.path(p) for p in seeds if not p.endswith("/")}
        for f in (lambda p: (lambda h, t: h.capitalize() + "/" + t if t else p.upper())(*p.partition("/")[::2]),
                  lambda p: (lambda h, t: f"{h}/zz/{t}" if t else f"zz/{p}")(*p.partition("/")[::2]),
                  lambda p: re.sub(r"\.yaml\Z", ".yml", p), lambda p: re.sub(r"-[0-9]{4}(?=[./-])", "-9001", p)):
            out.update({f(p): f(q) for p, q in list(out.items()) if p in seeds})
        return out

    def p4(self, tracked):
        o, n, problems, images = self.o, self.n, [], self.corpus(tracked)
        corpus = sorted(images)
        for label, regex in (("FICHIERS_LIBRE_SERVICE", [r for _, r in o.FICHIERS_LIBRE_SERVICE.values()]), ("CHEMIN_DEBAT", [o.CHEMIN_DEBAT]),
                             ("PARCOURS", [r for r, *_ in o.PARCOURS.values()])):
            problems += [f"P4: {label}: no example of {r.pattern} in the corpus" for r in regex if not any(r.match(p) for p in corpus)]
        seeds = {p: q for p, q in images.items() if q == self.names.path(p)}
        problems += [f"P4: the map is not a bijection on the corpus: {p} -> {q} -> {self.names.path(q, True)}" for p, q in seeds.items()
                     if self.names.path(q, True) != p] + (["P4: two paths of the corpus map to one"] if len(set(images.values())) != len(images) else [])
        for p in corpus:
            a, b = self.classify(o, p, False), self.classify(n, images[p], True)
            problems += [f"P4: {p} -> {images[p]}: {k}: {a[k]!r} before the move, {b[k]!r} after" for k in a if a[k] != b[k]]
        reads = {images[p] for p in self.council_reads(o, corpus, False)}, self.council_reads(n, sorted(images.values()), True)
        problems += [f"P4: R-u: the council files' check reads {q} {'only before the move' if q in reads[0] else 'only after the move'}" for q in sorted(reads[0] ^ reads[1])]
        retired = [p for p in corpus if any(p == r or r.endswith("/") and p.startswith(r) for r in self.names.m["retired"])]
        for p in retired:  # R-q: a retired French path, read by the new tool as it is
            c = self.classify(n, p, True)
            if "data" in c["ci-scope (R-b, R-c, R-n)"] or c["data commit (R-o)"] or c["history (R-r)"] or c["removal scan (R-g)"]:
                problems.append(f"P4: R-q: {p}, a retired name, is still data for the new tool")
        guard = getattr(n, "retired_name", None)  # the guard the switch's hand-made part adds: path -> its refusal, or None
        problems += [f"P4: R-q: {p} is {'not refused by' if p in retired else 'refused by'} the retired-names guard" for p in [*retired, *images.values()]
                     if guard and bool(guard(p)) != (p in retired)] or ([] if guard else ["P4: R-q: no retired-names guard (retired_name, the hand-made part)"])
        problems += [f"P4: R-i: {a} left AUTHORITY_FILES (an old name is kept for good)" for a in o.AUTHORITY_FILES if a not in n.AUTHORITY_FILES]
        for k in KEY_GROUPS:  # section 3.3: map(old set) == new set, each member mapped in its constant's own scope
            if (x := self.mapped(getattr(o, k), k)) != (y := self.mapped(getattr(n, self.i(k), None))):
                problems.append(f"P4: {k}: the map of the old set is {x!r:.300}, the new tool has {y!r:.300}")
        return problems, f"{len(corpus)} paths ({len(retired)} retired) classified alike by the rules R-a to R-u, {len(KEY_GROUPS)} key sets equal"

    def same_json(self, x, y, where=""):
        """An output as the map makes it (x) against the new one: the same keys and values; a text, through the map's names."""
        if isinstance(x, dict) and isinstance(y, dict):
            return [p for k in x for p in self.same_json(x[k], y[k], f"{where}/{k}")] if set(x) == set(y) else [
                f"{where or '/'}: the keys {sorted(set(x) - set(y))} expected, {sorted(set(y) - set(x))} found"]
        if isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            return [p for k, (a, b) in enumerate(zip(x, y)) for p in self.same_json(a, b, f"{where}[{k}]")]
        return [] if x == y or isinstance(x, str) and isinstance(y, str) and self.cm.string_change(x, y) is not None else [
            f"{where}: {x!r:.100} expected, {y!r:.100} found"]

    def run(self, root, argv, new):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root.parent), "LANG": "C.UTF-8", **NOW}
        tool = root / (self.names.path(f"{self.dir}/bee.py") if new else f"{self.dir}/bee.py")
        r = subprocess.run([sys.executable, "-E", "-s", str(tool), *self.argv(["--registre", str(root), *argv], new)],
                           capture_output=True, text=True, env=env, cwd=root, timeout=600)
        return r.returncode, r.stdout

    def p6(self):
        """Each read-only command on the fixture, then on the migrated fixture: the same output modulo the map (a JSON output
        through its family, strictly; a text, token by token through the map, and its data frame strictly)."""
        problems, task = [], next(p.stem for p in sorted((self.roots[0] / "taches").glob("*/*.yaml")))
        argvs = [*READ_ONLY[1:], ["voir", task], ["contexte", task], ["site", "--sortie", "SITE"]]
        for argv in argvs:
            (x, a), (y, b) = (self.run(r, [str(r.parent / f"site-{k}") if v == "SITE" else v for v in argv], k) for k, r in enumerate(self.roots))
            if argv[0] == "site":
                a, b = (next((r.parent / f"site-{k}/api").glob("*.json")).read_text(encoding="utf-8") for k, r in enumerate(self.roots))
            if x or y:  # a failure on both sides proves nothing
                problems.append(f"P6: bee {' '.join(argv)}: exit code {x} before the move, {y} after")
            elif argv[0] in OUTPUTS:
                try:
                    problems += [f"P6: bee {' '.join(argv)}: {x}" for x in self.same_json(self.names.data(OUTPUTS[argv[0]], json.loads(a), False), json.loads(b))[:3]]
                except (rename.Problem, ValueError, KeyError) as e:
                    problems.append(f"P6: bee {' '.join(argv)}: {type(e).__name__}: {e}")
            else:
                frames = [[bee.charger_texte_yaml(re.sub(r"(?m)^\| ?", "", (re.search(r"(?m)^(?:\|(?: .*)?\n)+", t) or [""])[0]))] for t in (a, b)]  # the first
                fam = self.names.families_of(f"taches/{task.rsplit('-', 1)[0]}/{task}.yaml")[0]
                size = lambda t: re.sub(r"(?<=Environ )[0-9]+(?= jetons)", "N", t)  # noqa: E731  (contexte's size counts renamed names)
                if self.names.data(fam, frames[0][0], False) != frames[1][0] or self.cm.string_change(size(a), size(b)) is None:
                    problems.append(f"P6: bee {' '.join(argv)}: the output differs otherwise than through the map")
        return problems, f"{len(argvs)} outputs equal modulo the map"


def section_13(names, base, head):
    """Beyond head == translate(base): debates and their arguments, the council, guardians, guarantors and agent accounts the
    same modulo the map; reserved logins unchanged; each family's file count equal, and some data at all."""
    problems, counts, read = [], [collections.Counter(), collections.Counter()], lambda f, p: bee.charger_texte_yaml(f[p].decode("utf-8"), p)
    for k, files in enumerate((base, head)):
        [counts[k].update(names.families_of(names.path(p, True) if k else p)) for p in files]
    problems += [f"section 13: family {f}: {counts[0][f]} file(s) at the base, {counts[1][f]} at the head" for f in names.fam if counts[0][f] != counts[1][f]]
    problems += [] if sum(counts[0].values()) else ["section 13: no data file at the base"]
    arguments = 0
    for p in sorted(p for p in base if {"debates", "council", "guardians", "guarantors", "agent_accounts"} & set(names.families_of(p))):
        fam, q = names.families_of(p)[0], names.path(p)
        if q not in head or names.data(fam, old := read(base, p), False) != read(head, q):
            problems.append(f"section 13: {q} is not {p} modulo the map")
        arguments += len(old.get("arguments") or []) if fam == "debates" and q in head else 0
    key = names.side("config", False)["keys"]["pseudos_reserves"]
    if read(base, "bee.yaml")["pseudos_reserves"] != read(head, "bee.yaml").get(key):
        problems.append("section 13: the reserved logins changed")
    empty = sorted(f for f in names.fam if names.fam[f]["files"] and not counts[0][f])
    return problems, (f"{counts[0]['debates']} debates ({arguments} arguments), the council, guardians, guarantors and agent accounts equal modulo the "
                      f"map; reserved logins unchanged; {sum(counts[0].values())} data files, each family's count equal"
                      + (f" (empty at the base: {', '.join(empty)})" if empty else ""))


def hand_part(repo, names, generated, head, after):
    """The head's commits on top of the generated one, the hand-made part: code files only."""
    mid, code = rename.tree_files(repo, generated), {names.path(p) for p in names.code}
    hand = sorted(q for q in {*mid, *after} if mid.get(q) != after.get(q))
    return [f"the hand-made part: {generated} is not an ancestor of {head}"] * bool(subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", generated, head]).returncode) + [
        f"the hand-made part changes {q}, which is not code" for q in hand if q not in code], f"hand-made part ({generated}..{head}): {len(hand)} code file(s): {', '.join(hand)}"


def check(repo, base, head, generated=None):
    """bee check-migration. Returns (problems, summary lines)."""
    generated, lines, files = generated or head, [], rename.tree_files(repo, base)
    if (at := next((c for c in rename.MAPS if c in files), None)) is None or files.get(at.replace("names.yaml", SELF.name)) != SELF.read_bytes():
        return [f"{SELF} is not the base's own: run the base's checker, python3 -I, from its checkout (bee check-migration does)"], lines
    p2, n2 = rename.check(repo, base, generated)
    lines.append(f"P2: {len(p2)} problem(s)" if p2 else f"P2: ✓ {n2['data']} data files and {n2['schema']} schemas are their translation, "
                 f"{n2['same']} files byte-identical, {n2['removed']} removed, {n2['code']} code files placed")
    p1, n1 = rename_code.check(repo, base, generated)
    lines.append(f"P1, P1b (a, b), P3: {len(p1)} problem(s)" if p1 else f"P1, P1b (a, b), P3: ✓ {sum(n1.values())} names renamed through the map, "
                 "nothing else changed, no French name left, every attribute name resolves, the parser is the same")
    problems, after = p2 + p1, rename.tree_files(repo, head)
    tool_dir, names = at.rpartition("/migration/")[0], rename.Names(files[at].decode("utf-8"))
    cm = rename_code.CodeMap(names, files[rename_code.IDS[rename.MAPS.index(at)]].decode("utf-8"))
    if generated != head:
        found, said = hand_part(repo, names, generated, head, after)
        problems, lines = problems + found, lines + [said]
    with tempfile.TemporaryDirectory() as tmp:
        fixture, data = f"{tool_dir}/tests/registre/", set(bee.DOSSIERS_LIBRE_SERVICE)
        roots = (checkout(files, pathlib.Path(tmp) / "base" / "r", data, fixture),
                 checkout(after, pathlib.Path(tmp) / "head" / "r", {names.path(d) for d in data}, names.path(fixture)))
        for label, proof in (("P1b (c)", "p1b_c"), ("P4", "p4"), ("P6", "p6")):
            try:  # the new tool runs: a head that breaks a proof is a refusal, never a crash
                move = move if label != "P1b (c)" else Move(names, cm, (load(roots[0] / f"{tool_dir}/bee.py", "bee_before_the_move"), load(
                    roots[1] / names.path(f"{tool_dir}/bee.py"), "bee_after_the_move")), roots, tool_dir)
                found, said = getattr(move, proof)(*[sorted(files)] * (label == "P4"))
            except Exception as e:  # noqa: BLE001
                found, said = [f"{label}: the new tool fails: {type(e).__name__}: {e}"], ""
            problems += found
            lines.append(f"{label}: {len(found)} problem(s)" if found else f"{label}: ✓ {said}")
    found, said = section_13(names, files, after)
    lines.append(f"section 13: {len(found)} problem(s)" if found else f"section 13: ✓ {said}")
    return problems + found, lines


def main(argv=None):
    p = argparse.ArgumentParser(prog="check_migration.py", description=__doc__.split("\n\n")[0])
    [p.add_argument(o, required=o in ("--base", "--head"), default=str(SELF.parents[2]) if o == "--repo" else None) for o in ("--base", "--head", "--generated", "--repo")]
    a = p.parse_args(argv)
    try:
        problems, lines = check(a.repo, a.base, a.head, a.generated)
    except (rename.Problem, bee.ErreurBee, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems, lines = [f"{type(e).__name__}: {e}"], []
    print("".join(f"✗ {x}\n" for x in problems) + "".join(f"{x}\n" for x in lines) + (f"✗ {len(problems)} problem(s): the head {a.head} is not proven"
          if problems else f"✓ the head {a.head}" + (f" (generated {a.generated}, then the hand-made part)" if a.generated else "") + " is proven")
          + f" to be the switch of the base {a.base}.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
