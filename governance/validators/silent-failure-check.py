#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Report syntactic Python failure-masking patterns.

SF001: exception handler containing only inert statements.
SF002: exception handler returning an empty/default value, even after logging.
SF003: environment lookup explicitly falling back to an empty string.

This is not semantic analysis: aliases, assigned fallback values, arbitrary call
results, implicit fallthrough, and conditional reachability are not resolved.
SF003 is a review candidate, not an inference that every environment value is
required. Optional empty defaults need a local, reviewed rationale. Use a
required lookup or validate missing values explicitly instead of hiding them.
Constructor names are matched syntactically, without resolving shadowed builtins.
Returns in nested function/class scopes are not attributed to their handlers.
Positions are one-based; columns follow Python AST UTF-8 byte offsets.
"""

import argparse
import ast
import io
import json
from pathlib import Path
import re
import stat
import sys
import tokenize


MESSAGES = {
    "SF001": "Exception handler contains only inert statements.",
    "SF002": "Exception handler returns an empty/default value, potentially masking failure.",
    "SF003": "Environment lookup has an empty-string fallback; validate required values or document an optional contract.",
}
SUPPRESSION = re.compile(r"#\s*governance: allow-silent (SF00[123]):\s*(\S.*)\Z")
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _inert(statement: ast.stmt) -> bool:
    return isinstance(statement, ast.Pass) or (
        isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
    )


def _default_value(value: ast.expr | None) -> bool:
    if value is None:
        return True
    if isinstance(value, ast.Constant):
        return value.value is None or value.value is False or (
            isinstance(value.value, (str, bytes, int, float, complex))
            and not value.value
        )
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return not value.elts
    if isinstance(value, ast.Dict):
        return not value.keys
    if isinstance(value, ast.Call):
        return (
            isinstance(value.func, ast.Name)
            and value.func.id in {"list", "dict", "tuple", "set", "frozenset", "str", "bytes"}
            and not value.args and not value.keywords
        )
    if isinstance(value, ast.IfExp):
        return _default_value(value.body) or _default_value(value.orelse)
    if isinstance(value, ast.BoolOp):
        for part in value.values[:-1]:
            truth = _literal_truth(part)
            if isinstance(value.op, ast.And):
                if _default_value(part):
                    return True
                if truth is False:
                    return False
            elif truth is True:
                return False
        return _default_value(value.values[-1])
    return False


def _literal_truth(value: ast.expr) -> bool | None:
    if isinstance(value, ast.Constant):
        return bool(value.value)
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        if not value.elts:
            return False
        return True if any(not isinstance(item, ast.Starred) for item in value.elts) else None
    if isinstance(value, ast.Dict):
        if not value.keys:
            return False
        return True if any(key is not None for key in value.keys) else None
    return None


def _always_exits(body: list[ast.stmt]) -> bool:
    """Recognize simple exits; deliberately do not infer loop/test outcomes."""
    for statement in body:
        if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        if isinstance(statement, ast.If) and statement.orelse:
            if _always_exits(statement.body) and _always_exits(statement.orelse):
                return True
        if isinstance(statement, (ast.Try, ast.TryStar)):
            if _always_exits(statement.finalbody):
                return True
    return False


def _handler_returns(body: list[ast.stmt]):
    """Walk handler control-flow blocks, excluding nested lexical scopes."""
    for statement in body:
        if isinstance(statement, SCOPES):
            continue
        if isinstance(statement, ast.Return):
            yield statement
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            # A guaranteed finally exit replaces any earlier return. Nested
            # except handlers are scanned independently by scan_source.
            if not _always_exits(statement.finalbody):
                yield from _handler_returns(statement.body)
                yield from _handler_returns(statement.orelse)
            yield from _handler_returns(statement.finalbody)
        else:
            for _, field in ast.iter_fields(statement):
                if isinstance(field, list):
                    statements = [item for item in field if isinstance(item, ast.stmt)]
                    if statements:
                        yield from _handler_returns(statements)
                    for item in field:
                        if isinstance(item, ast.match_case):
                            yield from _handler_returns(item.body)
        if _always_exits([statement]):
            break


def _effective_returns(result: ast.Return, parents: dict[ast.AST, ast.AST]):
    """Replace a return overridden by a guaranteed finally exit in this scope."""
    child = result
    while child in parents:
        parent = parents[child]
        if isinstance(parent, SCOPES):
            break
        if isinstance(parent, (ast.Try, ast.TryStar)):
            if child not in parent.finalbody and _always_exits(parent.finalbody):
                for replacement in _handler_returns(parent.finalbody):
                    yield from _effective_returns(replacement, parents)
                return
        child = parent
    yield result


def _enclosing_handler(node: ast.AST, parents: dict[ast.AST, ast.AST]):
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.ExceptHandler):
            return node
        if isinstance(node, SCOPES):
            break
    return None


def _suppressions(source: str) -> dict[int, tuple[str, bool, int]]:
    lines = source.splitlines()
    comments = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        match = SUPPRESSION.fullmatch(token.string)
        if match and any(char.isalnum() for char in match.group(2)):
            line, column = token.start
            comments[line] = (match.group(1), not lines[line - 1][:column].strip(), column)
    return comments


def _env_lookup(node):
    if not isinstance(node, ast.Call):
        return False
    return ast.unparse(node.func) in {"os.getenv", "os.environ.get"}


def _empty_string(node):
    return isinstance(node, ast.Constant) and node.value == ""


def _empty_environment_fallback(node):
    if _env_lookup(node):
        return (len(node.args) >= 2 and _empty_string(node.args[1])) or any(
            kw.arg == "default" and _empty_string(kw.value) for kw in node.keywords
        )
    return (
        isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)
        and _empty_string(node.values[-1])
        and any(_env_lookup(value) for value in node.values[:-1])
    )


def _statement(node, parents):
    while not isinstance(node, ast.stmt) and node in parents:
        node = parents[node]
    return node


def _immediately_validated(statement, parents, candidate):
    """Recognize only a following `if not value: ...; raise` in the same block."""
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
    elif isinstance(statement, ast.AnnAssign):
        target = statement.target
    else:
        return False
    if not isinstance(target, ast.Name):
        return False
    if not _empty_environment_fallback(statement.value):
        # Checking a client/result object does not validate credentials passed
        # into its constructor, nor a tuple/list containing an empty value.
        return False
    child = candidate
    while child is not statement.value:
        parent = parents.get(child)
        if not (isinstance(parent, ast.BoolOp) and isinstance(parent.op, ast.Or)
                and child in parent.values
                and all(_env_lookup(value) or _empty_string(value) for value in parent.values)):
            return False
        child = parent
    parent = parents.get(statement)
    if parent is None:
        return False
    for _, block in ast.iter_fields(parent):
        if not isinstance(block, list) or statement not in block:
            continue
        index = block.index(statement) + 1
        if index >= len(block) or not isinstance(block[index], ast.If):
            continue
        guard = block[index]
        if (isinstance(guard.test, ast.UnaryOp) and isinstance(guard.test.op, ast.Not)
                and isinstance(guard.test.operand, ast.Name) and guard.test.operand.id == target.id
                and isinstance(guard.body[-1], ast.Raise)
                and all(isinstance(part, ast.Expr)
                        and not any(isinstance(item, (ast.Yield, ast.YieldFrom)) for item in ast.walk(part))
                        for part in guard.body[:-1])):
            return True
    return False


def scan_source(source: str, path: str = "<memory>") -> list[dict]:
    """Scan one source string. Parse/tokenization errors propagate to callers."""
    tree = ast.parse(source, filename=path)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    comments = _suppressions(source)
    findings = []

    def add(node: ast.AST, rule: str, anchor: ast.AST | None = None, suppressible: bool = True):
        anchor = node if anchor is None else anchor
        same_line = comments.get(anchor.lineno)
        previous = comments.get(anchor.lineno - 1)
        if suppressible and same_line and same_line[0] == rule:
            return
        if suppressible and previous and previous == (rule, True, anchor.col_offset):
            return
        finding = {
            "path": str(path), "line": node.lineno, "column": node.col_offset + 1,
            "rule": rule, "message": MESSAGES[rule],
        }
        if finding not in findings:
            findings.append(finding)

    for node in ast.walk(tree):
        if _empty_environment_fallback(node):
            # One candidate per statement. The rationale belongs to the
            # statement, not to an enclosing exception or function.
            statement = _statement(node, parents)
            if not _immediately_validated(statement, parents, node):
                add(statement, "SF003")
        if isinstance(node, ast.ExceptHandler):
            if all(_inert(statement) for statement in node.body):
                add(node, "SF001")
            for result in _handler_returns(node.body):
                for effective in _effective_returns(result, parents):
                    if _default_value(effective.value):
                        # A finally replacement can lie outside the original
                        # handler. Its rationale must belong to its own actual
                        # enclosing handler, never to the overridden return.
                        anchor = _enclosing_handler(effective, parents)
                        add(effective, "SF002", anchor=anchor, suppressible=anchor is not None)
    return sorted(findings, key=lambda item: (item["path"], item["line"], item["column"], item["rule"]))


def scan_file(path: str | Path) -> list[dict]:
    """Scan an explicit .py/.pyi file, honoring Python encoding declarations.

    Non-Python paths are skipped. Read/decode/parse failures propagate; directories
    are never recursively discovered. A .py directory raises an I/O error.
    """
    file_path = Path(path)
    if file_path.suffix.lower() not in {".py", ".pyi"}:
        return []
    if not stat.S_ISREG(file_path.stat().st_mode):
        raise OSError("Python scan input must be a regular file")
    with tokenize.open(file_path) as stream:
        return scan_source(stream.read(), str(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Explicit Python files; no recursive discovery")
    parser.add_argument("--json", action="store_true", help="Print findings and errors as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Report findings without failing; scan errors still fail")
    args = parser.parse_args(argv)
    findings, errors = [], []
    for path in sorted(set(args.paths)):
        try:
            findings.extend(scan_file(path))
        except (OSError, UnicodeError, SyntaxError, tokenize.TokenError, ValueError) as error:
            # Never print exception text: SyntaxError and decoding errors can
            # contain source snippets or values from the file being scanned.
            errors.append({"path": path, "error": type(error).__name__, "message": "Unable to read or parse Python source."})
    if args.json:
        print(json.dumps({"findings": findings, "errors": errors}, sort_keys=True))
    else:
        for finding in findings:
            print(f"{finding['path']}:{finding['line']}:{finding['column']}: {finding['rule']} {finding['message']}")
        for error in errors:
            print(f"{error['path']}: {error['error']}: {error['message']}", file=sys.stderr)
    if errors:
        return 2
    return 1 if findings and not args.dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
