#!/usr/bin/env python3
"""Prove the published suite judges the module rather than remembering it.

Each mutant is one substitution in the reference implementation. A mutant that the suite
does not catch is a hole in the suite, and the run names it. A mutant whose text is not in
the file is refused rather than counted, because a substitution that landed nowhere proves
nothing.

    python3 mutants.py <path to marker_reach.py> <path to test_marker_reach.py>

Success prints `MARKER_REACH_MUTANTS=ok` and exits 0 only when every mutant builds and every
mutant is caught; otherwise it prints the ones that were not.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

MUTANTS = [
    ("a string constant stops naming a token",
     'elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):',
     'elif False:'),
    ("a token matches anywhere inside a longer string",
     'return {marker for marker, tokens in markers.items() if token in tokens}',
     'return {marker for marker, tokens in markers.items() if any(t in token for t in tokens)}'),
    ("a name rebound inside a scope no longer shadows the outer one",
     'if name in bound:', 'if False:'),
    ("a tuple target binds nothing",
     'if isinstance(target, (ast.Tuple, ast.List)):', 'if False:'),
    ("the fixed point stops after one pass",
     'while changed:', 'while changed and False:'),
    ("the arguments are never checked",
     'if not _valid(source, markers):', 'if False:'),
    ("a nested function is read as part of the one holding it",
     'if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):\n                continue\n            descend(child)',
     'descend(child)'),
    ("a Lambda stops being reported as unread",
     'elif isinstance(node, ast.Lambda):\n            why = "a Lambda body is not read"',
     'elif False:\n            why = "a Lambda body is not read"'),
]


def main(argv):
    if len(argv) != 2:
        print("usage: mutants.py <marker_reach.py> <test_marker_reach.py>")
        return 2
    module, suite = Path(argv[0]), Path(argv[1])
    source = module.read_text(encoding="utf-8")
    caught, missed, refused = [], [], []
    with tempfile.TemporaryDirectory(prefix="mutants-") as tmp:
        for name, old, new in MUTANTS:
            if source.count(old) != 1:
                refused.append("%s (%d matches)" % (name, source.count(old)))
                continue
            mutated = Path(tmp) / "mutated.py"
            mutated.write_text(source.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, str(suite), str(mutated)],
                                 capture_output=True, text=True)
            if run.returncode == 0:
                missed.append(name)
            else:
                caught.append(name)
    print("mutants caught %d/%d, refused to build %d" % (len(caught), len(MUTANTS), len(refused)))
    for name in caught:
        print("  caught  %s" % name)
    for name in missed:
        print("  MISSED  %s" % name)
    for name in refused:
        print("  refused %s" % name)
    if missed or refused:
        print("MARKER_REACH_MUTANTS=NOT ok")
        return 1
    print("MARKER_REACH_MUTANTS=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
