"""Orchestrates: load tasks → call models → judge → score → save."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console

from .caller import CallResult, call_model, close as close_caller
from .judge import JudgeScore, judge_responses
from .registry import ModelEntry, estimate_cost, get_enabled_models
from .scorer import Matrix, build_matrix
from .reporter import render_table, save_results


# ── Task loading ──────────────────────────────────────────────────────────────

TASKS_DIR = Path(__file__).parent.parent / "tasks"
RESULTS_DIR = Path(__file__).parent.parent / "results"


@dataclass
class TaskVariant:
    id: str
    prompt: str


@dataclass
class Task:
    id: str
    name: str
    description: str
    category: str
    variants: list[TaskVariant]
    rubric: list[dict]
    max_score: int
    timeout_seconds: int


def load_tasks(category: str | None = None) -> list[Task]:
    """Load task definitions from YAML files."""
    tasks = []
    yaml_files = sorted(TASKS_DIR.glob("*.yaml"))

    for path in yaml_files:
        data = yaml.safe_load(path.read_text())
        cat = data["category"]

        if category and cat != category:
            continue

        for t in data["tasks"]:
            tasks.append(
                Task(
                    id=t["id"],
                    name=t["name"],
                    description=t["description"],
                    category=cat,
                    variants=[TaskVariant(id=v["id"], prompt=v["prompt"]) for v in t["variants"]],
                    rubric=t["rubric"],
                    max_score=t["max_score"],
                    timeout_seconds=t.get("timeout_seconds", 30),
                )
            )

    return tasks


# ── Run orchestration ─────────────────────────────────────────────────────────


def run_benchmark(
    models: list[ModelEntry] | None = None,
    category: str | None = None,
    dry_run: bool = False,
    no_judge: bool = False,
    console: Console | None = None,
) -> Matrix | None:
    """Run the full benchmark sweep."""
    load_dotenv(Path(__file__).parent.parent / ".env")

    if console is None:
        console = Console()

    models = models or get_enabled_models()
    tasks = load_tasks(category)

    if not tasks:
        console.print("[red]No tasks found.[/red]")
        return None

    # Count totals
    total_variants = sum(len(t.variants) for t in tasks)
    total_calls = len(models) * total_variants
    categories = sorted(set(t.category for t in tasks))

    # Estimate cost
    avg_input_tokens = 500  # rough estimate per prompt
    avg_output_tokens = 800  # rough estimate per response
    est_cost = sum(
        estimate_cost(m, avg_input_tokens, avg_output_tokens) * total_variants for m in models
    )

    console.print(f"\n[bold]Benchmark Plan[/bold]")
    console.print(f"  Models:     {len(models)} ({', '.join(m.display_name for m in models)})")
    console.print(f"  Tasks:      {len(tasks)} across {len(categories)} categories")
    console.print(f"  Variants:   {total_variants}")
    console.print(f"  Total calls: {total_calls}")
    console.print(f"  Est. cost:  ${est_cost:.4f}")
    if not no_judge:
        console.print(f"  Judge:      Opus (via subscription)")
    console.print()

    if dry_run:
        console.print("[dim]Dry run — no calls made.[/dim]")
        return None

    # ── Execute ───────────────────────────────────────────────────────────
    all_call_results: list[CallResult] = []
    all_judge_scores: list[JudgeScore] = []

    for task in tasks:
        for variant in task.variants:
            console.print(f"[bold]{task.category}[/bold] / {task.name} / {variant.id}")

            # Collect responses from all models
            responses: dict[str, str] = {}

            for i, model in enumerate(models):
                console.print(f"  {model.display_name}...", end=" ")
                result = call_model(model, variant.prompt, task.timeout_seconds)

                # Tag with key for scorer (model, task, variant, category)
                result._key = (model.id, task.id, variant.id, task.category)  # type: ignore[attr-defined]
                all_call_results.append(result)

                if result.error:
                    console.print(f"[red]ERROR[/red] ({result.latency_ms}ms)")
                else:
                    console.print(f"[green]OK[/green] ({result.latency_ms}ms, {result.tokens_out}tok)")
                    responses[model.id] = result.response

                # Brief pause between cloud calls to avoid rate limiting
                if model.provider != "ollama" and i < len(models) - 1:
                    time.sleep(1.0)

            # Judge this task+variant
            if not no_judge and responses:
                console.print(f"  [dim]Judging with Opus...[/dim]", end=" ")
                scores = judge_responses(
                    task_id=task.id,
                    variant_id=variant.id,
                    category=task.category,
                    prompt=variant.prompt,
                    rubric=task.rubric,
                    max_score=task.max_score,
                    responses=responses,
                )
                all_judge_scores.extend(scores)
                avg = sum(s.overall for s in scores) / len(scores) if scores else 0
                console.print(f"[dim]avg {avg:.1f}/5[/dim]")

    # ── Build matrix and report ───────────────────────────────────────────
    close_caller()

    matrix = build_matrix(
        judge_scores=all_judge_scores,
        call_results=all_call_results,
        models=models,
        categories=categories,
    )

    console.print()
    render_table(matrix, console)

    json_path, md_path = save_results(matrix, RESULTS_DIR)
    console.print(f"\n[dim]Results saved: {json_path.name}, {md_path.name}[/dim]")

    return matrix
