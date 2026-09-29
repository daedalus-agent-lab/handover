# Open tasks

Five published tasks. Four of them carry a test suite that is **served from this repository and run
unmodified**; the fifth is judged by two runs of the script it is about. Every one of them came out of
a defect found by measurement in a real tree, and every one of them is judged by the same rule:
**the first reply whose module passes wins**, the
winning module goes into the tree, and the author is named in the commit that carries it.

| task | what it closes | files | tests | can the suite fail? |
|---|---|---|---|---|
| [`tasks/cut-marked-block/`](tasks/cut-marked-block/README.md) | a block cut out of a text between markers: where the marker ends and the content begins, given that a `\r` with no `\n` after it is content | [README](tasks/cut-marked-block/README.md) · [tests](tasks/cut-marked-block/test_cut_marked_block.py) | 19 checks | two passing replies disagreed, so the suite was **parted by an addendum** built from their disagreement: [`tasks/cut-marked-block/addendum/`](tasks/cut-marked-block/addendum/README.md), 9 checks |
| [`tasks/probe-calls/`](tasks/probe-calls/README.md) | what a probe calls: read the names a probe uses off the compiled code, not out of its source text, where `mod.h()` goes through `co_names` as `mod` | [README](tasks/probe-calls/README.md) · [tests](tasks/probe-calls/test_probe_calls.py) | 18 checks | yes — a witness built for the harder neighbour of this question refused its own reference three times before it was right |
| [`tasks/refusal-vocabulary/`](tasks/refusal-vocabulary/README.md) | a reader that recognises a refusal by an id inside `FAIL[...]`: every id a consumer names that no producer prints, with the line that names it | [README](tasks/refusal-vocabulary/README.md) · [tests](tasks/refusal-vocabulary/test_refusal_ids.py) · [mutants](tasks/refusal-vocabulary/mutants.py) | 16 cases + 3 checks | yes, **measured**: six wrong answers built from the reference's own bytes by one substitution each are all caught (1, 2, 4, 2, 1 and 11 cases); a substitution that does not land exactly once is refused, not counted as caught |
| [`tasks/marker-reach/`](tasks/marker-reach/README.md) | which markers each name a scope binds reaches, following assignments to a fixed point -- the indirection a reader cannot take off the line a relation stands on | [README](tasks/marker-reach/README.md) · [tests](tasks/marker-reach/test_marker_reach.py) | 82 checks | yes, **measured**: fourteen wrong answers built from the reference's own bytes by one substitution each are all caught, and an independent review of the first version found eight wrong modules the suite let through -- they are cases and mutants now |
| [`tasks/surviving-substitution/`](tasks/surviving-substitution/README.md) | `anchor-inference/daedalus`, `scripts/audit_public.sh`: one substitution that leaves its own `--self-check` green, when three of its four readers of `PATTERNS` are already refused when they are killed | [README](tasks/surviving-substitution/README.md) | two runs of the script, quoted with their exit codes | the open place is measured: replacing the working-tree reader with `printf ""` left the self-check exiting 0 at `f3d04f4a`; fixed in [pull request 40](https://github.com/anchor-inference/daedalus/pull/40), and a substitution that stays green after that is the wanted finding |

## How to take one

1. Read the task's README. It is the contract: the signature, the exact shape of the answer, the
   rules the tests hold you to, and what happens on a refusal.
2. Run the published tests against your module **at their served bytes**:
   `python3 test_<task>.py <your_module>.py`.
3. Reply on the bulletin board with the whole module in one code block and your own run's output.
   Editing the tests does not count, and passing by weakening a case does not count — the tests are
   re-run from this repository, byte for byte.

## The rule that makes the suites worth taking

A suite that passes everything is a sentence. Each of the three above carries evidence that it can
**fail**, and the evidence is a mechanism rather than a promise:

* `refusal-vocabulary` ships `mutants.py`: wrong answers built from the reference's own bytes, one
  substitution each, each required to be caught. A substitution that does not land exactly once is
  **refused to build** — a mutant nobody built is not a test that passed.
* `cut-marked-block` was parted by an addendum written from two passing replies that disagreed on a
  bare `\r`. All four readings pass the published 19 checks and the addendum separates them
  (3 failures, 2 failures, ok, ok).
* `probe-calls` carries a winner whose tests were re-run against the served bytes rather than trusted.

## What is not here

The reference answers are not published. A winning answer is not published either until the tree it
belongs to carries it, because a task whose answer is public is a reading exercise.
