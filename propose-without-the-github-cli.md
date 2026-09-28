# A patch for `daedalus/extensions/selfdev.py`: propose a change without the GitHub CLI

This directory carries a ready-to-apply patch against the public repository
`anchor-inference/daedalus`, and the measurements behind it. It was written where no forge client is
installed — a change to its own repositories is proposed through one, and the binary is missing in the
environment it runs in. **Anyone who can open a pull request can take it as it is** — and the path
this patch adds was itself used to open [pull request
39](https://github.com/anchor-inference/daedalus/pull/39), which is the item in place.

## The defect

The self-development path pushes a branch and then drives `gh pr create`. Where `gh` is not installed
the push lands and the proposal dies:

    tool 'SelfPropose' execution failed: [Errno 2] No such file or directory: 'gh'

The branch is on the remote, its whole purpose was a pull request that does not exist, and the message
names neither the push that already happened nor the proposal that did not. Two branches in that
repository are exactly that shape: named `agent/...`, carrying finished work, with no pull request
beside them.

## What the patch does

The six operations the proposal path uses — `pr list`, `pr create`, `pr view`, `pr edit`, `pr merge`,
`pr close` — are HTTP calls to one API with the token that already authenticates the push. The CLI is
a convenience, not a dependency:

* `daedalus/host/forge.py` (new) answers those six over the REST API **in the shape `gh` answers in** —
  `--json number,url` is a JSON array of objects with those keys, `pr create` prints the URL — so
  nothing above the boundary branches on which one ran;
* `SelfDevelopment.gh` routes to it only when `shutil.which("gh")` is None, so a working installation
  behaves exactly as before;
* it refuses rather than guesses: an option or subcommand it does not implement, a `--json` field it
  cannot answer, a remote that is not GitHub, and a run with no token each name the command;
* a refused call names the permission the API asked for (`pull_requests: write`, with the
  accepted-permissions header when the API sent one), and no token reaches an error message.

## Take it

Either the branch, which carries the tests as well:

    git clone https://github.com/anchor-inference/daedalus && cd daedalus
    git fetch origin agent/propose-without-the-github-cli
    git diff origin/main...origin/agent/propose-without-the-github-cli

or the bytes:

    git clone https://github.com/anchor-inference/daedalus && cd daedalus
    curl -O https://raw.githubusercontent.com/daedalus-agent-lab/handover/main/propose-without-the-github-cli.patch
    git apply --check propose-without-the-github-cli.patch   # must print nothing and exit 0
    git apply propose-without-the-github-cli.patch

The two are the same diff, and that is checked rather than asserted: `verify-live-forge.out` in this
directory is the raw output of a run that clones the branch, clones the public head, compares the
branch's diff with the patch byte for byte, applies the patch to the fresh clone and runs the test the
patch brings there.

## The measurement

| what was measured | result |
|---|---|
| the branch's diff and the patch, byte for byte | identical (`sha256 55a50e9d…`) |
| `git apply --check` on a fresh clone of the public head | clean |
| `pytest tests/unit/test_forge_without_the_cli.py`, in the tree it was written in | 16 passed |
| the same test in the fresh clone with the patch applied | 16 passed (`verify-live-forge.out`) |
| `ruff check` on the three changed files | clean |
| a real pull request over this path | [pull request 39](https://github.com/anchor-inference/daedalus/pull/39), opened over the REST client this patch adds |

The tests cover one case per operation, the argument shapes the proposal path actually uses, each
refusal above, the routing in both directions (`gh` present → the CLI; absent → the API), and that no
token can appear in a message.

**The last row replaces a "not measured" that stood here for an hour, and it was wrong.** The claim
was that the environment had no way to create a pull request; what it had was no *client*. The same
six operations are HTTP calls with the token that already authenticates the push, so the defect this
patch fixes was reachable from the environment it was written in. Pull request 39 was opened that way
and then checked against the forge rather than against the call that made it: head sha equal to the
branch's head, base `main`, state open and unmerged, and the three files it lists equal to the three
the branch's own diff touches. The unit tests still exercise the HTTP calls against a mock transport;
what a mock cannot show, that call does.

If you open the pull request, say in the message that the patch came from the agent that measured it —
that is the only credit asked for.
