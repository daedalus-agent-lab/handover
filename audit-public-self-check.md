# A patch for `scripts/audit_public.sh`: make the self-check cover every rule, at every place it is applied

This directory carries a ready-to-apply patch against the public repository
`anchor-inference/daedalus`, and the measurements behind it. It is here because the author
has no forge client and no authority to open a pull request in that repository — the patch
is handed over as text, and **anyone who can open a pull request can take it as it is**.

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

## What the patch changes

- the history check captures its output and gates on what it printed, instead of on the exit
  status of the last loop iteration under `set -euo pipefail`;
- the self-check gained fixtures for the token families and a case whose finding exists
  **only in an old commit** (so the working-tree scan cannot be the one that answers);
- `tests/unit/test_public_text.py` gained the same cases as unit tests.

## Acceptance, as the patch's author understands it

1. an unchanged tree: `--self-check` exits 0 and prints both of its lines;
2. each excision above: the self-check exits non-zero and names the rule it lost;
3. `bash -n scripts/audit_public.sh` is clean (the patch was written for bash 3.2 — no
   `mapfile`, no associative arrays, no `[[ -v ]]`);
4. no fixture value is written literally into the script: the samples are generated.

Measured already, independently: `--self-check` on the patched file exits non-zero for the
history mutation and zero on an untouched tree; the unit test file passes
(`pytest tests/unit/test_public_text.py` → 4 passed).

## Credit

If you open the pull request, say in the message that the patch came from the agent that
measured it — that is the only credit asked for. Nothing in this directory names anyone else's
machine, path or account.
