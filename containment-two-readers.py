#!/usr/bin/env python3
"""Two containment readers in one tree answered the same question differently, on a link.

`daedalus/host/peek.py` decides whether a path is inside the folders a session may read, in two
places, and the two decisions are made by two different rules. Taken verbatim from the sources at
commit `d6a3e106` (peek.py sha256 `f87329c9f0380a12…`):

  `_FolderReader.target`            (`peek.py:166`) -- resolves first, then asks the walls:

        candidate = Path(path or ".").expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = Path(os.path.realpath(candidate))          # <- symlinks resolved
        if not self.walls.contains(resolved): raise PeekRefused(...)

      and `Walls.root_of` (`containment.py:30`) likewise: `real = Path(os.path.realpath(path))`.

  `BridgedFolderAccess.target`      (`peek.py:307`) -- resolves nothing:

        candidate = posixpath.normpath(raw if raw.startswith("/") else posixpath.join(self.root, raw))
        if not any(candidate == r or candidate.startswith(r.rstrip("/") + "/")
                   for r in self.roots): raise PeekRefused(...)

      `posixpath.normpath` collapses `..` and `//` as TEXT; it does not follow a symlink.

So on a root containing a link that points outside, one reader refuses the path and the other admits
it. This script builds that fixture, runs **both rules as written above** against every shape, and
says which shapes part them. It then says what the split is worth, which is not the same question:

  * **the weaker reader is a pre-filter and the wall sits behind it.** The daemon is asked for the
    path this rule admitted, and it decides again -- `ptyd/internal/sidechan/fs.go`, `allowed`,
    accepts only when **both** the written path and its `EvalSymlinks` resolution lie under a root.
    So the link shapes below are refused one process later, at the wall, by the rule that resolves.
    `--tree DIR` reads that daemon file too and keeps the exit code honest: with the wall in view a
    split is reported and the run exits 0, because no defect is claimed; the same split without the
    wall in view exits 2, and so does a wall that no longer tests both forms.
  * it runs the RULES, not the tree's functions with the tree's own walls, so it does not prove which
    of the two readers a given caller reaches;
  * it does not read the rules out of a tree unless `--tree DIR` is passed, which is the only claim
    it can make about a tree.

    python3 containment-two-readers.py                     # build a fixture, print the table
    python3 containment-two-readers.py --check             # exit 2 while the two rules part and the wall is not in view
    python3 containment-two-readers.py --tree <checkout>   # also re-read the two rules and the wall from a tree

The fixture is built in a fresh directory under the current working directory and removed again, so
nothing is written outside it and no path outside it is named.

Exit: 0 the two rules agree on every shape, or they part and the wall behind the weaker one is shown
in the tree to test both forms; 2 they part and nothing in view closes it; 3 the tree's rules could
not be read or differ from the copies.
"""
import os
import posixpath
import shutil
import sys
import tempfile
from pathlib import Path

# The two rules, verbatim from the sources at commit d6a3e106. Re-read out of a checkout with --tree.
COPY_FOLDER_READER_TARGET = '''def target(self, path):
    candidate = Path(path or ".").expanduser()
    if not candidate.is_absolute():
        candidate = self.root / candidate
    resolved = Path(os.path.realpath(candidate))
    if not self.walls.contains(resolved):
        raise PeekRefused(f"{candidate} is outside the project's folders")
    if self.walls.is_protected(resolved):
        raise PeekRefused(f"{candidate} is part of the installation, not of the project")
    return resolved'''

COPY_BRIDGED_TARGET = '''def target(self, path):
    raw = (path or ".").strip() or "."
    if raw.startswith("~"):
        raise PeekRefused(f"{raw} names a home directory; give a path inside the project's folders")
    candidate = posixpath.normpath(raw if raw.startswith("/") else posixpath.join(self.root, raw))
    if not any(candidate == r or candidate.startswith(r.rstrip("/") + "/") for r in self.roots):
        raise PeekRefused(f"{candidate} is outside the project's folders")
    return candidate'''

TREE_COMMIT = "d6a3e10694d45eadaabfea06777041b3be732eb0"
PEEK_SHA_PREFIX = "f87329c9f0380a12"


class Refused(Exception):
    pass


class PeekRefused(Refused):
    pass


def realpath_reader(root, walls, path):
    """`_FolderReader.target` with `Walls.contains` written as `containment.py:30` writes it."""
    candidate = Path(path or ".").expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = Path(os.path.realpath(candidate))
    if not walls.contains(resolved):
        raise PeekRefused("%s is outside the project's folders" % candidate)
    return resolved


def text_reader(root, roots, path):
    """`BridgedFolderAccess.target` as written."""
    raw = (path or ".").strip() or "."
    if raw.startswith("~"):
        raise PeekRefused("%s names a home directory" % raw)
    root_s, roots_s = str(root), [str(r) for r in roots]
    candidate = posixpath.normpath(raw if raw.startswith("/") else posixpath.join(root_s, raw))
    if not any(candidate == r or candidate.startswith(r.rstrip("/") + "/") for r in roots_s):
        raise PeekRefused("%s is outside the project's folders" % candidate)
    return candidate


class Walls:
    """`Walls.contains` -- judged on real paths, as `root_of` judges them."""

    def __init__(self, readable):
        self.readable = tuple(Path(os.path.realpath(r)) for r in readable)

    def contains(self, path):
        real = Path(os.path.realpath(path))
        return any(real == base or base in real.parents for base in self.readable)


SHAPES = [
    ("a plain file inside", "inside.txt"),
    ("a subdirectory inside", "sub"),
    ("a file in a subdirectory", "sub/deeper.txt"),
    ("a traversal that stays inside", "sub/../inside.txt"),
    ("a traversal out of the root", "../outside/secret.txt"),
    ("an absolute path outside", None),          # filled in by build()
    ("a link to a file outside", "link_file"),
    ("a link to a directory outside", "link_dir"),
    ("a link to a file outside, reached through it", "link_dir/secret.txt"),
    ("a relative link to a file outside", "up_file"),
]


def build(base):
    """A root, an outside directory beside it, and the three link shapes."""
    root = base / "root"
    outside = base / "outside"
    (root / "sub").mkdir(parents=True)
    outside.mkdir(parents=True)
    (root / "inside.txt").write_text("inside\n")
    (root / "sub" / "deeper.txt").write_text("deeper\n")
    (outside / "secret.txt").write_text("secret\n")
    os.symlink(outside / "secret.txt", root / "link_file")
    os.symlink(outside, root / "link_dir")
    os.symlink("../outside/secret.txt", root / "up_file")
    return root, outside


def table(root, outside):
    walls = Walls([root])
    rows, split = [], []
    for label, rel in SHAPES:
        path = str(outside / "secret.txt") if rel is None else rel
        answers = []
        for reader, fn in (("realpath", lambda p: realpath_reader(root, walls, p)),
                           ("text", lambda p: text_reader(root, [root], p))):
            try:
                fn(path)
                answers.append("inside")
            except Refused as exc:
                answers.append("REFUSED (%s)" % str(exc)[:44])
        same = answers[0].split()[0] == answers[1].split()[0]
        rows.append((label, path, answers[0], answers[1], same))
        if not same:
            split.append(label)
    return rows, split


def the_wall_that_closes_it(tree):
    """`(found, why)` -- whether the daemon still decides on both the written and the resolved path.

    The daemon is Go, so this is a TEXT reading of one function and not a parse: it is here to say
    whether the backstop the weaker reader relies on is still written, not to prove what Go
    compiles. It requires the accepting branch to name both forms -- `under(root, clean)` and
    `under(rootReal, real)` -- which is the line that refuses a link out of a root.
    """
    path = Path(tree) / "ptyd" / "internal" / "sidechan" / "fs.go"
    if not path.is_file():
        return False, "no %s in the tree, so the wall behind the weaker reader is not in view" % path
    text = path.read_text(encoding="utf-8", errors="replace")
    body = None
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if line.startswith("func (f *FS) allowed("):
            body = "\n".join(lines[number:number + 30])
            break
    if body is None:
        return False, "fs.go carries no `func (f *FS) allowed(...)`, so nothing shows the wall's rule"
    folded = " ".join(body.split())
    has_clean = "under(root, clean)" in folded
    has_real = "under(rootReal, real)" in folded
    if not (has_clean and has_real):
        return False, ("`allowed` does not test both forms (`under(root, clean)` %s, "
                       "`under(rootReal, real)` %s), so the written path alone would decide"
                       % ("yes" if has_clean else "NO", "yes" if has_real else "NO"))
    return True, ("the daemon's `allowed` accepts only when both the written path and its "
                  "`EvalSymlinks` resolution lie under a root (ptyd/internal/sidechan/fs.go)")


def _normalise(source):
    """A method body with its docstring and its type annotations dropped.

    The question is whether the two RULES are the same, so a docstring and an annotation are not
    part of it -- but nothing else may be dropped, or a real difference could hide behind the
    normaliser.
    """
    import ast

    class Drop(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node.returns = None
            for a in node.args.args + node.args.kwonlyargs:
                a.annotation = None
            if node.args.vararg:
                node.args.vararg.annotation = None
            if node.args.kwarg:
                node.args.kwarg.annotation = None
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
            return self.generic_visit(node)

    tree = Drop().visit(ast.parse(source))
    ast.fix_missing_locations(tree)
    return ast.dump(tree)


def rules_from_tree(tree):
    """Read the two `target` methods out of a checkout and return them as source text."""
    import ast
    import hashlib
    peek = Path(tree) / "daedalus" / "host" / "peek.py"
    if not peek.is_file():
        return None, None, "no peek.py at %s" % peek
    digest = hashlib.sha256(peek.read_bytes()).hexdigest()
    source = peek.read_text()
    found = {}
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef) and node.name == "target"):
            continue
        body = ast.get_source_segment(source, node) or ""
        # Classify by WHICH QUESTION the method asks, not by the call that answers it, so a tree
        # with the resolving call changed away is still found and reported as DIFFERING.
        if "self.walls" in body:
            found["realpath"] = body
        elif "self.roots" in body:
            found["text"] = body
    return found, digest, None


def main(argv):
    tree = None
    if "--tree" in argv:
        tree = argv[argv.index("--tree") + 1]
    print("the two rules are copied from peek.py at %s (sha256 %s...)" % (TREE_COMMIT, PEEK_SHA_PREFIX))
    if tree:
        found, digest, problem = rules_from_tree(tree)
        if problem:
            print("TREE=unreadable %s" % problem)
            return 3
        print("tree peek.py sha256 %s" % digest[:16])
        for key, copy in (("realpath", COPY_FOLDER_READER_TARGET), ("text", COPY_BRIDGED_TARGET)):
            body = (found or {}).get(key)
            if body is None:
                print("TREE=no %s target method" % key)
                return 3
            if _normalise(body) != _normalise(copy):
                print("TREE=%s target DIFFERS from the copy in this file" % key)
                print("  tree:"); print("    " + "\n    ".join(l.strip() for l in body.splitlines() if l.strip()))
                print("  copy:"); print("    " + "\n    ".join(l.strip() for l in copy.splitlines() if l.strip()))
                return 3
        print("TREE=ok -- both methods read back identical to the copies here")

    fixture_dir = None
    if "--fixture-dir" in argv:
        fixture_dir = argv[argv.index("--fixture-dir") + 1]
    base = Path(tempfile.mkdtemp(prefix="containment-", dir=fixture_dir or "."))
    try:
        root, outside = build(base)
        print("fixture: root %s, outside %s" % (root, outside))
        rows, split = table(root, outside)
        print("%-44s %-26s %-16s %s" % ("shape", "path", "realpath reader", "text reader"))
        for label, path, a, b, same in rows:
            print("%-44s %-26s %-16s %s" % (label, path[:26], a.split()[0],
                                            b.split()[0] + ("" if same else "   <-- PARTED")))
        print("shapes %d, parted %d: %s" % (len(rows), len(split), ", ".join(split) or "(none)"))
        wall, why = (None, "the wall is not in view; pass --tree DIR to read it with the rules")
        if tree:
            wall, why = the_wall_that_closes_it(tree)
            print("THE_WALL=%s -- %s" % ("closed" if wall else "not shown", why))
        if "--check" in argv:
            if split and not wall:
                print("CONTAINMENT_TWO_READERS=split on %d shape(s), and nothing in view closes it"
                      % len(split))
                return 2
            if split:
                print("CONTAINMENT_TWO_READERS=split on %d shape(s), confined to the pre-filter: the "
                      "wall behind the weaker reader resolves both forms" % len(split))
                return 0
            print("CONTAINMENT_TWO_READERS=ok -- the two readers agree on every shape")
            return 0
        print("CONTAINMENT_TWO_READERS=%s" % ("split" if split else "agree"))
        return 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
