#!/usr/bin/env python3
"""English names, layer L7 (ruche-0146, ruche-0147): P1 restricted to message literals.

    python3 tools/migration/check_messages.py --base <commit> [--head <commit>] [--markers] [file …]

Compares each file (default: tools/bee.py and tools/test_bee.py) at the base and at the head (default: the working tree)
with the ast module. The two trees must be the same once every string literal is set aside: same code, same names, same
interpolated expressions (an f-string may reorder its interpolations, never change one), so behaviour, exit codes and
streams cannot change. Then each changed literal must be a message:
  - a name literal (a key, a value, a path, a command or an option: tools/marker_inventory.py's NAME) never changes;
  - a literal the base compares text against (marker_inventory's operands, and the constants they use) changes only with
    --markers, for the hand-made part that changes a marker and its comparison together;
  - a template keeps its str.format fields and its %-specifiers, so the code that fills it still fits.
Docstrings may change and are counted apart. Exit code 1 with every problem listed, 0 otherwise.
Limits: it sees the code, not what reads bee's output (workflows, scripts, docs that quote a message), which the review
checks; and a message held in a name-shaped literal (one word, no blank) is refused unless named with --prose.
"""
import argparse
import ast
import collections
import pathlib
import re
import string
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from marker_inventory import NAME, literals, names_of, operands  # noqa: E402

PERCENT = re.compile(r"%(?:\([^)]*\))?[-#0 +]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXeEfFgGcrsa%]")
HOLE = "\x00"


def source(repo, ref, path):
    if ref is None:
        return (repo / path).read_text(encoding="utf-8")
    out = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    if out.returncode != 0:
        raise SystemExit(f"check_messages: {path} not found at {ref}")
    return out.stdout.decode("utf-8")


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


def compared(text):
    """The literals the file compares text against, as marker_inventory finds them, constants included."""
    tree = ast.parse(text)
    found, used = set(), set()
    constants = [(n.targets[0].id, n.value) for n in tree.body if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper()]
    for n in ast.walk(tree):
        for o in operands(n):
            used.update(names_of(o))
            found.update(c.value for c in literals(o))
    while True:
        before = len(used)
        used.update(x for name, value in constants if name in used for x in names_of(value))
        if len(used) == before:
            break
    for name, value in constants:
        if name in used:
            found.update(c.value for c in literals(value))
    return found


def fields(text):
    try:
        named = collections.Counter(f for _, f, _, _ in string.Formatter().parse(text) if f is not None)
    except ValueError:
        named = None
    return named, PERCENT.findall(text)


def name_shaped(kind, text):
    return bool(NAME.match(text.replace(HOLE, "x"))) if text else False


def check(repo, base, head, files, markers, prose=()):
    problems, counts = [], collections.Counter()
    for path in files:
        old_text, new_text = source(repo, base, path), source(repo, head, path)
        (old_tree, old), (new_tree, new) = masked(old_text), masked(new_text)
        if [d for _, d in old_tree] != [d for _, d in new_tree] or len(old) != len(new):
            changed = [f"{a}->{b}" for (a, x), (b, y) in zip(old_tree, new_tree) if x != y][:5]
            problems.append(f"{path}: the code changed, not only string literals (P1 restricted to message literals): "
                            f"top-level statements at {', '.join(changed) or 'the end (one added or removed)'}")
            continue
        markers_of_base = compared(old_text)
        for (kind, a, line), (_, b, new_line) in zip(old, new):
            if a == b:
                continue
            where = f"{path}:{line}->{new_line}"
            if kind == "doc":
                counts["docstrings"] += 1
                continue
            counts[f"{path} messages"] += 1
            if (name_shaped(kind, a) and a not in prose) or (name_shaped(kind, b) and b not in prose):
                problems.append(f"{where}: a name literal changed: {a!r} -> {b!r}")
            elif kind == "str" and a in markers_of_base and not markers:
                problems.append(f"{where}: a literal the code compares text against changed (needs --markers and the "
                                f"comparison changed with it): {a!r} -> {b!r}")
            elif kind == "str" and fields(a) != fields(b):
                problems.append(f"{where}: the template's fields changed: {fields(a)} -> {fields(b)}")
    return problems, counts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--base", required=True)
    p.add_argument("--head", help="a commit (default: the working tree)")
    p.add_argument("--markers", action="store_true", help="the hand-made part: compared literals may change")
    p.add_argument("--prose", action="append", default=[], help="a name-shaped literal that is prose (one word of a "
                   "message, as a test's expected text): it may change; each one is listed in the PR")
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
