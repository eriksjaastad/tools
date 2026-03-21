#!/usr/bin/env python3
"""Claude Code runtime adapter.

Accepts a Task Envelope on stdin (or as a file argument),
calls `claude -p` with the appropriate flags,
and emits a Result Envelope on stdout.

Usage:
    echo '{"task_id": "w-abc", "goal": "...", "acceptance_criteria": [...]}' | python claude_code.py
    python claude_code.py task.json
    python claude_code.py --task-json '{"task_id": ...}'
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Resolve schema paths relative to this file
SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def load_schema(name: str) -> dict:
    schema_path = SCHEMA_DIR / name
    if schema_path.exists():
        return json.loads(schema_path.read_text())
    return {}


def validate_task_envelope(envelope: dict) -> list[str]:
    """Basic validation without jsonschema dependency."""
    errors = []
    for field in ("task_id", "goal", "acceptance_criteria"):
        if field not in envelope:
            errors.append(f"Missing required field: {field}")
    if "acceptance_criteria" in envelope and not isinstance(envelope["acceptance_criteria"], list):
        errors.append("acceptance_criteria must be an array")
    if "status" in envelope:
        errors.append("Task Envelope should not contain 'status' — that belongs in Result Envelope")
    return errors


def build_prompt(envelope: dict) -> str:
    """Convert a Task Envelope into a prompt string for claude -p."""
    parts = []
    parts.append(f"## Task: {envelope['task_id']}")
    parts.append(f"\n### Goal\n{envelope['goal']}")

    context = envelope.get("context", [])
    if context:
        parts.append("\n### Context")
        for item in context:
            parts.append(f"- {item}")

    criteria = envelope.get("acceptance_criteria", [])
    if criteria:
        parts.append("\n### Acceptance Criteria")
        for item in criteria:
            parts.append(f"- {item}")

    constraints = envelope.get("constraints", {})
    forbidden = constraints.get("forbidden_actions", [])
    if forbidden:
        parts.append("\n### Forbidden Actions")
        for item in forbidden:
            parts.append(f"- DO NOT: {item}")

    output_schema = envelope.get("output_schema", "free_text")
    parts.append(f"\n### Output Format\nReturn your result as: {output_schema}")

    parts.append(
        "\n### Response Format\n"
        "You MUST respond with valid JSON matching this structure:\n"
        '{"result": <your deliverable>, "artifacts": [{"type": "file_path"|"diff"|"inline", '
        '"value": "...", "description": "..."}], "notes": "any warnings or blockers"}'
    )

    return "\n".join(parts)


def build_claude_command(envelope: dict, system_prompt: str | None = None) -> list[str]:
    """Build the claude CLI command from the envelope."""
    cmd = ["claude", "-p", "--output-format", "json"]

    constraints = envelope.get("constraints", {})

    max_turns = constraints.get("max_turns")
    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])

    model = constraints.get("model")
    if model:
        cmd.extend(["--model", model])

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    return cmd


def parse_claude_output(raw_output: str) -> dict:
    """Parse claude --output-format json output into result components."""
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        # Claude returned non-JSON — wrap as free text
        return {
            "result": raw_output.strip(),
            "artifacts": [],
            "notes": "Output was not valid JSON; returned as free text.",
        }

    # claude -p --output-format json returns {"result": "...", "cost_usd": ..., ...}
    # The "result" field contains the assistant's text response
    assistant_text = data.get("result", raw_output)

    # Try to parse the assistant's text as our structured response
    try:
        structured = json.loads(assistant_text) if isinstance(assistant_text, str) else assistant_text
        if isinstance(structured, dict) and "result" in structured:
            return {
                "result": structured["result"],
                "artifacts": structured.get("artifacts", []),
                "notes": structured.get("notes"),
            }
    except (json.JSONDecodeError, TypeError):
        pass

    # Extract cost info if available
    cost_info = {}
    if "cost_usd" in data:
        cost_info["api_cost_usd"] = data["cost_usd"]
    if "input_tokens" in data:
        cost_info["input_tokens"] = data["input_tokens"]
    if "output_tokens" in data:
        cost_info["output_tokens"] = data["output_tokens"]

    return {
        "result": assistant_text,
        "artifacts": [],
        "notes": None,
        "cost": cost_info,
    }


def make_result_envelope(
    task_id: str,
    status: str,
    result,
    artifacts: list | None = None,
    cost: dict | None = None,
    notes: str | None = None,
    wall_time: float = 0.0,
) -> dict:
    """Construct a Result Envelope."""
    envelope = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "artifacts": artifacts or [],
        "cost": cost or {},
        "notes": notes,
        "child_tasks": [],
        "metadata": {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "runtime": "claude_code",
        },
    }
    if wall_time:
        envelope["cost"]["wall_time_seconds"] = round(wall_time, 2)
    return envelope


def run(envelope: dict, system_prompt: str | None = None, dry_run: bool = False) -> dict:
    """Execute a Task Envelope via claude -p and return a Result Envelope."""
    errors = validate_task_envelope(envelope)
    if errors:
        return make_result_envelope(
            task_id=envelope.get("task_id", "unknown"),
            status="failed",
            result=None,
            notes=f"Validation errors: {'; '.join(errors)}",
        )

    prompt = build_prompt(envelope)
    cmd = build_claude_command(envelope, system_prompt)

    if dry_run:
        return {
            "dry_run": True,
            "command": cmd,
            "prompt": prompt,
            "envelope": envelope,
        }

    constraints = envelope.get("constraints", {})
    timeout = constraints.get("timeout_seconds", 300)

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
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
            notes=f"Timed out after {timeout}s",
            wall_time=wall_time,
        )
    except FileNotFoundError:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=None,
            notes="claude CLI not found. Is Claude Code installed?",
        )

    wall_time = time.time() - start

    if proc.returncode != 0:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=proc.stderr.strip() or proc.stdout.strip(),
            notes=f"claude exited with code {proc.returncode}",
            wall_time=wall_time,
        )

    parsed = parse_claude_output(proc.stdout)
    cost = parsed.get("cost", {})
    cost["wall_time_seconds"] = round(wall_time, 2)

    return make_result_envelope(
        task_id=envelope["task_id"],
        status="completed",
        result=parsed["result"],
        artifacts=parsed.get("artifacts", []),
        cost=cost,
        notes=parsed.get("notes"),
        wall_time=wall_time,
    )


def main():
    parser = argparse.ArgumentParser(description="Claude Code runtime adapter for multi-layer delegation")
    parser.add_argument("task_file", nargs="?", help="Path to Task Envelope JSON file")
    parser.add_argument("--task-json", help="Task Envelope as inline JSON string")
    parser.add_argument("--system-prompt", help="Optional system prompt for the worker")
    parser.add_argument("--system-prompt-file", help="Path to system prompt file")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without executing")
    args = parser.parse_args()

    # Load task envelope from one of three sources
    if args.task_json:
        envelope = json.loads(args.task_json)
    elif args.task_file:
        envelope = json.loads(Path(args.task_file).read_text())
    elif not sys.stdin.isatty():
        envelope = json.load(sys.stdin)
    else:
        parser.error("Provide a task envelope via stdin, --task-json, or as a file argument")

    # Load system prompt
    system_prompt = args.system_prompt
    if args.system_prompt_file:
        system_prompt = Path(args.system_prompt_file).read_text().strip()

    result = run(envelope, system_prompt=system_prompt, dry_run=args.dry_run)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
