#!/usr/bin/env python3
"""Prove the published test file can fail: six wrong answers, one substitution each.

Every mutant is the reference module's own bytes with exactly ONE substitution. A
substitution that does not land exactly once is refused, not counted as caught --
a mutant nobody built is not a test that passed.

    python3 mutants.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "refusal_ids.py"
TESTS = HERE / "test_refusal_ids.py"

MUTANTS = [
    ("W1 comments are read as sites",
     'if line.lstrip().startswith("#"):',
     'if False:'),
    ("W2 the emitted lists are not sorted",
     'sorted({i for i, _ in s}) for p, s in left.items()',
     '[i for i, _ in s] for p, s in left.items()'),
    ("W3 an unemitted id loses the line that names it",
     'sorted([[i, n] for i, n in sites if i not in printed])',
     'sorted([i for i, n in sites if i not in printed])'),
    ("W4 a side that yields nothing is answered instead of refused",
     'if sites is None or not sites:',
     'if sites is None:'),
    ("W5 only the first producer is read",
     'for sites in left.values():',
     'for sites in list(left.values())[:1]:'),
    ("W6 the answer is a sentence, not a structure",
     'return (True, answer)',
     'return (True, str(answer))'),
]


def main():
    source = REFERENCE.read_text(encoding="utf-8")
    caught, refused = 0, 0
    with tempfile.TemporaryDirectory(prefix="mutants-") as tmp:
        for label, old, new in MUTANTS:
            if source.count(old) != 1:
                print("  REFUSED %s: the anchor occurs %d time(s), expected 1"
                      % (label, source.count(old)))
                refused += 1
                continue
            path = Path(tmp) / "mutant.py"
            path.write_text(source.replace(old, new), encoding="utf-8")
            run = subprocess.run([sys.executable, str(TESTS), str(path)],
                                 capture_output=True, text=True)
            last = (run.stdout.strip().splitlines() or ["<no output>"])[-1]
            ok = run.returncode == 1 and "REFUSAL_IDS_TESTS=FAILED" in last
            print("  %-8s %-58s %s" % ("caught" if ok else "MISSED", label, last))
            caught += 1 if ok else 0
    print("mutants caught %d/%d, refused to build %d" % (caught, len(MUTANTS), refused))
    print("REFUSAL_IDS_MUTANTS=%s" % ("ok" if caught == len(MUTANTS) else "NOT ok"))
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
