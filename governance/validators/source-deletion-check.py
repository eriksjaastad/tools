#!/usr/bin/env python3
"""Check changed Python deletion sites in Git's index (or HEAD vs --base).

This is bounded static analysis, not a Python sandbox. It recognizes imported
stdlib deletion aliases and Path-style unlink/rmdir calls. Temporary cleanup
requires a local tempfile origin; names and literal directory paths prove
nothing. Dynamic dispatch, eval, and arbitrary library implementations remain
review responsibilities. No source is executed and no worktree bytes are read.
"""
import argparse
import ast
from collections import Counter
import difflib
import io
import re
import subprocess
import sys
import tokenize


UNKNOWN = "?"
NONE = "none"
FILE = "temp-file"
DIR = "temp-dir"
CHILD = "temp-child"
FILE_OBJECT = "temp-file-object"
DIR_OBJECT = "temp-dir-object"
TEMP = {FILE, DIR, CHILD, FILE_OBJECT, DIR_OBJECT}
DELETE = {"os.unlink", "os.remove", "os.rmdir", "os.removedirs", "shutil.rmtree"}
EXCEPTION = re.compile(r"#\s*governance: allow-delete DS001:\s*(\S.*)")


def git(*args, data=None):
    return subprocess.run(["git", *args], input=data, capture_output=True,
                          check=True, timeout=20).stdout


def symbol(node, env):
    if isinstance(node, ast.Name):
        return env.get(node.id, UNKNOWN)
    if isinstance(node, ast.Attribute):
        base = symbol(node.value, env)
        if base.startswith("import:"):
            return base + "." + node.attr
    return UNKNOWN


def literal_child(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value not in {"", ".", ".."}
            and "/" not in node.value and "\\" not in node.value)


def value(node, env):
    if node is None or isinstance(node, ast.Constant) and node.value is None:
        return NONE
    known = symbol(node, env)
    if known != UNKNOWN:
        return known
    if isinstance(node, ast.Attribute) and node.attr == "name":
        return {FILE_OBJECT: FILE, DIR_OBJECT: DIR}.get(value(node.value, env), UNKNOWN)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return CHILD if value(node.left, env) == DIR and literal_child(node.right) else UNKNOWN
    if isinstance(node, ast.Call):
        name = symbol(node.func, env)
        origins = {"import:tempfile.mkdtemp": DIR, "import:tempfile.NamedTemporaryFile": FILE_OBJECT,
                   "import:tempfile.TemporaryDirectory": DIR_OBJECT}
        if name in origins:
            return origins[name]
        if name == "import:pathlib.Path" and len(node.args) == 1 and not node.keywords:
            return value(node.args[0], env)
        if isinstance(node.func, ast.Name) and node.func.id == "str" and node.func.id not in env and len(node.args) == 1:
            return value(node.args[0], env)
        if name == "import:os.path.join" and len(node.args) == 2 and not node.keywords:
            if value(node.args[0], env) == DIR and all(literal_child(arg) for arg in node.args[1:]):
                return CHILD
        if isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath":
            if value(node.func.value, env) == DIR and len(node.args) == 1 and not node.keywords and literal_child(node.args[0]):
                return CHILD
    return UNKNOWN


def assign(target, binding, env):
    if isinstance(target, ast.Name):
        env[target.id] = binding
    elif isinstance(target, (ast.Tuple, ast.List)):
        for child in target.elts:
            assign(child, UNKNOWN, env)
    elif isinstance(target, (ast.Attribute, ast.Subscript)):
        assign(target.value, UNKNOWN, env)


def merge(*branches):
    result = {}
    for name in set().union(*(branch.keys() for branch in branches)):
        values = {branch.get(name, UNKNOWN) for branch in branches}
        concrete = values - {NONE}
        result[name] = next(iter(concrete)) if len(concrete) == 1 else NONE if not concrete else UNKNOWN
    return result


def written_names(node):
    """Conservative invalidation, including writes through attributes."""
    names = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.Name, ast.Attribute, ast.Subscript)) and isinstance(child.ctx, (ast.Store, ast.Del)):
            while isinstance(child, (ast.Attribute, ast.Subscript)):
                child = child.value
            if isinstance(child, ast.Name):
                names.add(child.id)
        elif isinstance(child, (ast.MatchAs, ast.MatchStar, ast.ExceptHandler)) and child.name:
            names.add(child.name)
        elif isinstance(child, ast.MatchMapping) and child.rest:
            names.add(child.rest)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(child.name)
    return names


class Analyzer:
    def __init__(self, source):
        self.findings = []
        self.deletions = Counter()
        self.comments = {}
        self.unstable = written_names(ast.parse(source))
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and EXCEPTION.fullmatch(token.string):
                self.comments[token.start[0]] = token.start[1]

    def expression(self, node, env, scope):
        if node is None:
            return
        if isinstance(node, ast.Lambda):
            # Captured paths may be rebound before the lambda executes.
            local = {key: val for key, val in env.items() if val.startswith("import:") and key not in self.unstable}
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                local[arg.arg] = UNKNOWN
            self.expression(node.body, local, scope + ("lambda",))
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            local = dict(env)
            if isinstance(node, ast.GeneratorExp):
                local = {key: val for key, val in env.items() if val.startswith("import:") and key not in self.unstable}
            for generator in node.generators:
                self.expression(generator.iter, local, scope)
                assign(generator.target, UNKNOWN, local)
                for condition in generator.ifs:
                    self.expression(condition, local, scope)
            for part in (node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,):
                self.expression(part, local, scope)
            for child in ast.walk(node):
                if isinstance(child, ast.NamedExpr):
                    assign(child.target, UNKNOWN, env)
            return
        if isinstance(node, ast.NamedExpr):
            self.expression(node.value, env, scope)
            assign(node.target, value(node.value, env), env)
            return
        for child in ast.iter_child_nodes(node):
            self.expression(child, env, scope)
        if not isinstance(node, ast.Call):
            return
        name = symbol(node.func, env).removeprefix("import:")
        path = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg in {"path", "name"}), None)
        deleting = name in DELETE
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"unlink", "rmdir", "rmtree"}:
            deleting = True
            if name not in DELETE:
                path = node.func.value
        if deleting:
            self.deletions[node.end_lineno] += 1
        if deleting and (value(path, env) not in {FILE, DIR, CHILD} or name == "os.removedirs"):
            comment_col = self.comments.get(node.end_lineno)
            # A same-line rationale covers exactly one deletion call. If a
            # line contains two calls, neither may borrow the other's reason.
            exempt = comment_col is not None and comment_col >= node.end_col_offset
            key = (scope, ast.dump(node, include_attributes=False))
            self.findings.append((node.lineno, node.end_lineno, key, exempt))

    def block(self, statements, env, scope=(), observed=None):
        env = dict(env)
        for stmt in statements:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for alias in stmt.names:
                    if isinstance(stmt, ast.Import):
                        env[alias.asname or alias.name.split(".")[0]] = "import:" + (alias.name if alias.asname else alias.name.split(".")[0])
                    else:
                        env[alias.asname or alias.name] = "import:" + (stmt.module or "") + "." + alias.name
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Do not infer captured path lifetime across function calls.
                local = {key: val for key, val in env.items() if val.startswith("import:") and key not in self.unstable}
                for decorator in stmt.decorator_list:
                    self.expression(decorator, env, scope)
                if hasattr(stmt, "args"):
                    for default in (*stmt.args.defaults, *stmt.args.kw_defaults):
                        self.expression(default, env, scope)
                    for arg in (*stmt.args.posonlyargs, *stmt.args.args, *stmt.args.kwonlyargs):
                        local[arg.arg] = UNKNOWN
                    for arg in (stmt.args.vararg, stmt.args.kwarg):
                        if arg:
                            local[arg.arg] = UNKNOWN
                else:
                    for base in (*stmt.bases, *stmt.keywords):
                        self.expression(base, env, scope)
                self.block(stmt.body, local, scope + (stmt.name,))
                env[stmt.name] = UNKNOWN
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                self.expression(stmt.value, env, scope)
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for target in targets:
                    if (isinstance(target, (ast.Tuple, ast.List)) and len(target.elts) == 2
                            and isinstance(stmt.value, ast.Call) and symbol(stmt.value.func, env) == "import:tempfile.mkstemp"):
                        assign(target.elts[0], UNKNOWN, env)
                        assign(target.elts[1], FILE, env)
                    else:
                        assign(target, value(stmt.value, env), env)
            elif isinstance(stmt, ast.If):
                self.expression(stmt.test, env, scope)
                context = scope + ("if:" + ast.dump(stmt.test, include_attributes=False),)
                env = merge(self.block(stmt.body, env, context, observed), self.block(stmt.orelse, env, context, observed))
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                local = dict(env)
                for item in stmt.items:
                    self.expression(item.context_expr, local, scope)
                    binding = value(item.context_expr, local)
                    if item.optional_vars:
                        assign(item.optional_vars, DIR if binding == DIR_OBJECT else binding, local)
                env = self.block(stmt.body, local, scope, observed)
            elif isinstance(stmt, (ast.Try, ast.TryStar)):
                states = [dict(env)]
                body = self.block(stmt.body, env, scope, states)
                branches = [self.block(stmt.orelse, body, scope, states)]
                for handler in stmt.handlers:
                    local = merge(*states)
                    if handler.name:
                        local[handler.name] = UNKNOWN
                    branches.append(self.block(handler.body, local, scope, states))
                env = self.block(stmt.finalbody, merge(*states, *branches), scope, observed)
                if observed is not None:
                    observed.extend(states)
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                self.expression(stmt.iter if hasattr(stmt, "iter") else stmt.test, env, scope)
                local = dict(env)
                # A later iteration may see any binding written in the body.
                for name in written_names(stmt):
                    local[name] = UNKNOWN
                if hasattr(stmt, "target"):
                    assign(stmt.target, UNKNOWN, local)
                body = self.block(stmt.body, local, scope, observed)
                env = merge(env, self.block(stmt.orelse, body, scope, observed))
            elif isinstance(stmt, ast.Match):
                self.expression(stmt.subject, env, scope)
                branches = [dict(env)]
                for case in stmt.cases:
                    local = dict(env)
                    for name in written_names(case.pattern):
                        local[name] = UNKNOWN
                    self.expression(case.guard, local, scope)
                    branches.append(self.block(case.body, local, scope, observed))
                env = merge(*branches)
            else:
                self.expression(stmt, env, scope)
                if isinstance(stmt, ast.AugAssign):
                    assign(stmt.target, UNKNOWN, env)
                if isinstance(stmt, ast.Delete):
                    for target in stmt.targets:
                        assign(target, UNKNOWN, env)
            if observed is not None:
                observed.append(dict(env))
        return env


def unsafe_sites(source):
    analyzer = Analyzer(source)
    analyzer.block(ast.parse(source).body, {})
    return [(start, end, key) for start, end, key, exempt in analyzer.findings
            if not exempt or analyzer.deletions[end] > 1]


def source(blob):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(blob).readline)
    return blob.decode(encoding)


def changes(base):
    args = ["diff", "--raw", "-z", "--no-abbrev", "--no-ext-diff", "--no-textconv",
            "--find-renames", "--diff-filter=ACMRT"]
    if base:
        sha = git("rev-parse", "--verify", "--end-of-options", base + "^{commit}").decode().strip()
        args += [sha, "HEAD", "--"]
    else:
        args += ["--cached", "--"]
    fields = git(*args).split(b"\0")
    i = 0
    while i < len(fields) and fields[i]:
        header = fields[i].decode("ascii").split()
        old_mode, new_mode, old_oid, new_oid, status = header
        old_path = fields[i + 1].decode("utf-8", "surrogateescape")
        i += 2
        path = old_path
        if status[0] in "RC":
            path = fields[i].decode("utf-8", "surrogateescape")
            i += 1
        yield path, new_mode, old_oid, new_oid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--base", help="Compare committed HEAD with this commit (CI); default is staged index")
    args = parser.parse_args(argv)
    findings = []
    try:
        for path, mode, old_oid, new_oid in changes(args.base):
            if not path.endswith((".py", ".pyi")) or args.paths and path not in args.paths:
                continue
            if mode not in {"100644", "100755"}:
                raise ValueError("changed Python source is not a regular Git blob")
            before = "" if set(old_oid) == {"0"} else source(git("cat-file", "blob", old_oid))
            after = source(git("cat-file", "blob", new_oid))
            old = Counter(key for _, _, key in unsafe_sites(before))
            edited = set()
            for tag, _, _, start, end in difflib.SequenceMatcher(None, before.splitlines(), after.splitlines(), autojunk=False).get_opcodes():
                if tag in {"insert", "replace"}:
                    edited.update(range(start + 1, end + 1))
            for start, end, key in unsafe_sites(after):
                existed = old[key] > 0
                old[key] -= 1
                if not existed or any(line in edited for line in range(start, end + 1)):
                    findings.append((path, start))
    except (OSError, UnicodeError, SyntaxError, tokenize.TokenError, ValueError,
            subprocess.SubprocessError, RecursionError) as exc:
        print(f"DS000: unable to read or parse changed Git source ({type(exc).__name__}).", file=sys.stderr)
        return 2
    for path, line in findings:
        print(f"{path}:{line}: DS001 permanent deletion needs recoverable removal, verified temporary origin, or a local rationale.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
