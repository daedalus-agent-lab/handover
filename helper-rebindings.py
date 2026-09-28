#!/usr/bin/env python3
"""Does any module in a tree bind a `_readings_of_*` name more than once at module level?

Why this exists
---------------
A tool that decides "which helper does this probe call?" by looking up a NAME has a blind
spot: a probe can bind a `_readings_of_*` name to a function that is not a helper, and a
name bound twice at module level makes the name and the object answer differently. A tool
that decides by OBJECT (resolving each compiled name through the probe's own `__globals__`
and keeping the candidate on its `__name__`) is not fooled by the first shape -- it answers
"MISSED", a counted abstention. This check covers the second shape cheaply and
deterministically, so the abstention is not the only defence.

The rule: a `_readings_of_*` name may be bound once at module level. A `def` followed by an
assignment to the same name is refused, with both line numbers named.

What it does NOT cover (stated, so that nobody builds more on it than it holds): rebinding
inside a function at run time (`globals()['_readings_of_x'] = other`), `setattr` on the
module object, and a DIFFERENT module patching the name on its own side. The first two are
covered by resolving the object at the moment of use, not by reading source; the third is
not visible from inside this tree at all.

Usage
-----
    python3 helper-rebindings.py [--tree DIR]     # exit 0 clean, 2 refused

Standard library only, read-only: it opens the tree's `*.py` files and writes nothing.
"""
import argparse
import ast
import pathlib
import sys

PREFIX = "_readings_of_"


def binds(node):
    """The names a top-level statement binds, and whether the statement is a def or class."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}, True
    if isinstance(node, ast.Assign):
        out = set()
        for target in node.targets:
            if isinstance(target, ast.Name):
                out.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                out.update(e.id for e in target.elts if isinstance(e, ast.Name))
        return out, False
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}, False
    if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}, False
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {a.asname or a.name.split(".")[0] for a in node.names}, False
    return set(), False


def rebindings(path):
    """Every `_readings_of_*` name this module binds twice, with both line numbers."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    seen, found = {}, []
    for node in tree.body:
        names, is_def = binds(node)
        for name in names:
            if not name.startswith(PREFIX):
                continue
            if name in seen:
                first, first_is_def = seen[name]
                found.append((name, first, first_is_def, node.lineno, is_def))
            else:
                seen[name] = (node.lineno, is_def)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tree", default=".", help="directory to read (default: here)")
    args = ap.parse_args()
    root = pathlib.Path(args.tree)
    files = refusals = 0
    for path in sorted(root.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if PREFIX not in text:
            continue
        files += 1
        for name, first, first_is_def, line, is_def in rebindings(path):
            refusals += 1
            print(f"REBOUND {path.name}: {name} bound at line {first} "
                  f"({'def' if first_is_def else 'not a def'}) and again at line {line} "
                  f"({'def' if is_def else 'not a def'})")
    print(f"files read: {files} | rebindings: {refusals}")
    if refusals:
        print("REFUSED: a helper name is bound twice at module level")
        return 2
    print(f"ok: every {PREFIX}* name in this tree is bound once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
