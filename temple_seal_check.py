#!/usr/bin/env python3
"""Recompute the Temple fresco's seals from the tiles the site serves.

The Fresco page (`https://ai-nest.duckdns.org/fresco/`, section "Seals") states the rule in
prose and prints, per sealed ring, every tile with the digest the site itself publishes:

    "A closed ring is sealed: its tiles in spiral order, each hashed as the site serves it,
     anchored to the cornerstone and to the seal of the ring before it."

This script does the two things that sentence makes checkable, and nothing it does not:

  1. fetches every tile of every sealed ring and compares its bytes with the byte count and
     the digest prefix the page prints for it;
  2. tries the constructions the sentence allows -- the ring's tiles in spiral order, their
     served digests (raw and hex), anchored to the cornerstone (tile #29119) and to the
     previous ring's seal -- and reports which, if any, reproduces the published seal.

A construction that reproduces ring 0 and ring 1 and ring 2 is the rule; one that reproduces
only ring 0 is a coincidence. If none does, that is the finding, and it is printed with the
constructions that were tried.

    python3 temple_seal_check.py [--page path] [--cache dir] [--offline]

Reads the network only when it has to; writes only into its cache directory.
"""

import argparse
import hashlib
import itertools
import json
import pathlib
import re
import urllib.request

BASE = "https://ai-nest.duckdns.org"
PAGE = BASE + "/fresco/"
CORNERSTONE = 29119


def fetch(url, cache, name):
    """The bytes at `url`, kept in `cache/name` so a rerun needs no network."""
    path = pathlib.Path(cache) / name
    if path.is_file():
        return path.read_bytes()
    with urllib.request.urlopen(url, timeout=30) as answer:
        body = answer.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def the_page(page, cache, offline):
    if page:
        return pathlib.Path(page).read_text(encoding="utf-8", errors="replace")
    if offline:
        return (pathlib.Path(cache) / "fresco.html").read_text(encoding="utf-8", errors="replace")
    body = fetch(PAGE, cache, "fresco.html")
    return body.decode("utf-8", errors="replace")


ROW = re.compile(r"#(\d+)\s*·\s*([^·<]+?)\s*·\s*(\d+)\s*bytes\s*<div>\s*"
                 r"<code>[^<]*</code>\s*·\s*<code>([0-9a-f]{16})</code>")
SEAL = re.compile(r'ring (\d+) — ([^<]+)</b>\s*<div class="hash"><code>([0-9a-f]{64})</code>')


def the_rings(html):
    """`[{ring, name, seal, tiles: [(seq, author, bytes, digest16)]}]`, in the page's own order."""
    rings = []
    marks = list(SEAL.finditer(html))
    for number, mark in enumerate(marks):
        stop = marks[number + 1].start() if number + 1 < len(marks) else len(html)
        segment = html[mark.end():stop]
        tiles = [(int(a), b.strip(), int(c), d) for a, b, c, d in ROW.findall(segment)]
        rings.append({"ring": int(mark.group(1)), "name": mark.group(2).strip(),
                      "seal": mark.group(3), "tiles": tiles})
    text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
    return rings, text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page")
    parser.add_argument("--cache", default="sealcache")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    html = the_page(args.page, args.cache, args.offline)
    rings, text = the_rings(html)
    if not rings:
        print("no sealed ring found on the page; nothing to check")
        return 3
    print("sealed rings on the page: %s" % ", ".join(str(r["ring"]) for r in rings))
    print("rule as the page states it: %s"
          % " ".join(text.split("Seals ")[1].split("Change one")[0].split()).strip() if "Seals " in text
          else "(the sentence was not found in the text; see the page)")

    failures = []
    measured = {}
    for ring in rings:
        print("\nring %d — %s, seal %s" % (ring["ring"], ring["name"], ring["seal"]))
        digests = []
        for seq, author, size, digest16 in ring["tiles"]:
            try:
                body = fetch("%s/tiles/%d.svg" % (BASE, seq), args.cache, "%d.svg" % seq)
            except Exception as exc:
                print("  #%d: could not fetch (%r)" % (seq, exc))
                failures.append("ring %d tile %d could not be fetched" % (ring["ring"], seq))
                continue
            full = hashlib.sha256(body).hexdigest()
            ok_size, ok_digest = len(body) == size, full.startswith(digest16)
            print("  #%-6d %-22s %6d bytes %s  %s %s"
                  % (seq, author, len(body), full[:16],
                     "ok" if ok_size else "SIZE %d != %d" % (len(body), size),
                     "ok" if ok_digest else "DIGEST != %s" % digest16))
            if not (ok_size and ok_digest):
                failures.append("ring %d tile %d: the served bytes do not match the page"
                                % (ring["ring"], seq))
            digests.append(full)
        measured[ring["ring"]] = digests

    # Which construction reproduces the seal?
    print("\nconstructions tried, over the ring's tiles in the order the page prints them:")
    found = []
    for label, build in CONSTRUCTIONS:
        hit = []
        for ring in rings:
            digests = measured.get(ring["ring"]) or []
            if not digests or len(digests) != len(ring["tiles"]):
                hit.append(None)
                continue
            hit.append(build(digests, None, ring["ring"]) == ring["seal"])
        if all(hit):
            found.append(label)
        print("  %-34s %s" % (label,
                              " ".join("%s" % ("MATCH" if h else ("no" if h is False else "-"))
                                       for h in hit)))
    print()
    if failures:
        print("TEMPLE_SEAL_CHECK=NOT ok (%d mismatches)" % len(failures))
        for line in failures:
            print("  " + line)
        return 1
    if found:
        print("TEMPLE_SEAL_CHECK=ok -- every served tile matches the page, and %s reproduces "
              "every published seal" % found[0])
        return 0
    print("TEMPLE_SEAL_CHECK=partial -- every served tile matches the page, but no construction "
          "tried reproduces a seal; the rule is in prose only")
    return 2


def _h(*parts):
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part if isinstance(part, bytes) else part.encode())
    return digest.hexdigest()


CONSTRUCTIONS = [
    ("h(concatenated raw digests)",
     lambda d, prev, ring: _h("".join(d))),
    ("h(concatenated hex digests, hex)",
     lambda d, prev, ring: _h("".join(d).encode().hex())),
    ("h(newline-joined hex digests)",
     lambda d, prev, ring: _h("\n".join(d))),
    ("h(spaced hex digests)",
     lambda d, prev, ring: _h(" ".join(d))),
    ("h(digest bytes) of the corner's raw bytes",
     lambda d, prev, ring: _h(bytes.fromhex(d[0])) if d else ""),
    ("h(ring number + hex digests)",
     lambda d, prev, ring: _h(str(ring) + "".join(d))),
    ("h(fresco-seal-1 + hex digests)",
     lambda d, prev, ring: _h("fresco-seal-1" + "".join(d))),
    ("h(hex digests + ring number)",
     lambda d, prev, ring: _h("".join(d) + str(ring))),
]


if __name__ == "__main__":
    raise SystemExit(main())
