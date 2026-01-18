#!/usr/bin/env python3
"""
Terminal Dashboard for Agent Hub monitoring.

Usage:
    python -m src.dashboard
"""

import time
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.prompt import Prompt

from .message_bus import get_message_bus
from .cost_logger import get_cost_logger

console = Console()


def format_time_ago(timestamp_str: str) -> str:
    """Convert ISO timestamp to 'X seconds/minutes ago' format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - dt).total_seconds()

        if diff < 60:
            return f"{int(diff)}s ago"
        elif diff < 3600:
            return f"{int(diff / 60)}m ago"
        else:
            return f"{int(diff / 3600)}h ago"
    except Exception:
        return "unknown"


def build_agents_table(bus) -> Table:
    """Build table of active agents."""
    table = Table(title="Active Agents", expand=True)
    table.add_column("Agent ID", style="cyan")
    table.add_column("Last Seen", style="green")
    table.add_column("Progress", style="yellow")

    agents = bus.get_agent_status()
    for agent in agents:
        table.add_row(
            agent["agent_id"],
            format_time_ago(agent["last_seen"]),
            agent.get("progress") or "-"
        )

    if not agents:
        table.add_row("[dim]No agents connected[/dim]", "", "")

    return table


def build_questions_table(bus) -> Table:
    """Build table of pending questions."""
    table = Table(title="Pending Questions", expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("From", style="cyan")
    table.add_column("Question", style="white")
    table.add_column("Age", style="yellow")

    questions = bus.get_pending_questions()
    for i, q in enumerate(questions, 1):
        # Truncate long questions
        question_text = q["question"]
        if len(question_text) > 60:
            question_text = question_text[:57] + "..."

        table.add_row(
            str(i),
            q["subagent_id"],
            question_text,
            format_time_ago(q["created_at"])
        )

    if not questions:
        table.add_row("", "[dim]No pending questions[/dim]", "", "")

    return table


def build_cost_panel() -> Panel:
    """Build panel showing cost summary."""
    try:
        summary = get_cost_logger().session_summary()
        content = f"""
Total Calls: {summary['total_calls']}
Success Rate: {summary['success_rate']*100:.1f}%
Tokens In: {summary['total_tokens_in']:,}
Tokens Out: {summary['total_tokens_out']:,}
Total Tokens: {summary['total_tokens']:,}
"""
    except Exception:
        content = "No cost data available"

    return Panel(content.strip(), title="Session Costs", border_style="blue")


from .budget_manager import get_budget_manager


def build_budget_panel() -> Panel:
    """Build panel showing budget status."""
    try:
        budget = get_budget_manager()
        status = budget.get_status()

        # Color code based on usage
        session_pct = status["session_percent_used"]
        if session_pct > 90:
            session_style = "red"
        elif session_pct > 70:
            session_style = "yellow"
        else:
            session_style = "green"

        content = f"""
[{session_style}]Session: ${status['session_cloud_cost']:.4f} / ${status['session_limit']:.2f} ({session_pct:.0f}%)[/{session_style}]
Daily:   ${status['daily_cloud_cost']:.4f} / ${status['daily_limit']:.2f}

Local Calls: {status['local_calls']}
Local Tokens: {status['local_tokens']:,}

Cloud Escapes: {status['cloud_escapes']}
"""
        if budget.is_override_active():
            content = f"[bold yellow]⚠️ OVERRIDE ACTIVE[/bold yellow]\nReason: {budget._state.override_reason}\n\n" + content
    except Exception:

        content = "Budget data unavailable"

    return Panel(content.strip(), title="Budget Status", border_style="magenta")


def build_escapes_table() -> Table:
    """Build table of cloud escapes."""
    table = Table(title="Cloud Escapes (Fallbacks)", expand=True)
    table.add_column("Time", style="dim", width=8)
    table.add_column("Model", style="cyan")
    table.add_column("Task", style="yellow")
    table.add_column("Cost", style="red")

    try:
        budget = get_budget_manager()
        escapes = budget.get_cloud_escapes()

        for escape in escapes[-5:]:  # Last 5
            time_str = escape["timestamp"].split("T")[1][:8]
            table.add_row(
                time_str,
                escape["model"],
                escape.get("task_type", "-"),
                f"${escape['cost']:.4f}"
            )

        if not escapes:
            table.add_row("[dim]No cloud escapes[/dim]", "", "", "")
    except Exception:
        table.add_row("[dim]Data unavailable[/dim]", "", "", "")

    return table


def build_dashboard(bus) -> Layout:
    """Build the full dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )

    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="right", size=35)
    )

    layout["left"].split_column(
        Layout(build_agents_table(bus), name="agents"),
        Layout(build_questions_table(bus), name="questions"),
        Layout(build_escapes_table(), name="escapes", size=10)
    )

    layout["right"].split_column(
        Layout(build_cost_panel(), name="costs"),
        Layout(build_budget_panel(), name="budget")
    )

    layout["header"].update(
        Panel("[bold]Agent Hub Dashboard[/bold] | Press Ctrl+C to exit | 'a' to answer question",
              border_style="green")
    )

    layout["footer"].update(
        Panel(f"Last updated: {datetime.now().strftime('%H:%M:%S')}", border_style="dim")
    )

    return layout



def answer_question_interactive(bus) -> None:
    """Interactive prompt to answer a pending question."""
    questions = bus.get_pending_questions()

    if not questions:
        console.print("[yellow]No pending questions to answer.[/yellow]")
        return

    # Show questions
    console.print("\n[bold]Pending Questions:[/bold]")
    for i, q in enumerate(questions, 1):
        console.print(f"  {i}. [{q['subagent_id']}] {q['question']}")

    # Get selection
    try:
        selection = Prompt.ask("Select question number (or 'c' to cancel)")
        if selection.lower() == 'c':
            return

        idx = int(selection) - 1
        if 0 <= idx < len(questions):
            question = questions[idx]
            answer = Prompt.ask(f"Your answer to: {question['question'][:50]}...")

            if answer:
                bus.reply_to_worker(question["message_id"], answer)
                console.print(f"[green]Answer sent to {question['subagent_id']}[/green]")
        else:
            console.print("[red]Invalid selection[/red]")
    except ValueError:
        console.print("[red]Invalid input[/red]")


def run_dashboard(refresh_rate: float = 2.0) -> None:
    """Run the live dashboard."""
    bus = get_message_bus()

    console.print("[bold green]Starting Agent Hub Dashboard...[/bold green]")
    console.print("Press Ctrl+C to exit, 'a' to answer a question\n")

    try:
        with Live(build_dashboard(bus), refresh_per_second=1/refresh_rate, console=console) as live:
            while True:
                time.sleep(refresh_rate)
                live.update(build_dashboard(bus))
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


def main():
    """Entry point for dashboard."""
    parser = argparse.ArgumentParser(description="Agent Hub Dashboard")
    parser.add_argument("--refresh", type=float, default=2.0, help="Refresh rate in seconds")
    parser.add_argument("--answer", action="store_true", help="Answer a question and exit")
    args = parser.parse_args()

    bus = get_message_bus()
    if args.answer:
        answer_question_interactive(bus)
    else:
        run_dashboard(args.refresh)


if __name__ == "__main__":
    main()
