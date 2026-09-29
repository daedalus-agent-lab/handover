#!/usr/bin/env python3
"""Published tests for the `probe_calls` task. Run them unmodified:

    python3 test_probe_calls.py probe_calls.py

The single argument is the path to the module you wrote. The tests import it, run every
case, print one line per case, and finish with PROBE_CALLS_TESTS=ok or
PROBE_CALLS_TESTS=FAILED (exit 0 / 1). Stdlib only, no network, writes nothing.

The contract the module must meet is in README.md beside this file. Nothing here reads your
source: every case calls the module's own function and compares the value it returned.
"""
import ast
import importlib.util
import pathlib
import sys

# The contract, as cases. Every one of them is a call to calls_of() and a comparison.
CASES = [
    ("an expression calling one name",
     "the_fragment_it_exercises()", (True, ("the_fragment_it_exercises",))),
    ("an expression that calls nothing",
     "the_fragment", (False, ())),
    ("an expression calling through an attribute",
     "m.f()", (False, ())),
    ("a function whose body is one return of a call, with a docstring",
     'def the_probe():\n    """The probe this class carries."""\n'
     "    return the_247_fragment_it_exercises()\n",
     (True, ("the_247_fragment_it_exercises",))),
    ("a function whose body is one return of a call",
     "def the_probe():\n    return the_fragment_it_exercises()\n",
     (True, ("the_fragment_it_exercises",))),
    ("a function returning a literal",
     "def the_probe():\n    return 1\n", (False, ())),
    ("a function with two statements before the return",
     "def the_probe():\n    x = 1\n    return f()\n", (False, ())),
    ("a function that calls without returning the call",
     "def the_probe():\n    f()\n", (False, ())),
    ("a function returning a call through an attribute",
     "def the_probe():\n    return m.f()\n", (False, ())),
    ("a function whose body holds a nested function",
     "def the_probe():\n    def inner():\n        return f()\n    return inner()\n", (False, ())),
    ("a module carrying an import and one function",
     "import os\n\ndef the_probe():\n    return g()\n", (True, ("g",))),
    ("a module carrying two top-level functions",
     "def a():\n    return 1\ndef b():\n    return g()\n", (False, ())),
    ("a module whose function is not a function definition",
     "the_probe = 1\n", (False, ())),
    ("blank lines around a function source",
     "\n\ndef the_probe():\n    return f()\n\n", (True, ("f",))),
    ("a source that is not Python at all",
     "this is not python ((", (False, ())),
    ("an empty source", "", (False, ())),
]

FORBIDDEN = ("socket", "urllib", "http", "requests", "subprocess", "httpx", "asyncio")


def load(path: pathlib.Path):
    """Import the candidate and report which modules ITS import pulled in.

    Measured as a difference, not as an absolute: a module already in sys.modules when this
    file started is this file's own business, not the candidate's.
    """
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("the_candidate_probe_calls", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"PROBE_CALLS_TESTS=FAILED: cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sorted(set(sys.modules) - before)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 test_probe_calls.py <path to probe_calls.py>")
        return 2
    path = pathlib.Path(sys.argv[1])
    if not path.exists():
        print(f"PROBE_CALLS_TESTS=FAILED: no such file: {path}")
        return 1
    module, pulled_in = load(path)
    fn = getattr(module, "calls_of", None)
    if not callable(fn):
        print("PROBE_CALLS_TESTS=FAILED: the module does not define calls_of")
        return 1

    failed = 0
    for label, source, expected in CASES:
        try:
            got = fn(source)
        except Exception as exc:  # noqa: BLE001 -- a raise is a failed case, not a crash
            print(f"FAIL  {label}: raised {type(exc).__name__}: {exc}")
            failed += 1
            continue
        if not isinstance(got, tuple) or len(got) != 2:
            print(f"FAIL  {label}: calls_of returned {got!r}, not a two-tuple")
            failed += 1
            continue
        read, names = got
        if not isinstance(read, bool) or not isinstance(names, tuple):
            print(f"FAIL  {label}: (read, names) = {got!r}; want (bool, tuple)")
            failed += 1
            continue
        if got != expected:
            print(f"FAIL  {label}: got {got!r}, want {expected!r}")
            failed += 1
            continue
        print(f"ok    {label}")

    # The module may not reach the network: importing it must not pull these in.
    pulled = [m for m in pulled_in if m.split(".")[0] in FORBIDDEN]
    if pulled:
        print("FAIL  the module reaches for the network on import: " + ", ".join(pulled))
        failed += 1
    else:
        print("ok    the module imports no network module")

    # The module must not answer with a value it cannot read back: the ledger reads these
    # tuples with ast.literal_eval, so a sentence where a tuple belongs is not comparable.
    try:
        ast.literal_eval(repr(fn("the_fragment_it_exercises()")))
        print("ok    the answer is a structure a reader can read back")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  the answer is not readable back: {type(exc).__name__}: {exc}")
        failed += 1

    if failed:
        print(f"PROBE_CALLS_TESTS=FAILED ({failed} case(s))")
        return 1
    print(f"PROBE_CALLS_TESTS=ok ({len(CASES) + 2} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
