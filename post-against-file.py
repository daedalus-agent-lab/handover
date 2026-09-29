"""A posted block against the file it was merged into: missing, re-wrapped, or reworded?

A line-set difference over raw lines answers one question and is read as another. Given a
code block posted on a board and the file it was appended to, the count of lines of the
post that are not in the file has at least three readings, and they are not the same
finding:

  missing    the line's content is absent -- something was dropped in the merge
  re-wrapped the same words, broken at different places (the board's line breaks are the
             board's, not the author's)
  reworded   the same fact in different sentences -- the file's prose is not the post's

This script parts them. It compares the two artifacts twice:

  * code lines and comment lines separately -- prose and statements are different claims
    about a merge, and one count over both hides which moved;
  * prose re-flowed per paragraph -- a paragraph is the unit a wrap changes, so a
    paragraph-level comparison is the finest reading that ignores wrapping.

Output: for each direction, how many lines of each kind are absent, whether the posted
code lines appear in the file in the same order, and every posted comment paragraph that
is absent verbatim from the file beside its closest paragraph in the file, with a
similarity ratio -- so a rewording is shown as a rewording and not counted as a loss.

Usage:
    post_against_file.py <shipped.py> <post.md> [--block N]

The block is the Nth fenced block in the post (0-based, default: the largest one). The
script writes nothing and reaches no network. Stdlib only.
"""
import difflib
import re
import sys
from pathlib import Path

FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.S)


def fenced_blocks(text):
    return [b.split("\n") for b in FENCE.findall(text)]


def pick_block(blocks, index):
    if not blocks:
        raise SystemExit("no fenced block in the post")
    if index is None:
        return max(blocks, key=len)
    return blocks[index]


def kinds(lines):
    """The non-blank lines, split into the statements and the prose."""
    code, comment = [], []
    for line in lines:
        if not line.strip():
            continue
        (comment if line.lstrip().startswith("#") else code).append(line)
    return code, comment


def paragraphs(lines):
    """Runs of consecutive comment lines, each re-flowed to a single spaced line.

    A run of comments is the unit a wrap changes: the board breaks a sentence wherever
    its own width says, and the file breaks it wherever the author's width says. Grouping
    by blank lines alone would glue a comment run to the statement under it and compare
    prose against code, which is not the question.
    """
    out, current = [], []
    for line in lines:
        is_comment = line.lstrip().startswith("#") and bool(line.strip())
        if is_comment:
            current.append(" ".join(line.split()))
        elif current:
            out.append(" ".join(current))
            current = []
    if current:
        out.append(" ".join(current))
    return out


def in_order(needles, haystack):
    """Do `needles` occur in `haystack` in the same order, each after the last?"""
    at = -1
    for line in needles:
        try:
            at = haystack.index(line, at + 1)
        except ValueError:
            return False
    return True


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__.strip().split("Usage:")[1].strip())
    shipped_lines = Path(argv[1]).read_text().split("\n")
    post_text = Path(argv[2]).read_text()
    index = None
    if "--block" in argv:
        index = int(argv[argv.index("--block") + 1])

    blocks = fenced_blocks(post_text)
    block = pick_block(blocks, index)
    print("post: %d fenced block(s), comparing the %s one (%d line(s))"
          % (len(blocks), "largest" if index is None else "#%d" % index, len(block)))
    print("file: %d line(s)" % len(shipped_lines))
    print()

    s_code, s_comment = kinds(shipped_lines)
    p_code, p_comment = kinds(block)
    print("statements : posted %d, file %d" % (len(p_code), len(s_code)))
    print("prose lines: posted %d, file %d" % (len(p_comment), len(s_comment)))
    print()

    missing_code = [l for l in p_code if l not in s_code]
    missing_comment = [l for l in p_comment if l not in s_comment]
    print("posted statements absent from the file : %d" % len(missing_code))
    print("posted prose lines absent from the file: %d" % len(missing_comment))
    print("file statements absent from the post   : %d (the file is usually larger)"
          % len([l for l in s_code if l not in p_code]))
    print("posted statements in the file in the same order: %s"
          % in_order(p_code, s_code))
    print()

    if missing_code:
        print("A STATEMENT IS ABSENT -- this is the 'missing' reading:")
        for line in missing_code[:20]:
            print("  %s" % line)
        print()

    s_paras, p_paras = paragraphs(shipped_lines), paragraphs(block)
    absent = [p for p in p_paras if p not in s_paras]
    print("posted comment runs absent verbatim from the file: %d of %d"
          % (len(absent), len(p_paras)))
    for para in absent:
        close = difflib.get_close_matches(para, s_paras, n=1, cutoff=0.0)
        best = close[0] if close else ""
        ratio = difflib.SequenceMatcher(None, para, best).ratio()
        print()
        print("  posted : %s" % para[:160])
        print("  file   : %s" % best[:160])
        print("  similarity %.3f -- %s"
              % (ratio, "reworded" if ratio < 0.95 else "re-wrapped"))


if __name__ == "__main__":
    main(sys.argv)
