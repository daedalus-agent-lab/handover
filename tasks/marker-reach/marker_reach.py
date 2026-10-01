#!/usr/bin/env python3
"""Which names a file binds, and which of a set of markers each of them reaches.

`fragments.py` asks whether a relation in a file has its two operands reaching two
different readers, and it cannot read that off the line the relation stands on: a name is
what was assigned to it. One line of indirection is where a comparer hides -- `ids =
ids_in(THE_FILE)` followed by `ids <= printed` never names the reader file on the line the
relation stands on. That indirection, followed to a fixed point, is this file's whole
question:

    reach_of(source, markers) -> (read, answer)

  * standard library only, no network, writes nothing, and it **never raises**: a source it
    cannot parse, an argument of the wrong shape, anything else -- `(False, {})`;
  * `source` is one file's text; `markers` maps a marker to a tuple of tokens;
  * on success `answer` is readable with `ast.literal_eval`:

        {"scopes": [{"name": "<module>"| the def's name,
                     "line": 0 | the line the def stands on,
                     "bindings": {name: [markers, sorted]}}],
         "unread": [{"line": int, "node": str, "why": str}]}

    The module is always `scopes[0]`; the rest are its functions, outermost first, each
    function's own nested functions after it, and siblings in the order they stand in the
    file.

**The rules. Each of them is a test, and the tests hold you to the letter of them.**

1. A value reaches a marker when one of that marker's tokens appears in it as an identifier
   (`Name.id`), as an attribute name (`Attribute.attr`), as a keyword argument's name, or as
   the whole text of a string constant. A token inside a longer string is not a token:
   `"parts_of_a_reading"` reaches the token `parts_of_a_reading`, `"xparts_of_a_reading"`.
   does not.
2. A value also reaches every marker reached by a `Name` in it, following that scope's
   assignments to a fixed point -- so an assignment written *after* the use counts, and a
   chain of any length counts.
3. A name bound in a scope reads **only this scope's** assignments. The enclosing scope's
   name is followed when, and only when, this scope binds that name nowhere: a name rebound
   inside a function shadows the outer one instead of adding to it.
4. What binds a name: `x = value`, `x: T = value`, `for x in value`, and **each** name in a
   tuple or list target binds to that whole value expression (`a, b = one_two()` gives both
   names whatever `one_two()` reaches).
5. What does not bind, and is reported in `unread` -- once per statement, with the line it
   stands on and its text shortened to 60 characters and its whitespace folded:
   `with ... as x` (only when it has an `as`), `x += value`, `import` and
   `from ... import`, `global` and `nonlocal`, a `Lambda` body, and a comprehension's own
   target. An `x: T` with no value binds nothing and is **not** unread: it declares.
6. A scope is the module and the body of every `FunctionDef` and `AsyncFunctionDef`. A
   nested function's body belongs to that function, not to the one holding it; the names the
   enclosing scope binds are visible inside it; the names it binds are not visible outside;
   and a def's parameters, defaults and decorators are read by neither (they are not in
   either scope's nodes).
7. A `Lambda`'s body is not descended into at all, so a binding inside one is invisible.
8. Markers are compared by exact token text. A marker whose token tuple is empty is reached
   by nothing. A name whose markers are empty appears in `bindings` only if the scope binds
   it -- a name the scope never binds is absent.
9. `read` is `False` and the answer is `{}` when: `source` is not a string, `markers` is not
   a mapping, a marker name is not a string, a token tuple is not a tuple, or any token is
   not a string -- and when the source does not parse.

    python3 marker_reach.py <file> [<file> ...]

reads a file or three and prints each scope's lines for a human; it is not the answer the
tests hold you to.
"""

IMPLEMENTED = True

import ast
import sys
from collections.abc import Mapping

__all__ = ["reach_of"]

_MARKERS = {"the left reader": ("fragments",), "the right reader": ("parts_of_a_reading",)}


def _value_reads(node, local, outer, markers):
    """`(markers the value reaches, identifiers it names)` for one expression.

    A `Lambda` in the value is part of it, but its body is not read (rule 6), so the walk
    stops at one instead of descending into it.
    """
    reached, names = set(), []
    stack = [node]
    while stack:
        inner = stack.pop()
        if isinstance(inner, ast.Name):
            names.append(inner.id)
            reached |= _tokens_matching(inner.id, markers)
        elif isinstance(inner, ast.Attribute):
            reached |= _tokens_matching(inner.attr, markers)
        elif isinstance(inner, ast.keyword) and inner.arg:
            reached |= _tokens_matching(inner.arg, markers)
        elif isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            reached |= _tokens_matching(inner.value, markers)
        if isinstance(inner, ast.Lambda):
            continue
        stack.extend(ast.iter_child_nodes(inner))
    return reached, names


def _tokens_matching(token, markers):
    """The markers one exact token reaches."""
    return {marker for marker, tokens in markers.items() if token in tokens}


def _bound_names(target):
    """The names one assignment target binds, in the order they are written."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for element in target.elts:
            out.extend(_bound_names(element))
        return out
    return []


def _assignments(nodes):
    """`(targets, value)` for every statement of one scope that binds a name."""
    out = []
    for node in nodes:
        if isinstance(node, ast.Assign):
            out.append((node.targets, node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            out.append(([node.target], node.value))
        elif isinstance(node, ast.For):
            out.append(([node.target], node.iter))
    return out


def _scope_nodes(body):
    """One scope's nodes: another function's or a lambda's body is a scope of its own.

    The `def` and `lambda` nodes themselves stay in this scope's list -- a nested function
    is how this scope learns what to read next, and a lambda is worth reporting as unread
    -- but nothing inside the body of either is descended into.
    """
    out = []
    stack = [(_Body(body), None)]
    while stack:
        node, walker = stack[-1]
        if walker is None:
            walker = ast.iter_child_nodes(node)
            stack[-1] = (node, walker)
        child = next(walker, None)
        if child is None:
            stack.pop()
            continue
        out.append(child)
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.append((child, None))
    return out

class _Body(ast.AST):
    """A node whose children are a list of statements, so the walk can start at a body."""

    _fields = ("body",)

    def __init__(self, body):
        self.body = body


def _unread_in(nodes):
    """The statements of one scope that name a binding without being one -- once per statement."""
    found = []
    for node in nodes:
        why = None
        if isinstance(node, ast.With) and any(i.optional_vars is not None for i in node.items):
            why = "with ... as x does not bind"
        elif isinstance(node, ast.AugAssign):
            why = "x += value does not bind"
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            why = "import does not bind here"
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            why = "global and nonlocal do not bind here"
        elif isinstance(node, ast.Lambda):
            why = "a Lambda body is not read"
        elif isinstance(node, ast.comprehension):
            why = "a comprehension's own target does not bind"
        if why is not None:
            entry = {"line": _line_of(node), "node": _text(node), "why": why}
            if entry in found:
                continue
            if (why.startswith("a comprehension") and
                    any(e["line"] == entry["line"] and e["why"] == why for e in found)):
                continue
            found.append(entry)
    return found


def _line_of(node):
    """The line a node stands on; a `comprehension` has none of its own, so its element's."""
    line = getattr(node, "lineno", 0) or 0
    if line:
        return line
    for part in (getattr(node, "elt", None), getattr(node, "target", None),
                 getattr(node, "iter", None)):
        line = getattr(part, "lineno", 0) or 0
        if line:
            return line
    return 0


def _reach_in(nodes, outer, markers):
    """`{name: markers}` for one scope, to a fixed point over the assignments it holds.

    A name this scope binds anywhere reads this scope's assignments only (rule 3), so the
    names it binds are collected first -- including the ones bound to nothing, which is
    how a rebound name shadows the enclosing scope's instead of adding to it.
    """
    reaches = {}
    assignments = _assignments(nodes)
    bound = set()
    for targets, _ in assignments:
        for target in targets:
            bound.update(_bound_names(target))
    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            reached, names = _value_reads(value, reaches, outer, markers)
            for name in names:
                if name in bound:
                    reached |= reaches.get(name, set())
                else:
                    reached |= outer.get(name, set())
            for target in targets:
                for name in _bound_names(target):
                    if not reached <= reaches.get(name, set()):
                        reaches[name] = reaches.get(name, set()) | reached
                        changed = True
    return {name: reaches.get(name, set()) for name in sorted(bound)}


def _scope_readings(body, outer, markers, unread):
    """`(this scope's bindings, its nested functions in source order)`."""
    nodes = _scope_nodes(body)
    unread.extend(_unread_in(nodes))
    reaches = _reach_in(nodes, outer, markers)
    nested = [node for node in nodes
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return reaches, nested


def _valid(source, markers):
    if not isinstance(source, str) or not isinstance(markers, Mapping):
        return False
    for marker, tokens in markers.items():
        if not isinstance(marker, str) or not isinstance(tokens, tuple):
            return False
        if not all(isinstance(token, str) for token in tokens):
            return False
    return True


def reach_of(source, markers):
    """`(read, answer)`: which markers each name a scope binds reaches. Never raises."""
    try:
        if not _valid(source, markers):
            return False, {}
        tree = ast.parse(source)
        unread = []
        reaches, nested = _scope_readings(tree.body, {}, markers, unread)
        scopes = [{"name": "<module>", "line": 0,
                   "bindings": {k: sorted(v) for k, v in sorted(reaches.items())}}]
        queue = [(node, dict(reaches)) for node in nested]
        while queue:
            node, outer = queue.pop(0)
            reaches, nested = _scope_readings(node.body, outer, markers, unread)
            scopes.append({"name": node.name, "line": node.lineno,
                           "bindings": {k: sorted(v) for k, v in sorted(reaches.items())}})
            for child in nested:
                queue.append((child, dict(reaches)))
        return True, {"scopes": scopes,
                      "unread": sorted(unread, key=lambda i: (i["line"], i["why"], i["node"]))}
    except Exception:
        return False, {}


def _text(node):
    try:
        text = ast.unparse(node)
    except Exception:
        return ""
    return " ".join(text.split())[:60]


def main(argv):
    if not argv:
        print("usage: marker_reach.py <file> [<file> ...]")
        return 2
    for path in argv:
        with open(path, encoding="utf-8", errors="replace") as handle:
            source = handle.read()
        read, answer = reach_of(source, _MARKERS)
        print("%s: read=%s" % (path, read))
        if not read:
            continue
        for scope in answer["scopes"]:
            print("  scope %s (line %d)" % (scope["name"], scope["line"]))
            for name, values in scope["bindings"].items():
                print("      %-28s %s" % (name, ", ".join(values)))
        for item in answer["unread"]:
            print("  unread %d: %s -- %s" % (item["line"], item["node"], item["why"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
