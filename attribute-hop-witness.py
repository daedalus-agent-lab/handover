#!/usr/bin/env python3
"""Is there a safe witness for the attribute hop that rule B refuses?

    python3 attribute_hop_witness.py

The question (asked from outside): a probe that calls `mod.h()`, where `owner.py` sets
`h = _readings_of_good`, is MISSED by the name reader (rule B) and admitted by the reader
that follows one attribute hop (rule U). Is B's refusal a deliberate boundary, or is there
a witness that would admit the well-formed hop without admitting the dangerous one?

This file measures a candidate witness W, and answers the same question on three fixtures
that differ in one line each:

  * `good`    -- the owner sets `h` once, from a name it binds to exactly one helper.
  * `swapped` -- the same, and later in the SAME body it rebinds `h` to another helper.
  * `patched` -- the same as `good`, and another file in the tree sets `owner.h` after
                 import.

W is a static reading of the tree, not of a live object:
  (a) the owner's body assigns that attribute exactly once;
  (b) the right-hand side is a bare name the same module binds exactly once, to a callable
      whose `__name__` starts with the helper prefix;
  (c) no other file in the tree writes that attribute (an assignment to it, or a `setattr`
      naming it), and nothing rebinds the helper name the owner used.

W admits `mod.h -> _readings_of_good` on `good`, and refuses on `swapped` and `patched`.
Rule U admits all three, and on the last two names a helper that is not the one the probe
meant. Standard library only, read-only over the tree it is given, writes only its own
fixture.
"""
import ast
import functools
import importlib
import inspect
import pathlib
import shutil
import sys

PREFIX = "_readings_of_"
FIXTURE = pathlib.Path(__file__).with_name("attribute_hop_fixture")

OWNER_HEAD = '''\
"""A module that hands one of its helpers out under a short name."""
def _readings_of_good(x=0):
    return x

def _readings_of_other(x=0):
    return -x

h = _readings_of_good
'''
OWNER_SWAPPED = OWNER_HEAD + '''
h = _readings_of_other
'''
PATCHER = '''\
"""A file that rewrites the owner's short name after the owner has run."""
import owner_patched

owner_patched.h = owner_patched._readings_of_other
'''
CASE = '''\
import %s as mod

def probe():
    return mod.h()
'''


def build_fixture():
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    FIXTURE.mkdir()
    (FIXTURE / "owner_good.py").write_text(OWNER_HEAD)
    (FIXTURE / "owner_swapped.py").write_text(OWNER_SWAPPED)
    (FIXTURE / "owner_patched.py").write_text(OWNER_HEAD)
    (FIXTURE / "patcher.py").write_text(PATCHER)
    for name, owner in (("case_good", "owner_good"), ("case_swapped", "owner_swapped"),
                        ("case_patched", "owner_patched")):
        (FIXTURE / ("%s.py" % name)).write_text(CASE % owner)
    return FIXTURE


# --- the two live readers, as they are in the tool that published the table ----------------

def _unwrapped(obj):
    if isinstance(obj, functools.partial):
        obj = obj.func
    try:
        return inspect.unwrap(obj)
    except (ValueError, TypeError):
        return obj


def by_binding(fn, globals_, ns):
    out = []
    for n in inspect.unwrap(fn).__code__.co_names:
        obj = globals_.get(n, getattr(ns, n, None))
        if obj is None:
            continue
        obj = _unwrapped(obj)
        if callable(obj) and getattr(obj, "__name__", "").startswith(PREFIX):
            out.append((n, obj.__name__))
    return out


def by_union(fn, globals_, ns):
    names = list(inspect.unwrap(fn).__code__.co_names)
    out = list(by_binding(fn, globals_, ns))
    for i in range(len(names) - 1):
        holder = globals_.get(names[i], getattr(ns, names[i], None))
        if holder is None or callable(holder):
            continue
        obj = getattr(holder, names[i + 1], None)
        if obj is None:
            continue
        obj = _unwrapped(obj)
        if callable(obj) and getattr(obj, "__name__", "").startswith(PREFIX):
            pair = ("%s.%s" % (names[i], names[i + 1]), obj.__name__)
            if pair not in out:
                out.append(pair)
    return out


def verdict(pairs):
    targets = sorted({t for _, t in pairs})
    if len(targets) > 1:
        return "refuse(2+ targets: %s)" % ", ".join(targets)
    return pairs[0][0] if pairs else "MISSED (no candidate)"


def the_helper_it_names(pairs):
    """Which helper the reading points at -- the part a name-shaped verdict hides."""
    return ", ".join(sorted({t for _, t in pairs})) or "-"


# --- the candidate witness W: a static reading of the tree ---------------------------------

def _module_bindings(path):
    """Every top-level binding in this file: (target, value-source, line).

    A name is bound by an assignment, by a `def`/`class`, or by an import: a witness that
    counted only assignments would miss the `def` that gives `_readings_of_good` its name
    and refuse every well-formed hop.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                out.append((target, node.value, node.lineno))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            out.append((node.target, node.value, node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append((ast.Name(id=node.name, ctx=ast.Store()), None, node.lineno))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                out.append((ast.Name(id=bound, ctx=ast.Store()), None, node.lineno))
    return out


def _target_spelling(target):
    if isinstance(target, ast.Name):
        return ("name", target.id)
    if isinstance(target, ast.Attribute):
        return ("attr", target.attr)
    return (None, None)


def _writes_to_the_attribute(tree_path, attr, owner_stem):
    """Every statement in this file that writes `attr` ON THE OWNER, however it spells it.

    The write has to be tied to the owner module and not merely to the attribute's name:
    a file that writes `other_module.h` writes a different object's attribute, and a scan
    that counted it would refuse every well-formed hop in any tree that happens to contain
    such a file. Each file's own imports say what its base names mean, so the alias is
    resolved through them.
    """
    text = tree_path.read_text()
    tree = ast.parse(text, filename=str(tree_path))

    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == owner_stem:
                    aliases.add(alias.asname or alias.name.split(".")[0])
        if isinstance(node, ast.ImportFrom) and node.module \
                and node.module.split(".")[0] == owner_stem:
            for alias in node.names:
                aliases.add(alias.asname or alias.name)

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                kind, spelling = _target_spelling(target)
                if kind == "attr" and spelling == attr \
                        and isinstance(target.value, ast.Name) and target.value.id in aliases:
                    hits.append((tree_path.name, node.lineno, "%s.%s =" % (target.value.id, attr)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "setattr" and len(node.args) == 3:
            base, second = node.args[0], node.args[1]
            if isinstance(base, ast.Name) and base.id in aliases \
                    and isinstance(second, ast.Constant) and second.value == attr:
                hits.append((tree_path.name, node.lineno, "setattr(%s, %r, ...)" % (base.id, attr)))
    return hits


def witness(root, case_module, attribute="h"):
    """(admitted, why): the attribute hop, read from the tree's own bytes."""
    globals_ = case_module.probe.__globals__
    holder_name = None
    for name in inspect.unwrap(case_module.probe).__code__.co_names:
        value = globals_.get(name)
        if isinstance(value, type(sys)):
            holder_name = name
            break
    if holder_name is None:
        return False, "the probe reaches no module object by a bare name"
    holder = globals_[holder_name]
    owner = pathlib.Path(getattr(holder, "__file__", ""))

    if not owner.exists():
        return False, "the owner has no file in this tree"

    sets = [(t, v, ln) for t, v, ln in _module_bindings(owner)
            if _target_spelling(t) == ("name", attribute)]
    if len(sets) != 1:
        return False, "the owner assigns %s %d time(s), not once" % (attribute, len(sets))
    _, value, line = sets[0]
    if not isinstance(value, ast.Name):
        return False, "the owner's %s is not a bare name on line %d" % (attribute, line)
    source_name = value.id

    binds = [(t, v, ln) for t, v, ln in _module_bindings(owner)
             if _target_spelling(t) == ("name", source_name)]
    if len(binds) != 1:
        return False, "the owner binds %s %d time(s), not once" % (source_name, len(binds))

    fn = globals_[holder_name].__dict__.get(attribute)
    if not callable(fn) or not getattr(fn, "__name__", "").startswith(PREFIX):
        return False, "what the name holds now is not a helper: %r" % getattr(fn, "__name__", fn)

    # (c) nothing else in the tree writes the attribute, or rebinds the helper name.
    elsewhere = []
    owner_stem = owner.stem
    for path in sorted(root.glob("*.py")):
        if path.name in (owner.name, case_module.__name__ + ".py"):
            continue
        for fname, lineno, how in _writes_to_the_attribute(path, attribute, owner_stem):
            elsewhere.append("%s:%d %s" % (fname, lineno, how))
    if elsewhere:
        return False, "another file writes it on this module: %s" % ", ".join(elsewhere)

    return True, "%s.%s -> %s (set once, from %s, which this module binds once)" % (
        holder_name, attribute, fn.__name__, source_name)


def main():
    root = build_fixture()
    sys.path.insert(0, str(root))
    for name in ("patcher",):
        importlib.import_module(name)
    cases = ["case_good", "case_swapped", "case_patched"]
    print("%-14s %-24s %-10s %-24s %-9s %s" % (
        "case", "rule B (names)", "rule U", "helper U points at", "witness W", "what W says"))
    refused = 0
    for case_name in cases:
        module = importlib.import_module(case_name)
        probe = module.probe
        ns = module
        b = verdict(by_binding(probe, probe.__globals__, ns))
        u_pairs = by_union(probe, probe.__globals__, ns)
        u = verdict(u_pairs)
        ok, why = witness(root, module)
        if not ok:
            refused += 1
        print("%-14s %-24s %-10s %-24s %-9s %s" % (
            case_name, b, u, the_helper_it_names(u_pairs), "admits" if ok else "refuses", why))

    print()
    print("the tree's own bytes:")
    for name in ("owner_good.py", "owner_swapped.py", "owner_patched.py", "patcher.py"):
        print("  %-20s %s" % (name, " | ".join(
            l.strip() for l in (root / name).read_text().splitlines() if l.strip() and not l.startswith('"""'))))

    problems = []
    if refused != 2:
        problems.append("the witness refused %d case(s), expected 2" % refused)
    good = importlib.import_module("case_good")
    if not witness(root, good)[0]:
        problems.append("the witness refused the well-formed hop")
    print()
    if problems:
        print("ATTRIBUTE_HOP_WITNESS=NOT ok: " + "; ".join(problems))
        return 1
    print("ATTRIBUTE_HOP_WITNESS=ok (admitted the well-formed hop, refused the in-body "
          "rebinding and the cross-module patch)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
