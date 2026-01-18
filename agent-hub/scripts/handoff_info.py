#!/usr/bin/env python3
"""
Floor Manager Pre-Flight Script

Gathers all context needed before task execution:
- Available Ollama models
- Model capabilities and recommendations
- Active tasks in _handoff/
- System state (stalls, blockers)

Usage:
    python scripts/handoff_info.py
    python scripts/handoff_info.py --json  # Machine-readable output
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Project root (where this script lives)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
HANDOFF_DIR = PROJECT_ROOT / "_handoff"

# Model capability database (from LOCAL_MODEL_LEARNINGS.md)
MODEL_CAPABILITIES = {
    "deepseek-r1:7b": {
        "context_window": 32768,
        "strengths": ["reasoning", "debugging", "step-by-step logic"],
        "weaknesses": ["full file rewrites", "JSON-only output"],
        "max_output_lines": 200,
        "recommended_for": ["micro-tasks", "bug fixes", "code review"],
        "avoid_for": ["large refactors", "file rewrites > 100 lines"],
    },
    "deepseek-r1:14b": {
        "context_window": 32768,
        "strengths": ["complex reasoning", "multi-step tasks", "debugging"],
        "weaknesses": ["JSON-only output", "impatient with simple tasks"],
        "max_output_lines": 400,
        "recommended_for": ["debugging", "architecture decisions", "complex logic"],
        "avoid_for": ["simple edits", "boilerplate generation"],
    },
    "qwen2.5-coder:7b": {
        "context_window": 32768,
        "strengths": ["code generation", "refactoring", "following patterns"],
        "weaknesses": ["long context", "reasoning about why"],
        "max_output_lines": 300,
        "recommended_for": ["new functions", "code generation", "pattern application"],
        "avoid_for": ["debugging", "architecture decisions"],
    },
    "qwen2.5-coder:14b": {
        "context_window": 32768,
        "strengths": ["larger code tasks", "refactoring", "multi-file awareness"],
        "weaknesses": ["overkill for simple tasks", "slower"],
        "max_output_lines": 500,
        "recommended_for": ["medium refactors", "feature implementation"],
        "avoid_for": ["micro-tasks", "single-line fixes"],
    },
}


def get_ollama_models() -> list[dict]:
    """Get list of available Ollama models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if result.returncode != 0:
            return []

        models = []
        lines = result.stdout.strip().split("\n")

        # Skip header line
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 4:
                model_name = parts[0]
                model_id = parts[1]
                size = parts[2]
                # Parse modified time (remaining parts)
                modified = " ".join(parts[3:])

                models.append({
                    "name": model_name,
                    "id": model_id,
                    "size": size,
                    "modified": modified,
                    "capabilities": MODEL_CAPABILITIES.get(model_name, {}),
                })

        return models
    except subprocess.TimeoutExpired:
        return [{"error": "ollama list timed out"}]
    except FileNotFoundError:
        return [{"error": "ollama not found in PATH"}]
    except Exception as e:
        return [{"error": str(e)}]


def get_active_tasks() -> list[dict]:
    """Get list of active tasks in _handoff/."""
    tasks = []

    if not HANDOFF_DIR.exists():
        return [{"error": f"{HANDOFF_DIR} does not exist"}]

    for task_file in HANDOFF_DIR.glob("TASK_*.md"):
        content = task_file.read_text()

        # Extract objective from content
        objective = ""
        for line in content.split("\n"):
            if line.startswith("**Objective:**"):
                objective = line.replace("**Objective:**", "").strip()
                break

        # Extract target file if present
        target_file = ""
        for line in content.split("\n"):
            if "Target File:" in line or "target file" in line.lower():
                target_file = line.split(":")[-1].strip().strip("`")
                break

        tasks.append({
            "file": task_file.name,
            "path": str(task_file),
            "objective": objective,
            "target_file": target_file,
            "modified": datetime.fromtimestamp(task_file.stat().st_mtime).isoformat(),
        })

    return tasks


def get_stall_reports() -> list[dict]:
    """Check for any stall reports."""
    stalls = []

    stall_file = HANDOFF_DIR / "STALL_REPORT.md"
    if stall_file.exists():
        content = stall_file.read_text()
        stalls.append({
            "file": "STALL_REPORT.md",
            "exists": True,
            "preview": content[:500] if len(content) > 500 else content,
        })

    return stalls


def get_system_state() -> dict:
    """Get overall system state."""
    state = {
        "handoff_dir_exists": HANDOFF_DIR.exists(),
        "drafts_dir_exists": (HANDOFF_DIR / "drafts").exists(),
        "archive_dir_exists": (HANDOFF_DIR / "archive").exists(),
        "transition_log_exists": (HANDOFF_DIR / "transition.ndjson").exists(),
    }

    # Check hubstate if exists
    hubstate_file = HANDOFF_DIR / "hubstate.json"
    if hubstate_file.exists():
        try:
            hubstate = json.loads(hubstate_file.read_text())
            state["hubstate"] = {
                "current_state": hubstate.get("state", "unknown"),
                "task_id": hubstate.get("task_id"),
                "last_updated": hubstate.get("updated_at"),
            }
        except json.JSONDecodeError:
            state["hubstate"] = {"error": "malformed hubstate.json"}

    # Count archived tasks
    archive_dir = HANDOFF_DIR / "archive"
    if archive_dir.exists():
        state["archived_task_count"] = len(list(archive_dir.iterdir()))

    return state


def recommend_model(task: dict, models: list[dict]) -> str:
    """Recommend a model for a given task."""
    available_names = [m["name"] for m in models if "error" not in m]

    if not available_names:
        return "No models available"

    # Simple heuristics based on task content
    objective = task.get("objective", "").lower()

    # Prefer smaller models for simple tasks
    if any(word in objective for word in ["pin", "update", "change", "simple", "micro"]):
        for model in ["qwen2.5-coder:7b", "deepseek-r1:7b"]:
            if model in available_names:
                return model

    # Prefer reasoning models for debugging/fixing
    if any(word in objective for word in ["fix", "debug", "bug", "error"]):
        for model in ["deepseek-r1:7b", "deepseek-r1:14b"]:
            if model in available_names:
                return model

    # Prefer coder models for generation
    if any(word in objective for word in ["generate", "create", "add", "implement"]):
        for model in ["qwen2.5-coder:7b", "qwen2.5-coder:14b"]:
            if model in available_names:
                return model

    # Default to first available
    return available_names[0] if available_names else "No recommendation"


def print_report(as_json: bool = False):
    """Print the full pre-flight report."""

    models = get_ollama_models()
    tasks = get_active_tasks()
    stalls = get_stall_reports()
    state = get_system_state()

    # Add recommendations to tasks
    for task in tasks:
        if "error" not in task:
            task["recommended_model"] = recommend_model(task, models)

    report = {
        "timestamp": datetime.now().isoformat(),
        "ollama_models": models,
        "active_tasks": tasks,
        "stall_reports": stalls,
        "system_state": state,
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return

    # Human-readable output
    print("=" * 60)
    print("FLOOR MANAGER PRE-FLIGHT REPORT")
    print(f"Generated: {report['timestamp']}")
    print("=" * 60)

    # Ollama Models
    print("\n## AVAILABLE OLLAMA MODELS")
    print("-" * 40)
    if not models:
        print("  No models found (is Ollama running?)")
    elif "error" in models[0]:
        print(f"  Error: {models[0]['error']}")
    else:
        for m in models:
            print(f"  - {m['name']} ({m['size']})")
            caps = m.get("capabilities", {})
            if caps:
                print(f"    Context: {caps.get('context_window', 'unknown')}")
                print(f"    Good for: {', '.join(caps.get('recommended_for', []))}")
                print(f"    Avoid: {', '.join(caps.get('avoid_for', []))}")

    # Active Tasks
    print("\n## ACTIVE TASKS")
    print("-" * 40)
    if not tasks:
        print("  No active tasks in _handoff/")
    elif "error" in tasks[0]:
        print(f"  Error: {tasks[0]['error']}")
    else:
        for t in tasks:
            print(f"  - {t['file']}")
            print(f"    Objective: {t['objective'][:60]}..." if len(t.get('objective', '')) > 60 else f"    Objective: {t.get('objective', 'N/A')}")
            print(f"    Target: {t.get('target_file', 'N/A')}")
            print(f"    Recommended Model: {t.get('recommended_model', 'N/A')}")

    # Stall Reports
    print("\n## STALL REPORTS")
    print("-" * 40)
    if not stalls:
        print("  No stall reports - all clear")
    else:
        for s in stalls:
            print(f"  WARNING: {s['file']} exists")
            print(f"  Preview: {s['preview'][:200]}...")

    # System State
    print("\n## SYSTEM STATE")
    print("-" * 40)
    print(f"  Handoff dir: {'OK' if state['handoff_dir_exists'] else 'MISSING'}")
    print(f"  Drafts dir: {'OK' if state['drafts_dir_exists'] else 'MISSING'}")
    print(f"  Archive dir: {'OK' if state['archive_dir_exists'] else 'MISSING'}")
    print(f"  Transition log: {'OK' if state['transition_log_exists'] else 'MISSING'}")
    if "hubstate" in state:
        hs = state["hubstate"]
        print(f"  Hub state: {hs.get('current_state', 'unknown')}")
    print(f"  Archived tasks: {state.get('archived_task_count', 0)}")

    print("\n" + "=" * 60)
    print("Ready for execution. Run tasks sequentially.")
    print("=" * 60)


if __name__ == "__main__":
    as_json = "--json" in sys.argv
    print_report(as_json=as_json)
