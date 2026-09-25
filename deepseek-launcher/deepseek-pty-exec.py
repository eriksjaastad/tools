#!/usr/bin/env python3
"""Run DeepSeek execution under a bounded PTY.

Grok Bot MacBook Shell (and other non-TTY remotes) hang forever if you call
`deepseek -x` with a plain pipe. DeepCode needs a terminal. This wrapper is the
supported launch path for those managers.

Usage:
  deepseek-pty-exec.py -p 'prompt text'
  deepseek-pty-exec.py -p '...' --cwd /path/to/workdir
  deepseek-pty-exec.py -p '...' --timeout 300
  deepseek-pty-exec.py --ping   # expects the single word PONG

Additional arguments after -- are passed to the launcher. Does not print secrets.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import pty
import re
import select
import signal
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-p", "--prompt", help="Prompt for deepseek -x")
    ap.add_argument("--ping", action="store_true", help="Run a PONG smoke test")
    ap.add_argument("--cwd", default=os.getcwd(), help="Working directory")
    ap.add_argument("--timeout", type=int, default=300, help="Seconds before SIGTERM")
    ap.add_argument(
        "--bin",
        default=os.path.expanduser("~/bin/deepseek"),
        help="DeepSeek launcher (default: ~/bin/deepseek → deepcode-run.sh)",
    )
    args, passthrough = ap.parse_known_args()

    if args.ping:
        prompt = (
            "Reply with exactly the single word PONG and nothing else. "
            "Do not use tools. Do not write files."
        )
    elif passthrough:
        prompt = None
    else:
        if not args.prompt:
            ap.error("provide -p/--prompt or --ping")
        prompt = args.prompt

    cmd = [args.bin, *(passthrough[1:] if passthrough[:1] == ["--"] else passthrough)] if prompt is None else [args.bin, "-x", "-p", prompt]
    cwd = os.path.abspath(args.cwd)
    if not os.path.isdir(cwd):
        print(f"deepseek-pty-exec: cwd not a directory: {cwd}", file=sys.stderr)
        return 2
    if not os.path.exists(args.bin):
        print(f"deepseek-pty-exec: missing launcher: {args.bin}", file=sys.stderr)
        return 2

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.environ["DEEPCODE_PTY_ACTIVE"] = "1"
        os.execvp(cmd[0], cmd)

    if args.timeout < 1:
        print("deepseek-pty-exec: timeout must be positive", file=sys.stderr)
        return 2
    deadline = time.monotonic() + args.timeout
    exit_status: int | None = None
    output_open = True
    ping_output = bytearray()
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd] if output_open else [], [], [], 0.2)
            if ready:
                try:
                    data = os.read(fd, 8192)
                except OSError:
                    data = b""
                if not data:
                    output_open = False
                else:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    if args.ping and len(ping_output) < 65536:
                        ping_output.extend(data[:65536 - len(ping_output)])
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid == pid:
                exit_status = status
                break
        else:
            print(
                f"\ndeepseek-pty-exec: watchdog timeout after {args.timeout}s; killing",
                file=sys.stderr,
            )
            def signal_child(sig):
                # An already-exited process needs no further signal.
                with contextlib.suppress(ProcessLookupError):
                    try:
                        os.killpg(pid, sig)
                    except PermissionError:
                        os.kill(pid, sig)

            signal_child(signal.SIGTERM)
            time.sleep(2)
            signal_child(signal.SIGKILL)
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
            reap_deadline = time.monotonic() + 2
            while time.monotonic() < reap_deadline:
                try:
                    reaped, _ = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if reaped == pid:
                    break
                time.sleep(0.05)
            return 124
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)

    if exit_status is None:
        return 1
    if os.WIFEXITED(exit_status):
        code = os.WEXITSTATUS(exit_status)
        if code == 0 and args.ping:
            plain = re.sub(rb"\x1b\][^\x07]*(?:\x07|\x1b\\)", b"", bytes(ping_output))
            plain = re.sub(rb"\x1b\[[0-9;]*[A-Za-z]", b"", plain)
            if b"PONG" not in [line.strip() for line in plain.splitlines()]:
                print("deepseek-pty-exec: ping response did not contain a standalone PONG", file=sys.stderr)
                return 1
        return code
    if os.WIFSIGNALED(exit_status):
        return 128 + os.WTERMSIG(exit_status)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
