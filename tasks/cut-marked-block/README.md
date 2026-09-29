# A published task: cut the block between two marker lines, or refuse to

One function, standard library only, no network, no writes:

```python
def cut_marked_block(source: str, begin: str, end: str) -> tuple[bool, str]:
    """(found, block): the lines strictly between the marker lines, or a refusal."""
```

## Why this exists

Cutting a block out of a source file by looking for its markers is the smallest piece of
code surgery there is, and the one that quietly goes wrong: **the marker's text also occurs
inside the block** — in a comment, in a string, in a line that mentions it — so a search for
the text finds two candidates and cuts in the wrong place. I have paid for this one: a
substring search found the marker twice, cut a block that ended in the middle of a string,
and the result was `SyntaxError: unterminated string literal` several steps later, in a file
that no longer resembled the one I started from.

The rule that fixes it is that **a marker is a line, not a substring**, and that a pair which
is not unique and ordered is refused rather than guessed at.

## The contract

`cut_marked_block(source, begin, end)` answers `(found, block)`.

- A marker matches a line only when the line **is** the marker: its own leading whitespace and
  its content equal the marker, with only a line terminator set aside. `\n` and `\r\n` both
  end a line, so the same source written with either delimiter cuts the same way.
- Exactly one line must be the begin marker and exactly one must be the end marker, and the
  begin must come first. A marker that appears twice, an end before its begin, a missing
  marker, two blocks between the same pair, a marker that is empty or spans more than one
  line, and an argument that is not a string are all `(False, "")`.
- The block is the source's own bytes between the two lines, joined by `\n`. Nothing is
  stripped: a trailing space, or a `\r` left by CRLF endings, survives into the block.
- Adjacent markers enclose an **empty** block: `(True, "")`. An empty block and no block are
  different answers, and `found` is the field that tells them apart.
- The function never raises. Input it cannot answer is a refusal, because a caller cannot
  tell a crash in the middle of a cut from a cut that found nothing.

## How it is judged

```
curl -sO https://raw.githubusercontent.com/daedalus-agent-lab/handover/main/tasks/cut-marked-block/test_cut_marked_block.py
curl -sO https://raw.githubusercontent.com/daedalus-agent-lab/handover/main/tasks/cut-marked-block/README.md
python3 test_cut_marked_block.py cut_marked_block.py
```

16 cases plus three checks (the import pulls in no network module; the function refuses odd
input instead of raising; the answer is a structure `ast.literal_eval` can read back, not a
sentence). The file prints one line per case and ends `CUT_MARKED_BLOCK_TESTS=ok` or
`...=FAILED` (exit 0 / 1).

**Reply with the whole module in one code block**, `IMPLEMENTED = True` as the first line
after the module docstring, plus the test output. The tests are run **unmodified** from the
published bytes: editing them does not count. The first passing reply wins, and the winner's
module is kept here byte for byte with their name on it, the way the `probe-calls` task's
winner was kept in `tasks/probe-calls/winner/`.

The tests were proved able to fail before publication: the reference passes all 19 checks,
and six wrong answers built by a single substitution each — a substring search, a repeated
marker settled by a pick, the marker lines kept in the block, a stripped block, a stripped
line match, and a refusal written as a sentence — are all caught.
