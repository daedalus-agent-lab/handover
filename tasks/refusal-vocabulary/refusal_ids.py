"""Compare the refusal-id vocabulary of two sides of a tree.

A reader that recognises a refusal by the id inside `FAIL[...]` names those ids in one
file, while the ids themselves are printed in another. Nothing makes the two spellings
agree, and a rename on one side is silent. This module compares them.

`unemitted_ids(producers, consumers)` takes two mappings of path -> source text and
returns `(read, answer)`.

  * `read` is True when the comparison was made, False when it was refused;
  * `answer` on success is a dict readable by `ast.literal_eval`:
      {"emitted":    {path: sorted ids that file prints},
       "named":      {path: sorted ids that file names},
       "unemitted":  {path: sorted [id, line] pairs, one per named id the producers
                      never print, the line being where that file names it}}

Rules:

  * an id is a token inside `FAIL[ ... ]` -- upper case, digits and dashes; `FAIL[no-helper]`
    is not an id;
  * a comment line is prose about the vocabulary, not a site in it, so it is dropped on
    BOTH sides before anything is read;
  * a file handed in as a producer or as a consumer that yields no id at all is a refusal:
    a comparison over a file that prints nothing is a comparison over nothing;
  * an empty mapping is a refusal, not a green answer.

Standard library only, no network, no writes, and it never raises: a question it cannot
answer comes back as `(False, {})`.
"""

IMPLEMENTED = True

import re as _re

_AN_ID = _re.compile(r"FAIL\[([A-Z0-9][A-Z0-9-]*)\]")


def _sites(source):
    """(id, line_number) for every id in a source, comment lines set aside."""
    if not isinstance(source, str):
        return None
    out = []
    for n, line in enumerate(source.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for m in _AN_ID.finditer(line):
            out.append((m.group(1), n))
    return out


def _one_side(files, what):
    """{path: sites} for one side, or None when the side cannot be read."""
    if not isinstance(files, dict) or not files:
        return None
    seen = {}
    for path, source in files.items():
        sites = _sites(source)
        if sites is None or not sites:
            return None
        seen[str(path)] = sites
    return seen


def unemitted_ids(producers, consumers):
    """(read, answer) -- see the module docstring."""
    try:
        left = _one_side(producers, "producer")
        right = _one_side(consumers, "consumer")
        if left is None or right is None:
            return (False, {})
        printed = set()
        for sites in left.values():
            printed.update(i for i, _ in sites)
        answer = {
            "emitted": {p: sorted({i for i, _ in s}) for p, s in left.items()},
            "named": {p: sorted({i for i, _ in s}) for p, s in right.items()},
            "unemitted": {},
        }
        for path, sites in right.items():
            missing = sorted([[i, n] for i, n in sites if i not in printed])
            answer["unemitted"][path] = missing
        return (True, answer)
    except Exception:
        return (False, {})
