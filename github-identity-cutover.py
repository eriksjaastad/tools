#!/usr/bin/env python3
"""Audit or reversibly switch local Git/GitHub paths to Erik's personal account.

Run on each host with ``uv run --no-project github-identity-cutover.py`` first.
``--apply`` writes a private rollback snapshot before changing any setting.
"""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone


KEYS = ("user.name", "user.email", "credential.helper")
PERSONAL_HELPER = '!f() { env -u GH_TOKEN -u GITHUB_TOKEN gh auth git-credential "$@"; }; f'
PERSONAL_GHA = b'#!/bin/sh\nunset GH_TOKEN GITHUB_TOKEN\nexec gh "$@"\n'


def run(args, *, cwd=None, check=True, env=None):
    try:
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                                timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"command could not finish: {args[0]}") from exc
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {args[0]} {args[1] if len(args) > 1 else ''}")
    return result


def personal_account():
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    account = json.loads(run(["gh", "api", "user"], env=env).stdout)
    if account.get("login") != "eriksjaastad" or account.get("id") != 2491180:
        raise RuntimeError("personal gh authentication is not eriksjaastad (2491180)")
    return account


def scope_settings(scope, repo=None):
    result = {}
    for key in KEYS:
        response = run(["git", "config", scope, "--null", "--get-all", key],
                       cwd=repo, check=False)
        if response.returncode not in (0, 1):
            raise RuntimeError(f"cannot read {key} in {repo}")
        result[key] = [part.decode() for part in response.stdout.split(b"\0") if part]
        if response.stdout.startswith(b"\0"):
            result[key].insert(0, "")
    return result


def settings(repo):
    return scope_settings("--local", repo)


def repositories(home):
    root = home / "projects"
    candidates = [root]
    candidates.extend(path for path in root.iterdir() if path.is_dir()
                      and (path / ".git").exists())
    candidates.extend((home / ".openclaw", home / ".openclaw/workspace",
                       home / ".hermes/projects/looplens",
                       root / "holoscape-deepseek-worker"))
    # Independent temporary clones retain their own .git/config. A project
    # checkout can be resumed from there after the primary clone is migrated.
    temp_root = Path("/private/tmp")
    for marker in (*temp_root.glob("*/.git"), *temp_root.glob("*/*/.git")):
        repo = marker.parent
        remote = run(["git", "remote", "get-url", "origin"], cwd=repo, check=False)
        if remote.returncode == 0 and remote.stdout.decode().strip().startswith(
                ("https://github.com/eriksjaastad/", "git@github.com:eriksjaastad/")):
            candidates.append(repo)
    found = {}
    for path in candidates:
        if not path.exists():
            continue
        result = run(["git", "rev-parse", "--git-common-dir"], cwd=path, check=False)
        if result.returncode:
            continue
        common = Path(result.stdout.decode().strip())
        if not common.is_absolute():
            common = (path / common).resolve()
        found.setdefault(str(common), str(path.resolve()))
    return sorted(found.values())


def scope_replace(scope, values, repo=None):
    for key in KEYS:
        response = run(["git", "config", scope, "--unset-all", key],
                       cwd=repo, check=False)
        if response.returncode not in (0, 5):
            raise RuntimeError(f"cannot clear {key} in {repo}")
        for value in values[key]:
            run(["git", "config", scope, "--add", key, value], cwd=repo)


def replace_config(repo, values):
    scope_replace("--local", values, repo)


def write_bytes(path, data, mode):
    temporary = path.with_name(path.name + ".personal-cutover-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    os.chmod(path, mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    if args.apply and args.restore:
        parser.error("--apply and --restore are exclusive")
    home = Path.home()
    archive = home / "projects/.github-history-archive"
    wrapper = Path(shutil.which("gha") or "")
    if not wrapper.is_file() or home not in wrapper.parents:
        raise RuntimeError("gha wrapper must be an installed file under this user's home")
    zshrc = home / ".zshrc"
    repos = repositories(home)
    if args.restore:
        backup = json.loads(args.restore.read_text())
        for row in backup["repos"]:
            replace_config(row["path"], row["settings"])
        scope_replace("--global", backup["global_settings"])
        write_bytes(Path(backup["wrapper_path"]), bytes.fromhex(backup["wrapper_hex"]),
                    backup["wrapper_mode"])
        if backup["zshrc_changed"]:
            current = zshrc.read_text()
            previous = backup["zshrc_alias"]
            replacement = backup.get("zshrc_replacement", 'alias gha="gh"')
            if replacement not in current:
                raise RuntimeError("cannot restore alias: expected cutover marker is missing")
            zshrc.write_text(current.replace(replacement, previous, 1))
        print(json.dumps({"restored_repos": len(backup["repos"]), "backup": str(args.restore)}))
        return 0
    personal_account()
    email = "2491180+eriksjaastad@users.noreply.github.com"
    alias_line = None
    if zshrc.exists():
        alias_line = next((line for line in zshrc.read_text().splitlines()
                           if re.match(r"^alias gha=", line)), None)
    if alias_line and alias_line != 'alias gha="gh"' and "gh-agent.sh --auto" not in alias_line:
        raise RuntimeError("unknown gha shell alias; inspect before cutover")
    alias_replacement = "# gha uses the installed shim on PATH"
    rows = [{"path": path, "settings": settings(path)} for path in repos]
    old_global = scope_settings("--global")
    print(json.dumps({"host": os.uname().nodename, "repos": len(rows),
                      "bot_authors": sum(any("[bot]" in name or name == "CodexSpud"
                                             for name in row["settings"]["user.name"])
                                         for row in rows),
                      "wrapper": str(wrapper), "target_login": "eriksjaastad",
                      "target_email": email, "mode": "apply" if args.apply else "audit"}))
    if not args.apply:
        return 0
    archive.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(archive, 0o700)
    backup = {"captured_at": datetime.now(timezone.utc).isoformat(),
              "host": os.uname().nodename, "repos": rows,
              "global_settings": old_global,
              "wrapper_path": str(wrapper), "wrapper_hex": wrapper.read_bytes().hex(),
              "wrapper_mode": wrapper.stat().st_mode & 0o777,
              "zshrc_alias": alias_line, "zshrc_changed": bool(alias_line),
              "zshrc_replacement": alias_replacement}
    backup_path = archive / ("identity-backup-" + os.uname().nodename + "-" +
                             datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    write_bytes(backup_path, (json.dumps(backup, indent=2) + "\n").encode(), 0o600)
    target = {"user.name": ["eriksjaastad"], "user.email": [email],
              "credential.helper": ["", PERSONAL_HELPER]}
    for row in rows:
        replace_config(row["path"], target)
        if settings(row["path"]) != target:
            raise RuntimeError(f"cutover verification failed for {row['path']}; restore from {backup_path}")
    scope_replace("--global", target)
    if scope_settings("--global") != target:
        raise RuntimeError(f"global cutover verification failed; restore from {backup_path}")
    write_bytes(wrapper, PERSONAL_GHA, backup["wrapper_mode"])
    if backup["zshrc_changed"]:
        original = zshrc.read_text()
        zshrc.write_text(original.replace(alias_line, alias_replacement, 1))
    print(json.dumps({"applied_repos": len(rows), "backup": str(backup_path),
                      "wrapper": str(wrapper)}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print(f"cutover error: {exc}", file=sys.stderr)
        sys.exit(1)
