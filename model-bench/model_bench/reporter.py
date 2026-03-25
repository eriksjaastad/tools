"""Renders matrix as terminal table (rich) or markdown."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .scorer import Matrix


def render_table(matrix: Matrix, console: Console | None = None) -> None:
    """Print rich table to terminal."""
    if console is None:
        console = Console()

    # ── Overall summary table ─────────────────────────────────────────────
    table = Table(title="Model Benchmark Results", show_lines=True)
    table.add_column("Model", style="bold")
    table.add_column("Tier", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Cost", justify="right")

    for cat in matrix.categories:
        table.add_column(cat.replace("_", " ").title(), justify="right")

    # Sort by overall score descending
    sorted_models = sorted(matrix.models.values(), key=lambda m: m.overall_score, reverse=True)

    for m in sorted_models:
        row = [
            m.display_name,
            m.tier,
            f"{m.overall_score:.1f}/5",
            f"{m.overall_latency_ms:.0f}ms",
            f"${m.total_cost_usd:.4f}",
        ]
        for cat in matrix.categories:
            cs = m.categories.get(cat)
            if cs and cs.num_tasks > 0:
                err_flag = f" ({cs.errors}err)" if cs.errors else ""
                row.append(f"{cs.avg_score:.1f}{err_flag}")
            else:
                row.append("—")
        table.add_row(*row)

    console.print(table)


def render_markdown(matrix: Matrix) -> str:
    """Render matrix as markdown string."""
    lines = ["# Model Benchmark Results", ""]
    lines.append(f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")

    # Header
    cats = matrix.categories
    header = "| Model | Tier | Score | Latency | Cost |"
    sep = "|-------|------|-------|---------|------|"
    for cat in cats:
        header += f" {cat.replace('_', ' ').title()} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    sorted_models = sorted(matrix.models.values(), key=lambda m: m.overall_score, reverse=True)
    for m in sorted_models:
        row = f"| {m.display_name} | {m.tier} | {m.overall_score:.1f}/5 | {m.overall_latency_ms:.0f}ms | ${m.total_cost_usd:.4f} |"
        for cat in cats:
            cs = m.categories.get(cat)
            if cs and cs.num_tasks > 0:
                row += f" {cs.avg_score:.1f} |"
            else:
                row += " — |"
        lines.append(row)

    lines.append("")
    return "\n".join(lines)


def save_results(matrix: Matrix, results_dir: Path) -> tuple[Path, Path]:
    """Save run results as JSON and markdown. Returns (json_path, md_path)."""
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # JSON
    json_path = results_dir / f"run_{timestamp}.json"
    data = {
        "timestamp": timestamp,
        "categories": matrix.categories,
        "models": {},
    }
    for mid, summary in matrix.models.items():
        data["models"][mid] = {
            "display_name": summary.display_name,
            "tier": summary.tier,
            "overall_score": summary.overall_score,
            "overall_latency_ms": summary.overall_latency_ms,
            "total_cost_usd": summary.total_cost_usd,
            "categories": {
                cat: {
                    "avg_score": cs.avg_score,
                    "avg_latency_ms": cs.avg_latency_ms,
                    "avg_cost_usd": cs.avg_cost_usd,
                    "num_tasks": cs.num_tasks,
                    "errors": cs.errors,
                }
                for cat, cs in summary.categories.items()
            },
        }
    json_path.write_text(json.dumps(data, indent=2))

    # Markdown
    md_path = results_dir / f"run_{timestamp}.md"
    md_path.write_text(render_markdown(matrix))

    return json_path, md_path


def load_latest_results(results_dir: Path) -> dict | None:
    """Load the most recent results JSON."""
    json_files = sorted(results_dir.glob("run_*.json"), reverse=True)
    if not json_files:
        return None
    return json.loads(json_files[0].read_text())
