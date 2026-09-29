#!/usr/bin/env python3
"""Addendum to the published `cut-marked-block` tests: a bare CR is content.

    python3 test_bare_cr.py cut_marked_block.py

The single argument is the path to the module you wrote. Stdlib only, no network, writes
nothing. This file is an addendum, not a replacement: the 19-check suite in
`test_cut_marked_block.py` stays as published, byte for byte, and this one adds the cases
that suite does not carry -- the ones on which the first two passing replies disagree.

The contract's rule, read off the root post: "a marker matches a line only when the line
IS the marker ... with only a line terminator set aside. `\\n` and `\\r\\n` both end a
line." Two terminators are named, so a `\\r` with no `\\n` after it is not one of them: it
is content, and it counts against the marker and survives into the block like any other
byte. Every case below is that rule, or a control that the rule must not break.
"""
import ast
import importlib.util
import pathlib
import sys

CASES = [
    # The two shapes the first two passing replies disagree on. The `\r` here is the last
    # byte of the source, so nothing follows it: it is not a `\r\n` terminator.
    ("a bare CR at the end of the source is content, so the marker is not there",
     ("# begin\nx\n# end\r", "# begin", "# end"), (False, "")),
    ("a bare CR before a CRLF is content, so the begin marker is not there",
     ("# begin\r\r\nx\n# end\n", "# begin", "# end"), (False, "")),
    ("a bare CR at the end of the source after CRLF lines",
     ("# begin\r\nx\n# end\r", "# begin", "# end"), (False, "")),
    # The controls: a CRLF terminator is set aside, and a bare CR elsewhere is content that
    # neither matches a marker nor gets eaten out of the block.
    ("a CRLF terminator is set aside",
     ("# begin\r\nx\r\n# end\r\n", "# begin", "# end"), (True, "x\r")),
    ("a bare CR inside the block survives into the block",
     ("# begin\nx\ry\n# end\n", "# begin", "# end"), (True, "x\ry")),
    ("a line that only looks like the end marker, because it carries a bare CR",
     ("# begin\nx\n# end\ry\n# end\n", "# begin", "# end"), (True, "x\n# end\ry")),
    ("the last line with no terminator at all is still the marker",
     ("# begin\nx\n# end", "# begin", "# end"), (True, "x")),
    ("a CRLF-terminated begin line is the marker",
     ("# begin\r\nx\n# end\n", "# begin", "# end"), (True, "x")),
]


def load(path):
    spec = importlib.util.spec_from_file_location("the_module_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    if len(argv) != 2:
        print("usage: python3 test_bare_cr.py <module.py>")
        return 2
    before = set(sys.modules)
    module = load(argv[1])
    pulled_in = set(sys.modules) - before
    fn = getattr(module, "cut_marked_block", None)
    if not callable(fn):
        print("FAIL  the module defines no callable cut_marked_block")
        print("BARE_CR_ADDENDUM=FAILED (1 case(s))")
        return 1

    failed = 0
    for label, args, want in CASES:
        try:
            got = fn(*args)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {label}: raised {type(exc).__name__}: {exc}")
            failed += 1
            continue
        if got == want:
            print(f"ok    {label}")
        else:
            print(f"FAIL  {label}: got {got!r}, want {want!r}")
            failed += 1

    try:
        ast.literal_eval(repr(fn("# begin\nx\n# end\n", "# begin", "# end")))
        print("ok    the answer is a structure a reader can read back")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  the answer is not readable back: {type(exc).__name__}: {exc}")
        failed += 1

    if failed:
        print(f"BARE_CR_ADDENDUM=FAILED ({failed} case(s))")
        return 1
    print(f"BARE_CR_ADDENDUM=ok ({len(CASES) + 1} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
