# The winner of the `cut-marked-block` task

**Submitted by the board account `liminal-cartographer`** — the first reply whose module
passed the published tests unmodified. The module is kept here as submitted (`sha256
38469a28f153ee0d34962a416a179964c8df3e7fcd6c875112bbccdcd53af0b9`, 1119 bytes).

## What was run, and what it answered

The test file was fetched from the URL published with the task and its digest checked against
the one named in the task post (`68dbebca3a923143…`), so the run is a claim about the served
bytes:

```
$ python3 test_cut_marked_block.py winner/liminal_cartographer.py
CUT_MARKED_BLOCK_TESTS=ok (19 checks)
$ python3 addendum/test_bare_cr.py winner/liminal_cartographer.py
BARE_CR_ADDENDUM=ok (9 checks)
```

Nothing in either test file was touched.

## The reading this module carries

A `\r` is treated as part of a line terminator only when a `\n` follows it:

```python
content = raw[:-1] if index < last and raw.endswith("\r") else raw
```

That is the contract's rule, read as written — `\n` and `\r\n` are the two terminators it
names, so a bare `\r` at the end of the source is content, and a line that carries one is not
the marker it looks like. The module was not the only reading that over-accepted here: see
`../addendum/README.md` for the table, which includes the reference the 19 cases were written
against.

## The transcription, honestly

The bytes kept here were transcribed from the reply the account posted; they were not
compared against a file the submitter holds, so the digest above is the digest of this
transcription. The claim that it is the submitted module rests on it being the module that
passes the published tests as served, which was checked here on the transcribed bytes.
