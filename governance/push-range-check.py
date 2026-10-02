#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Pre-push governance backstop: check every commit a push would publish (#7841).

The pre-commit gate (governance-check.sh) runs for `git commit` and `git merge`
only. Commits made by cherry-pick, revert, am and rebase replays never pass
through it, and `git commit --no-verify` skips it on purpose. This script runs
the same validators over each commit a push is about to publish, so those
commits are checked before they leave the machine.

Input is Git's pre-push protocol on stdin, one line per ref:
`<local ref> <local sha> <remote ref> <remote sha>`. Positional arguments
(remote name and URL) are accepted and ignored.

Which commits are checked: everything reachable from the pushed tips that is
not already on a remote, i.e. `git rev-list <tips> --not --remotes <old remote
tips>`. A new branch (remote sha all zeros) has no old tip, so its base is
whatever any remote-tracking ref already contains. A branch deletion, and a
push whose commits are all on a remote already, check nothing. A repository
whose history was never pushed anywhere checks every commit on the first push;
`git push --no-verify` is the explicit way past that, and it skips the other
pre-push checks too.

How each commit is judged: against its parents, as pre-commit would have
judged it. The whole-file validators (secrets, absolute paths, API wrapper)
read the committed blobs of the files the commit added or changed, written to a
temporary directory under their repository-relative names (paths that would
collide on a case-insensitive filesystem go to separate directories). Symlinks and
submodules carry no file content in the commit and are skipped. The
changed-code validators (silent failure, source deletion) read Git directly
through their `--commit` mode. A merge is judged only on what it introduces:
files and findings that differ from every parent. Its parents are judged as
commits of their own, here if unpublished, or already on a remote.

Exit 0 when every commit passes, 1 when any validator reports findings or
fails to run.
"""
import argparse
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import unicodedata

VALIDATORS_DIR = Path(__file__).resolve().parent / "validators"
FILE_VALIDATORS = ("secrets-scanner.py", "absolute-path-check.py", "api-wrapper-check.py")
COMMIT_VALIDATORS = ("silent-failure-check.py", "source-deletion-check.py")
REGULAR = {"100644", "100755"}
HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
GIT_TIMEOUT = 60
VALIDATOR_TIMEOUT = 300


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True,
                          timeout=GIT_TIMEOUT).stdout


def is_zero(sha: str) -> bool:
    return set(sha) == {"0"}


def commit_of(sha: str) -> str | None:
    """The commit a pushed object names, or None for a tag of a tree or blob.

    An object that does not exist is an error, never a skip.
    """
    if not HEX.fullmatch(sha):
        raise ValueError(f"pre-push object name is not a hex SHA: {sha!r}")
    git("cat-file", "-e", sha)
    peeled = subprocess.run(["git", "rev-parse", "--verify", "--quiet", sha + "^{commit}"],
                            capture_output=True, timeout=GIT_TIMEOUT)
    if peeled.returncode not in (0, 1):
        raise subprocess.CalledProcessError(peeled.returncode, peeled.args, peeled.stdout, peeled.stderr)
    return peeled.stdout.decode().strip() or None


def known_locally(sha: str) -> bool:
    if not HEX.fullmatch(sha):
        raise ValueError(f"pre-push object name is not a hex SHA: {sha!r}")
    # `rev-parse --verify --quiet` exits 1 only when the name does not resolve;
    # any other status is a broken repository, not an absent tip, and raises.
    result = subprocess.run(["git", "rev-parse", "--verify", "--quiet", sha + "^{commit}"],
                            capture_output=True, timeout=GIT_TIMEOUT)
    if result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result.returncode == 0


def pushed_commits(lines: list[str]) -> list[str]:
    """Commits the push publishes, parents before children."""
    tips, published = [], []
    for line in lines:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"unexpected pre-push input line: {line!r}")
        _, local_sha, _, remote_sha = fields
        if is_zero(local_sha):
            continue  # a deletion publishes nothing
        commit = commit_of(local_sha)
        if commit is None:
            continue  # a tag of a tree or blob has no commits to check
        tips.append(commit)
        # The old remote tip is excluded when this clone has it. When it does
        # not (someone else pushed), Git rejects a non-fast-forward anyway, and
        # --remotes still excludes everything already fetched.
        if not is_zero(remote_sha) and known_locally(remote_sha):
            published.append(remote_sha)
    if not tips:
        return []
    out = git("rev-list", "--topo-order", "--reverse", *tips, "--not", "--remotes", *published)
    return out.decode().split()


def parents_of(sha: str) -> list[str]:
    parents = git("rev-list", "--parents", "-n", "1", sha).decode().split()[1:]
    return parents or [git("hash-object", "-t", "tree", os.devnull).decode().strip()]


def changed_blobs(parent: str, sha: str) -> dict[str, tuple[str, str]]:
    """{path: (mode, blob)} of files the commit adds or changes relative to `parent`."""
    fields = git("diff", "--raw", "-z", "--no-abbrev", "--no-ext-diff", "--no-textconv",
                 "--no-renames", "--diff-filter=AMT", parent, sha, "--").split(b"\0")
    blobs = {}
    i = 0
    while i + 1 < len(fields) and fields[i]:
        _, new_mode, _, new_oid, _ = fields[i].decode("ascii").lstrip(":").split()
        blobs[fields[i + 1].decode("utf-8", "surrogateescape")] = (new_mode, new_oid)
        i += 2
    return blobs


def introduced_files(sha: str) -> dict[str, tuple[str, str]]:
    """Files whose committed content differs from every parent."""
    parents = parents_of(sha)
    files = changed_blobs(parents[0], sha)
    for other in parents[1:]:
        if not files:
            break
        files = {path: blob for path, blob in files.items() if path in changed_blobs(other, sha)}
    return files


def _fold(path: str) -> str:
    """The name a case-insensitive, normalizing filesystem sees for `path`."""
    return unicodedata.normalize("NFD", path).casefold()


def layers(files: dict[str, tuple[str, str]]) -> list[dict[str, str]]:
    """Regular-file blobs split into layers whose paths cannot collide on disk.

    On a case-insensitive or normalizing filesystem (macOS by default), `A.py`
    and `a.py` in one commit would be written to the same file, and one blob
    would never be scanned. Colliding paths, and a file whose name is another
    path's directory, go into separate layers. Each layer keeps the real
    repository-relative names, so validator path rules see what they see at
    commit time.
    """
    result: list[tuple[dict[str, str], set[str], set[str]]] = []
    for path, (mode, oid) in sorted(files.items()):
        if mode not in REGULAR:
            continue  # symlink or submodule: no file content in this commit
        pure = PurePosixPath(path)
        if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
            raise ValueError(f"refusing to write unexpected Git path: {path!r}")
        key = _fold(path)
        parents = {_fold(str(parent)) for parent in pure.parents if str(parent) != "."}
        for blobs, names, directories in result:
            if key not in names and key not in directories and not parents & names:
                break
        else:
            blobs, names, directories = {}, set(), set()
            result.append((blobs, names, directories))
        blobs[path] = oid
        names.add(key)
        directories.update(parents)
    return [blobs for blobs, _, _ in result]


def materialize(blobs: dict[str, str], root: Path) -> list[str]:
    """Write one layer's blobs under `root`; return their relative paths.

    Every file is read back after all are written, so any collision the
    layering did not foresee fails closed instead of hiding a blob.
    """
    contents = {path: git("cat-file", "blob", oid) for path, oid in blobs.items()}
    for path, content in contents.items():
        target = root.joinpath(*PurePosixPath(path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    for path, content in contents.items():
        if root.joinpath(*PurePosixPath(path).parts).read_bytes() != content:
            raise ValueError(f"scratch copy of {path!r} does not match its blob (filesystem name collision)")
    return sorted(contents)


def run_validator(name: str, args: list[str], cwd: Path | None) -> tuple[int, str]:
    try:
        result = subprocess.run([sys.executable, str(VALIDATORS_DIR / name), *args], cwd=cwd,
                                capture_output=True, text=True, timeout=VALIDATOR_TIMEOUT)
    except subprocess.TimeoutExpired:
        return 124, f"{name} timed out after {VALIDATOR_TIMEOUT}s\n"
    return result.returncode, result.stdout + result.stderr


def check_commit(sha: str, scratch: Path) -> list[tuple[str, int, str]]:
    """[(validator, exit code, output)] for every validator that did not pass."""
    failures = []
    for index, blobs in enumerate(layers(introduced_files(sha))):
        root = scratch / str(index)
        root.mkdir()
        files = materialize(blobs, root)
        for name in FILE_VALIDATORS:
            code, output = run_validator(name, files, root)
            if code != 0:
                failures.append((name, code, output))
    for name in COMMIT_VALIDATORS:
        code, output = run_validator(name, ["--commit", sha], None)
        if code != 0:
            failures.append((name, code, output))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("hook_args", nargs="*", help="pre-push remote name and URL (ignored)")
    parser.parse_args(argv)
    try:
        commits = pushed_commits(sys.stdin.read().splitlines())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"governance push check: unable to list the pushed commits ({type(error).__name__}: {error})",
              file=sys.stderr)
        return 1
    if not commits:
        return 0
    print(f"governance push check: {len(commits)} commit(s)", file=sys.stderr)
    blocked = 0
    with tempfile.TemporaryDirectory(prefix="governance-push-") as tmp:
        for index, sha in enumerate(commits):
            scratch = Path(tmp) / str(index)
            scratch.mkdir()
            subject = sha
            try:
                failures = check_commit(sha, scratch)
                if failures:
                    subject = git("log", "-1", "--format=%h %s", sha).decode(errors="replace").strip()
            except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
                failures = [("push-range-check", 1, f"unable to read the commit ({type(error).__name__}: {error})\n")]
            if not failures:
                continue
            blocked += 1
            print(f"\n✗ commit {subject}", file=sys.stderr)
            for name, code, output in failures:
                print(f"  {name} (exit {code}):", file=sys.stderr)
                for line in output.rstrip().splitlines():
                    print(f"    {line}", file=sys.stderr)
    if blocked:
        print(f"\n✗ Governance push check: {blocked} of {len(commits)} commit(s) failed - push blocked",
              file=sys.stderr)
        return 1
    print("✓ Governance push check passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
