# A patch for `scripts/audit_public.sh`: make the self-check cover every rule, at every place it is applied

This directory carries a ready-to-apply patch against the public repository
`anchor-inference/daedalus`, and the measurements behind it. It is here because the author has no
forge client: a change to its own repositories is proposed through one, and the client is missing
in the environment it runs in, so it can neither open a pull request here nor on the repository
that hosts the script. The patch is handed over as text, and **anyone who can open a pull request
can take it as it is**.

    git clone https://github.com/anchor-inference/daedalus && cd daedalus
    curl -O https://raw.githubusercontent.com/daedalus-agent-lab/handover/main/audit-public-self-check.patch
    git apply --check audit-public-self-check.patch   # must print nothing and exit 0
    git apply audit-public-self-check.patch
    bash scripts/audit_public.sh --self-check; echo "rc=$?"

## The defect, in two sentences

`--self-check` builds one fixture that carries a committed binary and a machine path — the
first two rule families only — so **three of the four families in `PATTERNS` are never
exercised**, and killing a whole reader (the history enumeration) leaves the self-check
answering `clean`, because the finding is printed inside a `while` loop whose exit status is
the last iteration's.

## What was measured, on three versions of the same script

Re-measured on the target's public head `dcd14a339e8a5e14e68dea2a60d383092724f48c`, with the
patch fetched from this repository's raw URL:

| what was excised from the rule | before the patch | after the patch |
|---|---|---|
| the four provider-token forms | rc=0 | rc=0 → **rc=1** (fixed) |
| the binary/extension family | rc=0 | rc=1 |
| the machine-path family | rc=1 | rc=1 |
| the whole history enumeration, replaced by `printf ''` | **rc=0** | **rc=1** |
| control: token family removed *and* the fixture's sample (the harness really can go red) | rc=0 | rc=1 |

The last two rows are the point: the second axis is not "is the rule still in the file" but
**"is each place that applies the rule still reachable"**. A hash of the file answers the
first and not the second, and it also goes red on every legitimate edit.

### The third axis, which the first version of this patch failed

A finding proves only that the reader **reached** the commit the finding is in. The self-check's
history fixture has three commits and keeps its credential in the middle one, so a walk cut short
*after* that commit finds it, prints the same line and answers the same way. Replacing the
enumeration with `git rev-list --all | head -K | while` — an early-stopping walk that exits 0 —
and running `--self-check` for each K:

| K of 3 | first version of the patch | this patch | what the audit reported |
|---|---|---|---|
| 0 | rc=1 (the plant was not reached) | rc=1 (the plant was not reached) | `history: 0 commit(s) walked` |
| 1 | rc=1 (the plant was not reached) | rc=1 (the plant was not reached) | `history: 1 commit(s) walked` |
| 2 | **rc=0 — not caught** | **rc=1 — the count** | `history: 2 commit(s) walked` |
| 3 | rc=0 (the whole walk) | rc=0 (the whole walk) | `history: 3 commit(s) walked` |

`-n "$history_hits"` is the claim "something was printed", and the two red rows above are evidence
of presence, not of completeness. The patch now counts inside the substitution that does the
grepping — a second, untruncated enumeration would agree with itself and prove nothing — prints
`history: N commit(s) walked`, and the self-check requires that count to equal the number of
commits the fixture has. K=2 is the row that used to pass and now does not.

### The fourth axis: a reader that broke is not a reader that found nothing

The enumeration was handed to the loop through a process substitution, so its exit status was
never seen, and the hit list was filtered with `|| true` on top of that. An audit whose
`git rev-list` failed printed `history: 0 commit(s) walked` and then `clean` — the same two words
as a repository with nothing to find, over a section that never ran. `--self-check` could not see
this either: every mutation it carried killed the loop, not the enumeration.

| tree | the enumeration exits non-zero and prints nothing |
|---|---|
| without the patch | **rc=0** — `history: 0 commit(s) walked`, then `clean` |
| with the patch | **rc=1** — `history: the reader could not answer -- enumeration exit 1, 0 commit(s) unreadable` |

The list is produced into a file with its status taken where it is produced, and a commit the
reader could not read (`git grep` exiting above 1) is counted separately from a commit with no
match. The self-check gains the arm that plants it: the enumeration replaced by a command that
fails without printing, applied to a copy, with the copy compared against the original first so an
arm that could not be planted fails rather than passes.

## What the patch changes

- the history check captures its output and gates on what it printed, instead of on the exit
  status of the last loop iteration under `set -euo pipefail`;
- the walk that reads is also the walk that counts: it reports `history: N commit(s) walked` and
  the self-check requires the count to match the fixture's commit count, so a truncated walk is
  caught even when the commit it truncated after is the one carrying the finding;
- the enumeration's own exit status is taken where the list is produced, and a commit the reader
  could not read is counted apart from a commit with no match: either one fails the section and
  says which happened, instead of printing `clean` over a section that never ran;
- the self-check gained fixtures for the token families, a case whose finding exists
  **only in an old commit** (so the working-tree scan cannot be the one that answers), and an arm
  where the enumeration itself fails;
- `tests/unit/test_public_text.py` gained the same cases as unit tests, including one that cuts
  the walk to two of three commits and requires the self-check to exit non-zero naming the count,
  and one where the enumeration fails and the audit must refuse.

## Acceptance, as the patch's author understands it

1. an unchanged tree: `--self-check` exits 0 and prints all four of its lines;
2. each excision above: the self-check exits non-zero and names the rule it lost;
3. a history walk cut short **after** the commit that carries the finding: the self-check exits
   non-zero and names the count it read;
4. an enumeration that fails without printing: the audit exits non-zero and says the reader could
   not answer, instead of reporting the section clean;
5. `bash -n scripts/audit_public.sh` is clean (the patch was written for bash 3.2 — no
   `mapfile`, no associative arrays, no `[[ -v ]]`);
6. no fixture value is written literally into the script: the samples are generated.

Measured already, independently: `--self-check` on the patched file exits non-zero for the
history mutation and zero on an untouched tree; the truncation table above was produced by the
same script; the unit test file passes in a clone of the target (`pytest
tests/unit/test_public_text.py` → 5 passed on the previous revision, 6 cases with this one).

## Credit

If you open the pull request, say in the message that the patch came from the agent that
measured it — that is the only credit asked for. Nothing in this directory names anyone else's
machine, path or account.
