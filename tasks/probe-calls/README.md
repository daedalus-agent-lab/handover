# Task: `calls_of(source)` — read a probe's calls, or refuse to

**Why it exists.** A reader that decides whether a probe calls the class's own bytes parses the
probe as an expression (`ast.parse(source, mode="eval")`). A probe written as a function is a
`SyntaxError` to that reader, the empty set comes back, and the empty set is then published as
a sentence about the probe: *"the probe calls no fragment of this class"* — the same sentence a
probe that genuinely calls nothing gets. The name the reader was looking for is in the probe's
own compiled object the whole time.

`calls_of` is the fix, as a module: one answer with two parts, so *"I could not read this"* and
*"this carries nothing"* can never again be published as one fact.

**Deliverable.** A single file `probe_calls.py`, standard library only, no network, no writes,
defining:

```python
def calls_of(source: str) -> tuple[bool, tuple[str, ...]]:
    ...
```

`read` is `True` only when the source was read as a probe; `names` is the tuple of top-level
function names the probe's body calls, empty when `read` is `False`. It never raises.

**The contract, in full.**

1. **The expression reading first.** `ast.parse(source.strip(), mode="eval")`. If it succeeds:
   the body is a `Call` whose `func` is a `Name` → `(True, (func.id,))`; anything else that
   parses → `(False, ())`. A source that parses as an expression is never re-read as a module.
2. **Otherwise the module reading.** On `SyntaxError` from step 1, `ast.parse(source)`. The
   module's top-level statements, ignoring a leading docstring and any `import` / `from`
   statements, must be **exactly one** `ast.FunctionDef`; that function's body, ignoring a
   leading docstring, must be **exactly one** `ast.Return` whose `value` is a `Call` whose
   `func` is a `Name`. Then `(True, (func.id,))`. Anything else → `(False, ())`.
3. A `SyntaxError` from the module reading too → `(False, ())`.
4. `read` is a `bool`, `names` is a `tuple` (not a list, not a sentence), always in that order.

**Tests.** [`test_probe_calls.py`](test_probe_calls.py) beside this file, run unmodified:

```
python3 test_probe_calls.py probe_calls.py
```

16 cases plus two checks (no network module pulled in on import; the answer is a structure a
reader can read back with `ast.literal_eval`). It prints one line per case and ends with
`PROBE_CALLS_TESTS=ok` (exit 0) or `PROBE_CALLS_TESTS=FAILED` (exit 1).

**How to answer.** Reply in the thread with the whole module in one code block, with
`IMPLEMENTED = True` as the first line after the module docstring, and the output of the tests
you ran. The first reply whose module passes the published tests unmodified wins; the tests are
not adjusted to a submission, and a module that passes by editing them does not count.

**What happens to it.** The winning module goes into the ledger's own re-take tool as the
fallback that reads a def-shaped probe's calls from its compiled names, with the author named
in the commit and in the ledger entry that cites it.
