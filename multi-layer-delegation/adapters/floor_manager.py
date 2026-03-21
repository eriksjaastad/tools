#!/usr/bin/env python3
"""Floor Manager adapter.

Runs the Floor Manager as a claude -p session with a delegate_task tool.
When the FM calls delegate_task, this adapter spawns a Worker via the
Claude Code adapter and returns the result.

Usage:
    echo '{"task_id": "fm-abc", "goal": "...", ...}' | python floor_manager.py
    python floor_manager.py task.json
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

from claude_code import make_result_envelope, validate_task_envelope, run as run_worker

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
FM_PROMPT = PROMPTS_DIR / "floor_manager.md"
WORKER_PROMPT = PROMPTS_DIR / "worker.md"


def generate_task_id(prefix: str = "w") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def run_floor_manager(envelope: dict, dry_run: bool = False) -> dict:
    """Run the Floor Manager loop: decompose → delegate → aggregate."""
    errors = validate_task_envelope(envelope)
    if errors:
        return make_result_envelope(
            task_id=envelope.get("task_id", "unknown"),
            status="failed",
            result=None,
            notes=f"Validation errors: {'; '.join(errors)}",
        )

    fm_system_prompt = FM_PROMPT.read_text() if FM_PROMPT.exists() else ""
    worker_system_prompt = WORKER_PROMPT.read_text() if WORKER_PROMPT.exists() else ""

    # NOTE: When claude -p supports tool-use streaming, the FM will use a
    # delegate_task tool definition and the full prompt/tool-use protocol.
    # For the MVP, we use a simpler two-phase approach (decompose + execute).

    # For the MVP, we run this as a simple loop:
    # 1. Send the envelope to the FM
    # 2. FM returns sub-tasks (we parse its response)
    # 3. We execute each sub-task via the worker adapter
    # 4. We send results back to the FM for aggregation

    # In practice, this uses claude -p with --tool-use, but since that requires
    # the tool-use streaming protocol, the MVP uses a simpler approach:
    # The FM outputs a plan, we execute it, then ask the FM to aggregate.

    import subprocess

    start = time.time()
    constraints = envelope.get("constraints", {})
    timeout = constraints.get("timeout_seconds", 600)

    # Phase 1: Ask FM to decompose the goal into sub-tasks
    decompose_prompt = (
        f"{fm_system_prompt}\n\n"
        f"## Your Task Envelope\n\n"
        f"```json\n{json.dumps(envelope, indent=2)}\n```\n\n"
        f"Decompose this goal into 2-5 worker sub-tasks. "
        f"Return ONLY a JSON array of sub-task objects, each with: "
        f"goal, context (array), acceptance_criteria (array), output_schema.\n\n"
        f"Example:\n"
        f'[{{"goal": "...", "context": ["..."], "acceptance_criteria": ["..."], "output_schema": "free_text"}}]'
    )

    cmd = ["claude", "-p", "--output-format", "json"]
    model = constraints.get("model")
    if model:
        cmd.extend(["--model", model])

    if dry_run:
        return {
            "dry_run": True,
            "phase": "decompose",
            "command": cmd,
            "prompt_preview": decompose_prompt[:500] + "...",
        }

    try:
        proc = subprocess.run(
            cmd, input=decompose_prompt, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=None,
            notes=f"FM decompose phase failed: {e}",
            wall_time=time.time() - start,
        )

    if proc.returncode != 0:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=proc.stderr.strip(),
            notes=f"FM decompose exited {proc.returncode}",
            wall_time=time.time() - start,
        )

    # Parse FM's decomposition
    try:
        fm_output = json.loads(proc.stdout)
        fm_text = fm_output.get("result", proc.stdout) if isinstance(fm_output, dict) else proc.stdout
        # Try to extract JSON array from the text
        if isinstance(fm_text, str):
            # Find the JSON array in the response
            start_idx = fm_text.find("[")
            end_idx = fm_text.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                sub_tasks = json.loads(fm_text[start_idx:end_idx])
            else:
                sub_tasks = json.loads(fm_text)
        else:
            sub_tasks = fm_text
    except (json.JSONDecodeError, TypeError):
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=proc.stdout[:500],
            notes="Could not parse FM decomposition as JSON array",
            wall_time=time.time() - start,
        )

    if not isinstance(sub_tasks, list) or len(sub_tasks) == 0:
        return make_result_envelope(
            task_id=envelope["task_id"],
            status="failed",
            result=None,
            notes="FM returned empty or non-list decomposition",
            wall_time=time.time() - start,
        )

    # Phase 2: Execute each sub-task via the worker adapter
    child_results = []
    all_artifacts = []
    budget_per_task = {}
    if constraints.get("max_cost_usd"):
        budget_per_task["max_cost_usd"] = constraints["max_cost_usd"] * 0.8 / len(sub_tasks)
    if constraints.get("max_turns"):
        budget_per_task["max_turns"] = max(1, constraints["max_turns"] // len(sub_tasks))

    for i, sub_task in enumerate(sub_tasks):
        task_id = generate_task_id("w")
        worker_envelope = {
            "task_id": task_id,
            "goal": sub_task.get("goal", f"Sub-task {i+1}"),
            "context": sub_task.get("context", []),
            "acceptance_criteria": sub_task.get("acceptance_criteria", []),
            "constraints": {**budget_per_task, "model": constraints.get("model")},
            "output_schema": sub_task.get("output_schema", "free_text"),
            "parent_task_id": envelope["task_id"],
        }

        worker_result = run_worker(worker_envelope, system_prompt=worker_system_prompt)
        child_results.append({
            "task_id": task_id,
            "goal": worker_envelope["goal"],
            "status": worker_result.get("status", "failed"),
            "summary": (
                worker_result.get("notes") or
                str(worker_result.get("result", ""))[:200]
            ),
        })
        all_artifacts.extend(worker_result.get("artifacts", []))

    # Phase 3: Aggregate results
    completed = sum(1 for c in child_results if c["status"] == "completed")
    total = len(child_results)

    if completed == total:
        status = "completed"
    elif completed > 0:
        status = "partial"
    else:
        status = "failed"

    wall_time = time.time() - start
    return make_result_envelope(
        task_id=envelope["task_id"],
        status=status,
        result=f"{completed}/{total} sub-tasks completed",
        artifacts=all_artifacts,
        notes=json.dumps(child_results, indent=2) if child_results else None,
        wall_time=wall_time,
    )


def main():
    parser = argparse.ArgumentParser(description="Floor Manager adapter")
    parser.add_argument("task_file", nargs="?", help="Path to Task Envelope JSON file")
    parser.add_argument("--task-json", help="Task Envelope as inline JSON string")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    if args.task_json:
        envelope = json.loads(args.task_json)
    elif args.task_file:
        envelope = json.loads(Path(args.task_file).read_text())
    elif not sys.stdin.isatty():
        envelope = json.load(sys.stdin)
    else:
        parser.error("Provide a task envelope via stdin, --task-json, or as a file argument")

    result = run_floor_manager(envelope, dry_run=args.dry_run)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
