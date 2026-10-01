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

With --staged (pre-commit) or --base REV (CI), only changed code is checked.
A finding blocks when it is new, or when its own statement or governing handler
changed: a broadened clause, a deleted guard or `raise`, or any edited line.
Untouched findings, including moved ones, stay in the portfolio backlog.
Source is read from Git blobs, never from the working tree.
"""

import argparse
import ast
from collections import Counter
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tokenize


MESSAGES = {
    "SF001": "Exception handler contains only inert statements.",
    "SF002": "Exception handler returns an empty/default value, potentially masking failure.",
    "SF003": "Environment lookup has an empty-string fallback; validate required values or document an optional contract.",
}
SUPPRESSION = re.compile(r"#\s*governance: allow-silent (SF00[123]):\s*(\S.*)\Z")
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
REGULAR = {"100644", "100755"}  # Git modes of regular files; symlinks and submodules are not source
NO_BASELINE = "0" * 40  # Git's null object id: nothing to compare against


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
    return [finding for finding, _, _, _ in _scan_entries(source, path)]


def _scan_entries(source: str, path: str) -> list[tuple[dict, int, int, tuple]]:
    """Findings with the line span that governs them and a position-free identity.

    For SF002 both the span and the identity include the handler whose clause
    and body decide what the return masks, so broadening `except ValueError` to
    `except Exception`, or deleting a guard or `raise` inside it, changes the
    finding even though the return line is untouched. Identities carry no
    positions, so a finding that merely moved keeps its identity.
    """
    tree = ast.parse(source, filename=path)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    comments = _suppressions(source)
    entries = {}

    def add(node: ast.AST, rule: str, anchor: ast.AST | None = None, suppressible: bool = True,
            governs: ast.AST | None = None):
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
        spans = [node] if governs is None else [node, governs]
        start = min(item.lineno for item in spans)
        end = max(item.end_lineno or item.lineno for item in spans)
        handlers = frozenset() if governs is None else frozenset({ast.dump(governs, include_attributes=False)})
        marker = tuple(finding[field] for field in ("path", "line", "column", "rule"))
        if marker in entries:
            # The same return can be reached from several handlers (a finally
            # override); every one of them governs it.
            old, old_start, old_end, (_, dump, old_handlers) = entries[marker]
            key = (rule, dump, old_handlers | handlers)
            entries[marker] = (old, min(start, old_start), max(end, old_end), key)
        else:
            entries[marker] = (finding, start, end, (rule, ast.dump(node, include_attributes=False), handlers))

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
                        add(effective, "SF002", anchor=anchor, suppressible=anchor is not None, governs=node)
    return [entries[marker] for marker in sorted(entries)]


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


def changed_findings(before: str, after: str, path: str) -> list[dict]:
    """Findings in `after` that are new or whose governing lines changed since `before`.

    A finding blocks when its identity (rule, flagged node and governing handler,
    without positions) is new, or when the exact text of its span appears nowhere
    in `before`. Moving untouched code, in either direction, changes neither.
    An unparseable `before` gives no baseline, so every finding in `after` counts.
    Parse errors in `after` propagate to the caller.
    """
    try:
        old = Counter(key for _, _, _, key in _scan_entries(before, path))
    except (SyntaxError, tokenize.TokenError, ValueError, RecursionError):
        before, old = "", Counter()
    previous = "\n" + "\n".join(before.splitlines()) + "\n"
    lines = after.splitlines()
    findings = []
    for finding, first, last, key in _scan_entries(after, path):
        existed = old[key] > 0
        old[key] -= 1
        block = "\n" + "\n".join(lines[first - 1:last]) + "\n"
        if not existed or block not in previous:
            findings.append(finding)
    return findings


def _git(*args) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True, timeout=20).stdout


def _blob_source(oid: str) -> str:
    blob = _git("cat-file", "blob", oid)
    encoding, _ = tokenize.detect_encoding(io.BytesIO(blob).readline)
    return blob.decode(encoding)


def _python_source(path: str, mode: str) -> bool:
    return path.lower().endswith((".py", ".pyi")) and mode in REGULAR


def _changed_python(base: str | None):
    """Yield (path, old_oid, new_oid) for changed regular Python blobs.

    Symlinks and submodules carry no Python source of their own and are skipped.
    Only an old side that was itself a regular Python file is a baseline: a
    `.txt` renamed to `.py`, or a symlink replaced by a file, is new coverage.
    """
    args = ["diff", "--raw", "-z", "--no-abbrev", "--no-ext-diff", "--no-textconv",
            "--find-renames", "--diff-filter=ACMRT"]
    if base:
        sha = _git("rev-parse", "--verify", "--end-of-options", base + "^{commit}").decode().strip()
        args += [sha, "HEAD", "--"]
    else:
        args += ["--cached", "--"]
    fields = _git(*args).split(b"\0")
    i = 0
    while i < len(fields) and fields[i]:
        old_mode, new_mode, old_oid, new_oid, status = fields[i].decode("ascii").lstrip(":").split()
        old_path = path = fields[i + 1].decode("utf-8", "surrogateescape")
        i += 2
        if status[0] in "RC":
            path = fields[i].decode("utf-8", "surrogateescape")
            i += 1
        if _python_source(path, new_mode):
            yield path, old_oid if _python_source(old_path, old_mode) else NO_BASELINE, new_oid


def _merge_heads() -> list[str]:
    """Other parents of a staged merge commit; empty outside a merge."""
    merge_head = Path(_git("rev-parse", "--git-path", "MERGE_HEAD").decode().strip())
    try:
        return merge_head.read_text(encoding="ascii").split()
    except FileNotFoundError:  # governance: allow-silent SF002: an absent MERGE_HEAD means the commit is not a merge
        return []


def _old_source(oid: str) -> str:
    try:
        return "" if set(oid) == {"0"} else _blob_source(oid)
    except (UnicodeError, SyntaxError, LookupError):  # governance: allow-silent SF002: no baseline makes every finding count, which is stricter
        return ""


def _tree_oid(commit: str, path: str) -> str:
    """Blob id of regular file `path` in `commit`, or NO_BASELINE when it is not one."""
    entry = _git("ls-tree", "-z", "--full-tree", commit, "--", path).split(b"\0")[0]
    parts = entry.split(None, 3)
    if len(parts) == 4 and parts[1] == b"blob" and parts[0].decode("ascii") in REGULAR:
        return parts[2].decode("ascii")
    return NO_BASELINE


def _repo_paths(paths: list[str]) -> set[str]:
    """Caller paths in the repository-root-relative form Git reports.

    `./m.py`, `pkg/../m.py`, a path relative to a subdirectory and an absolute
    path all name the same staged file. Only the parent directory is resolved,
    so a symlinked file keeps its own name.
    """
    top = Path(os.path.realpath(_git("rev-parse", "--show-toplevel").decode().strip()))
    names = set()
    for raw in paths:
        absolute = Path(os.path.abspath(raw))
        resolved = Path(os.path.realpath(absolute.parent)) / absolute.name
        if resolved.is_relative_to(top):
            names.add(resolved.relative_to(top).as_posix())
    return names


def _scan_changes(base: str | None, only: set[str] | None) -> tuple[list[dict], list[dict]]:
    """Changed-line findings for the staged index (base None) or base..HEAD.

    For a staged merge, a finding blocks only when it is new or edited relative
    to every parent, so code the merge brings in from the other side does not
    count against this commit.
    """
    findings, errors = [], []
    others = [] if base else _merge_heads()
    for path, old_oid, new_oid in _changed_python(base):
        if only is not None and path not in only:
            continue
        try:
            after = _blob_source(new_oid)
            found = changed_findings(_old_source(old_oid), after, path)
            for other in others:
                if not found:
                    break
                relative = changed_findings(_old_source(_tree_oid(other, path)), after, path)
                found = [finding for finding in found if finding in relative]
            findings.extend(found)
        except (UnicodeError, SyntaxError, LookupError, tokenize.TokenError, ValueError, RecursionError) as error:
            errors.append({"path": path, "error": type(error).__name__, "message": "Unable to read or parse Python source."})
    return findings, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="Explicit Python files; no recursive discovery. "
                        "With --staged/--base, optional filter on the changed paths")
    parser.add_argument("--json", action="store_true", help="Print findings and errors as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Report findings without failing; scan errors still fail")
    changed = parser.add_mutually_exclusive_group()
    changed.add_argument("--staged", action="store_true", help="Check only changed lines of staged Python files (pre-commit)")
    changed.add_argument("--base", help="Check only lines changed between this commit and HEAD (CI)")
    args = parser.parse_args(argv)
    if args.staged or args.base:
        try:
            findings, errors = _scan_changes(args.base, _repo_paths(args.paths) if args.paths else None)
        except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as error:
            print(f"Unable to read changed Git source ({type(error).__name__}).", file=sys.stderr)
            return 2
        return _report(findings, errors, args)
    if not args.paths:
        parser.error("explicit paths are required unless --staged or --base is given")
    findings, errors = [], []
    for path in sorted(set(args.paths)):
        try:
            findings.extend(scan_file(path))
        except (OSError, UnicodeError, SyntaxError, tokenize.TokenError, ValueError) as error:
            # Never print exception text: SyntaxError and decoding errors can
            # contain source snippets or values from the file being scanned.
            errors.append({"path": path, "error": type(error).__name__, "message": "Unable to read or parse Python source."})
    return _report(findings, errors, args)


def _report(findings: list[dict], errors: list[dict], args) -> int:
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
