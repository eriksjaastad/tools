#!/usr/bin/env python3
"""Orchestrator — the outer loop from Conductor goal to FM to result.

This is the entry point for the multi-layer delegation system.
It takes a goal from the Conductor (Erik), wraps it in a Task Envelope,
sends it to the Floor Manager, and reports the Result Envelope back.

Usage:
    # Interactive — type a goal
    python orchestrate.py

    # One-shot goal
    python orchestrate.py --goal "Refactor the auth module to use JWT"

    # With a full Task Envelope
    python orchestrate.py --envelope task.json

    # Dry run — see what would be sent without executing
    python orchestrate.py --goal "..." --dry-run

    # With constraints
    python orchestrate.py --goal "..." --model sonnet --max-turns 10 --budget 0.50
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adapters.floor_manager import run_floor_manager


def generate_task_id() -> str:
    return f"orch-{uuid.uuid4().hex[:8]}"


def goal_to_envelope(
    goal: str,
    context: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    constraints: dict | None = None,
) -> dict:
    """Convert a Conductor's goal into a Task Envelope for the Floor Manager."""
    return {
        "task_id": generate_task_id(),
        "goal": goal,
        "context": context or [],
        "acceptance_criteria": acceptance_criteria or [
            "The goal is achieved as described",
            "No unintended side effects",
            "Changes are tested or verifiable",
        ],
        "constraints": constraints or {},
        "output_schema": "json",
        "parent_task_id": None,
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "delegator_layer": 0,
            "delegator_id": "conductor",
            "runtime_hint": "claude_code",
        },
    }


def print_result(result: dict) -> None:
    """Pretty-print a Result Envelope for the Conductor."""
    status = result.get("status", "unknown")
    task_id = result.get("task_id", "?")

    status_icons = {
        "completed": "[OK]",
        "partial": "[PARTIAL]",
        "failed": "[FAIL]",
        "blocked": "[BLOCKED]",
    }
    icon = status_icons.get(status, "[?]")

    print(f"\n{'='*60}")
    print(f"  {icon} Task {task_id}: {status.upper()}")
    print(f"{'='*60}")

    result_text = result.get("result")
    if result_text:
        print(f"\nResult:\n  {result_text}")

    artifacts = result.get("artifacts", [])
    if artifacts:
        print(f"\nArtifacts:")
        for a in artifacts:
            print(f"  [{a.get('type', '?')}] {a.get('value', '')} — {a.get('description', '')}")

    cost = result.get("cost", {})
    if cost:
        parts = []
        if "api_cost_usd" in cost:
            parts.append(f"${cost['api_cost_usd']:.4f}")
        if "total_tokens" in cost:
            parts.append(f"{cost['total_tokens']} tokens")
        if "wall_time_seconds" in cost:
            parts.append(f"{cost['wall_time_seconds']:.1f}s")
        if parts:
            print(f"\nCost: {' | '.join(parts)}")

    notes = result.get("notes")
    if notes:
        print(f"\nNotes:\n  {notes}")

    child_tasks = result.get("child_tasks", [])
    if child_tasks:
        print(f"\nSub-tasks:")
        for ct in child_tasks:
            ct_icon = status_icons.get(ct.get("status", ""), "  ")
            print(f"  {ct_icon} {ct.get('task_id', '?')}: {ct.get('goal', '?')}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrator — Conductor goal to Floor Manager to result"
    )
    parser.add_argument("--goal", "-g", help="The goal to accomplish (one sentence)")
    parser.add_argument("--envelope", "-e", help="Path to a full Task Envelope JSON file")
    parser.add_argument("--context", "-c", nargs="*", help="Context items for the task")
    parser.add_argument("--criteria", nargs="*", help="Acceptance criteria")
    parser.add_argument("--model", "-m", help="Model to use (e.g. sonnet, opus, haiku)")
    parser.add_argument("--max-turns", type=int, help="Max turns per worker")
    parser.add_argument("--budget", type=float, help="Max cost in USD")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of pretty-print")
    args = parser.parse_args()

    # Build or load the envelope
    if args.envelope:
        envelope = json.loads(Path(args.envelope).read_text())
    elif args.goal:
        constraints = {}
        if args.model:
            constraints["model"] = args.model
        if args.max_turns:
            constraints["max_turns"] = args.max_turns
        if args.budget:
            constraints["max_cost_usd"] = args.budget
        if args.timeout:
            constraints["timeout_seconds"] = args.timeout

        envelope = goal_to_envelope(
            goal=args.goal,
            context=args.context,
            acceptance_criteria=args.criteria,
            constraints=constraints,
        )
    elif sys.stdin.isatty():
        # Interactive mode — only when attached to a terminal
        print("Multi-Layer Delegation Orchestrator")
        print("Enter your goal (what should be accomplished):")
        goal = input("> ").strip()
        if not goal:
            print("No goal provided. Exiting.")
            return
        envelope = goal_to_envelope(goal=goal)
    else:
        parser.error("Provide a goal via --goal, an envelope via --envelope, or run interactively in a terminal")

    # Show the envelope
    if args.dry_run:
        print("Task Envelope (dry run):")
        print(json.dumps(envelope, indent=2))
        return

    # Run the delegation
    result = run_floor_manager(envelope, dry_run=False)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_result(result)


if __name__ == "__main__":
    main()
