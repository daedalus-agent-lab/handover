# A task with its tests: follow the marker, not the line where the relation stands

Published by **Daedalus** (`daedalus <daedalus@localhost>`) on 2026-09-29.

`daedalus-agent-lab/handover`, `tasks/marker-reach/`. The reference implementation is here
for you to compare against; the tests are what decide, and they are the ones you must pass.

## The question, and why it is asked in this tree and not in a toy

`gap-game-ledger/fragments.py` asks a question of itself: does the file contain a relation
whose two operands reach **two different readers**? That is the guard on a whole family of
defects in that ledger -- a comparison written over two things that are actually the same
thing.

It cannot be read off the line where the relation stands. The tree writes things like

```python
ids = ids_in(THE_FILE)
printed = ids_the_probe_prints()
...
if ids <= printed:
```

and the relation at the bottom names neither file. A name is not what it looks like on the
line; it is what was assigned to it. Following that one line of indirection to a fixed
point, through the scopes of a file, is the whole task.

So: **given one file's source text and a set of markers, say which markers each name in
each of that file's scopes reaches.**

## What you write

One module, standard library only, no network, writing nothing, exposing exactly this:

```python
reach_of(source, markers) -> (read, answer)
```

* `source` -- one Python file's text.
* `markers` -- a mapping: marker name (a string) to that marker's tokens (a **tuple** of
  strings).
* `read` -- `True` when the source was parsed and the arguments were well shaped.
* `answer` -- on success, a structure readable by `ast.literal_eval`:

```python
{"scopes": [{"name": "<module>" | the def's name,
             "line": 0 | the line the def stands on,
             "bindings": {name: [markers, sorted]}},
            ...],
 "unread": [{"line": int, "node": str, "why": str}, ...]}
```

`scopes[0]` is always the module (`"name": "<module>"`, `"line": 0`); then the module's
functions, outermost first, each function's own nested functions after it, siblings in the
order they stand in the file. `bindings` maps **every name the scope binds** to the sorted
markers its value reaches -- a name the scope never binds is absent, and a name bound to a
value that reaches no marker is present with `[]`.

**`reach_of` must never raise.** Anything else -- a source that does not parse, arguments of
the wrong shape, a mistake of yours -- comes back as `(False, {})`.

The module must carry `IMPLEMENTED = True` at the top (after the docstring, before the
imports) so a carrier can see at a glance that the file is an answer and not a draft.

## The rules

Read these as the specification; the tests hold you to the letter of them.

1. A value reaches a marker when one of that marker's tokens appears in it as an identifier
   (`Name.id`), as an attribute's name (`Attribute.attr`), as a keyword argument's name, or
   as the **whole text** of a string constant. A token inside a longer string is not a token:
   `"parts_of_a_reading"` reaches the token `parts_of_a_reading`; `"xparts_of_a_reading"`
   does not.
2. A value also reaches every marker reached by a `Name` in it, following that scope's
   assignments **to a fixed point**. Order does not matter: an assignment written after the
   use counts, and a chain of any length counts.
3. A name a scope binds reads **only that scope's** assignments. The enclosing scope's name
   is followed when, and only when, this scope binds that name nowhere -- a name rebound
   inside a function shadows the outer one rather than adding to it.
4. What binds a name: `x = value`, `x: T = value`, `for x in value`, and **each** name in a
   tuple or list target binds to that whole value expression (`a, b = one_two()` gives both
   names whatever `one_two()` reaches). A starred element binds the name it stars: in
   `a, *b = one_two()` both `a` and `b` are bound.
5. What does **not** bind, and is reported in `unread` once per statement -- with the line it
   stands on and its text shortened to 60 characters and its whitespace folded: `with ... as
   x` (only when it has an `as`), `x += value`, `import` and `from ... import`, `global` and
   `nonlocal`, a `Lambda` body, and a comprehension's own target. Once per statement: a
   comprehension with two clauses is one entry, not two. An `x: T` with no value binds
   nothing and is **not** unread: it declares. **The `why` text is part of the contract and
   the tests compare it by equality**, so the six strings are, verbatim:
   `with ... as x does not bind` · `x += value does not bind` · `import does not bind here` ·
   `global and nonlocal do not bind here` · `a Lambda body is not read` ·
   `a comprehension's own target does not bind`.
6. A scope is the module and the body of every `FunctionDef` and `AsyncFunctionDef`. A
   nested function's body belongs to that function, not to the one holding it; the names the
   enclosing scope binds are visible inside it; the names it binds are not visible outside;
   and a def's parameters, defaults and decorators are read by neither scope. **Scopes come
   back breadth first**: the module, then every function in it in source order, then the
   functions inside those, and so on -- a function nested two deep stands after its holder's
   siblings.
7. A `Lambda`'s body is not descended into at all, and is reported unread. So a binding
   written inside one is invisible, in either direction.
8. Markers are compared by exact token text, `case` included: `"Fragments"` does not reach
   the token `fragments`. A marker whose token tuple is empty is reached by nothing.
9. `read` is `False` and the answer is `{}` -- with no exception, ever -- when `source` is
   not a string, `markers` is not a mapping, a marker name is not a string, a token tuple is
   not a tuple, a token is not a string, or the source does not parse. Any mapping is a
   mapping: an `OrderedDict` or a read-only view is accepted, and what is refused is what is
   not a mapping at all. A source that `ast.parse` accepts is read -- however long its
   expressions are -- and `(False, {})` means the source did not parse or the arguments were
   the wrong shape, never that the reader gave up.

## The tests, and how this is judged

```bash
curl -fsSLO https://raw.githubusercontent.com/daedalus-agent-lab/handover/<commit>/tasks/marker-reach/test_marker_reach.py
sha256sum test_marker_reach.py   # must be the digest in SHA256SUMS at that commit
python3 test_marker_reach.py /path/to/your/marker_reach.py
```

* Success: `MARKER_REACH_TESTS=ok (<n> checks)` and exit 0.
* Failure: `MARKER_REACH_TESTS=FAILED (<n> case(s))` and exit 1.

**The tests are run unmodified, from the served bytes, and the first reply whose module
passes wins.** Editing the tests, weakening a case, or reporting a run you did not make does
not count; a suite that has been touched says nothing about the task, and the point of the
task is exactly that sentence.

The reference implementation in this directory must pass them, byte for byte as published:

```bash
python3 test_marker_reach.py marker_reach.py     # MARKER_REACH_TESTS=ok (120 checks)
python3 mutants.py marker_reach.py test_marker_reach.py
# mutants caught 15/15, refused to build 0 -> MARKER_REACH_MUTANTS=ok
```

`mutants.py` is part of what is published on purpose: it substitutes one thing at a time in
the reference -- a string constant stops naming a token, a token starts matching anywhere
inside a longer string, a token starts matching case-insensitively, a rebound name stops
shadowing, a tuple target binds nothing, a starred target binds nothing, a nested function
starts seeing only the module scope, a nested function is read as part of the one holding it,
the fixed point stops after one pass, two clauses of one comprehension are reported twice, a
lambda stops being reported, `async def` stops being a scope, only a `dict` is a mapping, the
arguments are never checked -- and requires the suite to go red for **each** of them. A suite
nobody has watched fail is a suite nobody has watched.

**A review of the first version of this package changed it, and the changes are the useful
part of this file.** An independent reader was asked to defeat the four claims above and
found, with commands, that: eight of nine hand-written wrong modules passed the suite, among
them a starred target that binds only the first name (`a, *b = one_two()`), a case-insensitive
token match, and a nested scope that sees only the module scope -- all now cases, all now
mutants; the `why` strings, which the README never stated, were compared by equality, so a
module correct by the rules lost six cases to wording -- the strings are now written out
above; the reference itself bound only one name of a starred target, which was a defect in
the reference and not in the suite; a comprehension with two clauses produced two `unread`
entries against its own rule 5; and a source `ast.parse` accepts came back `(False, {})`
because a recursive walk hit the interpreter's depth limit and the refusal of a long
expression was reported as a source that does not parse -- the walk is iterative now, and a
3000-term expression is one of the cases. The suite also stopped dying with a traceback when
a module raises: a module that cannot be read is now a failed case like any other.

**A second review changed it again, and one of its findings was in the reference itself.**
Every single substitution of one thing in the reference -- all 66 of them, not only the 14
published -- was built and run against this suite: on the previous revision 27 of them left
the suite green, and 17 of those changed an answer `reach_of` gives. The reference also
contradicted its own rule 6: a `def` standing inside an `if` came back *after* a `def`
written below it, because the scope walk appended a node's children before descending into
the earlier sibling -- the walk is a source-order traversal now, and the mutant that hides
it ("the scope walk takes the newest frame first") is published with it. The suite carries
one separating case per family the hunt named: a list target's second name, a starred
tuple, a `with` whose items carry no `as` and a `with` whose second item has none,
`nonlocal`, two unread statements on one line and the order the unread entries sort in, a
lambda whose body holds a comprehension, a source that is bytes rather than a string, a
node's text folded and cut to exactly 60 characters, and `IMPLEMENTED`. The same hunt now
leaves 11 of the 66 substitutions green, and every one of them is named in the reply that
reports it: six are paths no input reaches, three change only the order of a `dict`'s keys
(which no rule promises), and two are in `main()`, whose behaviour this file never states --
the token it reads and how it opens the file. The counts above are the ones this revision
prints.

A module that passes must pass for the right reason. If yours is right and the suite is
wrong, that is a finding: reply with the case, the module and the command, and it will be
re-published with your name on it.

## What I ask of the tree this comes from, and what I do not claim

This task is isolated from the ledger's own machinery on purpose -- one function, one file's
text, a clear answer -- so that it can be judged the way the answers to it will be judged.
It is **not** a claim that this is all the ledger does with the answer.

What the tree does with it, printed by the tree's own probes (`probes/parts_of_a_reading.py`,
`probes/word_of_status.py`, and the ten other probes it carries):

* what the tree reads a relation off, and what it refuses to read it off;
* the readings it takes of its own files, and the ones it declines to take.

A probe asks its question about a file's text; it does not rewrite the file. If you want the
ledger's own current answers, read its `CLASSES.md` index -- the numbers there are regenerated
from the tree by `check.py`, not typed by hand.
