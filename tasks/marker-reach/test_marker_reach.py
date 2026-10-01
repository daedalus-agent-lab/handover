#!/usr/bin/env python3
"""The tests for `marker_reach.py`. Run: python3 test_marker_reach.py <path to marker_reach.py>

Success prints `MARKER_REACH_TESTS=ok (<n> checks)` and exits 0; failure prints
`MARKER_REACH_TESTS=FAILED (<n> case(s))` and exits 1. The module under test is imported
from the path you give, and these bytes are the ones that judge it: edit them and the run
says nothing about the task.
"""
import ast
import importlib.util
import sys

LEFT, RIGHT = "left", "right"
MARKERS = {LEFT: ("fragments",), RIGHT: ("parts_of_a_reading",)}


def load(path):
    spec = importlib.util.spec_from_file_location("marker_reach_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_of(bindings, unread=()):
    return {"scopes": [{"name": "<module>", "line": 0, "bindings": dict(bindings)}],
            "unread": list(unread)}


def two_scopes(first, second, unread=()):
    return {"scopes": [first, second], "unread": list(unread)}


# Each case: (name, source, expected answer). Expected unread entries name `line` and `why`
# only; the text of a node is required to be non-empty and at most 60 characters, which is
# checked separately so that it does not depend on how this Python version unparses.
CASES = [
    ("a string constant names a token",
     'A = "fragments"\n', module_of({"A": [LEFT]})),

    ("a token inside a longer string is not a token",
     'A = "xfragments"\n', module_of({"A": []})),

    ("an identifier names a token",
     "A = fragments.read\n", module_of({"A": [LEFT]})),

    ("an attribute name names a token",
     "A = mod.parts_of_a_reading\n", module_of({"A": [RIGHT]})),

    ("a keyword argument's name names a token",
     "A = call(fragments=1)\n", module_of({"A": [LEFT]})),

    ("a chain is followed to a fixed point, whatever the order it is written in",
     'A = B\nB = C\nC = "fragments"\n', module_of({"A": [LEFT], "B": [LEFT], "C": [LEFT]})),

    ("both markers at once",
     'A = call(fragments, "parts_of_a_reading")\n', module_of({"A": [LEFT, RIGHT]})),

    ("a name bound to nothing is present and carries nothing",
     "A = 1\n", module_of({"A": []})),

    ("a name the scope never binds is absent",
     "A = 1\nB = unknown_name\n", module_of({"A": [], "B": []})),

    ("a docstring naming a token binds nothing",
     '"""fragments"""\n', module_of({})),

    ("an annotation with a value binds",
     'A: str = "fragments"\nB: str\n', module_of({"A": [LEFT]})),

    ("a for target binds to the iterable",
     "for x in [fragments]:\n    pass\n", module_of({"x": [LEFT]})),

    ("a tuple target binds each name to the whole value",
     "a, b = one_two(fragments)\n", module_of({"a": [LEFT], "b": [LEFT]})),

    ("a function's own bindings are its own, and the enclosing ones are visible inside it",
     'outer = "fragments"\ndef f():\n    used = outer\n    mine = "parts_of_a_reading"\n',
     two_scopes({"name": "<module>", "line": 0, "bindings": {"outer": [LEFT]}},
                {"name": "f", "line": 2,
                 "bindings": {"mine": [RIGHT], "used": [LEFT]}})),

    ("a name rebound inside a function shadows the outer one",
     'x = "fragments"\ndef f():\n    x = "something else"\n    y = x\n',
     two_scopes({"name": "<module>", "line": 0, "bindings": {"x": [LEFT]}},
                {"name": "f", "line": 2, "bindings": {"x": [], "y": []}})),

    ("a nested function's body belongs to it, not to the one holding it",
     'def outer():\n    a = "fragments"\n    def inner():\n        b = "parts_of_a_reading"\n',
     {"scopes": [{"name": "<module>", "line": 0, "bindings": {}},
                 {"name": "outer", "line": 1, "bindings": {"a": [LEFT]}},
                 {"name": "inner", "line": 3, "bindings": {"b": [RIGHT]}}],
      "unread": []}),

    ("a starred target binds the name it stars",
     "a, *b = one_two(fragments)\n", module_of({"a": [LEFT], "b": [LEFT]})),

    ("a starred for target binds the name it stars",
     "for *a, b in [fragments]:\n    pass\n", module_of({"a": [LEFT], "b": [LEFT]})),

    ("a token is matched exactly, not case-insensitively",
     'A = "Fragments"\n', module_of({"A": []})),

    ("two sibling functions, one of them holding another, come back breadth first",
     "def g():\n    def h():\n        pass\ndef f():\n    pass\n",
     {"scopes": [{"name": "<module>", "line": 0, "bindings": {}},
                 {"name": "g", "line": 1, "bindings": {}},
                 {"name": "f", "line": 4, "bindings": {}},
                 {"name": "h", "line": 2, "bindings": {}}],
      "unread": []}),

    ("a long expression is read, not refused as unreadable",
     'A = "fragments" + ' + " + ".join(["1"] * 3000) + "\n", module_of({"A": [LEFT]})),

    ("async def is a scope like def",
     'async def f():\n    a = "fragments"\n',
     {"scopes": [{"name": "<module>", "line": 0, "bindings": {}},
                 {"name": "f", "line": 1, "bindings": {"a": [LEFT]}}],
      "unread": []}),

    ("functions separated by a compound statement come back in the order they stand",
     'if True:\n    def f():\n        pass\nif True:\n    def g():\n        pass\n',
     {"scopes": [{"name": "<module>", "line": 0, "bindings": {}},
                 {"name": "f", "line": 2, "bindings": {}},
                 {"name": "g", "line": 5, "bindings": {}}],
      "unread": []}),

    ("a def under an if stands before a def written after it",
     'if True:\n    def early():\n        pass\ndef late():\n    pass\n',
     {"scopes": [{"name": "<module>", "line": 0, "bindings": {}},
                 {"name": "early", "line": 2, "bindings": {}},
                 {"name": "late", "line": 4, "bindings": {}}],
      "unread": []}),

    ("a list target binds each name, not only the first",
     "[a, b] = one_two(fragments)\n", module_of({"a": [LEFT], "b": [LEFT]})),

    ("a starred element that stars a tuple binds every name in it",
     "a, *(b, c) = one_two(fragments)\n",
     module_of({"a": [LEFT], "b": [LEFT], "c": [LEFT]})),
]


def main(argv):
    if len(argv) != 1:
        print("usage: test_marker_reach.py <path to marker_reach.py>")
        return 2
    module = load(argv[0])
    checks, failures = 0, []

    def says(condition, case, detail):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append("%s: %s" % (case, detail))

    for name, source, expected in CASES:
        try:
            read, answer = module.reach_of(source, MARKERS)
        except Exception as exc:
            says(False, name, "it raised %r" % (exc,))
            continue
        says(read is True, name, "read was %r" % (read,))
        if answer != expected:
            says(False, name, "answer was %r" % (answer,))

    # The unread rules, by line and reason.
    unread_cases = [
        ("with ... as x is unread and binds nothing",
         'with open("fragments") as handle:\n    pass\n', {}, [(1, "with ... as x does not bind")]),
        ("x += value is unread",
         "x = 1\nx += 2\n", {"x": []}, [(2, "x += value does not bind")]),
        ("an import is unread",
         "import os\nfrom os import path\n", {}, [(1, "import does not bind here"),
                                                  (2, "import does not bind here")]),
        ("global is unread although the name is bound",
         'def f():\n    global G\n    G = "fragments"\n', {"G": [LEFT]},
         [(2, "global and nonlocal do not bind here")]),
        ("a lambda body is not read",
         'F = lambda: "fragments"\n', {"F": []}, [(1, "a Lambda body is not read")]),
        ("a comprehension's own target does not bind",
         "xs = [y for y in fragments]\n", {"xs": [LEFT]},
         [(1, "a comprehension's own target does not bind")]),
        ("a comprehension with two clauses is one unread statement",
         "xs = [y for y in z for w in y]\n", {"xs": []},
         [(1, "a comprehension's own target does not bind")]),
        ("a with whose items carry no as binds nothing and is not unread",
         'with open("fragments"):\n    pass\n', {}, []),
        ("a with whose second item has no as is one unread statement",
         'with open("a") as x, open("b"):\n    pass\n', {},
         [(1, "with ... as x does not bind")]),
        ("nonlocal is unread although the name is bound",
         "def f():\n    x = 1\n    def g():\n        nonlocal x\n        x = 2\n", {},
         [(4, "global and nonlocal do not bind here")]),
        ("two unread statements on one line are two entries, sorted by reason",
         "x = 1\nx += 2; import os\n", {"x": []},
         [(2, "import does not bind here"), (2, "x += value does not bind")]),
        ("the reason is read before the line when the entries are sorted",
         "x = 1\nx += 2\nimport os\n", {"x": []},
         [(2, "x += value does not bind"), (3, "import does not bind here")]),
        ("a lambda whose body holds a comprehension is still not read into",
         "F = lambda: [y for y in fragments]\n", {"F": []},
         [(1, "a Lambda body is not read")]),
    ]
    for name, source, bindings, wanted in unread_cases:
        read, answer = module.reach_of(source, MARKERS)
        says(read is True, name, "read was %r" % (read,))
        if not read:
            continue
        scope = answer["scopes"][-1] if name.startswith("global") else answer["scopes"][0]
        says(scope["bindings"] == bindings, name, "bindings were %r" % (scope["bindings"],))
        got = [(i["line"], i["why"]) for i in answer["unread"]]
        says(got == wanted, name, "unread was %r" % (got,))
        for item in answer["unread"]:
            says(isinstance(item["node"], str) and 0 < len(item["node"]) <= 60, name,
                 "the node text was %r" % (item.get("node"),))

    # The answer must be readable by a reader that only evaluates literals.
    for name, source, _ in CASES:
        try:
            _, answer = module.reach_of(source, MARKERS)
            round_tripped = ast.literal_eval(repr(answer))
        except Exception as exc:
            says(False, name, "ast.literal_eval refused the answer: %r" % (exc,))
            continue
        says(round_tripped == answer, name, "the answer did not survive literal_eval")

    # An empty token tuple is reached by nothing.
    read, answer = module.reach_of("A = fragments\n", {"empty": ()})
    says(read is True and answer["scopes"][0]["bindings"] == {"A": []},
         "an empty marker is reached by nothing", "answer was %r" % (answer,))

    # Any mapping is a mapping: rule 9 refuses what is not one, not what is not a dict.
    import collections
    import types
    for name, markers in (("an OrderedDict of token tuples",
                           collections.OrderedDict(left=("fragments",))),
                          ("a read-only mapping view",
                           types.MappingProxyType({"left": ("fragments",)}))):
        try:
            read, answer = module.reach_of("A = fragments\n", markers)
        except Exception as exc:
            says(False, name, "it raised %r" % (exc,))
            continue
        says(read is True and answer["scopes"][0]["bindings"] == {"A": [LEFT]}, name,
             "gave %r, %r" % (read, answer))

    # Refusals: wrong shapes and a source that does not parse, and never an exception.
    refusals = [
        ("a source that is not a string", None, MARKERS),
        ("markers that are not a mapping", "A = 1\n", None),
        ("a token list that is not a tuple", "A = 1\n", {"m": ["a"]}),
        ("a token that is not a string", "A = 1\n", {"m": ("a", 1)}),
        ("a marker name that is not a string", "A = 1\n", {1: ("a",)}),
        ("a source that does not parse", "def f(:\n", MARKERS),
        ("a source that is bytes, not a string", b"A = 1\n", MARKERS),
    ]
    for name, source, markers in refusals:
        try:
            read, answer = module.reach_of(source, markers)
        except Exception as exc:
            says(False, name, "it raised %r" % (exc,))
            continue
        says(read is False and answer == {}, name, "gave %r, %r" % (read, answer))

    # A node's text is folded onto one line and cut to exactly 60 characters.
    read, answer = module.reach_of('with open("fragments") as handle:\n    pass\n', MARKERS)
    text = answer["unread"][0]["node"] if read and answer.get("unread") else ""
    says(read is True and len(answer.get("unread", [])) == 1,
         "a with ... as x is one unread entry", "gave %r, %r" % (read, answer))
    says(text.startswith("with open") and "\n" not in text and "  " not in text,
         "a node's text is folded onto one line", "the text was %r" % (text,))
    read, answer = module.reach_of("with open(fragments_%s) as handle:\n    pass\n" % ("a" * 200),
                                   MARKERS)
    text = answer["unread"][0]["node"] if read and answer.get("unread") else ""
    says(len(text) == 60, "a node's text is cut to 60 characters",
         "the text was %d characters: %r" % (len(text), text))

    # The task asks the module to say it is an answer and not a draft.
    says(getattr(module, "IMPLEMENTED", None) is True, "the module carries IMPLEMENTED = True",
         "IMPLEMENTED was %r" % (getattr(module, "IMPLEMENTED", None),))

    if failures:
        print("MARKER_REACH_TESTS=FAILED (%d case(s))" % len(failures))
        for line in failures:
            print("  " + line)
        return 1
    print("MARKER_REACH_TESTS=ok (%d checks)" % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
