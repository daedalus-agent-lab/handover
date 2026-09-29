#!/usr/bin/env python3
"""What to print beside a callable so a row stays comparable between runs.

`__qualname__` is a NAME, and a name is not an identity: two distinct lambdas are both
`<lambda>`, `functools.partial` has no `__qualname__` at all, and a callable instance's
`__qualname__` belongs to its class, not to the instance. This module answers with two
columns instead of one:

  * `name`   -- for a human to read; never used to compare rows;
  * `digest` -- for a run to compare; a hash of the code the callable will execute plus
               the shape it will execute it with, and NOT of where the file sits.

Measured below on shapes that part the two columns:

  shape                     name                                  digest differs from
  ------------------------  ------------------------------------  --------------------
  a plain function          module.func                           the lambda
  two lambdas in one file   <lambda> (identical!)                 each other
  the same body by 2 names  the two names differ                  nothing -- same digest
  a functools.partial       (no __qualname__)                     the wrapped function
  a callable instance       the CLASS's qualname                  a second instance
  a bound method            Class.method                          the unbound function
  a builtin                 len                                   --

    python3 callable_identity.py
"""
import functools
import hashlib
import sys
import types


def _code_digest(code, depth=0):
    """A digest of what this code object executes, with nested code objects folded in."""
    h = hashlib.sha256()
    parts = [
        b"code", code.co_code,
        b"consts", repr([c for c in code.co_consts if not isinstance(c, types.CodeType)]).encode(),
        b"varnames", repr(code.co_varnames).encode(),
        b"flags", bytes([code.co_flags & 0xFF, (code.co_flags >> 8) & 0xFF]),
    ]
    for part in parts:
        h.update(part)
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            h.update(b"nested" + bytes.fromhex(_code_digest(c, depth + 1)))
    return h.hexdigest()


def _digest_of(obj, seen=None):
    """A stable, name-independent digest of a callable, or None when it has no body."""
    seen = seen or set()
    if id(obj) in seen:
        return None
    seen.add(id(obj))
    if isinstance(obj, types.MethodType):
        return "bound:" + (_digest_of(obj.__func__, seen) or "?")
    if isinstance(obj, functools.partial):
        base = _digest_of(obj.func, seen) or "?"
        shape = repr((obj.args, tuple(sorted(obj.keywords.items())) if obj.keywords else ()))
        return "partial:" + base[:16] + ":" + hashlib.sha256(shape.encode()).hexdigest()[:8]
    code = getattr(obj, "__code__", None)
    if code is not None:
        return "code:" + _code_digest(code)[:16]
    if isinstance(obj, type):
        return "class:" + hashlib.sha256(
            repr(sorted(obj.__dict__)).encode()).hexdigest()[:16]
    if callable(obj) and not isinstance(obj, types.BuiltinFunctionType):
        cls = type(obj)
        return "obj:" + (cls.__module__ or "?") + "." + cls.__qualname__
    return "native:" + (getattr(obj, "__qualname__", None) or type(obj).__name__)


def location(obj):
    """(file, line) of the code that will run, WITHOUT the directories around it.

    The file alone is machine-specific, so only its tail is stable and comparable: the
    relative path inside the tree, and the first line of the body.
    """
    code = getattr(obj, "__code__", None)
    if code is None and isinstance(obj, (types.MethodType, functools.partial)):
        inner = obj.__func__ if isinstance(obj, types.MethodType) else obj.func
        code = getattr(inner, "__code__", None)
    if code is None:
        return None
    return (code.co_filename.rsplit("/", 1)[-1], code.co_firstlineno)


def identity(obj):
    """(name, digest, place) -- the reading triple.

    `name` is for a human, `digest` for a run, `place` for going to look. No column on
    its own is an identity, and the two limits are printed by `main()`.
    """
    name = getattr(obj, "__qualname__", None)
    if name is None and isinstance(obj, functools.partial):
        name = "(no __qualname__: functools.partial)"
    elif name is None:
        name = "(no __qualname__: %s)" % type(obj).__name__
    module = getattr(obj, "__module__", None)
    if isinstance(obj, functools.partial):
        module = "%s -> %s" % (module, getattr(obj.func, "__module__", "?"))
    place = location(obj)
    return ("%s.%s" % (module, name) if module else name, _digest_of(obj),
            "%s:%d" % place if place else "-")


# ---------------------------------------------------------------- the measurements
def _readings_of_func():
    return 1


_alias_of_func = _readings_of_func

LAMBDA_ONE = lambda x: x + 1
LAMBDA_TWO = lambda x: x - 1

PARTIAL_OF_FUNC = functools.partial(_readings_of_func)


class Holder:
    def method(self):
        return 1


class OtherHolder:
    def method(self):
        return 2


class Counter:
    """A callable instance: two of these with different state run the SAME body."""

    def __init__(self, step):
        self.step = step

    def __call__(self, x):
        return x + self.step


CASES = [
    ("a plain function", _readings_of_func),
    ("the same body under another name", _alias_of_func),
    ("first lambda", LAMBDA_ONE),
    ("second lambda in the same file", LAMBDA_TWO),
    ("functools.partial of the function", PARTIAL_OF_FUNC),
    ("functools.partial with an argument", functools.partial(_readings_of_func)),
    ("an instance of Holder", Holder()),
    ("an instance of OtherHolder", OtherHolder()),
    ("a callable instance, step 1", Counter(1)),
    ("a callable instance, step 2", Counter(2)),
    ("a bound method of a second instance", OtherHolder().method),
    ("a bound method of a second Holder", Holder().method),
    ("the bound method Holder.method", Holder().method),
    ("the unbound function Holder.method", Holder.method),
    ("a builtin, len", len),
]


def main():
    print("%-34s %-46s %-24s %s" % ("shape", "name", "digest", "place (file:line)"))
    seen = {}
    problems = []
    for label, obj in CASES:
        name, digest, place = identity(obj)
        print("%-34s %-46s %-24s %s" % (label, name, digest, place))
        seen[label] = (name, digest, place)

    def check(what, ok, detail):
        print("%-6s %s -- %s" % ("ok" if ok else "FAILED", what, detail))
        if not ok:
            problems.append(what)

    def identical(a, b):
        return seen[a] == seen[b]

    # 1. two distinct lambdas print the SAME name and must have different digests
    check("two lambdas share the name column",
          seen["first lambda"][0] == seen["second lambda in the same file"][0],
          "both read %s" % seen["first lambda"][0])
    check("two lambdas are parted by the digest",
          seen["first lambda"][1] != seen["second lambda in the same file"][1],
          "%s vs %s" % (seen["first lambda"][1], seen["second lambda in the same file"][1]))
    # 2. the same body reached by two names in the tree: ONE name, ONE digest
    check("one body reached by two names prints ONE name and ONE digest",
          identical("a plain function", "the same body under another name"),
          "%s / %s" % (seen["a plain function"][0], seen["a plain function"][1]))
    # 3. a partial has no __qualname__ and must still be distinguishable
    check("a partial has no __qualname__",
          "(no __qualname__" in seen["functools.partial of the function"][0],
          seen["functools.partial of the function"][0])
    check("a partial is separable from what it wraps",
          seen["functools.partial of the function"][1] != seen["a plain function"][1],
          "%s vs %s" % (seen["functools.partial of the function"][1], seen["a plain function"][1]))
    # 4. instances of DIFFERENT classes are parted
    check("instances of different classes are parted by the digest",
          seen["an instance of Holder"][1] != seen["an instance of OtherHolder"][1],
          "%s vs %s" % (seen["an instance of Holder"][1], seen["an instance of OtherHolder"][1]))
    # 5. bound and unbound: the name differs, the body is the same
    check("a bound method carries its class name",
          seen["the bound method Holder.method"][0].endswith("Holder.method"),
          seen["the bound method Holder.method"][0])
    check("the bound prefix parts the bound from the unbound",
          seen["the bound method Holder.method"][1] != seen["the unbound function Holder.method"][1],
          "%s vs %s" % (seen["the bound method Holder.method"][1],
                         seen["the unbound function Holder.method"][1]))
    check("bound and unbound point at the same line",
          seen["the bound method Holder.method"][2] == seen["the unbound function Holder.method"][2],
          seen["the bound method Holder.method"][2])

    # the two limits, asserted so they are printed rather than discovered later
    check("LIMIT: two callable instances of one class are identical in all three columns",
          identical("a callable instance, step 1", "a callable instance, step 2"),
          "both read %s / %s / %s -- neither the name nor the digest sees `step`"
          % seen["a callable instance, step 1"])
    check("LIMIT: so are two bound methods of different instances of ONE class",
          identical("the bound method Holder.method", "a bound method of a second Holder"),
          "both read %s" % (seen["the bound method Holder.method"],))

    print("CALLABLE_IDENTITY=%s (%d shapes, %d failed)" % (
        "ok" if not problems else "NOT ok", len(CASES), len(problems)))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
