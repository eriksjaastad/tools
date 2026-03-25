"""Typer CLI: run, results, models, estimate."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="model-bench — benchmark worker models, score with Opus.")
console = Console()


@app.command()
def run(
    category: str | None = typer.Option(None, help="Run only one category (e.g. code_generation)"),
    models: str | None = typer.Option(None, help="Comma-separated model IDs or names to test"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan + cost estimate, no calls"),
    no_judge: bool = typer.Option(False, "--no-judge", help="Skip Opus scoring, latency only"),
):
    """Run benchmark sweep."""
    from .registry import get_enabled_models, get_models_by_ids
    from .runner import run_benchmark

    model_list = None
    if models:
        ids = [m.strip() for m in models.split(",")]
        model_list = get_models_by_ids(ids)
        if not model_list:
            console.print(f"[red]No models matched: {models}[/red]")
            raise typer.Exit(1)

    run_benchmark(
        models=model_list,
        category=category,
        dry_run=dry_run,
        no_judge=no_judge,
        console=console,
    )


@app.command()
def results(
    format: str = typer.Option("table", help="Output format: table or markdown"),
):
    """Show latest benchmark results."""
    from .reporter import load_latest_results
    from .scorer import CategoryScore, Matrix, ModelSummary

    results_dir = Path(__file__).parent.parent / "results"
    data = load_latest_results(results_dir)

    if not data:
        console.print("[dim]No results found. Run a benchmark first.[/dim]")
        raise typer.Exit(1)

    # Reconstruct matrix from JSON
    matrix = Matrix(categories=data.get("categories", []))
    for mid, mdata in data.get("models", {}).items():
        summary = ModelSummary(
            model_id=mid,
            display_name=mdata["display_name"],
            tier=mdata["tier"],
            overall_score=mdata["overall_score"],
            overall_latency_ms=mdata["overall_latency_ms"],
            total_cost_usd=mdata["total_cost_usd"],
        )
        for cat, cdata in mdata.get("categories", {}).items():
            summary.categories[cat] = CategoryScore(
                avg_score=cdata["avg_score"],
                avg_latency_ms=cdata["avg_latency_ms"],
                avg_cost_usd=cdata["avg_cost_usd"],
                num_tasks=cdata["num_tasks"],
                errors=cdata["errors"],
            )
        matrix.models[mid] = summary

    if format == "markdown":
        from .reporter import render_markdown

        console.print(render_markdown(matrix))
    else:
        from .reporter import render_table

        render_table(matrix, console)


@app.command()
def models():
    """List registered models and their availability."""
    from .registry import MODELS, is_ollama_available, list_ollama_models

    ollama_up = is_ollama_available()
    ollama_models = list_ollama_models() if ollama_up else []

    table = Table(title="Registered Models")
    table.add_column("Model ID", style="bold")
    table.add_column("Display Name")
    table.add_column("Provider")
    table.add_column("Tier")
    table.add_column("Enabled")
    table.add_column("Status")

    for m in MODELS:
        if m.provider == "ollama":
            name = m.id.removeprefix("ollama/")
            if not ollama_up:
                status = "[red]Ollama offline[/red]"
            elif any(name in om for om in ollama_models):
                status = "[green]Available[/green]"
            else:
                status = "[yellow]Not installed[/yellow]"
        else:
            status = "[green]Cloud[/green]"

        table.add_row(
            m.id,
            m.display_name,
            m.provider,
            m.tier,
            "[green]Yes[/green]" if m.enabled else "[red]No[/red]",
            status,
        )

    console.print(table)
    if ollama_up:
        console.print(f"\n[dim]Ollama: {len(ollama_models)} models installed[/dim]")
    else:
        console.print(f"\n[yellow]Ollama not reachable[/yellow]")


@app.command()
def estimate():
    """Show cost estimate for a full benchmark run."""
    from .registry import get_enabled_models, estimate_cost
    from .runner import load_tasks

    models_list = get_enabled_models()
    tasks = load_tasks()
    total_variants = sum(len(t.variants) for t in tasks)

    avg_input = 500
    avg_output = 800

    table = Table(title="Cost Estimate (Full Run)")
    table.add_column("Model", style="bold")
    table.add_column("Tier")
    table.add_column("Calls", justify="right")
    table.add_column("Est. Cost", justify="right")

    total_cost = 0.0
    for m in models_list:
        cost = estimate_cost(m, avg_input, avg_output) * total_variants
        total_cost += cost
        table.add_row(
            m.display_name,
            m.tier,
            str(total_variants),
            f"${cost:.4f}" if cost > 0 else "FREE",
        )

    table.add_row("", "", "", f"[bold]${total_cost:.4f}[/bold]", style="bold")
    console.print(table)
    console.print(f"\n[dim]{len(tasks)} tasks × ~{total_variants / len(tasks):.1f} variants = {total_variants} calls per model[/dim]")
    console.print(f"[dim]Judge calls (Opus via subscription): {total_variants} — no API cost[/dim]")


if __name__ == "__main__":
    app()
