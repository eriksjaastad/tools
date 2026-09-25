#!/usr/bin/env python3
"""Clear a temporary DeepCode credential before moving it to Trash."""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def identity(path):
    if not os.path.lexists(path):
        return ""
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("settings path is not a regular file")
    return f"{info.st_dev}:{info.st_ino}"


def owner(path):
    value = ""
    # A partial file can be produced by an interrupted Doppler write. The
    # inode check still guards its cleanup, so a missing marker is expected.
    with contextlib.suppress(ValueError, TypeError, AttributeError):
        value = str(json.loads(Path(path).read_text(encoding="utf-8")).get(
            "_deepcode_run_owner_pid", ""))
    return value


def alive(pid):
    running = False
    try:
        os.kill(int(pid), 0)
        running = True
    except ProcessLookupError:
        # Expected for a stale owner; the caller will reclaim its file.
        running = False
    except PermissionError:
        running = True
    return running


def source_fingerprint(args):
    source = [args.project, args.config, args.secret, args.base_url, args.model]
    return hashlib.sha256(json.dumps(source).encode("utf-8")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("identity", "owner", "empty", "stale", "fetch", "source", "fingerprint"))
    parser.add_argument("path")
    parser.add_argument("--inode", default="")
    parser.add_argument("--pid", default="")
    parser.add_argument("--project", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--secret", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--doppler-timeout", type=int, default=30)
    args = parser.parse_args()
    try:
        if args.mode == "fingerprint":
            print(source_fingerprint(args))
            return 0
        if args.mode == "source":
            source = ""
            with contextlib.suppress(ValueError, TypeError, AttributeError):
                source = str(json.loads(Path(args.path).read_text(encoding="utf-8")).get(
                    "_deepcode_run_source", ""))
            print(source)
            return 0
        if args.mode == "fetch":
            if args.doppler_timeout < 1:
                raise ValueError("Doppler timeout must be positive")
            result = subprocess.run(
                ["doppler", "secrets", "get", args.secret, "--project", args.project,
                 "--config", args.config, "--plain"],
                capture_output=True, text=True, timeout=args.doppler_timeout, check=False,
            )
            key = result.stdout.strip()
            if result.returncode or not re.fullmatch(r"[A-Za-z0-9_.-]{16,}", key):
                raise ValueError("Doppler did not return a valid key")
            json.dump({"_deepcode_run_owner_pid": args.pid,
                       "_deepcode_run_source": source_fingerprint(args),
                       "env": {"API_KEY": key, "BASE_URL": args.base_url,
                               "MODEL": args.model}}, sys.stdout)
            return 0
        current = identity(args.path)
        if args.mode == "identity":
            print(current)
            return 0
        if not current:
            return 0
        if args.inode and args.inode != current:
            return 0
        file_owner = owner(args.path)
        if args.mode == "owner":
            permitted = file_owner == args.pid or (not file_owner and bool(args.inode))
        elif args.mode == "empty":
            permitted = not os.path.getsize(args.path)
        else:
            permitted = bool(file_owner) and file_owner == args.pid and not alive(file_owner)
        if not permitted:
            return 0
        # Trash is persistent. Clear the file and sync before moving it there.
        # Never touch an unmarked, nonempty handwritten configuration.
        with open(args.path, "r+b", buffering=0) as stream:
            if identity(args.path) != current:
                return 0
            stream.truncate(0)
            os.fsync(stream.fileno())
        result = subprocess.run(["trash", args.path], capture_output=True, text=True,
                                timeout=10, check=False)
        if result.returncode:
            raise OSError(f"trash failed with status {result.returncode}: {result.stderr.strip()}")
        if identity(args.path) == current:
            raise OSError("trash reported success but settings file is still present")
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"deepcode-run: settings operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
