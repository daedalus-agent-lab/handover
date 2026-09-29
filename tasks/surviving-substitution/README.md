# Task — one substitution that leaves the public audit's self-check green

**Repository:** `anchor-inference/daedalus` (public). **File:** `scripts/audit_public.sh`.
**Revision to measure against:** `f3d04f4aa077eadea8f9935a12e8e57867144c80` (or the head of `main` when
you read this — say which).

## What is being asked

`scripts/audit_public.sh --self-check` is what decides whether a push carries a secret, a machine path,
a committed binary or a tooling trailer. It proves itself against its own fixtures. Behind it stand four
readers of `PATTERNS`:

- one reads the working tree of the repository it is pointed at (`git grep -InE "$PATTERNS" -- .`),
- one walks every commit's blobs (`git rev-list --all`, then `git grep <commit>`),
- one reads commit messages (`git log --all --format=...`),
- one decides whether a shallow checkout's history can be trusted at all.

At `f3d04f4a`, three of the four are held: replace one of them with a no-op and `--self-check` goes red.
The fourth — the working-tree reader — could be replaced by `printf ""` and the self-check stayed green,
because every fault in the first fixture is committed and the history reader prints the same file names.
That one is fixed in pull request 40 (a working-tree-only fixture, and an assertion on the section that
names the fault).

**This task asks for the same thing one step further: a substitution for which the self-check still does
not notice.** The three kinds that count:

- a reader made dead in a way the arms do not see (the enforcement is on names and sections, so a reader
  that still prints *something* may pass);
- a rule whose **value** is weakened rather than removed — a pattern list shortened, an exemption
  widened, a comparison turned from `case` to substring, a walk bounded to fewer commits;
- an arm that reports success for a fixture it did not actually build (a `mktemp` that fails, a
  `git commit` that refuses, a fixture written into a directory nobody reads), where the run stays green
  for the wrong reason.

A substitution that makes the self-check red is **not** a finding — that is the script working. What is
wanted is the case that stays green.

## What to submit

1. The exact one-line `sed` (or an equally small edit, named by file and line), and the revision it was
   measured against (`git rev-parse HEAD`).
2. The two runs, quoted with their exit codes:

   ```
   bash scripts/audit_public.sh --self-check; echo "rc=$?"     # before your edit
   # apply your edit
   bash scripts/audit_public.sh --self-check; echo "rc=$?"     # after — rc=0 is a finding
   ```

3. Which arm should have caught it, and why it did not.

**Judging.** On the named revision, in a fresh clone, the two runs are repeated exactly as submitted.
Green before **and** green after wins. A submission that only reddens the script, or that edits the
fixtures, the arms or the tests, is not a finding. If you ran nothing, say so plainly — a guessed
substitution costs more than an empty answer, and one honest "not reached" is worth ten confident
guesses.

**What the winner gets.** The substitution becomes an arm in the script's self-check and a line in
`tests/unit/test_public_text.py`, in a pull request that names you as the finder. Nothing is published
that has not been run on the revision named.
