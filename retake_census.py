#!/usr/bin/env python3
"""Check that a re-take log's own census balances.

`retake_all.py` prints, once per pass, a line like

    [pass 1] considered 241 = retaken 3 + refused 3 + no helper 207 + in agreement 28

and, before it, one line per class it looked at.  The line is a claim about the
lines above it.  This reads both and refuses when they disagree: a bucket count
that does not add up to `considered`, or a `considered` that does not equal the
number of classes actually walked, is a census kept beside the thing it counts.

Usage:  python3 retake_census.py LOG [LOG ...]
Exit 0 when every pass in every log balances; 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SUMMARY = re.compile(
    r"^\[pass (?P<pass>\d+)\] considered (?P<considered>\d+) = "
    r"retaken (?P<retaken>\d+) \+ refused (?P<refused>\d+) \+ "
    r"no helper (?P<no_helper>\d+) \+ in agreement (?P<in_agreement>\d+)$"
)
WALKED = re.compile(
    r"^\[pass (?P<pass>\d+)\] considering (?P<class>\S+)$"
)
BUCKET = re.compile(
    r"^\[pass (?P<pass>\d+)\] "
    r"(?P<verb>RETAKEN|NOT RETAKEN|no two-half helper for|in agreement) (?P<class>\S+)"
)


def census_of(text: str) -> list[dict]:
    """One row per pass: what the summary claims and what the lines above it hold."""
    passes: dict[int, dict] = {}
    for line in text.splitlines():
        m = SUMMARY.match(line)
        if m:
            p = int(m.group("pass"))
            row = passes.setdefault(p, {"pass": p, "walked": 0, "buckets": {}})
            row["claimed"] = {k: int(m.group(k)) for k in
                              ("considered", "retaken", "refused", "no_helper", "in_agreement")}
            continue
        m = WALKED.match(line)
        if m:
            p = int(m.group("pass"))
            passes.setdefault(p, {"pass": p, "walked": 0, "buckets": {}})["walked"] += 1
            continue
        m = BUCKET.match(line)
        if m:
            p = int(m.group("pass"))
            row = passes.setdefault(p, {"pass": p, "walked": 0, "buckets": {}})
            verb = {"RETAKEN": "retaken", "NOT RETAKEN": "refused",
                    "no two-half helper for": "no_helper", "in agreement": "in_agreement"}[m.group("verb")]
            row["buckets"][verb] = row["buckets"].get(verb, 0) + 1
    return [passes[p] for p in sorted(passes)]


def check(path: Path) -> tuple[list[str], str]:
    """Verdict for one log: 'ok', 'incomplete' (a pass ends with no census line)
    or 'mismatch' (a census line that its own lines do not add up to)."""
    rows = census_of(path.read_text(errors="replace"))
    out, verdict = [], "ok"
    if not rows:
        return [f"{path.name}: no census line -- this log makes no claim"], "incomplete"
    for row in rows:
        c = row.get("claimed")
        if c is None:
            out.append(
                f"{path.name}: pass {row['pass']}: walked {row['walked']} and the log ends "
                "before the line that would account for them -- INCOMPLETE"
            )
            verdict = "incomplete"
            continue
        b = row["buckets"]
        named = sum(b.values())
        total = c["retaken"] + c["refused"] + c["no_helper"] + c["in_agreement"]
        faults = []
        if total != c["considered"]:
            faults.append(f"BUCKETS {total} != considered {c['considered']}")
        if row["walked"] != c["considered"]:
            faults.append(f"WALKED {row['walked']} != considered {c['considered']}")
        for k in ("retaken", "refused", "no_helper", "in_agreement"):
            if b.get(k, 0) != c[k]:
                faults.append(f"{k} lines {b.get(k, 0)} != claimed {c[k]}")
        if named and named != c["considered"] and not any(v.startswith("WALKED") for v in faults):
            faults.append(f"bucket lines {named} != considered {c['considered']}")
        if faults:
            verdict = "mismatch"
        out.append(
            "%s: pass %d: considered %d = retaken %d + refused %d + no helper %d + in agreement %d"
            " | walked %d | %s"
            % (path.name, row["pass"], c["considered"], c["retaken"], c["refused"],
               c["no_helper"], c["in_agreement"], row["walked"],
               "BALANCED" if not faults else "MISMATCH: " + "; ".join(faults))
        )
    return out, verdict


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[-2])
        return 2
    verdicts = []
    for name in argv[1:]:
        path = Path(name)
        if not path.exists():
            print(f"{name}: absent -- not read")
            continue
        lines, verdict = check(path)
        for line in lines:
            print(line)
        verdicts.append(verdict)
    overall = "mismatch" if "mismatch" in verdicts else (
        "incomplete" if "incomplete" in verdicts else "ok")
    print(
        f"RETAKES_BALANCE={overall}  (balanced {verdicts.count('ok')} log(s), "
        f"incomplete {verdicts.count('incomplete')}, mismatch {verdicts.count('mismatch')})"
    )
    return 0 if overall == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
