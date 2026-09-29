#!/usr/bin/env python3
"""Published tests for the `cut-marked-block` task. Run them unmodified:

    python3 test_cut_marked_block.py cut_marked_block.py

The single argument is the path to the module you wrote. The tests import it, run every
case, print one line per case, and finish with CUT_MARKED_BLOCK_TESTS=ok or ...=FAILED
(exit 0 / 1). Stdlib only, no network, writes nothing.

The contract the module must meet is in README.md beside this file. Nothing here reads your
source: every case calls the module's own function and compares the value it returned.
"""
import ast
import importlib.util
import pathlib
import sys

# The contract, as cases: (label, (source, begin, end), expected (found, block)).
CASES = [
    ("a block between two markers",
     ("# begin\nx\ny\n# end\n", "# begin", "# end"), (True, "x\ny")),
    ("a marker appearing inside the block as a substring",
     ("# begin\ny = '# end'\n# end\n", "# begin", "# end"), (True, "y = '# end'")),
    ("a marker inside the block as a whole line",
     ("# begin\n# end\n# end\n", "# begin", "# end"), (False, "")),
    ("the begin marker twice",
     ("# begin\na\n# begin\nb\n# end\n", "# begin", "# end"), (False, "")),
    ("the end before the begin",
     ("# end\nx\n# begin\n", "# begin", "# end"), (False, "")),
    ("the begin marker missing",
     ("x\n# end\n", "# begin", "# end"), (False, "")),
    ("the end marker missing",
     ("# begin\nx\n", "# begin", "# end"), (False, "")),
    ("markers on adjacent lines",
     ("# begin\n# end\n", "# begin", "# end"), (True, "")),
    ("CRLF endings keep the block's own bytes",
     ("# begin\r\nx\r\n# end\r\n", "# begin", "# end"), (True, "x\r")),
    ("an indented marker is not the marker",
     ("  # begin\nx\n# end\n", "# begin", "# end"), (False, "")),
    ("trailing spaces inside the block are kept",
     ("# begin\nx  \n# end\n", "# begin", "# end"), (True, "x  ")),
    ("a marker that is not one line",
     ("# a\n# b\nx\n# end\n", "# a\n# b", "# end"), (False, "")),
    ("an empty marker",
     ("# begin\nx\n# end\n", "", "# end"), (False, "")),
    ("the last line carries no newline",
     ("# begin\nx\n# end", "# begin", "# end"), (True, "x")),
    ("a source that is not a string",
     (None, "# begin", "# end"), (False, "")),
    ("two blocks between the same pair of markers",
     ("# begin\na\n# end\n# begin\nb\n# end\n", "# begin", "# end"), (False, "")),
]

FORBIDDEN = ("socket", "urllib", "http", "requests", "subprocess", "httpx", "asyncio")
ODD_INPUTS = [
    (None, "# begin", "# end"),
    (123, "# begin", "# end"),
    (b"# begin\nx\n# end\n", "# begin", "# end"),
    ("# begin\nx\n# end\n", None, "# end"),
    ("# begin\nx\n# end\n", "# begin", 7),
]


def load(path: pathlib.Path):
    """Import the candidate and report which modules ITS import pulled in.

    Measured as a difference, not as an absolute: a module already in sys.modules when this
    file started is this file's own business, not the candidate's.
    """
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("the_candidate_cut_marked_block", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"CUT_MARKED_BLOCK_TESTS=FAILED: cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sorted(set(sys.modules) - before)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 test_cut_marked_block.py <path to cut_marked_block.py>")
        return 2
    path = pathlib.Path(sys.argv[1])
    if not path.exists():
        print(f"CUT_MARKED_BLOCK_TESTS=FAILED: no such file: {path}")
        return 1
    module, pulled_in = load(path)
    fn = getattr(module, "cut_marked_block", None)
    if not callable(fn):
        print("CUT_MARKED_BLOCK_TESTS=FAILED: the module does not define cut_marked_block")
        return 1

    failed = 0
    for label, args, expected in CASES:
        try:
            got = fn(*args)
        except Exception as exc:  # noqa: BLE001 -- a raise is a failed case, not a crash
            print(f"FAIL  {label}: raised {type(exc).__name__}: {exc}")
            failed += 1
            continue
        if not isinstance(got, tuple) or len(got) != 2:
            print(f"FAIL  {label}: cut_marked_block returned {got!r}, not a two-tuple")
            failed += 1
            continue
        found, block = got
        if not isinstance(found, bool) or not isinstance(block, str):
            print(f"FAIL  {label}: (found, block) = {got!r}; want (bool, str)")
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

    # A reader that cannot answer must refuse, never raise: a crash in the middle of a cut is
    # the one outcome a caller cannot tell from a cut that found nothing.
    raised = []
    for args in ODD_INPUTS:
        try:
            fn(*args)
        except Exception as exc:  # noqa: BLE001
            raised.append(f"{args[0]!r}/{args[1]!r}/{args[2]!r}: {type(exc).__name__}")
    if raised:
        print("FAIL  the function raised on odd input: " + "; ".join(raised))
        failed += 1
    else:
        print("ok    the function refuses odd input instead of raising")

    # The answer must be a structure a reader can read back: the ledger reads these tuples
    # with ast.literal_eval, so a sentence where a tuple belongs is not comparable.
    try:
        ast.literal_eval(repr(fn("# begin\nx\n# end\n", "# begin", "# end")))
        print("ok    the answer is a structure a reader can read back")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  the answer is not readable back: {type(exc).__name__}: {exc}")
        failed += 1

    if failed:
        print(f"CUT_MARKED_BLOCK_TESTS=FAILED ({failed} case(s))")
        return 1
    print(f"CUT_MARKED_BLOCK_TESTS=ok ({len(CASES) + 3} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
