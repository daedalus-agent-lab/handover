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
says which shapes part them. It prints the limits of its own claim:

  * it runs the RULES, not the tree's functions with the tree's own walls, so it does not prove that
    `BridgedFolderAccess` is ever reached with a link-shaped path in production;
  * it does not read the tree at all -- pass `--tree DIR` to have it read the two rules out of a
    checkout and compare them with the copies here, which is the only claim it can make about a tree.

    python3 containment-two-readers.py                     # build a fixture, print the table
    python3 containment-two-readers.py --check             # exit 2 while the two rules part on a link
    python3 containment-two-readers.py --tree <checkout>   # also re-read the two rules from a tree

The fixture is built in a fresh directory under the current working directory and removed again, so
nothing is written outside it and no path outside it is named.

Exit: 0 the two rules agree on every shape (the split is closed), 2 they part on a link-shaped path
(the defect this file witnesses), 3 the tree's rules could not be read or differ from the copies.
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
        if "--check" in argv:
            if split:
                print("CONTAINMENT_TWO_READERS=split on %d shape(s) -- the defect is present" % len(split))
                return 2
            print("CONTAINMENT_TWO_READERS=ok -- the two readers agree on every shape")
            return 0
        print("CONTAINMENT_TWO_READERS=%s" % ("split" if split else "agree"))
        return 0 if not split else 2
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
