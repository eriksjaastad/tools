"""Typer CLI for project-owned seat-fit model evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv(Path(__file__).parent.parent / ".env")

app = typer.Typer(
    help="model-bench — compare models against project-owned seats and real fixtures."
)
console = Console()
RESULTS_DIR = Path(__file__).parent.parent / "results"


@app.command()
def run(
    projects_root: Path | None = typer.Option(  # noqa: B008
        None,
        help="Portfolio root containing immediate child project repositories.",
    ),
    project: str | None = typer.Option(
        None, help="Comma-separated project IDs to run."
    ),
    seat: str | None = typer.Option(
        None, help="Comma-separated seat IDs or project/seat IDs to run."
    ),
    models: str | None = typer.Option(
        None, help="Comma-separated registered candidate model IDs or names."
    ),
    split: str = typer.Option("dev", help="Fixture split: dev or sealed."),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Make model/judge calls. Without this flag, run is a dry plan.",
    ),
    no_judge: bool = typer.Option(
        False, "--no-judge", help="Skip quality judging; validity/latency/cost only."
    ),
    no_dirty: bool = typer.Option(
        False, "--no-dirty", help="Disable the required deterministic dirty variant."
    ),
    max_cases: int | None = typer.Option(
        None, min=1, help="Optional per-seat case cap for targeted runs."
    ),
):
    """Plan or execute a seat-fit sweep."""
    from .seat_bench import plan_seats, run_seats, select_seats

    root = _projects_root(projects_root)
    if split not in {"dev", "sealed"}:
        raise typer.BadParameter("split must be 'dev' or 'sealed'")
    selected = select_seats(
        root,
        project_ids=_csv_set(project),
        seat_ids=_csv_set(seat),
    )
    requested_models = _csv_list(models)
    plans = plan_seats(
        selected,
        split=split,
        model_ids=requested_models,
        include_dirty=not no_dirty,
        max_cases=max_cases,
    )
    _render_plan(plans, root)
    if not execute:
        console.print("\n[dim]Dry plan — no model or judge calls made.[/dim]")
        return

    completed = run_seats(
        selected,
        results_dir=RESULTS_DIR,
        split=split,
        model_ids=requested_models,
        include_dirty=not no_dirty,
        max_cases=max_cases,
        no_judge=no_judge,
    )
    console.print()
    table = Table(title="Seat-fit run results")
    table.add_column("Seat", style="bold")
    table.add_column("Status")
    table.add_column("Recommendation")
    table.add_column("Report")
    for scorecard, (_, markdown_path) in completed:
        manifest = scorecard.manifest
        table.add_row(
            f"{manifest.project_id}/{manifest.seat_id}",
            manifest.seat_status,
            scorecard.recommendation.status,
            markdown_path.name,
        )
    console.print(table)


@app.command("legacy-run", hidden=True)
def legacy_run(
    category: str | None = typer.Option(None),
    models: str | None = typer.Option(None),
    dry_run: bool = typer.Option(False, "--dry-run"),
    no_judge: bool = typer.Option(False, "--no-judge"),
):
    """Run the retired generic-category benchmark during migration only."""
    from .registry import get_models_by_ids
    from .runner import run_benchmark

    model_list = get_models_by_ids(_csv_list(models) or []) if models else None
    run_benchmark(
        models=model_list,
        category=category,
        dry_run=dry_run,
        no_judge=no_judge,
        console=console,
    )


@app.command()
def seats(
    projects_root: Path | None = typer.Option(None),  # noqa: B008
    project: str | None = typer.Option(None, help="Comma-separated project IDs."),
):
    """List strictly validated, project-owned seats."""
    from .seat_bench import select_seats

    root = _projects_root(projects_root)
    discovered = select_seats(root, project_ids=_csv_set(project))
    table = Table(title=f"Project model seats — {root}")
    table.add_column("Seat", style="bold")
    table.add_column("Status")
    table.add_column("Current pin")
    table.add_column("Output")
    table.add_column("Input")
    for definition in discovered:
        table.add_row(
            definition.qualified_id,
            definition.status.value,
            f"{definition.pin.provider}/{definition.pin.model}",
            str(definition.raw["output_contract"]["type"]),
            str(definition.raw["input_character"]),
        )
    console.print(table)
    frozen = sum(definition.is_frozen for definition in discovered)
    console.print(
        f"\n[dim]{len(discovered)} validated seats; "
        f"{frozen} FROZEN and excluded from optimization.[/dim]"
    )


@app.command()
def results(
    format: str = typer.Option("markdown", help="Output format: markdown or json."),
):
    """Show the latest seat report."""
    suffix = ".json" if format == "json" else ".md"
    reports = sorted(
        RESULTS_DIR.glob(f"seat_*{suffix}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        console.print("[dim]No seat reports found. Execute a seat run first.[/dim]")
        raise typer.Exit(1)
    content = reports[0].read_text()
    if format == "json":
        console.print_json(json.dumps(json.loads(content)))
    else:
        console.print(content)


@app.command()
def models():
    """List registered candidates and model-native capabilities."""
    from .registry import MODELS, is_ollama_available, list_ollama_models

    ollama_up = is_ollama_available()
    ollama_models = list_ollama_models() if ollama_up else []
    table = Table(title="Registered candidate models")
    table.add_column("Model ID", style="bold")
    table.add_column("Provider")
    table.add_column("Tier")
    table.add_column("Capabilities")
    table.add_column("Status")
    for model in MODELS:
        if model.provider == "ollama":
            name = model.id.removeprefix("ollama/")
            if not ollama_up:
                status = "[red]Ollama offline[/red]"
            elif any(name in installed for installed in ollama_models):
                status = "[green]Available[/green]"
            else:
                status = "[yellow]Not installed[/yellow]"
        else:
            status = "[green]Cloud[/green]"
        table.add_row(
            model.id,
            model.provider,
            model.tier,
            ", ".join(sorted(model.capabilities)),
            status,
        )
    console.print(table)


@app.command()
def estimate(
    projects_root: Path | None = typer.Option(None),  # noqa: B008
    project: str | None = typer.Option(None),
    seat: str | None = typer.Option(None),
    models: str | None = typer.Option(None),
):
    """Show call counts for a development seat sweep without API calls."""
    from .seat_bench import plan_seats, select_seats

    root = _projects_root(projects_root)
    plans = plan_seats(
        select_seats(
            root,
            project_ids=_csv_set(project),
            seat_ids=_csv_set(seat),
        ),
        model_ids=_csv_list(models),
    )
    _render_plan(plans, root)
    calls = sum(plan.cases * len(plan.candidate_model_ids) for plan in plans)
    judge_calls = sum(plan.cases for plan in plans if plan.status != "FROZEN")
    console.print(
        f"\n[dim]Planned candidate calls: {calls}; "
        f"batched seat-judge calls: {judge_calls}.[/dim]"
    )


def _projects_root(value: Path | None) -> Path:
    configured = value or (
        Path(os.environ["PROJECTS_ROOT"])
        if os.environ.get("PROJECTS_ROOT")
        else Path.home() / "projects"
    )
    resolved = configured.expanduser().resolve()
    if not resolved.is_dir():
        raise typer.BadParameter(
            f"projects root is not a readable directory: {resolved}"
        )
    return resolved


def _csv_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or None


def _csv_set(value: str | None) -> set[str] | None:
    parsed = _csv_list(value)
    return set(parsed) if parsed else None


def _render_plan(plans, root: Path) -> None:
    table = Table(title=f"Seat-fit plan — {root}")
    table.add_column("Seat", style="bold")
    table.add_column("Status")
    table.add_column("Split")
    table.add_column("Cases", justify="right")
    table.add_column("Dirty", justify="right")
    table.add_column("Models", justify="right")
    for plan in plans:
        table.add_row(
            plan.qualified_id,
            plan.status,
            plan.split,
            str(plan.cases),
            str(plan.dirty_cases),
            str(len(plan.candidate_model_ids)),
        )
    console.print(table)
    for plan in plans:
        if plan.frozen_reason:
            console.print(
                f"[yellow]{plan.qualified_id} FROZEN:[/yellow] {plan.frozen_reason}"
            )


if __name__ == "__main__":
    app()
