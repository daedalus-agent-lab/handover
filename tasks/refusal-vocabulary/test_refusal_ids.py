"""Tests for `refusal_ids.py`: compare the refusal-id vocabulary of two sides of a tree.

Run it as

    python3 test_refusal_ids.py refusal_ids.py

It passes the module path as its single argument, uses the standard library only, reads
no network and writes nothing. The module under test must define

    unemitted_ids(producers, consumers) -> (read, answer)

taking two mappings of path -> source text and answering `(bool, dict)`. Every answer must
be readable with `ast.literal_eval`; a question the module cannot answer is `(False, {})`
and never an exception.

The last line is `REFUSAL_IDS_TESTS=ok (<n> checks)` with exit 0, or
`REFUSAL_IDS_TESTS=FAILED (<n> case(s))` with exit 1.
"""
import ast
import importlib.util
import sys

PRODUCER = '''\
print("FAIL[NO-HELPER] the copy has no helper")
print("FAIL[ENTRY-DISAGREES] a-half-is-a-literal: 3")
'''

CONSUMER = '''\
marker = "FAIL[ENTRY-DISAGREES] "
if line.startswith(marker):
    pass
'''

# (name, producers, consumers, wanted_read, wanted_answer_or_None)
CASES = [
    ("an id printed on one side and named on the other",
     {"p.py": PRODUCER}, {"c.py": CONSUMER}, True,
     {"emitted": {"p.py": ["ENTRY-DISAGREES", "NO-HELPER"]},
      "named": {"c.py": ["ENTRY-DISAGREES"]},
      "unemitted": {"c.py": []}}),

    ("an id named and printed by nobody, with the line that names it",
     {"p.py": 'print("FAIL[NO-HELPER] x")'},
     {"c.py": 'a = 1\nmarker = "FAIL[GONE-AWAY] "\n'}, True,
     {"emitted": {"p.py": ["NO-HELPER"]},
      "named": {"c.py": ["GONE-AWAY"]},
      "unemitted": {"c.py": [["GONE-AWAY", 2]]}}),

    ("a rename on the producer side leaves the consumer naming an unemitted id",
     {"p.py": 'print("FAIL[ENTRY-DIFFERS] x")'}, {"c.py": CONSUMER}, True,
     {"emitted": {"p.py": ["ENTRY-DIFFERS"]},
      "named": {"c.py": ["ENTRY-DISAGREES"]},
      "unemitted": {"c.py": [["ENTRY-DISAGREES", 1]]}}),

    ("a comment is prose about the vocabulary, not a site in it",
     {"p.py": '# FAIL[NOT-REAL] is planned\nprint("FAIL[NO-HELPER] x")'},
     {"c.py": '# we used to check FAIL[NOT-REAL]\nmarker = "FAIL[NO-HELPER] "'}, True,
     {"emitted": {"p.py": ["NO-HELPER"]},
      "named": {"c.py": ["NO-HELPER"]},
      "unemitted": {"c.py": []}}),

    ("a lower-case token inside FAIL[] is not an id",
     {"p.py": 'print("FAIL[no-helper] x")\nprint("FAIL[NO-HELPER] y")'},
     {"c.py": 'a = "FAIL[no-helper] "\nb = "FAIL[NO-HELPER] "'}, True,
     {"emitted": {"p.py": ["NO-HELPER"]},
      "named": {"c.py": ["NO-HELPER"]},
      "unemitted": {"c.py": []}}),

    ("an id read out of a larger string is still an id",
     {"p.py": "msg = 'the probe refused: FAIL[TYPED-LIST] at once'"},
     {"c.py": 'if "FAIL[TYPED-LIST]" in text:\n    pass'}, True,
     {"emitted": {"p.py": ["TYPED-LIST"]},
      "named": {"c.py": ["TYPED-LIST"]},
      "unemitted": {"c.py": []}}),

    ("two producers, and the union is what counts",
     {"a.py": 'print("FAIL[NO-HELPER]")', "b.py": 'print("FAIL[NO-ENTRY]")'},
     {"c.py": 'x = "FAIL[NO-ENTRY] "\ny = "FAIL[NO-HELPER] "'}, True,
     {"emitted": {"a.py": ["NO-HELPER"], "b.py": ["NO-ENTRY"]},
      "named": {"c.py": ["NO-ENTRY", "NO-HELPER"]},
      "unemitted": {"c.py": []}}),

    ("two consumers are reported one by one",
     {"p.py": 'print("FAIL[NO-HELPER]")'},
     {"c.py": 'x = "FAIL[NO-HELPER] "', "d.py": 'y = "FAIL[MISSING] "'}, True,
     {"emitted": {"p.py": ["NO-HELPER"]},
      "named": {"c.py": ["NO-HELPER"], "d.py": ["MISSING"]},
      "unemitted": {"c.py": [], "d.py": [["MISSING", 1]]}}),

    ("an id named twice is one id, with both lines",
     {"p.py": 'print("FAIL[NO-HELPER]")'},
     {"c.py": 'a = "FAIL[GONE] "\nb = 1\nc = "FAIL[GONE] "'}, True,
     {"emitted": {"p.py": ["NO-HELPER"]},
      "named": {"c.py": ["GONE"]},
      "unemitted": {"c.py": [["GONE", 1], ["GONE", 3]]}}),

    ("emitted and named lists are sorted",
     {"p.py": 'print("FAIL[Z-ONE]")\nprint("FAIL[A-ONE]")'},
     {"c.py": 'x = "FAIL[Z-ONE] "\ny = "FAIL[A-ONE] "'}, True,
     {"emitted": {"p.py": ["A-ONE", "Z-ONE"]},
      "named": {"c.py": ["A-ONE", "Z-ONE"]},
      "unemitted": {"c.py": []}}),

    ("the answer reads back with ast.literal_eval",
     {"p.py": PRODUCER}, {"c.py": CONSUMER}, True, None),

    ("a consumer that names nothing is a refusal, not an empty answer",
     {"p.py": 'print("FAIL[NO-HELPER]")'}, {"c.py": "pass\n"}, False, None),

    ("a producer that prints nothing is a refusal",
     {"p.py": "pass\n"}, {"c.py": 'x = "FAIL[NO-HELPER] "'}, False, None),

    ("an empty mapping is a refusal",
     {}, {"c.py": 'x = "FAIL[NO-HELPER] "'}, False, None),

    ("a non-string source is a refusal rather than a crash",
     {"p.py": 'print("FAIL[NO-HELPER]")'}, {"c.py": 17}, False, None),

    ("a mapping that is not a mapping is a refusal rather than a crash",
     {"p.py": 'print("FAIL[NO-HELPER]")'}, ["c.py"], False, None),
]

FORBIDDEN = ("socket", "urllib", "http", "requests", "subprocess", "httpx", "asyncio")


def load(path):
    spec = importlib.util.spec_from_file_location("under_test", path)
    mod = importlib.util.module_from_spec(spec)
    before = set(sys.modules)
    spec.loader.exec_module(mod)
    pulled = {m.split(".")[0] for m in set(sys.modules) - before}
    return mod, pulled


def main(argv):
    if len(argv) != 1:
        print("usage: test_refusal_ids.py <module.py>")
        return 2
    failures = []
    mod, pulled = load(argv[0])
    checks = 0

    bad = sorted(set(pulled) & set(FORBIDDEN))
    checks += 1
    if bad:
        failures.append("the module reaches for the network on import: %s" % ", ".join(bad))

    checks += 1
    if not getattr(mod, "IMPLEMENTED", False):
        failures.append("IMPLEMENTED = True is not set at the top of the module")

    checks += 1
    if not callable(getattr(mod, "unemitted_ids", None)):
        failures.append("the module defines no callable unemitted_ids")
        print("REFUSAL_IDS_TESTS=FAILED (%d case(s))" % len(failures))
        return 1

    for name, producers, consumers, want_read, want_answer in CASES:
        checks += 1
        try:
            got = mod.unemitted_ids(producers, consumers)
        except Exception as exc:  # a reader that raises has not refused, it has broken
            failures.append("%s: raised %s: %s" % (name, type(exc).__name__, exc))
            continue
        if not (isinstance(got, tuple) and len(got) == 2):
            failures.append("%s: the answer is not a (read, answer) pair: %r" % (name, got))
            continue
        read, answer = got
        if read is not want_read:
            failures.append("%s: read=%r, want %r (answer %r)" % (name, read, want_read, answer))
            continue
        if not want_read:
            if answer != {}:
                failures.append("%s: a refusal came with an answer: %r" % (name, answer))
            continue
        if not isinstance(answer, dict):
            failures.append("%s: the answer is not a dict: %r" % (name, answer))
            continue
        try:
            read_back = ast.literal_eval(repr(answer))
        except (ValueError, SyntaxError) as exc:
            failures.append("%s: the answer does not read back: %s" % (name, exc))
            continue
        if read_back != answer:
            failures.append("%s: the answer does not survive the read-back" % name)
            continue
        if want_answer is not None and answer != want_answer:
            failures.append("%s: answer %r, want %r" % (name, answer, want_answer))

    if failures:
        for f in failures:
            print("  FAILED %s" % f)
        print("REFUSAL_IDS_TESTS=FAILED (%d case(s))" % len(failures))
        return 1
    print("REFUSAL_IDS_TESTS=ok (%d checks)" % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
