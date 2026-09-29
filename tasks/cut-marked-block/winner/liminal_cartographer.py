"""Extract one uniquely delimited block without guessing at ambiguous markers."""
IMPLEMENTED = True


def cut_marked_block(source: str, begin: str, end: str) -> tuple[bool, str]:
    """Return the exact joined lines between unique, ordered marker lines."""
    if not all(isinstance(value, str) for value in (source, begin, end)):
        return False, ""
    if not begin or not end or "\n" in begin or "\r" in begin or "\n" in end or "\r" in end:
        return False, ""

    lines = source.split("\n")
    begin_hits = []
    end_hits = []
    last = len(lines) - 1
    for index, raw in enumerate(lines):
        # A CR is part of a CRLF terminator only when this segment precedes LF.
        content = raw[:-1] if index < last and raw.endswith("\r") else raw
        if content == begin:
            begin_hits.append(index)
        if content == end:
            end_hits.append(index)

    if len(begin_hits) != 1 or len(end_hits) != 1:
        return False, ""
    start, finish = begin_hits[0], end_hits[0]
    if start >= finish:
        return False, ""
    return True, "\n".join(lines[start + 1:finish])
