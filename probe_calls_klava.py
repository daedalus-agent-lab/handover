"""Read a probe's calls, or refuse to."""
IMPLEMENTED = True

import ast


def calls_of(source: str) -> tuple[bool, tuple[str, ...]]:
    """(read, names): read is True only when the source was read as a probe."""
    # Step 1: expression reading first
    try:
        tree = ast.parse(source.strip(), mode="eval")
        body = tree.body
        if isinstance(body, ast.Call) and isinstance(body.func, ast.Name):
            return (True, (body.func.id,))
        return (False, ())
    except SyntaxError:
        pass

    # Step 2: module reading
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return (False, ())

    stmts = tree.body

    # Filter out leading docstring and all import/from statements
    filtered = []
    for i, stmt in enumerate(stmts):
        if (
            i == 0
            and not filtered
            and isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue  # leading module docstring
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        filtered.append(stmt)

    # Must be exactly one FunctionDef
    if len(filtered) != 1 or not isinstance(filtered[0], ast.FunctionDef):
        return (False, ())

    func_def = filtered[0]
    body = func_def.body

    # Filter out leading docstring from function body
    func_stmts = []
    for i, stmt in enumerate(body):
        if (
            i == 0
            and not func_stmts
            and isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            continue  # leading function docstring
        func_stmts.append(stmt)

    # Must be exactly one Return whose value is a Call(func=Name)
    if len(func_stmts) != 1 or not isinstance(func_stmts[0], ast.Return):
        return (False, ())

    value = func_stmts[0].value
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
        return (False, ())

    return (True, (value.func.id,))
