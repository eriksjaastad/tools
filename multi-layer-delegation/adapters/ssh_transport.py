#!/usr/bin/env python3
"""SSH transport adapter for cross-machine worker spawning.

Wraps the Claude Code adapter to execute on a remote machine via SSH.
The Task Envelope is sent as JSON over stdin, and the Result Envelope
is captured from stdout.

Usage:
    # Spawn a worker on the Mac mini
    echo '{"task_id": "w-abc", ...}' | python ssh_transport.py --host macmini

    # With explicit user and key
    python ssh_transport.py --host macmini --user erik --key ~/.ssh/id_ed25519 task.json

    # Dry run — see the SSH command without executing
    python ssh_transport.py --host macmini --dry-run --task-json '{"task_id": ...}'
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from adapters.claude_code import make_result_envelope, validate_task_envelope

# Default path to the adapter on remote machines
DEFAULT_REMOTE_ADAPTER = "~/projects/_tools/multi-layer-delegation/adapters/claude_code.py"
DEFAULT_REMOTE_PYTHON = "~/.local/bin/uv run"


def build_ssh_command(
    host: str,
    user: str | None = None,
    key_path: str | None = None,
    remote_adapter: str = DEFAULT_REMOTE_ADAPTER,
    remote_python: str = DEFAULT_REMOTE_PYTHON,
    port: int = 22,
    connect_timeout: int = 10,
) -> list[str]:
    """Build the SSH command to run the Claude Code adapter remotely."""
    cmd = ["ssh"]

    # Connection options
    cmd.extend(["-o", f"ConnectTimeout={connect_timeout}"])
    cmd.extend(["-o", "StrictHostKeyChecking=accept-new"])
    cmd.extend(["-o", "BatchMode=yes"])

    if port != 22:
        cmd.extend(["-p", str(port)])

    if key_path:
        cmd.extend(["-i", key_path])

    # Target
    target = f"{user}@{host}" if user else host
    cmd.append(target)

    # Remote command: pipe stdin to the adapter
    cmd.append(f"{remote_python} {remote_adapter}")

    return cmd


def run_remote(
    envelope: dict,
    host: str,
    user: str | None = None,
    key_path: str | None = None,
    remote_adapter: str = DEFAULT_REMOTE_ADAPTER,
    remote_python: str = DEFAULT_REMOTE_PYTHON,
    port: int = 22,
    system_prompt: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Execute a Task Envelope on a remote machine via SSH."""
    errors = validate_task_envelope(envelope)
    if errors:
        return make_result_envelope(
            task_id=envelope.get("task_id", "unknown"),
            status="failed",
            result=None,
            notes=f"Validation errors: {'; '.join(errors)}",
        )

    cmd = build_ssh_command(
        host=host,
        user=user,
        key_path=key_path,
        remote_adapter=remote_adapter,
        remote_python=remote_python,
        port=port,
    )

    # When a system prompt is provided, we bundle it with the envelope as a
    # wrapper JSON object and use a remote one-liner to split them apart.
    # This avoids tempfiles, rm, and shell injection entirely.
    use_wrapper = system_prompt is not None

    if use_wrapper:
        # The wrapper JSON has {"envelope": ..., "system_prompt": "..."}.
        # Remote side: python3 -c reads wrapper, writes envelope to stdin of adapter.
        unwrap_script = (
            "import json,sys,subprocess; "
            "w=json.load(sys.stdin); "
            "p=subprocess.run("
            f"[*'{remote_python}'.split(), '{remote_adapter}', '--system-prompt', w['system_prompt']],"
            "input=json.dumps(w['envelope']),capture_output=True,text=True); "
            "sys.stdout.write(p.stdout); sys.stderr.write(p.stderr); sys.exit(p.returncode)"
        )
        cmd[-1] = f"python3 -c {repr(unwrap_script)}"

    if dry_run:
        return {
            "dry_run": True,
            "ssh_command": cmd,
            "envelope": envelope,
            "target": f"{user}@{host}" if user else host,
        }

    constraints = envelope.get("constraints", {})
    # SSH tasks get extra timeout for connection overhead
    timeout = constraints.get("timeout_seconds", 300) + 30

    if use_wrapper:
        stdin_payload = json.dumps({"envelope": envelope, "system_prompt": system_prompt})
    else:
        stdin_payload = json.dumps(envelope)
    start = time.time()

    try:
        proc = subprocess.run(
            cmd,
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        wall_time = time.time() - start
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=None,
            notes=f"SSH timed out after {timeout}s to {host}",
            wall_time=wall_time,
        )
    except FileNotFoundError:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=None,
            notes="ssh command not found",
        )

    wall_time = time.time() - start

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        # Common SSH errors
        if "Connection refused" in stderr:
            note = f"SSH connection refused to {host}. Is sshd running?"
        elif "No route to host" in stderr:
            note = f"Cannot reach {host}. Network issue?"
        elif "Permission denied" in stderr:
            note = f"SSH auth failed to {host}. Check key/user."
        elif "timed out" in stderr.lower():
            note = f"SSH connection timed out to {host}."
        else:
            note = f"SSH exited {proc.returncode}: {stderr[:300]}"

        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=proc.stdout.strip()[:500] if proc.stdout else None,
            notes=note,
            wall_time=wall_time,
        )

    # Parse the remote Result Envelope
    try:
        remote_result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=proc.stdout.strip()[:500],
            notes="Remote adapter returned non-JSON output",
            wall_time=wall_time,
        )

    # Augment with transport metadata
    remote_result.setdefault("metadata", {})
    remote_result["metadata"]["transport"] = "ssh"
    remote_result["metadata"]["remote_host"] = host
    if "cost" not in remote_result:
        remote_result["cost"] = {}
    remote_result["cost"]["wall_time_seconds"] = round(wall_time, 2)

    return remote_result


def main():
    parser = argparse.ArgumentParser(description="SSH transport for cross-machine worker spawning")
    parser.add_argument("task_file", nargs="?", help="Path to Task Envelope JSON file")
    parser.add_argument("--task-json", help="Task Envelope as inline JSON string")
    parser.add_argument("--host", required=True, help="Remote hostname or alias (e.g. macmini)")
    parser.add_argument("--user", help="SSH user (default: current user)")
    parser.add_argument("--key", help="Path to SSH private key")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--remote-adapter", default=DEFAULT_REMOTE_ADAPTER,
                        help="Path to claude_code.py on remote machine")
    parser.add_argument("--remote-python", default=DEFAULT_REMOTE_PYTHON,
                        help="Python command on remote machine")
    parser.add_argument("--system-prompt", help="System prompt for the worker")
    parser.add_argument("--dry-run", action="store_true", help="Show SSH command without executing")
    args = parser.parse_args()

    if args.task_json:
        envelope = json.loads(args.task_json)
    elif args.task_file:
        envelope = json.loads(Path(args.task_file).read_text())
    elif not sys.stdin.isatty():
        envelope = json.load(sys.stdin)
    else:
        parser.error("Provide a task envelope via stdin, --task-json, or as a file argument")

    result = run_remote(
        envelope=envelope,
        host=args.host,
        user=args.user,
        key_path=args.key,
        remote_adapter=args.remote_adapter,
        remote_python=args.remote_python,
        port=args.port,
        system_prompt=args.system_prompt,
        dry_run=args.dry_run,
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
