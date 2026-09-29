# A rebinding check that could not fail, and the two readings that can

`helper-rebindings-two-readings.py` answers one question two ways:

> a `_readings_of_*` name in a tree — does it still mean, at check time, what its module's
> own import left behind?

## Why it is written twice

The first version of this check imported each module and *then* looked at the name. That
records "the binding at import" as the value at the **end** of the import, because the
import runs the whole module body first. A module that rebinds the name partway through its
own body — the ordinary way this shape is written — is invisible to it: both readings are
the same reading, and the check cannot fail.

It could not even fail its own selftest. The plant is a module that defines
`_readings_of_good`, defines `probe()` calling it, and then rebinds the name to `_other` at
the end of the body:

```
planted rebinding: rows 0, names read 1, import errors 0
SELFTEST=1 (0 row(s), 1 name(s) read)
```

`SELFTEST=1` is the first version telling you it did not fire. A green run of that version
is agreement by construction, not evidence about the tree.

## The two readings

| reading | how it is taken | the shape it can see |
|---|---|---|
| during import | the module body runs under a line tracer; every distinct object the name holds while the body runs is kept; more than one is a rebinding inside the body | `_readings_of_x = _other` after the `def`, before the module ends |
| after import | the tree is imported a second time with nothing traced, letting cross-module patching happen as a consumer would see it; each name's current `__name__` is compared with the traced one | `setattr(other_module, "_readings_of_x", something)` from a different file |

Both plants fire on the shipped file:

```
plant 1 (rebound inside the module body): names read 1, rows 1, errors 0
    during import planted._readings_of_good: _readings_of_good -> _other
plant 2 (patched by another module): names read 1, rows 1, errors 0
    after import planted._readings_of_good: _readings_of_good -> _other
SELFTEST=0
```

## Why the after-import comparison is by name and not by identity

Two imports of one source build two different function objects, so an identity comparison
across the two passes reports **every** name in the tree as moved — the first attempt at
this file did exactly that, and printed `_other -> _other` as a rebinding. The comparison is
therefore on the `__name__` the value carries, which parts the patched shape from the
unpatched one; a patched-in function carrying the same `__name__` as the original is stated
in the file's docstring as a shape this reading does not part.

## Running it

```sh
python3 helper-rebindings-two-readings.py --selftest          # both plants; exit 0
python3 helper-rebindings-two-readings.py --check --root DIR  # 0 clean, 1 a name moved, 2 nothing read
```

Standard library only, read-only; the only writes are the temporary trees the selftest
builds. A module the walk cannot import is counted as unreadable and printed, never
reported clean.

Measured on a Python tree that resolves helper names at check time:

```
CHECK root .: 38 helper name(s) read, 0 moved, 529 module(s) unreadable
```

The unreadable modules are caches and vendored packages the walk cannot import under their
own names; they are named in the output rather than folded into the zero.

## What the static reading next to it covers

`helper-rebindings.py` reads the **source** and refuses a name bound twice at module level.
That is a different question from this one (it needs no import, and it sees a `def` followed
by an assignment even in a module nothing imports), and its docstring hands the run-time
shapes to "resolving the object at the moment of use". That hand-off is exactly the claim
the first version of this file falsified, which is why both instruments are worth keeping
and why each one states the shapes it does not part.
