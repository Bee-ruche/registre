#!/usr/bin/env python3
"""English names, step 1c (ruche-0143; docs/english-migration.md, sections 3, 9, 12 and 13): proofs P1b (c), P4, P6 and section
13's list, run with P1, P1b (a, b), P2 and P3 by `bee check-migration`, from a copy of the base (the base's own code, isolated):
    python3 -I outils/migration/check_migration.py --base REV --head REV [--generated REV] [--repo DIR] [--observe FILE | --observed FILE]
--generated: the commit the switch script wrote (default: the head), which P1, P1b (a, b), P2 and P3 prove is translate(base);
the head's later commits are the hand-made part, listed file by file, code only. The process that decides never loads code of
the head: workers (python3 -I, an empty environment) run each tool and write what they saw as JSON, which the base's code checks
and compares. --observe: only run the head's tool, its observations to FILE (the workflow's first job); --observed: read them
from FILE instead of running the head's code (its second job). Exit 0: proven; 1: problems.
"""
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    sys.exit("check_migration.py: run it isolated, python3 -I outils/migration/check_migration.py …, so that nothing shadows a module")

import argparse, ast, collections, contextlib, importlib.util, io, json, math, os, pathlib, re, subprocess, tempfile, types  # noqa: E401, E402
from unittest import mock  # noqa: E402

SELF = pathlib.Path(__file__).resolve()
sys.path += [str(SELF.parent.parent), str(SELF.parent)]  # last: never in front of the standard library or PyYAML
import bee, rename, rename_code  # noqa: E402, E401

NOW = dict.fromkeys(("BEE_MAINTENANT", "BEE_NOW"), "2026-11-08T12:00:00Z")  # the tools' clock, before and after the move
KEPT = ("PATH", "LD_LIBRARY_PATH")  # a worker's environment: these (the interpreter's and git's), the clock, a scratch home; nothing else
BOOT = "import runpy, sys; sys.argv = sys.argv[1:]; sys.path.insert(0, sys.argv[0].rpartition('/')[0]); runpy.run_path(sys.argv[0], run_name='__main__')"
OBSERVED_MAX = 256 << 20  # bytes of observations read at most
READ_ONLY = (["valider"], ["lister", "--statut", "toutes", "--json"], ["cap", "--json"], ["essaim", "--json"], ["niveaux", "--json"],
             ["classement", "--json"], ["debats", "--json"])
OUTPUTS = {"lister": "out_list", "cap": "out_balance", "essaim": "out_swarm", "classement": "out_ranking", "niveaux": "out_levels",
           "debats": "out_debates"}  # P6: each JSON output and its family of the map
API = {"registre.json": ("site_api", "generer")}  # P6: each file of the site's api/, its family and the scope of site_bee.py that names it
WRITE_ONLY_SCANS = {"cmd_proposer_tache": "R-d", "cmd_proposer": "R-d", "cmd_inviter": "R-d", "verifier_pr_de": "R-b"}  # P1 and P4 cover them
KEY_GROUPS = ("CLES_LIBRE_SERVICE_TACHE", "CLES_NAISSANCE", "CLES_CONFIRMATION", "CLES_DEBAT", "CLES_ARGUMENT", "CLES_IMMUABLES_DEBAT",
              "CLES_SYNTHESE", "CLES_CLOTURE", "CLES_INVITATION", "GESTES_INVITATION", "VERS_LE_CONTACT", "NATURES_INVITATION", "CHAMPS_PSEUDO",
              "CHAMPS_DE_LA_PERSONNE", "LIENS", "CREES_PAR", "CLES_ENTETE_NOEUD", "DECLARE_MAX", "VERDICT_MAX", "LIBRE_SERVICE", "POIDS_GESTES",
              "POSTE_PAR_TYPE", "ROLE_PAR_TYPE", "DOSSIERS_LIBRE_SERVICE", "FICHIERS_LIBRE_SERVICE", "OCTETS_MAX", "CHAMPS_LONGS",
              "TEXTES_PROPRES", "SCHEMAS_TEXTES", "PARCOURS", "CHEMINS_OUTILLAGE", "LISTES_LIEES", "DOSSIERS_GESTES")  # sections 3.1, 3.3
CALLED = ("Registre", "principal", "balayer", "problemes_textes_du_conseil", "ci_scope", "date_compte_requise", "sorte_libre_service",
          "borne_octets", "commit_de_donnees", "sorte_parcourue", "correspond", "DOSSIERS_LIBRE_SERVICE", "CHEMIN_TACHE", "CHEMIN_PROPOSITION",
          "CHEMIN_INVITATION", "CHEMIN_SIGNALEMENT", "CHEMIN_DEBAT", "CHEMIN_HISTORIQUE", "DOSSIERS_GESTES", "CHEMINS_OUTILLAGE",
          "AUTHORITY_FILES", "LISTES_LIEES", "CHEMIN_RETRAITS")  # what a worker calls of a tool, as the old one spells it
LABELS = ("self-service kind (R-e)", "byte bound (R-e)", "self-service folder (R-a)", "ci-scope (R-b, R-c, R-n)", "data commit (R-o)",
          "numbering (R-d)", "history (R-r)", "removal scan (R-g)", "tooling (R-h)", "authority (R-i)", "linked list (R-j)",
          "removals file (R-l)", "account date (R-p)")  # P4: what the path rules of the gate answer for a path
SAMPLES = ("taches/miniz/miniz-0001.yaml", "contributions/miniz/miniz-0001-c1.yaml", "votes/miniz-0001-c1/alice.yaml", "votes/P-0001/alice.yaml",
           "mesures/miniz-0001-c1/alice.yaml", "membres/alice.yaml", "propositions/P-0001.yaml", "invitations/I-0001.yaml",
           "invitations/ne-plus-contacter.yaml", "signalements/S-0001.yaml", "debats/D-0001.yaml", "gouvernance/incidents.yaml",
           "gouvernance/retraits.yaml", "docs/decisions.md", "taches/ruche/ruche-9001.yaml")  # a positive example of each shape
SHAPES = {"scans": {"seen": [(str, str, str, int)], "sizes": {str: int}, "codes": [{int, str, type(None)}]}, "classes": {str: dict.fromkeys(LABELS)},
          "council": [str], "guard": {"exists": bool, "refused": {str: bool}}, "constants": {str: None}, "outputs": [{"code": int, "stdout": str}],
          "api": {str: str}, "errors": {str: str}}  # what a worker writes (see fits)
SECTIONS = {"P1b (c)": ("scans",), "P4": ("classes", "council", "guard", "constants"), "P6": ("outputs", "api")}
FRAME = re.compile(r"((?:^\|(?: .*)?(?:\n|\Z))+)", re.M)  # a data frame of a text output: its lines, each after « | »


PATTERN = type("Pattern", (), {"__repr__": lambda s: "<re>"})()  # what a regular expression decodes to: P4 compares no pattern


def encoded(v):
    """A value as JSON that keeps its type: a container is [its kind, its items]; a regular expression, ["re", ""]; else its type's name."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    kind = next((k for k in (dict, tuple, list, frozenset, set) if isinstance(v, k)), None)
    return ["re", ""] if isinstance(v, re.Pattern) else ["other", type(v).__name__] if kind is None else \
        ["dict", [[encoded(k), encoded(x)] for k, x in v.items()]] if kind is dict else [kind.__name__, [encoded(x) for x in v]]


def decoded(x):
    """encoded's inverse, on untrusted JSON: plain values only (no object of the worker's can compare equal to anything); else ValueError."""
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    kinds = {"tuple": tuple, "list": list, "set": set, "frozenset": frozenset}
    if not (isinstance(x, list) and len(x) == 2 and (x[0] in (*kinds, "dict") and isinstance(x[1], list) or x[0] in ("other", "re") and isinstance(x[1], str))):
        raise ValueError(f"not a value: {x!r:.80}")
    if x[0] in ("other", "re"):
        return ("<other>", x[1]) if x[0] == "other" else PATTERN
    if x[0] == "dict":
        if not all(isinstance(p, list) and len(p) == 2 for p in x[1]):
            raise ValueError(f"not a dict: {x!r:.80}")
        return {decoded(k): decoded(v) for k, v in x[1]}
    return kinds[x[0]](map(decoded, x[1]))


def fits(x, s):
    """Whether untrusted JSON x has the shape s: a type (a bool is no int); a set of types, any of them; [s], a list of s; (s, …),
    a list of these; {str: s}, a dict of s; {"k": s, …}, exactly these keys; None, anything (dec reads it)."""
    if s is None:
        return True
    if isinstance(s, type):
        return isinstance(x, s) and not (s is int and isinstance(x, bool))
    if isinstance(s, (set, list, tuple)):
        return any(fits(x, t) for t in s) if isinstance(s, set) else isinstance(x, list) and (
            all(fits(y, s[0]) for y in x) if isinstance(s, list) else len(x) == len(s) and all(map(fits, x, s)))
    if list(s) == [str]:
        return isinstance(x, dict) and all(isinstance(k, str) and fits(v, s[str]) for k, v in x.items())
    return isinstance(x, dict) and set(x) == set(s) and all(fits(x[k], s[k]) for k in s)


# --- the worker: a process of its own that runs one tool; what it writes is only data for the base's code ---

def load(path, name):
    """A tool's module from its file, under its own name."""
    spec = importlib.util.spec_from_file_location(name, path)
    spec.loader.exec_module(module := importlib.util.module_from_spec(spec))
    return module


def observe(plan):
    """A worker's work: run the tool at plan["tool"] as the plan says; what it saw, as JSON (each part, or its error)."""
    out = {"errors": {}}

    def part(name, f):
        try:
            out[name] = f()
        except BaseException as e:  # noqa: BLE001 - a tool that fails, or exits, is a refusal, never a crash
            out["errors"][name] = f"{type(e).__name__}: {e}"
    if "parser" in plan:
        part("parser", lambda: encoded(rename_code.parser_rows(getattr(load(plan["tool"], "the_new_tool"), plan["parser"])())))
        return out
    tool = []
    part("load", lambda: tool.append(load(plan["tool"], "the_tool")))
    t, g = (tool or [None])[0], lambda x: getattr(tool[0], plan["ids"][x])
    if "read_only" in plan:
        part("scans", lambda: scans(t, g, plan))
    if "corpus" in plan:
        part("classes", lambda: {p: {k: encoded(v) for k, v in classify(g, p).items()} for p in plan["corpus"]})
        part("council", lambda: council_reads(g, plan))
        part("guard", lambda: {"exists": callable(f := getattr(t, plan["guard"]["name"], None)),
                               "refused": {p: bool(f(p)) for p in plan["guard"]["paths"]} if callable(f) else {}})
        part("constants", lambda: {k: encoded(getattr(t, k)) for k in plan["constants"] if hasattr(t, k)})
    if "commands" in plan:
        part("outputs", lambda: [(lambda r: {"code": r.returncode, "stdout": r.stdout})(subprocess.run(
            [sys.executable, "-I", "-c", BOOT, plan["tool"], *argv], capture_output=True, text=True, errors="replace", env=dict(os.environ),
            cwd=plan["root"], timeout=600)) for argv in plan["commands"]])
        api = pathlib.Path(plan["api"])
        part("api", lambda: {f.relative_to(api).as_posix(): f.read_text(encoding="utf-8", errors="replace") for f in sorted(api.rglob("*")) if f.is_file()})
    return out


def scans(t, g, plan):
    """The tool on its registry: each glob, rglob and iterdir (caller, folder, pattern, files found), its Registre's sizes, the exit
    code of bee valider and each read-only command, and the removal scan (balayer)."""
    root, seen, real, inside = pathlib.Path(plan["root"]), [], {m: getattr(pathlib.Path, m) for m in ("glob", "rglob", "iterdir")}, []

    def spy(m):
        def scan(path, *a, **k):
            if inside:  # rglob may glob: one scan
                return real[m](path, *a, **k)
            inside.append(f := sys._getframe(1))
            found = list(real[m](path, *a, **k))
            inside.pop()
            while f and (f.f_code.co_filename != t.__file__ or f.f_code.co_name.startswith("<")):
                f = f.f_back
            seen.append((f.f_code.co_name if f else "?", os.path.relpath(path, root), str(a[0]) if a else "", len(found)))
            return iter(found)
        return scan
    codes = []
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), mock.patch.multiple(pathlib.Path, **{m: spy(m) for m in real}):
        reg = g("Registre")(root)
        sizes = {k: len(v) for k, v in vars(reg).items() if isinstance(v, (list, dict, set, tuple))}
        for argv in plan["read_only"]:
            try:
                codes.append(g("principal")(argv) or 0)
            except SystemExit as e:
                codes.append(e.code if isinstance(e.code, (int, str, type(None))) else repr(e.code))
        g("balayer")(reg, plan["sweep"])
    return {"seen": seen, "sizes": sizes, "codes": codes}


def classify(g, p):
    """What the path rules of the gate (plan, section 3.1) answer for one path, as the tool says it."""
    raw = lambda s, a, b: f":{a} {b} {'0' * 40} {'1' * 40} {s}\0{p}\0"  # noqa: E731
    ci = tuple(g("ci_scope")(None, None, None, raw(*m))[0] for m in (("A", "000000", "100644"), ("A", "000000", "100755"), ("A", "000000", "120000"),
                                                                       ("M", "100644", "100644"), ("D", "100644", "000000")))
    with mock.patch.object(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, f"A\0{p}\0".encode(), b"")):
        date = g("date_compte_requise")(None, "b", "h")
    return dict(zip(LABELS, (g("sorte_libre_service")(p), g("borne_octets")(p), p.startswith(tuple(g("DOSSIERS_LIBRE_SERVICE"))), ci,
                             g("commit_de_donnees")(["p"], [(raw("M", "100644", "100644").split("\0")[0], p)], {p: 1}),
                             tuple(m.groups() if (m := g(r).match(p)) else None for r in
                                   ("CHEMIN_TACHE", "CHEMIN_PROPOSITION", "CHEMIN_INVITATION", "CHEMIN_SIGNALEMENT", "CHEMIN_DEBAT")),
                             bool(g("CHEMIN_HISTORIQUE").match(p)) and p.split("/")[0] in g("DOSSIERS_GESTES"), g("sorte_parcourue")(p),
                             g("correspond")(p, g("CHEMINS_OUTILLAGE")), p.casefold().startswith(tuple(a.casefold() for a in g("AUTHORITY_FILES"))),
                             p in g("LISTES_LIEES"), p == g("CHEMIN_RETRAITS"), date)))


def council_reads(g, plan):
    """R-u: the paths the council files' check reads, on a tree that holds the corpus."""
    with tempfile.TemporaryDirectory() as tmp:
        for p in plan["council"]:
            (pathlib.Path(tmp) / p).parent.mkdir(parents=True, exist_ok=True)
            (pathlib.Path(tmp) / p).write_text("a: 1\n", encoding="utf-8")
        read, real = [], pathlib.Path.read_text
        with mock.patch.object(pathlib.Path, "read_text", lambda s, *a, **k: read.append(s.relative_to(tmp).as_posix()) or real(s, *a, **k)):
            racine, rel = plan["attrs"]
            list(g("problemes_textes_du_conseil")(types.SimpleNamespace(**{racine: pathlib.Path(tmp), rel: lambda c: pathlib.Path(c).relative_to(tmp).as_posix()})))
        return sorted(set(read))


def work(plan, tmp):
    """A worker on plan, in a process of its own (python3 -I -E -s, an empty environment, a scratch home): its observations."""
    d = pathlib.Path(tempfile.mkdtemp(dir=tmp))
    (d / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    env = {k: os.environ[k] for k in KEPT if k in os.environ} | NOW | {"HOME": str(d), "LANG": "C.UTF-8"}
    try:
        r = subprocess.run([sys.executable, "-I", "-E", "-s", str(SELF), "--worker", str(d / "plan.json"), str(d / "observed.json")], env=env, cwd=d,
                           capture_output=True, text=True, errors="replace", timeout=2400)
    except subprocess.TimeoutExpired:
        return {"errors": {"*": "no observations: the worker ran out of time (40 minutes)"}}
    return read_observations(d / "observed.json", f"the worker exited {r.returncode}" + "".join(f": {x:.200}" for x in r.stderr.strip().splitlines()[-1:]))


def read_observations(path, why=""):
    """Observations as a worker, or the workflow's first job, wrote them: untrusted JSON, bounded; none, an error that says so."""
    try:
        if pathlib.Path(path).stat().st_size > OBSERVED_MAX:
            raise ValueError(f"more than {OBSERVED_MAX} bytes")
        if isinstance(x := json.loads(pathlib.Path(path).read_text(encoding="utf-8")), dict):
            return x
        raise ValueError("not an object")
    except (OSError, ValueError, RecursionError) as e:
        return {"errors": {"*": f"no observations ({type(e).__name__}: {e}{'; ' + why if why else ''})"}}


def worker_rows(tmp):
    """P3, for rename_code.check: the new tool's parser rows, read by a worker once P1 holds for that tool."""
    def rows(path, name):
        x = work({"tool": str(path), "parser": name}, tmp)
        if not isinstance(r := decoded(x.get("parser")), list):
            raise rename.Problem((x.get("errors") or {}).get("parser") or (x.get("errors") or {}).get("*") or "no parser rows")
        return r
    return rows


# --- the base's code: what each tool should see, and the comparison ---

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
    """The two tools and the map: names, cm, dir (the tools' folder at the base), the base's files. i: an identifier of the old
    tool as the new one spells it; w: a name it holds (a text: its names), as the new one holds it. The old tool's constants are
    the base's own module's (bee: this checker runs from the base); each tool runs in a worker."""

    def __init__(self, names, cm, tool_dir, files):
        self.names, self.cm, self.dir, self.i = names, cm, tool_dir, lambda x: cm.ids.get(x, x)
        self.fixture = f"{tool_dir}/tests/registre/"
        self.data = {p[len(self.fixture):]: c for p, c in files.items() if p.startswith(self.fixture)} or files  # what the old tool reads
        self.images = self.corpus(sorted(files))
        self.retired = [p for p in sorted(self.images) if any(p == r or r.endswith("/") and p.startswith(r) for r in names.m["retired"])]
        task = next((p.rpartition("/")[2][:-5] for p in sorted(self.data) if re.fullmatch(r"taches/[^/]+/[^/]+\.yaml", p)), "?")
        self.commands = [*READ_ONLY[1:], ["voir", task], ["contexte", task], ["site", "--sortie", "SITE"]]

    def w(self, s, scope=""):
        self.cm.scoped(f"{self.dir}/bee.py", scope)
        return self.cm.whole(s) if re.fullmatch(rename_code.NAME_SHAPE, s) else self.cm.text(s)

    def argv(self, argv, new):
        return [self.w(x) if new and not x.startswith("/") else x for x in argv]  # a path stays

    def mapped(self, v, scope=None):
        """A constant with its names mapped in its own scope (None: the new tool's, as it is)."""
        f = lambda x: self.mapped(x, scope)  # noqa: E731
        return (v if scope is None else self.w(v, scope)) if isinstance(v, str) else {f(k): f(x) for k, x in v.items()} if isinstance(v, dict) \
            else type(v)(map(f, v)) if isinstance(v, (tuple, list, set, frozenset)) else v

    def root(self, files, tmp, new):
        """A scratch checkout for one tool: the base's files on the fixture, or the head's on the migrated fixture."""
        data, path = set(bee.DOSSIERS_LIBRE_SERVICE), (lambda p: self.names.path(p)) if new else str
        return checkout(files, pathlib.Path(tmp) / ("head" if new else "base") / "r", {path(d) for d in data}, path(self.fixture))

    def plan(self, root, new, parts=("p1b_c", "p4", "p6")):
        """What a worker runs: the old tool (new False) on the fixture, or the new one on the migrated fixture; paths as given."""
        n, site = self.i if new else str, root.parent / f"site-{int(new)}"
        plan = {"tool": str(root / (self.names.path(f"{self.dir}/bee.py") if new else f"{self.dir}/bee.py")), "root": str(root), "ids": {x: n(x) for x in CALLED}}
        if "p1b_c" in parts:
            plan |= {"read_only": [self.argv(["--registre", str(root), *a], new) for a in READ_ONLY], "sweep": {self.w("empreintes") if new else "empreintes": []}}
        if "p4" in parts:
            plan |= {"corpus": self.corpus_of(new), "council": sorted(self.images.values()) if new else sorted(self.images),
                     "attrs": [self.cm.attrs.get(k, k) if new else k for k in ("racine", "rel")], "constants": [n(k) for k in (*KEY_GROUPS, "AUTHORITY_FILES")],
                     "guard": {"name": "retired_name", "paths": self.guarded(new)}}
        if "p6" in parts:
            plan |= {"commands": [self.argv(["--registre", str(root), *(str(site) if x == "SITE" else x for x in a)], new) for a in self.commands],
                     "api": str(site / "api")}
        return plan

    def corpus_of(self, new):
        return sorted({*self.images.values(), *self.retired}) if new else sorted(self.images)

    def guarded(self, new):
        return sorted({*self.retired, *self.images.values()}) if new else []

    def corpus(self, tracked):
        """{old path: its image}: every tracked path, the constants' own paths and a positive example of each shape, and their
        negative neighbours, made alike on both sides: the first folder capitalised, a folder more, another extension, a
        number of the tests' reserve."""
        o = bee
        seeds = {*tracked, *SAMPLES, *(c.replace("*", "x.md") for c in o.CHEMINS_OUTILLAGE), *o.AUTHORITY_FILES, *o.LISTES_LIEES,
                 o.CHEMIN_RETRAITS, *(d.rstrip("/") + "/x.yaml" for d in (*o.DOSSIERS_LIBRE_SERVICE, *o.DOSSIERS_GESTES, *o.PARCOURS))}
        out = {p: self.names.path(p) for p in seeds if not p.endswith("/")}
        for f in (lambda p: (lambda h, t: h.capitalize() + "/" + t if t else p.upper())(*p.partition("/")[::2]),
                  lambda p: (lambda h, t: f"{h}/zz/{t}" if t else f"zz/{p}")(*p.partition("/")[::2]),
                  lambda p: re.sub(r"\.yaml\Z", ".yml", p), lambda p: re.sub(r"-[0-9]{4}(?=[./-])", "-9001", p)):
            out.update({f(p): f(q) for p, q in list(out.items()) if p in seeds})
        return out

    def shape(self, x, new):
        """Problems if a worker's observations are not shaped as its plan asks: they may come from a process that ran the head's code."""
        problems = [f"{k}: not shaped as asked" for k, s in SHAPES.items() if k in x and not fits(x[k], s)]
        problems += [f"{k}: unknown" for k in x if k not in (*SHAPES, "load")]
        if not problems and "classes" in x and set(x["classes"]) != set(self.corpus_of(new)):
            problems.append("classes: not the corpus asked")
        if not problems and "outputs" in x and len(x["outputs"]) != len(self.commands):
            problems.append(f"outputs: {len(x['outputs'])}, not {len(self.commands)}")
        if not problems and "guard" in x and x["guard"]["exists"] and set(x["guard"]["refused"]) != set(self.guarded(new)):
            problems.append("guard: not the paths asked")
        return problems

    def p1b_c(self, o, n):
        """validate, the loaders, the council files' check (R-u), the removal scan (R-g) and every glob literal find the same files."""
        (old, so, co), (new, sn, cn) = ((x["scans"]["seen"], x["scans"]["sizes"], x["scans"]["codes"]) for x in (o, n))
        want = collections.Counter((self.i(c), self.names.path(d + "/")[:-1], self.w(p), k) for c, d, p, k in old)
        got, problems = collections.Counter(map(tuple, new)), []
        problems += [f"P1b (c): {c} scans {d}/{p} and finds {k} file(s) only {w} the move" for x, w in ((want - got, "before"), (got - want, "after"))
                     for c, d, p, k in x]
        problems += [f"P1b (c): the registry's {k}: {v} before the move, {sn.get(self.cm.attrs.get(k, k))} after" for k, v in so.items()
                     if sn.get(self.cm.attrs.get(k, k)) != v]
        problems += [f"P1b (c): bee {' '.join(a)}: exit code {x} before the move, {y} after" for a, x, y in zip(READ_ONLY, co, cn) if x != y]
        callers = {c for c, *_ in old}
        data = sum(k for _, d, p, k in old if f"{d}/{p}".removeprefix("./").split("/")[0] + "/" in bee.DOSSIERS_LIBRE_SERVICE)
        problems += [f"P1b (c): {c} finds no file: the check would prove nothing" for c, m in (("problemes_textes_du_conseil", None), ("balayer", None),
                     ("data folders", data)) if not (m if m is not None else sum(k for x, _, _, k in old if x == c))]
        sites = {f.name for f in ast.walk(ast.parse(pathlib.Path(bee.__file__).read_text(encoding="utf-8"))) if isinstance(f, ast.FunctionDef)
                 for c in ast.walk(f) if isinstance(c, ast.Call) and getattr(c.func, "attr", None) in ("glob", "rglob", "iterdir")}
        problems += [f"P1b (c): the scan in {s} is not run here, nor covered by P4" for s in sorted(sites - callers - set(WRITE_ONLY_SCANS))]
        return problems, f"{len(old)} scans in {len(callers)} functions find the same {sum(k for *_, k in old)} files, {len(so)} collections"

    def one_to_one(self):
        """P4 on the map alone: an example of each shape in the corpus; map a bijection on it."""
        problems, images, corpus = [], self.images, sorted(self.images)
        for label, regex in (("FICHIERS_LIBRE_SERVICE", [r for _, r in bee.FICHIERS_LIBRE_SERVICE.values()]), ("CHEMIN_DEBAT", [bee.CHEMIN_DEBAT]),
                             ("PARCOURS", [r for r, *_ in bee.PARCOURS.values()])):
            problems += [f"P4: {label}: no example of {r.pattern} in the corpus" for r in regex if not any(r.match(p) for p in corpus)]
        seeds = {p: q for p, q in images.items() if q == self.names.path(p)}
        return problems + [f"P4: the map is not a bijection on the corpus: {p} -> {q} -> {self.names.path(q, True)}" for p, q in seeds.items()
                           if self.names.path(q, True) != p] + (["P4: two paths of the corpus map to one"] if len(set(images.values())) != len(images) else [])

    def p4(self, o, n):
        problems, images, corpus = self.one_to_one(), self.images, sorted(self.images)
        back = lambda k: k and self.names.path(k + "/" * ("/" not in k), True).rstrip("/")  # noqa: E731  (a folder's name, as the old tool says it)
        old = {p: {k: decoded(v) for k, v in c.items()} for p, c in o["classes"].items()}
        new = {p: {k: decoded(v) for k, v in c.items()} for p, c in n["classes"].items()}
        for p in corpus:
            a, b = old[p], dict(new[images[p]])
            b |= {k: back(b[k]) for k in ("self-service kind (R-e)", "removal scan (R-g)")}
            problems += [f"P4: {p} -> {images[p]}: {k}: {a[k]!r} before the move, {b[k]!r} after" for k in LABELS if a[k] != b[k]]
        reads = {images[p] for p in o["council"]}, set(n["council"])
        problems += [f"P4: R-u: the council files' check reads {q} {'only before the move' if q in reads[0] else 'only after the move'}" for q in sorted(reads[0] ^ reads[1])]
        for p in self.retired:  # R-q: a retired French path, read by the new tool as it is
            if "data" in new[p]["ci-scope (R-b, R-c, R-n)"] or new[p]["data commit (R-o)"] or new[p]["history (R-r)"] or new[p]["removal scan (R-g)"]:
                problems.append(f"P4: R-q: {p}, a retired name, is still data for the new tool")
        guard = n["guard"]  # the guard the switch's hand-made part adds, retired_name: path -> its refusal, or None
        problems += [f"P4: R-q: {p} is {'not refused by' if p in self.retired else 'refused by'} the retired-names guard" for p in sorted({*self.retired, *images.values()})
                     if guard["exists"] and guard["refused"][p] != (p in self.retired)] or ([] if guard["exists"] else ["P4: R-q: no retired-names guard (retired_name, the hand-made part)"])
        constants = {k: decoded(v) for k, v in n["constants"].items()}
        problems += [f"P4: R-i: {a} left AUTHORITY_FILES (an old name is kept for good)" for a in bee.AUTHORITY_FILES
                     if not isinstance(c := constants.get(self.i("AUTHORITY_FILES")), (tuple, list, set, frozenset)) or a not in c]
        for k in KEY_GROUPS:  # section 3.3: map(old set) == new set, each member mapped in its constant's own scope
            if (x := self.mapped(decoded(encoded(getattr(bee, k))), k)) != (y := self.mapped(constants.get(self.i(k)))):
                problems.append(f"P4: {k}: the map of the old set is {x!r:.300}, the new tool has {y!r:.300}")
        return problems, f"{len(corpus)} paths ({len(self.retired)} retired) classified alike by the rules R-a to R-u, {len(KEY_GROUPS)} key sets equal"

    def same_json(self, x, y, where=""):
        """An output as the map makes it (x) against the new one: the same keys and values; a text, through the map's names."""
        if isinstance(x, dict) and isinstance(y, dict):
            return [p for k in x for p in self.same_json(x[k], y[k], f"{where}/{k}")] if set(x) == set(y) else [
                f"{where or '/'}: the keys {sorted(set(x) - set(y))} expected, {sorted(set(y) - set(x))} found"]
        if isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            return [p for k, (a, b) in enumerate(zip(x, y)) for p in self.same_json(a, b, f"{where}[{k}]")]
        return [] if x == y or isinstance(x, str) and isinstance(y, str) and self.cm.string_change(x, y) is not None else [
            f"{where}: {x!r:.100} expected, {y!r:.100} found"]

    def framed(self, line):
        """The data file a frame shows, from the line above it (as the old tool writes it): (its family, the key it sits under, its path)."""
        for fmt, under in ((bee.DEBUT_DONNEES, None), (bee.DEBUT_DECLARE, "declare")):
            if m := re.fullmatch(re.escape(fmt).replace(r"\{id\}", "(?P<id>.+?)").replace(r"\{sha\}", ".+?"), line):
                found = [p for p in self.data if p.startswith(tuple(bee.DOSSIERS_LIBRE_SERVICE)) and p.rpartition("/")[2] == f"{m['id']}.yaml"]
                return (self.names.families_of(found[0])[0], under, found[0]) if len(found) == 1 and self.names.families_of(found[0]) else None

    def same_text(self, a, b):
        """A text output: each data frame strictly, through the map of the file it shows; the size estimate by its formula; the
        rest token by token through the map (a word stays, or becomes its English name; nothing else changes)."""
        (ra, fa), (rb, fb) = ((FRAME.sub("|\n", t), [(t[:m.start()].rstrip("\n").rpartition("\n")[2], re.sub(r"(?m)^\| ?", "", m[0]))
                                                      for m in FRAME.finditer(t)]) for t in (a, b))
        problems = [f"{len(fa)} data frame(s) before the move, {len(fb)} after"] if len(fa) != len(fb) else []
        for k, ((line, x), (_, y)) in enumerate(zip(fa, fb) if not problems else [], 1):
            if (where := self.framed(line)) is None:
                problems.append(f"data frame {k}: it shows no single file of the fixture ({line!r:.80})")
                continue
            fam, under, path = where
            try:
                want, got = self.names.data(fam, {under: bee.charger_texte_yaml(x)} if under else bee.charger_texte_yaml(x), False), bee.charger_texte_yaml(y)
                want = next(iter(want.values())) if under else want
            except (rename.Problem, bee.ErreurBee, ValueError, KeyError, StopIteration) as e:
                problems.append(f"data frame {k} ({path}): {type(e).__name__}: {e}")
                continue
            if want != got:
                keys = sorted(map(str, {*want, *got})) if not (isinstance(want, dict) and isinstance(got, dict)) else sorted(
                    str(q) for q in {*want, *got} if want.get(q, ...) != got.get(q, ...))
                problems.append(f"data frame {k} ({path}): {', '.join(keys)[:200]}: not the map of the data it shows")
        size = re.compile(r"(?<=Environ )[0-9]+(?= jetons \(([0-9]+) )")  # contexte's size estimate, from its own text: it counts renamed names
        for t, side in ((a, "before"), (b, "after")):
            if (m := size.search(t)) and int(m[0]) != math.ceil(len(size.sub("0", t)) / int(m[1])):
                problems.append(f"the size estimate {m[0]} {side} the move is not its formula's (its text's length / {m[1]})")
        if self.cm.string_change(*(size.sub("N", t) for t in (ra, rb))) is None:
            problems.append("the output differs otherwise than through the map, outside its data frames")
        return problems

    def same_api(self, a, b):
        """The site's api/: the same files through the map, each one's JSON through its family."""
        problems, images = [], {}
        for k in a:
            self.cm.scoped(f"{self.dir}/site_bee.py", API.get(k, ("", ""))[1], k)
            images[k] = self.cm.whole(k)
        self.cm.scoped(f"{self.dir}/bee.py", "")
        problems += [f"api/{k}: only before the move" for k in sorted(a) if images[k] not in b]
        problems += [f"api/{q}: only after the move" for q in sorted(b) if q not in images.values()]
        for k in sorted(a):
            if k not in API:
                problems.append(f"api/{k}: P6 does not know the family of the map it holds")
            elif images[k] in b:
                try:
                    problems += [f"api/{k}: {x}" for x in self.same_json(self.names.data(API[k][0], json.loads(a[k]), False), json.loads(b[images[k]]))[:3]]
                except (rename.Problem, ValueError, KeyError) as e:
                    problems.append(f"api/{k}: {type(e).__name__}: {e}")
        return problems

    def p6(self, o, n):
        """Each read-only command on the fixture, then on the migrated fixture: the same output modulo the map (a JSON output
        through its family, strictly but for texts; a text by same_text; the site's api by same_api)."""
        problems = []
        self.cm.scoped(f"{self.dir}/bee.py", "")
        for argv, r, s in zip(self.commands, o["outputs"], n["outputs"]):
            say, (x, a), (y, b) = f"P6: bee {' '.join(argv)}", (r["code"], r["stdout"]), (s["code"], s["stdout"])
            if x or y:  # a failure on both sides proves nothing
                problems.append(f"{say}: exit code {x} before the move, {y} after")
            elif argv[0] == "site":
                problems += [f"{say}: {p}" for p in self.same_api(o["api"], n["api"])]
            elif argv[0] in OUTPUTS:
                try:
                    problems += [f"{say}: {p}" for p in self.same_json(self.names.data(OUTPUTS[argv[0]], json.loads(a), False), json.loads(b))[:3]]
                except (rename.Problem, ValueError, KeyError) as e:
                    problems.append(f"{say}: {type(e).__name__}: {e}")
            else:
                problems += [f"{say}: {p}" for p in self.same_text(a, b)]
        return problems, f"{len(self.commands)} outputs equal modulo the map, every data frame and api file strictly"

    def compare(self, o, n):
        """P1b (c), P4 and P6 on the observations of the old tool (o) and the new one (n): (problems, summary lines)."""
        problems, lines, sides = [], [], (("old", o), ("new", n))
        bad = [f"the {s} tool's observations: {x}" for s, obs in sides for x in self.shape(obs, s == "new")]
        for label, proof in (("P1b (c)", self.p1b_c), ("P4", self.p4), ("P6", self.p6)):
            failed = bad or [f"the {s} tool fails: {part}: {obs['errors'][part]}" for s, obs in sides for part in ("*", "load", *SECTIONS[label])
                             if part in obs.get("errors", {})]
            failed = failed or [f"the {s} tool's observations: no {part}" for s, obs in sides for part in SECTIONS[label] if part not in obs]
            try:
                found, said = ([f"{label}: {x}" for x in failed], "") if failed else proof(o, n)
            except (KeyError, TypeError, ValueError, AttributeError, IndexError, RecursionError) as e:  # shaped, yet not as the plan asked
                found, said = [f"{label}: the new tool's observations do not fit: {type(e).__name__}: {e}"], ""
            problems += found
            lines.append(f"{label}: {len(found)} problem(s)" if found else f"{label}: ✓ {said}")
        return problems, lines


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
    """The head's commits on top of the generated one, the hand-made part: every file they touch, with its lines added and removed,
    for the founder and the hand-made part's own review; code only, never the proofs' own tooling, nor data."""
    mid, code, tooling = rename.tree_files(repo, generated), {names.path(p) for p in names.code}, tuple({m.rpartition("/")[0] + "/" for m in rename.MAPS})
    out = subprocess.run(["git", "-C", str(repo), "diff", "--numstat", "-z", "--no-renames", "--no-ext-diff", "--no-textconv", generated, head, "--"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    stat = {p: (a, r) for a, r, p in (x.split("\t", 2) for x in out.split("\0") if x.count("\t") >= 2)}
    hand = sorted({*stat, *(q for q in {*mid, *after} if mid.get(q) != after.get(q))})
    lines = [f"  {q}: " + ("binary" if stat.get(q, "00")[0] == "-" else "+{} -{}".format(*stat.get(q, "00"))) for q in hand]
    total = [sum(int(stat.get(q, "00")[i]) for q in hand if stat.get(q, "00")[0] != "-") for i in (0, 1)]
    ancestor = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", generated, head]).returncode == 0
    return [f"the hand-made part: {generated} is not an ancestor of {head}"] * (not ancestor) + [
        f"the hand-made part changes {q}, " + ("the proofs' own tooling" if q.startswith(tooling) or q.rpartition("/")[2] == SELF.name else
                                               "which is not code (data, or a file the switch does not write)")
        for q in hand if q.startswith(tooling) or q.rpartition("/")[2] == SELF.name or q not in code], [
        f"hand-made part ({generated}..{head}): {len(hand)} file(s), +{total[0]} -{total[1]} lines in all, for its review:", *lines]


def context(files):
    """The base's map as its own checker reads it, (names, its CodeMap, the tools' folder); None if this checker is not the base's."""
    if (at := next((c for c in rename.MAPS if c in files), None)) is None or files.get(at.replace("names.yaml", SELF.name)) != SELF.read_bytes():
        return None
    names = rename.Names(files[at].decode("utf-8"))
    return names, rename_code.CodeMap(names, files[rename_code.IDS[rename.MAPS.index(at)]].decode("utf-8")), at.rpartition("/migration/")[0]


NOT_OWN = "is not the base's own: run the base's checker, python3 -I, from its checkout (bee check-migration does)"
NOTE = ("note: P1b (c), P4 and P6 compare the base's tool with what a worker saw of the head's tool; code written to fool this check can fake "
        "what it shows there. They catch honest mistakes; the hand-made part's review, from the list above, stands against a hostile one.")


def observe_head(repo, base, head, out):
    """--observe (the workflow's first job): run the head's tool as the base's proofs ask; its observations to out. They prove nothing
    by themselves: the verdict (--observed, the second job) checks and compares them."""
    files = rename.tree_files(repo, base)
    if (ctx := context(files)) is None:
        raise rename.Problem(f"{SELF} {NOT_OWN}")
    with tempfile.TemporaryDirectory() as tmp:
        move = Move(*ctx, files)
        x = {"base": base, "head": head, "observations": work(move.plan(move.root(rename.tree_files(repo, head), tmp, True), True), tmp)}
    pathlib.Path(out).write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")


def check(repo, base, head, generated=None, observed=None):
    """bee check-migration. Returns (problems, summary lines). observed: the head's observations from that file (the workflow's
    first job), else a worker runs the head's tool here; either way, this process never loads code of the head."""
    generated, lines, files = generated or head, [], rename.tree_files(repo, base)
    if (ctx := context(files)) is None:
        return [f"{SELF} {NOT_OWN}"], lines
    names, cm, tool_dir = ctx
    with tempfile.TemporaryDirectory() as tmp:
        p2, n2 = rename.check(repo, base, generated)
        n2 = collections.Counter(n2)
        lines.append(f"P2: {len(p2)} problem(s)" if p2 else f"P2: ✓ {n2['data']} data files and {n2['schema']} schemas are their translation, "
                     f"{n2['same']} files byte-identical, {n2['commands']} with their commands renamed (change 10), {n2['removed']} removed, "
                     f"{n2['code']} code files placed")
        p1, n1 = rename_code.check(repo, base, generated, worker_rows(tmp))
        lines.append(f"P1, P1b (a, b), P3: {len(p1)} problem(s)" if p1 else f"P1, P1b (a, b), P3: ✓ {sum(n1.values())} names renamed through the map, "
                     "nothing else changed, no French name left, every attribute name resolves, the parser is the same")
        problems, after = p2 + p1, rename.tree_files(repo, head)
        if generated != head:
            found, said = hand_part(repo, names, generated, head, after)
            problems, lines = problems + found, lines + said
        move = Move(names, cm, tool_dir, files)
        o = work(move.plan(move.root(files, tmp, False), False), tmp)  # the old tool's, read before any code of the head runs
        if observed is None:
            n = work(move.plan(move.root(after, tmp, True), True), tmp)
        elif set(x := read_observations(observed)) == {"base", "head", "observations"} and [x["base"], x["head"]] == [base, head] and isinstance(x["observations"], dict):
            n = x["observations"]
        else:
            n = {"errors": {"*": f"{observed}: " + (x["errors"]["*"] if set(x) == {"errors"} and isinstance(x["errors"], dict) and isinstance(
                x["errors"].get("*"), str) else "not the observations of this base and head")}}
        found, said = move.compare(o, n)
        problems, lines = problems + found, lines + said
    found, said = section_13(names, files, after)
    lines.append(f"section 13: {len(found)} problem(s)" if found else f"section 13: ✓ {said}")
    return problems + found, lines + [NOTE] * (generated != head)


def main(argv=None):
    p = argparse.ArgumentParser(prog="check_migration.py", description=__doc__.split("\n\n")[0])
    for o in ("--base", "--head", "--generated", "--repo", "--observe", "--observed"):
        p.add_argument(o, required=o in ("--base", "--head"), default=str(SELF.parents[2]) if o == "--repo" else None)
    if (a := (sys.argv[1:] if argv is None else argv))[:1] == ["--worker"] and len(a) == 3:  # --worker PLAN OUT: a worker's work (see observe)
        x = observe(json.loads(pathlib.Path(a[1]).read_text(encoding="utf-8")))
        pathlib.Path(a[2]).write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")
        return 0
    a = p.parse_args(argv)
    try:
        if a.observe:
            observe_head(a.repo, a.base, a.head, a.observe)
            print(f"The head {a.head}'s observations are in {a.observe}: they prove nothing by themselves (check-migration --observed compares them).")
            return 0
        problems, lines = check(a.repo, a.base, a.head, a.generated, a.observed)
    except (rename.Problem, bee.ErreurBee, subprocess.CalledProcessError, OSError, UnicodeDecodeError, KeyError, TypeError) as e:
        problems, lines = [f"{type(e).__name__}: {e}"], []
    print("".join(f"✗ {x}\n" for x in problems) + "".join(f"{x}\n" for x in lines) + (f"✗ {len(problems)} problem(s): the head {a.head} is not proven"
          if problems else f"✓ the head {a.head}" + (f" (generated {a.generated}, then the hand-made part)" if a.generated else "") + " is proven")
          + f" to be the switch of the base {a.base}.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
