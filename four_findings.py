"""Four findings reported against the REST fallback for the GitHub CLI, run against two revisions.

The findings were posted as a static audit of the patch pull request 39 carries
(``propose-without-the-github-cli.patch``). This harness drives the same four shapes through the
module as that patch writes it and through the module as the superseding patch writes it, and
prints what each revision does with each shape.

It answers with the requests the module would have made, not with a claim about the source: every
call goes through an ``httpx.MockTransport`` that records the method, the path, the query and the
body, and answers a canned body. Nothing leaves the machine and no token is used.

    # two revisions, read out of the patches themselves, over a clone for the files they do not touch
    git clone --depth 1 https://github.com/anchor-inference/daedalus /tmp/d
    uv run --no-project --with httpx python four_findings.py --clone /tmp/d \\
        --patch propose-without-the-github-cli.patch \\
        --patch propose-over-rest-without-the-cli-v2.patch

    # or a tree that already carries the module
    python3 four_findings.py --tree /path/to/clone
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import httpx

SHAPES: list[tuple[str, tuple[str, ...], str]] = [
    (
        "1  pr view 8 --json number,url",
        ("pr", "view", "8", "--json", "number,url"),
        "a pull request asked for by number",
    ),
    (
        "2  pr create -t T -b B --base main",
        ("pr", "create", "-t", "T", "-b", "B", "--base", "main"),
        "the CLI's short spellings",
    ),
    (
        "2b pr close 7 -c bye",
        ("pr", "close", "7", "-c", "bye"),
        "a short spelling the tree does not use",
    ),
    (
        "3  pr create --title=T --body=B",
        ("pr", "create", "--title=T", "--body=B"),
        "one token carrying its own value",
    ),
    (
        "4  pr list --head fork-user:branch",
        ("pr", "list", "--head", "fork-user:branch", "--json", "number,url"),
        "a head that already names its fork",
    ),
]

SLUG = ("anchor-inference", "daedalus")
PR = {"number": 8, "html_url": "https://github.com/anchor-inference/daedalus/pull/8", "state": "open"}
THE_ADDED_FILE = "daedalus/host/forge.py"


class Recorded:
    """A transport that answers the paths these shapes ask for and records every request."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        query = request.url.query.decode() if request.url.query else ""
        sent = ""
        if request.content:
            try:
                sent = " body=" + json.dumps(json.loads(request.content), sort_keys=True)[:120]
            except ValueError:
                sent = " body=<not json>"
        self.seen.append(f"{request.method} {request.url.path}" + (f"?{query}" if query else "") + sent)
        path = request.url.path
        if path.endswith("/pulls/8"):
            return httpx.Response(200, json=PR)
        if path.endswith("/pulls/7") or path.endswith("/pulls"):
            if request.method == "GET":
                return httpx.Response(200, json=[])
            if request.method == "POST":
                return httpx.Response(201, json=PR)
            return httpx.Response(200, json={**PR, "number": 7})
        return httpx.Response(200, json={})


def added_file(patch: Path, name: str = THE_ADDED_FILE) -> str:
    """The content a patch adds for ``name``, read out of its diff — a whole new file, so exact."""
    lines = patch.read_text().splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith(f"diff --git a/{name}"))
    except StopIteration:
        raise SystemExit(f"REFUSED: {patch} does not add {name}") from None
    body: list[str] = []
    inside = False
    for line in lines[start:]:
        if line.startswith("diff --git ") and body:
            break
        if line.startswith("@@"):
            inside = True
            continue
        if inside and line.startswith("+"):
            body.append(line[1:])
    if not body:
        raise SystemExit(f"REFUSED: {patch} carries no added lines for {name}")
    return "\n".join(body) + "\n"


def revision_from_patch(clone: Path, patch: Path) -> Path:
    """A tree carrying this revision of the module: the added file from the patch, the rest from the clone."""
    tmp = Path(tempfile.mkdtemp(prefix="forge-revision-"))
    (tmp / "daedalus" / "host").mkdir(parents=True)
    for name in ("__init__.py",):
        (tmp / "daedalus" / name).write_text("")
        (tmp / "daedalus" / "host" / name).write_text("")
    (tmp / THE_ADDED_FILE).write_text(added_file(patch))
    for sibling in ("gitrun.py",):
        source = clone / "daedalus" / "host" / sibling
        if not source.exists():
            raise SystemExit(f"REFUSED: {clone} has no daedalus/host/{sibling} to carry over")
        shutil.copy(source, tmp / "daedalus" / "host" / sibling)
    return tmp


def load(tree: Path):
    sys.path.insert(0, str(tree))
    for name in [n for n in sys.modules if n == "daedalus" or n.startswith("daedalus.")]:
        del sys.modules[name]
    return importlib.import_module("daedalus.host.forge")


async def one(forge, args: tuple[str, ...], recorded: Recorded) -> str:
    """What this revision does with this argument list: the request it made, or its refusal."""
    try:
        sub, opts, positional = forge.parse_gh_args(args)
    except forge.GitError as exc:
        return f"refused by the parser: {exc}"
    lost = [p for p in positional if p.startswith("-")]
    note = f" parser: opts={opts} positional={positional}" if (opts or lost) else ""
    client = forge.RestForge("token", transport=httpx.MockTransport(recorded.handler))
    try:
        answer = await client.run(args, SLUG)
    except forge.GitError as exc:
        return f"refused: {str(exc)[:110]}{note}"
    asked = recorded.seen[-1] if recorded.seen else "no request"
    return f"answered by {asked} -> {answer[:60].replace(chr(10), ' ')}{note}"


def rows(tree: Path, label: str) -> None:
    forge = load(tree)
    path = tree / THE_ADDED_FILE
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "absent"
    print(f"=== {label}  forge.py sha256 {digest}")
    for title, args, why in SHAPES:
        recorded = Recorded()
        result = asyncio.run(one(forge, args, recorded))
        print(f"   {title}\n      ({why})\n      {result}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", action="append", default=[], help="a tree that already carries the module")
    ap.add_argument("--clone", help="a checkout, for the files the patches do not touch")
    ap.add_argument("--patch", action="append", default=[], help="a patch that adds the module")
    args = ap.parse_args()
    if not args.tree and not (args.clone and args.patch):
        print(__doc__)
        return 2
    for tree in args.tree:
        rows(Path(tree), tree)
    for patch in args.patch:
        tree = revision_from_patch(Path(args.clone), Path(patch))
        rows(tree, f"{patch} (over {args.clone})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
