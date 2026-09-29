#!/usr/bin/env python3
"""Re-take the record of the classes whose own readings no longer answer what the record says.

`check.py` replays each entry's probe and compares the answer with the entry's `observed`.
An entry whose fragment enumerates the tree's other readings therefore goes stale the moment
another class registers -- the population it counts has changed, so the record is a reading of
a tree that is no longer there. Nothing here re-derives a half by hand: for each entry it
takes the function the entry's own probe CALLS (`check.called_names`, the gate's own rule for
a call as against a mention), and calls that function's two-half helper `_readings_of_<name>`.
Every field it changes is printed with the old and the new value beside it, so the change is a
reading of the tree and not a sentence about it. An entry whose two re-taken halves come out
equal is refused: equal halves erase the divergence instead of recording it.

    retake_all.py [--repo DIR] [--classes a,b,c] [--dry]

`--classes` names the classes the gate reported `MISS` for; without it every entry is tried,
which costs minutes per helper because a helper builds and reads copies of the tree. A class
whose name is not the helper's name is still found, because the lookup goes through the probe.
A probe written as a FUNCTION is read by the certified fallback reader beside this tool
(`probe_calls_klava.py`, the answer that won the published task); the expression read stays
first, so no entry whose probe reads today changes bucket.
"""
import argparse
import functools
import inspect
import json
import pathlib
import re
import sys
import importlib.util

# The reader that won the published task, kept beside this tool. A fallback that cannot
# find its reader must refuse, not answer the empty set: the whole point of the fallback is
# that "I could not read the probe" and "the probe calls nothing" are different answers.
_CERTIFIED = pathlib.Path(__file__).with_name("probe_calls_klava.py")
if not _CERTIFIED.is_file():
    raise SystemExit(f"REFUSED: the certified reader is missing: {_CERTIFIED}")
_spec = importlib.util.spec_from_file_location("probe_calls_klava", _CERTIFIED)
_certified_reader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_certified_reader)

DEFAULT_REPO = "/srv/workspaces/62d62b5f668d/gap-game-ledger"


def leaves(old, new, prefix=""):
    """Every leaf that moved, as (dotted key, old, new); a list is compared item by item.

    A key or a list item that exists on one side only is reported with a sentinel in angle
    brackets, NOT with a bare word: the caller prints both sides as `{before!r} -> {after!r}`,
    so a sentinel `"new"` came out as `'new' -> "'_readings_of_...'"` -- indistinguishable from
    a reading that happens to be the string `new`, and a log grep for a value would have found
    it. The sentinel must be a thing no reading can be.
    """
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in sorted(set(old) | set(new)):
            out += leaves(old.get(key), new.get(key), f"{prefix}{key}.")
        return out
    if isinstance(old, list) and isinstance(new, list):
        if old == new:
            return []
        out = []
        for item in old:
            if item not in new:
                out.append((prefix.rstrip("."), f"<was there: {item!r}>", "<gone>"))
        for item in new:
            if item not in old:
                out.append((prefix.rstrip("."), "<not there before>", f"<added: {item!r}>"))
        return out
    if old == new:
        return []
    return [(prefix.rstrip("."), old, new)]


def _helper_object(obj):
    """The helper `obj` is, or None. A partial is stripped to `.func`, the object is
    unwrapped, and it counts only when its own `__name__` carries the prefix -- so a
    `_readings_of_` name bound to some other function is not a helper."""
    if obj is None:
        return None
    if isinstance(obj, functools.partial):
        obj = obj.func
    try:
        obj = inspect.unwrap(obj)
    except (ValueError, TypeError):
        pass
    if callable(obj) and getattr(obj, "__name__", "").startswith("_readings_of_"):
        return obj
    return None


def _objects_the_name_may_be_bound_to(name, fragments):
    """Every object a called name may stand for, as (where it was found, the object).

    The name itself, and one attribute hop past anything that carries attributes: a probe
    written `mod.h()` compiles to the name `h`, and the helper is not `fragments.h` but
    `fragments.mod.h` (mira, board seq 61932: "`mod.h()` goes through `co_names` as `mod`
    + `h`, so it needs one more `getattr` hop, which I didn't write"). Both are readings of
    the binding, not guesses: the object found is kept only where it IS a helper.
    """
    yield f"fragments.{name}", getattr(fragments, name, None)
    for holder_name, holder in sorted(vars(fragments).items()):
        if holder_name.startswith("__") or holder is None or not hasattr(holder, "__dict__"):
            continue
        try:
            found = getattr(holder, name, None)
        except Exception:
            continue
        if found is not None:
            yield f"fragments.{holder_name}.{name}", found


def _names_the_probe_calls(source: str) -> set:
    """The names a def-shaped probe calls, read by the certified reader.

    `called_names` parses the probe with `mode="eval"`, so a probe written as a function
    answers the empty set whatever its body calls. This asks the reader that won the
    published task (`_handover/tasks/probe-calls/`), which reads an expression first and a
    module only on `SyntaxError`, and whose answer carries `read` beside the names: a
    source it could not read is a refusal, never an empty answer. Used only where the
    expression read found none, so no entry whose probe reads today changes bucket.
    """
    read, names = _certified_reader.calls_of(source)
    return set(names) if read else set()



def helper_for(reader, fragments, entry):
    """The two-half helper this entry's probe reads, and which rule named it.

    The class's name is not always the helper's name: the fragment answers with one
    half of a pair whose name differs (`a-control-that-varies-an-argument-its-subject-
    takes-none-of` reads `_readings_of_a_control_over_an_argument_no_helper_takes`).
    The function the probe calls names that helper in its own body, so the helper is
    read off the probe rather than guessed from the class name.

    The name is read from the probe's COMPILED names (`__code__.co_names`), not from
    the text of its source: a comment or a docstring naming the helper the probe used
    BEFORE a rename is not compiled in, and a text read returns that name first --
    then runs the old helper, which still exists, and calls the result `retaken`.
    A count of buckets cannot see that: `retaken + refused + missing` still balances.

    The name being compiled in is not enough, and that is what a compiled-NAME read misses
    (mira, board seq 61932, measured here on a fixture of the six shapes): `_readings_of_fake
    = _other` puts a `_readings_of_` NAME on a function that is not a helper -- the name read
    names it and this tool would run `_other` and call the half it answered `retaken`; and a
    probe that reaches its helper through an alias, a `functools.partial` or `mod.h` has no
    `_readings_of_` name in its own body at all, so the name read answers "no helper" where a
    helper was called. So each name is resolved through the probe's own `__globals__`, a
    partial is stripped to `.func`, and the candidate is kept on the OBJECT's `__name__`, not
    on the spelling: an alias then merges with the helper it names instead of being a second
    candidate, and a `_readings_of_` name on another function is not a candidate at all.

    Exactly one candidate, or the entry is refused with the list printed. Zero goes to
    the missing-helper bucket; two or more would otherwise be settled by whichever the
    fragment happens to define first, which is a pick, not a reading.

    A name that SPELLS the prefix while the object it is bound to is not a helper is
    refused, not bucketed as "no helper": `_readings_of_fake = _other` and a helper
    behind a decorator without `functools.wraps` (whose `__name__` is the wrapper's) are
    the same bytes to this read, and the difference between them is not something this
    tool may decide. Before this, both answered "no helper" -- a statement about the
    ledger, made by a lookup that could not read the binding. Measured on nine shapes in
    `_scratch/i257/helper_shapes.py`.
    """
    called = sorted(reader.called_names(entry.get("probe", "")))
    if not called:
        # The expression read answered nothing. Before this the tool called that "no
        # helper"; the certified reader is asked instead, and the bucket is only reached
        # when it carries no helper either.
        called = sorted(_names_the_probe_calls(entry.get("probe", "")))
    candidates: dict[str, list[str]] = {}
    for name in called:
        plain = "_readings_of_" + name
        obj = _helper_object(getattr(fragments, plain, None))
        if obj is not None:
            candidates.setdefault(obj.__name__, []).append(f"named by the class: {plain}()")
        for where, bound in _objects_the_name_may_be_bound_to(name, fragments):
            obj = _helper_object(bound)
            if obj is not None:
                candidates.setdefault(obj.__name__, []).append(f"bound to {where}")
            elif name.startswith("_readings_of_") and bound is not None:
                return None, (
                    f"`{name}` is spelled like a two-half helper and is bound to "
                    f"{getattr(bound, '__name__', type(bound).__name__)!r} at {where}, which is not one: "
                    "a decorated helper and a `_readings_of_` name on another function are the same "
                    "read here, and which of them this is not something this tool may decide")
        fn = getattr(fragments, name, None)
        if fn is None or not hasattr(fn, "__code__"):
            continue
        try:
            code = inspect.unwrap(fn).__code__
        except (ValueError, TypeError):
            code = fn.__code__
        globals_ = getattr(fn, "__globals__", {})
        for found in code.co_names:
            obj = _helper_object(globals_.get(found, getattr(fragments, found, None)))
            if obj is None:
                continue
            candidates.setdefault(obj.__name__, []).append(f"called by {name}() as {found}")
    if not candidates:
        return None, None
    if len(candidates) > 1:
        listed = "; ".join(f"{name} ({', '.join(why)})" for name, why in sorted(candidates.items()))
        return None, (f"the probe reaches {len(candidates)} two-half helpers, not one: {listed}; "
                      "which of them answered is not something this tool may decide")
    return next(iter(candidates)), None


# ---------------------------------------------------------------------------------------------
# Fixed-point re-take (review i233). The one-pass version computed every requested class from
# ONE snapshot of catches.json and wrote once. A helper that reads OTHER entries' records
# (`_readings_of_a_half_written_as_a_literal` lists the entries its copy disagrees with) then
# records a value about the snapshot, not about the record it is written into, and the next
# re-take flips it. Here:
#   * the re-take runs in a STAGING copy of the repository (git-tracked files + catches.json as
#     it is on disk), so each pass's helpers read the record as it stands at the start of that
#     pass, and the real catches.json is untouched until the end;
#   * passes repeat until one pass moves nothing (a fixed point) -> the staged record is copied
#     back once (unless --dry);
#   * a cycle is the WHOLE state of the re-taken classes coming back to a state it already held.
#     One class returning to an earlier value is NOT a cycle: a helper that reads other entries'
#     records moves back while the tree converges (the class that lists the entries its copy
#     disagrees with does exactly that on the pass after those entries have been re-taken), and
#     reading that return as an oscillation stops a run that was settling. On a repeated joint
#     state the classes that moved are printed, exit 3, NOTHING is written;
#   * --max-passes bounds the loop; hitting it without a fixed point is exit 4, nothing written.
# ---------------------------------------------------------------------------------------------
import os
import shutil
import subprocess
import tempfile


def stage(repo: pathlib.Path, dest: pathlib.Path) -> None:
    """Copy what git tracks, then the working catches.json/fragments.py/check.py over it.

    Untracked-but-not-ignored files are copied too (review i233, finding 4): a new probe a
    helper needs may not be committed yet, and its absence would show up as a refusal that
    has nothing to do with the class. `--exclude-standard` keeps .gitignore's exclusions,
    so a cache stays out. The count is printed, because a copy rule that reports nothing
    about what it copied cannot be checked ("an exclusion list is a sentence about what was
    large when it was written").
    """
    try:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=repo, capture_output=True,
                                check=True).stdout.split(b"\0")
        files = [f.decode() for f in listed if f]
        others = subprocess.run(["git", "ls-files", "-z", "--others", "--exclude-standard"],
                                cwd=repo, capture_output=True,
                                check=True).stdout.split(b"\0")
        untracked = [f.decode() for f in others if f]
    except Exception:
        files, untracked = [], []
    if not files:  # not a git tree (fixture): copy everything except caches
        shutil.copytree(repo, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "verify"))
        print("staged by full copy (not a git tree)")
        return
    copied = 0
    for rel in files + untracked:
        src = repo / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            copied += 1
    print(f"staged {copied} file(s): {len(files)} tracked + {len(untracked)} untracked-not-ignored",
          flush=True)


def one_pass(workdir: pathlib.Path, wanted, pass_no: int):
    """Run the class loop once inside `workdir` in a fresh interpreter-free import.

    Returns (new_data, buckets, moved_log). The helpers read `workdir/catches.json`, which
    holds the record as it stood at the start of this pass."""
    for mod in ("check", "fragments"):
        sys.modules.pop(mod, None)
    sys.path.insert(0, str(workdir))
    try:
        import check as reader  # noqa: E402
        fragments = sys.modules.get("fragments")
        if fragments is None:
            import fragments  # noqa: E402
    finally:
        sys.path.remove(str(workdir))
    data = json.loads((workdir / "catches.json").read_text(encoding="utf-8"))
    b = dict(retaken=0, refused=0, no_helper=0, in_agreement=0, considered=0, filtered=0)
    for entry in data["entries"]:
        cls = entry.get("class")
        if wanted is not None and cls not in wanted:
            b["filtered"] += 1
            continue
        b["considered"] += 1
        print(f"[pass {pass_no}] considering {cls}", flush=True)
        helper_name, why = helper_for(reader, fragments, entry)
        if why is not None:
            b["refused"] += 1; print(f"[pass {pass_no}] NOT RETAKEN {cls}: {why}"); continue
        if helper_name is None:
            b["no_helper"] += 1; print(f"[pass {pass_no}] no two-half helper for {cls}"); continue
        try:
            answer = getattr(fragments, helper_name)()
        except Exception as exc:
            b["refused"] += 1
            print(f"[pass {pass_no}] NOT RETAKEN {cls}: {helper_name} raised {type(exc).__name__} ({exc})")
            continue
        if not isinstance(answer, dict) or set(answer) != {"as_written", "as_repaired"}:
            b["refused"] += 1; print(f"[pass {pass_no}] NOT RETAKEN {cls}: bad answer shape"); continue
        try:
            recorded = eval(entry.get("observed"))  # noqa: S307
        except Exception:
            recorded = None
        if isinstance(recorded, dict) and isinstance(answer["as_written"], dict) \
                and set(recorded) != set(answer["as_written"]):
            b["refused"] += 1; print(f"[pass {pass_no}] NOT RETAKEN {cls}: key sets differ"); continue
        written, repaired = answer["as_written"], answer["as_repaired"]
        if written == repaired:
            b["refused"] += 1; print(f"[pass {pass_no}] NOT RETAKEN {cls}: halves equal"); continue
        moved = []
        for field, value in (("observed", written), ("expected", repaired)):
            old = entry.get(field)
            if str(old).strip() == repr(value).strip():
                continue
            try:
                old_value = eval(old)  # noqa: S307
            except Exception:
                old_value = old
            moved += [(field, k, x, y) for k, x, y in leaves(old_value, value)]
        if not moved:
            b["in_agreement"] += 1; print(f"[pass {pass_no}] in agreement {cls}  (via {helper_name})"); continue
        b["retaken"] += 1
        print(f"[pass {pass_no}] RETAKEN {cls}  (via {helper_name})")
        for field, key, x, y in moved:
            print(f"    {field}.{key}: {x!r} -> {y!r}")
        entry["observed"] = repr(written)
        entry["expected"] = repr(repaired)
    return data, b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--classes", default=None)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--max-passes", type=int, default=6)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    repo = pathlib.Path(args.repo).resolve()
    wanted = set(args.classes.split(",")) if args.classes else None
    path = repo / "catches.json"
    original_bytes = path.read_bytes()
    dump = lambda d: json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n"

    def state(d):
        return {e["class"]: (e.get("observed"), e.get("expected")) for e in d["entries"]
                if wanted is None or e["class"] in wanted}

    with tempfile.TemporaryDirectory(prefix="retake_fix_") as tmp:
        work = pathlib.Path(tmp)
        stage(repo, work)
        shutil.copy2(path, work / "catches.json")
        history = [state(json.loads(original_bytes))]
        refused_last = 0
        for pass_no in range(1, args.max_passes + 1):
            data, b = one_pass(work, wanted, pass_no)
            if sum(b[k] for k in ("retaken", "refused", "no_helper", "in_agreement")) != b["considered"]:
                print("UNBALANCED buckets"); return 2
            print(f"[pass {pass_no}] considered {b['considered']} = retaken {b['retaken']} + refused "
                  f"{b['refused']} + no helper {b['no_helper']} + in agreement {b['in_agreement']}")
            refused_last = b["refused"]
            now = state(data)
            # cycle: the WHOLE state of the wanted classes comes back to a state it already held.
            # A single class returning to an earlier value is not a cycle: a helper that reads
            # other entries' records can move back while the tree is still converging.
            for k, old in enumerate(history[:-1]):
                if old != now:
                    continue
                moved = [cls for cls in now if now[cls] != history[-1].get(cls)]
                for cls in moved:
                    prev, cur = history[-1].get(cls), now[cls]
                    for i, field in enumerate(("observed", "expected")):
                        was = prev[i] if prev else None
                        if was != cur[i]:
                            print(f"CYCLE class={cls} field={field} period={len(history) - k} "
                                  f"(pass {k} -> pass {pass_no})\n    value A: {cur[i]}\n    value B: {was}")
                print("NOT WRITTEN: the joint state of the re-taken classes repeats "
                      f"(pass {k} -> pass {pass_no}); {path} left byte-identical")
                return 3
            (work / "catches.json").write_text(dump(data), encoding="utf-8")
            history.append(now)
            if b["retaken"] == 0:
                print(f"FIXED POINT after {pass_no} pass(es) ({pass_no - 1} pass(es) moved something)")
                break
        else:
            print(f"NO FIXED POINT within {args.max_passes} passes and no cycle seen; NOT WRITTEN")
            return 4
        if args.dry:
            print("dry: nothing written")
            return 1 if refused_last else 0
        if len(history) == 2 and history[0] == history[1]:
            print("nothing moved; not written")
            return 1
        if path.read_bytes() != original_bytes:
            print(f"REFUSED TO WRITE: {path} changed on disk during the run"); return 5
        shutil.copy2(work / "catches.json", path)
        print(f"wrote {path}")
        return 1 if refused_last else 0


if __name__ == "__main__":
    raise SystemExit(main())
