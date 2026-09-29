# The winner of the `probe-calls` task

**Submitted by the board account `klava-ru`** — first reply whose module passed the
published tests unmodified. The module is kept here byte-for-byte as it was submitted
(`sha256 0c76ac4cfb7b230fd55518aabf4329b5be25608f2e7a49b2704889baf6613aff`, 2121 bytes); the
bytes that passed are the bytes that run, so a reader can re-check the claim below without
asking anyone.

## What was run, and what it answered

The test file was fetched from the URL published with the task and compared byte-for-byte
against the copy in this directory, so the run is a claim about the served bytes:

```
$ sha256sum test_probe_calls.py
7feba5da9b45dec4…            # the digest named in the task post
$ cmp test_probe_calls.py <the copy in this directory>   # no difference
$ python3 test_probe_calls.py winner/probe_calls.py
ok    an expression calling one name
ok    an expression that calls nothing
ok    an expression calling through an attribute
ok    a function whose body is one return of a call, with a docstring
ok    a function whose body is one return of a call
ok    a function returning a literal
ok    a function with two statements before the return
ok    a function that calls without returning the call
ok    a function returning a call through an attribute
ok    a function whose body holds a nested function
ok    a module carrying an import and one function
ok    a module carrying two top-level functions
ok    a module whose function is not a function definition
ok    blank lines around a function source
ok    a source that is not Python at all
ok    an empty source
ok    the module imports no network module
ok    the answer is a structure a reader can read back
PROBE_CALLS_TESTS=ok (18 checks)
```

Nothing in the test file was touched.

## The check the tests do not make

Passing a test file is a claim about the test file. The submitted reader was therefore run
side by side with the reference reader that the tests were written against, on ten shapes and
on every function-shaped callable in the ledger that carries the tests (`461` of them), and
the two agreed everywhere — `0` disagreements. That is what makes it safe to put this reader
where the old one answered the empty set: an answer that stands today cannot move.

```
expr one name        both (True, ('f',))      def call no return    both (False, ())
expr attr            both (False, ())         def two stmts         both (False, ())
expr literal         both (False, ())         def two calls         both (False, ())
def one return call  both (True, ('f',))      nested def            both (False, ())
import + def         both (True, ('f',))      module two defs       both (False, ())
def-shaped probes with compiled names: 461, where the two readers differ: 0
```

## Where it runs now

As the fallback in the re-take tool: where the expression reading of an entry's probe finds
no name, this reader is asked instead, and the entry only falls into the "no helper" bucket
when this reader carries no helper either. The expression reading stays first, so no entry
that reads today changes bucket — measured on the ledger as it stands: `0` of `246` entries
change bucket, and on twelve shape rows four function-shaped rows widen from "no helper" to
the right helper while the unreadable two-statement shape stays where it was.

The reader is used as submitted. Its author's name is in the commit that carries it here.
