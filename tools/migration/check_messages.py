#!/usr/bin/env python3
"""English names, layer L7 (ruche-0146, ruche-0147): P1 restricted to message literals.

    python3 tools/migration/check_messages.py --base <commit> [--head <commit>] [--markers] [--prose TEXT …] [file …]

Compares each file (default: tools/bee.py and tools/test_bee.py) at the base and at the head (default: the working tree)
with the ast module. The two trees must be the same once every string literal is set aside: same code, same names, same
interpolated expressions (an f-string may reorder its interpolations, never change one), so behaviour, exit codes and
streams cannot change. Then each changed literal must be a message:
  - a name literal (a key, a value, a path, a command or an option: tools/marker_inventory.py's NAME, read at the base)
    never changes, and neither does a literal without a letter (a separator, a blank, a punctuation mark: a join, an end=,
    a JSON separator), unless the old text is named with --prose (a one-word expected text of a test, « : » before a
    message…), each one listed in the PR;
  - a literal the base compares text against changes only with --markers, for the hand-made part that changes a marker and
    its comparison together: marker_inventory's operands, and every literal reached from one through a name bound in the
    file (a constant, a local variable, an argument's default), argparse's choices, and the text parts of f-strings;
  - a template keeps its str.format fields, each with its conversion and format spec, and its %-specifiers (in any order).
Docstrings may change and are counted apart (the template check applies to them too). Exit code 1 with every problem
listed, 0 otherwise.
Limits: it sees the code, not what reads bee's output (workflows, scripts, the forks' CI, docs that quote a message),
which each PR's review checks. A literal with letters, a blank and no comparison is taken for a message: a header name, an
encoding, a shell command line or a mode string passed to a function would pass, and the review reads every changed
literal. --prose waives a text for the whole file, not one place. A string inside an interpolation (f"{'s' if n > 1 else
''}") is code: translating it is refused as a code change (rewrite the message around it instead). A docstring read by the
code (__doc__) is not looked for; bee.py reads none today. A marker reaching a comparison through a function's return value
(f() in s) or a global assigned inside a function is missed.
"""
import argparse
import ast
import collections
import importlib.util
import pathlib
import re
import string
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PERCENT = re.compile(r"%(?:\([^)]*\))?[-#0 +]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXeEfFgGcrsa%]")
HOLE = "\x00"


class Unreadable(Exception):
    pass


def source(repo, ref, path):
    if ref is None:
        try:
            return (repo / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise Unreadable(f"{path}: unreadable in the working tree ({e.__class__.__name__})")
    out = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    if out.returncode != 0:
        raise Unreadable(f"{path}: not found at {ref}")
    try:
        return out.stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise Unreadable(f"{path}: not UTF-8 at {ref}")


def rules_at(repo, base):
    """marker_inventory as the base has it (a PR cannot loosen the rules that judge it); this checker's copy when the
    base has none (a repository without the registry's tools, as the tests')."""
    out = subprocess.run(["git", "-C", str(repo), "show", f"{base}:tools/marker_inventory.py"], capture_output=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "marker_inventory.py"
        path.write_bytes(out.stdout if out.returncode == 0 else (ROOT / "tools" / "marker_inventory.py").read_bytes())
        spec = importlib.util.spec_from_file_location("marker_inventory_at_base", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class Masked(ast.NodeTransformer):
    """Sets every string literal aside, in order: (kind, text, line); kind is doc, str or f (an f-string's text with a hole
    for each interpolation, whose expressions stay in the tree, sorted, so a reordering is not a change)."""

    def __init__(self):
        self.found = []

    def _docstring(self, node):
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            self.found.append(("doc", body[0].value.value, body[0].lineno))
            body[0].value = ast.Constant(value=HOLE)
        return self.generic_visit(node)

    visit_Module = visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = _docstring

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value != HOLE:
            self.found.append(("str", node.value, node.lineno))
            return ast.copy_location(ast.Constant(value=HOLE), node)
        return node

    def visit_JoinedStr(self, node):
        text, holes = "", []
        for part in node.values:
            if isinstance(part, ast.Constant):
                text += part.value
            else:
                text += HOLE
                holes.append(ast.dump(part))
        self.found.append(("f", text, node.lineno))
        return ast.copy_location(ast.Constant(value=HOLE + "".join(sorted(holes))), node)


def masked(text):
    """Per top-level statement, (its first line, its dump with the literals set aside); and the literals, in order."""
    m = Masked()
    tree = m.visit(ast.parse(text))
    return [(n.lineno, ast.dump(n, include_attributes=False)) for n in tree.body], m.found


def compared(text, rules):
    """The literals the file compares text against: marker_inventory's operands, and what a name they use is bound to in
    its scope or an enclosing one (an assignment, an argument's default; the module's names last), argparse's choices;
    f-string parts included."""
    found, attributes, found_attributes = set(), collections.defaultdict(list), set()

    def own_nodes(scope_node):
        """The nodes of a scope, without the bodies of the functions and classes defined in it."""
        todo = list(ast.iter_child_nodes(scope_node))
        while todo:
            n = todo.pop()
            yield n
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                todo.extend(ast.iter_child_nodes(n))

    def visit(scope_node, chain):
        bound, used = collections.defaultdict(list), set()
        args = getattr(scope_node, "args", None)
        if args is not None:
            positional = args.posonlyargs + args.args
            for arg, default in zip(positional[len(positional) - len(args.defaults):], args.defaults):
                bound[arg.arg].append(default)
            for arg, default in zip(args.kwonlyargs, args.kw_defaults):
                if default is not None:
                    bound[arg.arg].append(default)
        children = []
        for n in own_nodes(scope_node):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and n.value is not None:
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            bound[x.id].append(n.value)
                        elif isinstance(x, ast.Attribute):  # self.mark = …, compared in another method: the module's
                            attributes[x.attr].append(n.value)
            elif isinstance(n, ast.NamedExpr):
                bound[n.target.id].append(n.value)
            elif isinstance(n, ast.keyword) and n.arg == "choices":
                found.update(c.value for c in rules.literals(n.value))
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                children.append(n)
            for o in rules.operands(n):
                used.update(rules.names_of(o))
                found_attributes.update(x.attr for x in ast.walk(o) if isinstance(x, ast.Attribute))
                found.update(c.value for c in rules.literals(o))
        chain = [bound] + chain
        seen = set()
        while used - seen:
            name = (used - seen).pop()
            seen.add(name)
            for values in chain:
                if name in values:
                    for value in values[name]:
                        found.update(c.value for c in rules.literals(value))
                        used.update(rules.names_of(value))
                    break
        for child in children:
            visit(child, chain)

    visit(ast.parse(text), [])
    used, seen = set(found_attributes), set()  # an attribute compared anywhere (self.mark in s): what any x.mark = holds
    while used - seen:
        name = (used - seen).pop()
        seen.add(name)
        for value in attributes.get(name, []):
            found.update(c.value for c in rules.literals(value))
    return found


def fields(text):
    try:
        named = collections.Counter((f, c, s) for _, f, s, c in string.Formatter().parse(text) if f is not None)
    except ValueError:
        named = None
    return named, collections.Counter(PERCENT.findall(text))


def lettered(text):
    return any(c.isalpha() for c in text)


def check(repo, base, head, files, markers, prose=()):
    problems, counts = [], collections.Counter()
    rules = rules_at(repo, base)
    for path in files:
        try:
            old_text, new_text = source(repo, base, path), source(repo, head, path)
            (old_tree, old), (new_tree, new) = masked(old_text), masked(new_text)
            markers_of_base = compared(old_text, rules)
        except Unreadable as e:
            problems.append(str(e))
            continue
        except SyntaxError as e:
            problems.append(f"{path}: does not parse ({e.msg}, line {e.lineno})")
            continue
        if [d for _, d in old_tree] != [d for _, d in new_tree] or len(old) != len(new):
            changed = [f"{a}->{b}" for (a, x), (b, y) in zip(old_tree, new_tree) if x != y][:5]
            problems.append(f"{path}: the code changed, not only string literals (P1 restricted to message literals): "
                            f"top-level statements at {', '.join(changed) or 'the end (one added or removed)'}")
            continue
        for (kind, a, line), (_, b, new_line) in zip(old, new):
            if a == b:
                continue
            where = f"{path}:{line}->{new_line}"
            counts["docstrings" if kind == "doc" else f"{path} messages"] += 1
            parts = a.split(HOLE) if kind == "f" else [a]
            if kind != "doc" and a not in prose and (
                    rules.NAME.match(a.replace(HOLE, "x")) or rules.NAME.match(b.replace(HOLE, "x"))):
                problems.append(f"{where}: a name literal changed: {a!r} -> {b!r}")
            elif kind != "doc" and a not in prose and not (lettered(a) and lettered(b)):
                problems.append(f"{where}: a literal without a letter changed (a separator or a blank; --prose if it is "
                                f"a message's): {a!r} -> {b!r}")
            elif kind != "doc" and not markers and a not in prose and any(p in markers_of_base for p in parts if p):
                problems.append(f"{where}: a literal the code compares text against changed (needs --markers and the "
                                f"comparison changed with it): {a!r} -> {b!r}")
            elif kind != "f" and fields(a) != fields(b):
                problems.append(f"{where}: the template's fields changed: {fields(a)} -> {fields(b)}")
    return problems, counts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--base", required=True)
    p.add_argument("--head", help="a commit (default: the working tree)")
    p.add_argument("--markers", action="store_true", help="the hand-made part: compared literals may change")
    p.add_argument("--prose", action="append", default=[], help="the old text of a name-shaped, letterless or compared "
                   "literal that is only a message (a test's one-word expected text, « : », a constant dict's shown value): "
                   "it may change; each one is listed in the PR")
    p.add_argument("files", nargs="*", default=["tools/bee.py", "tools/test_bee.py"])
    a = p.parse_args(argv)
    problems, counts = check(ROOT, a.base, a.head, a.files, a.markers, a.prose)
    for k, v in sorted(counts.items()):
        print(f"{k}: {v} changed")
    for x in problems:
        print(f"✗ {x}", file=sys.stderr)
    print("✓ P1 restricted to message literals" if not problems else f"✗ {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
