#!/usr/bin/env python3
"""Did a `_readings_of_*` name stop meaning what its module's import left behind?

The question
------------
A tool that binds a probe to its helper by looking a NAME up at check time (resolving the
name through the probe function's own `__globals__`) is only as good as the name: whatever
the name holds when the tool looks is what the probe "calls". A tree can break that in two
places, and they need two readings:

  * DURING IMPORT -- the module body binds `_readings_of_x` to the helper and later in the
    same body rebinds it (`_readings_of_x = _other`). Reading the binding by importing the
    module first and then looking at the name CANNOT SEE THIS: the import runs the whole
    body, so the value recorded as "at import" is already the value at the END of the
    import. Both readings are the same reading, and the check cannot fail. That is not a
    hypothesis: the first version of this file planted exactly this rebinding and printed
    `SELFTEST=1 (0 row(s), 1 name(s) read)`.
  * AFTER IMPORT -- another module patches the name on the first module's object
    (`setattr(mod, "_readings_of_x", other)`). Nothing in the module body shows this.

So the walk runs twice. The first pass imports every file under a line tracer and keeps
every distinct object each name holds while its own body runs. The second pass imports the
tree again with nothing traced, letting cross-module patching happen as it would for a
consumer, and then compares, for each name, the `__name__` the value carries now with the
one the traced import left behind. Two labels, two causes, printed as two rows. The
comparison is by name and not by identity on purpose: two imports of one source build two
different function objects, so `is` across them would report every name in the tree as
moved.

Usage
-----
    python3 helper_rebindings.py --selftest          # both plants must fire; exit 0
    python3 helper_rebindings.py --check --root DIR  # exit 0 clean, 1 a name moved, 2 nothing read
    python3 helper_rebindings.py --check --root DIR --json

Standard library only, read-only: the walk imports the tree's modules and writes nothing
outside a temporary directory.

What it does NOT cover, stated so nobody builds more on it than it holds: a name that was
already rebound before the walk reached the module (invisible by construction -- the tree
is simply written that way, and the static reading, a name bound twice at module level, is
the instrument for it); a rebinding that happens after the walk has read the name (a race,
not a tree property); a replacement whose `__name__` matches the traced one (the two-import
comparison is by name, so a patched-in function carrying the same name is not parted from
the original here); and a module the walk cannot import, which is counted as unreadable
rather than reported clean.
"""
import argparse
import importlib
import importlib.util
import json
import pathlib
import sys
import tempfile

PREFIX = "_readings_of_"

# --- the two plants -------------------------------------------------------------------------
PLANT_DURING = '''\
def _readings_of_good(x=0):
    return x


def _other(x=0):
    return -x


def probe():
    return _readings_of_good()


_readings_of_good = _other        # rebound inside the module body, after the probe was defined
'''

PLANT_AFTER = '''\
def _readings_of_good(x=0):
    return x


def probe():
    return _readings_of_good()
'''

PATCHER = '''\
import planted


def _other(x=0):
    return -x


setattr(planted, "_readings_of_good", _other)     # another module patches the name
'''


def module_name(path, root):
    try:
        rel = path.relative_to(root).with_suffix("")
    except ValueError:
        return None
    modname = ".".join(rel.parts)
    if modname.endswith(".__init__"):
        modname = modname[: -len(".__init__")]
    return modname


def bindings_during_import(path, root, modname):
    """(module, {name: [objects in the order this module's own body bound them]})."""
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        return None, None
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    seen = {}

    def snapshot():
        for name in list(module.__dict__):
            if not name.startswith(PREFIX):
                continue
            obj = module.__dict__[name]
            seq = seen.setdefault(name, [])
            if not seq or seq[-1] is not obj:
                seq.append(obj)

    def tracer(frame, event, arg):
        if event in ("call", "line") and frame.f_code.co_filename == str(path):
            snapshot()
        return tracer

    sys.settrace(tracer)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.settrace(None)
    snapshot()                      # what the last line of the body left behind
    return module, seen


def walk(root, limit=400):
    """(rows, errors, names read). A row is a name that moved, with which of the two causes."""
    root = pathlib.Path(root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    files = sorted(p for p in root.rglob("*.py")
                   if ".git" not in p.parts and "__pycache__" not in p.parts
                   and "verify" not in p.parts and "_scratch" not in p.parts)[:limit]
    rows, errors, during = [], [], {}

    for path in files:                                    # pass 1: traced, each file fresh
        modname = module_name(path, root)
        if modname is None:
            continue
        sys.modules.pop(modname, None)
        try:
            _, seen = bindings_during_import(path, root, modname)
        except Exception as exc:
            errors.append("%s: %s: %s" % (path, type(exc).__name__, exc))
            sys.modules.pop(modname, None)
            continue
        sys.modules.pop(modname, None)                    # no module survives pass 1
        for name, seq in (seen or {}).items():
            during[(modname, name)] = seq

    for path in files:                                    # pass 2: untraced, patching allowed
        modname = module_name(path, root)
        if modname is None or modname in sys.modules:
            continue
        try:
            importlib.import_module(modname)
        except Exception as exc:
            errors.append("%s: %s: %s" % (path, type(exc).__name__, exc))

    for (modname, name), seq in sorted(during.items()):
        if len(seq) > 1:
            rows.append({"module": modname, "name": name, "when": "during import",
                         "path": [getattr(o, "__name__", type(o).__name__) for o in seq]})
    for (modname, name), seq in sorted(during.items()):
        module = sys.modules.get(modname)
        if module is None:
            continue
        now = getattr(module, name, None)
        last = seq[-1]
        now_name = getattr(now, "__name__", type(now).__name__)
        last_name = getattr(last, "__name__", type(last).__name__)
        if now_name != last_name:
            rows.append({"module": modname, "name": name, "when": "after import",
                         "path": [last_name, now_name]})
    return rows, sorted(set(errors)), len(during)


def _plant(root, **files):
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")


def selftest():
    ok = True
    with tempfile.TemporaryDirectory(prefix="rebinding-during-") as td:
        root = pathlib.Path(td)
        _plant(root, **{"planted.py": PLANT_DURING})
        rows, errors, read = walk(root)
        hit = [r for r in rows if r["when"] == "during import" and r["name"] == "_readings_of_good"]
        print("plant 1 (rebound inside the module body): names read %d, rows %d, errors %d"
              % (read, len(rows), len(errors)))
        for row in rows:
            print("    %s %s.%s: %s" % (row["when"], row["module"], row["name"], " -> ".join(row["path"])))
        for err in errors:
            print("    import error: %s" % err)
        ok = ok and len(hit) == 1
    for modname in ("planted", "patcher"):
        sys.modules.pop(modname, None)
    with tempfile.TemporaryDirectory(prefix="rebinding-after-") as td:
        root = pathlib.Path(td)
        _plant(root, **{"planted.py": PLANT_AFTER, "patcher.py": PATCHER})
        rows, errors, read = walk(root)
        hit = [r for r in rows if r["when"] == "after import" and r["name"] == "_readings_of_good"]
        print("plant 2 (patched by another module): names read %d, rows %d, errors %d"
              % (read, len(rows), len(errors)))
        for row in rows:
            print("    %s %s.%s: %s" % (row["when"], row["module"], row["name"], " -> ".join(row["path"])))
        for err in errors:
            print("    import error: %s" % err)
        ok = ok and len(hit) == 1
    print("SELFTEST=%d" % (0 if ok else 1))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="a helper name that stopped meaning what its import left behind")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.check:
        rows, errors, read = walk(args.root)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for row in rows:
                print("MOVED (%s) %s.%s: %s" % (row["when"], row["module"], row["name"], " -> ".join(row["path"])))
            for err in errors:
                print("SKIPPED (would not import) %s" % err)
            print("CHECK root %s: %d helper name(s) read, %d moved, %d module(s) unreadable"
                  % (args.root, read, len(rows), len(errors)))
        if not read:
            return 2
        return 1 if rows else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
