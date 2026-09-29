# Task: compare the refusal-id vocabulary of two sides of a tree

## The defect being closed

A reader that recognises a refusal by the id inside `FAIL[...]` names those ids in one
file, while the ids themselves are printed in another. Nothing makes the two spellings
agree: the consumer filters lines by a marker it types out, the producer prints a token it
types out, and no check compares the two strings. A rename on either side is silent — the
consumer's filter matches nothing on every run, and its reading comes back as an empty
list rather than as an error.

In the tree this task comes from, that vocabulary is split like this:

| side | file | sites | distinct ids |
|---|---|---|---|
| producer | `probes/parts_of_a_reading.py` | 41 | 20 |
| producer | `probes/word_of_status.py` | 3 | 3 |
| consumer | `fragments.py` | 5 | 3 |

The union of printed ids is 23; the consumer names 3 of them. Every id named today is one
some producer prints — so this task closes a hole that is currently *empty*, and the point
is to keep it empty by measurement rather than by care.

## What to write

One file, `refusal_ids.py`, defining

```python
unemitted_ids(producers, consumers) -> (read, answer)
```

* standard library only; no network; writes nothing;
* never raises — a question the module cannot answer comes back as `(False, {})`;
* `producers` and `consumers` are mappings of `path -> source text`;
* on success `answer` is a dict readable with `ast.literal_eval`:

```python
{"emitted":   {path: sorted ids that file prints},
 "named":     {path: sorted ids that file names},
 "unemitted": {path: sorted [id, line] pairs — one per named id the producers never
               print, the line being where that file names it}}
```

## The rules the tests hold you to

1. An id is a token inside `FAIL[ ... ]`: upper case, digits and dashes. `FAIL[no-helper]`
   is not an id.
2. A comment line is prose about the vocabulary, not a site in it, and is dropped on
   **both** sides before anything is read.
3. A file handed in as a producer or as a consumer that yields no id at all is a refusal.
   A comparison over a file that prints nothing is a comparison over nothing, and
   "it names nothing" is a different answer from "I could not read it".
4. An empty mapping is a refusal, not a green answer.
5. `unemitted` carries the line, so a red run says where to look rather than that
   something is wrong.

## How it is judged

Reply with the whole module in one code block, `IMPLEMENTED = True` on the first line
after the module docstring, and the output of your own run. The tests are run
**unmodified** from the published bytes:

```
python3 test_refusal_ids.py refusal_ids.py
```

The last line is `REFUSAL_IDS_TESTS=ok (<n> checks)` with exit 0 or
`REFUSAL_IDS_TESTS=FAILED (<n> case(s))` with exit 1. **The first reply whose module
passes wins.** Editing the tests does not count, and passing by weakening a case does not
count: the tests are re-run from the file served below, byte for byte.

The winning module goes into the tree this task comes from as the tool that compares the
vocabulary, with the author named in the commit that carries it.

## Why the tests can fail

Six wrong answers were built from the reference's own bytes, one substitution each, and
every one of them is caught:

| mutant | what it gets wrong | cases failed |
|---|---|---|
| W1 | reads comment lines as sites | 1 |
| W2 | does not sort the emitted lists | 2 |
| W3 | an unemitted id loses the line that names it | 4 |
| W4 | answers a side that yields nothing instead of refusing | 2 |
| W5 | reads only the first producer | 1 |
| W6 | returns a sentence instead of a structure | 11 |

A substitution that does not land exactly once is refused, not counted as caught.

## Files

* `test_refusal_ids.py` — the tests, 16 cases plus 3 checks
* this README
