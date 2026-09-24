"""CLI commands for deepseek-worker."""

import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional

import click
import yaml

from .schemas import JobState, WorkOrderSchema
from .store import JobStore
from .supervisor import WorkerSupervisor


def get_store(data_dir: Optional[str] = None) -> JobStore:
    """Get or create job store."""
    return JobStore(data_dir=data_dir)


def generate_idempotency_key(work_order: WorkOrderSchema) -> str:
    """Generate idempotency key from work order content."""
    content = f"{work_order.pt_task_id}:{work_order.repo_path}:{work_order.branch}:{work_order.goal}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


@click.group()
@click.version_option(package_name="deepseek-worker")
def main():
    """DeepSeek coding-worker harness CLI."""
    pass


@main.command()
@click.option("--order", required=True, type=click.Path(exists=True), help="Work order YAML/JSON file")
@click.option("--idempotency-key", help="Custom idempotency key")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--data-dir", envvar="DSW_DATA_DIR", help="Data directory override")
def submit(order: str, idempotency_key: Optional[str], output_json: bool, data_dir: Optional[str]):
    """Submit a work order and spawn a worker."""
    order_path = Path(order)

    if order_path.suffix in {".yaml", ".yml"}:
        with open(order_path) as f:
            order_data = yaml.safe_load(f)
    else:
        with open(order_path) as f:
            order_data = json.load(f)

    try:
        work_order = WorkOrderSchema.model_validate(order_data)
    except Exception as e:
        click.echo(f"Error: Invalid work order: {e}", err=True)
        sys.exit(2)

    if not idempotency_key:
        idempotency_key = generate_idempotency_key(work_order)

    store = get_store(data_dir)
    supervisor = WorkerSupervisor(store)

    existing = store.find_by_idempotency_key(idempotency_key)
    if existing:
        if output_json:
            click.echo(json.dumps({"job_id": existing.job_id, "reused": True}))
        else:
            click.echo(f"Job already exists: {existing.job_id}")
        sys.exit(0)

    active_task = store.find_active_by_task(work_order.pt_task_id)
    if active_task:
        if output_json:
            click.echo(
                json.dumps(
                    {
                        "error": "conflict",
                        "reason": "active_job_for_task",
                        "existing_job_id": active_task.job_id,
                    }
                )
            )
        else:
            click.echo(
                f"Error: Active job {active_task.job_id} already exists for task {work_order.pt_task_id}",
                err=True,
            )
        sys.exit(3)

    worktree_path = work_order.repo_path
    active_worktree = store.find_active_by_worktree(worktree_path)
    if active_worktree:
        if output_json:
            click.echo(
                json.dumps(
                    {
                        "error": "conflict",
                        "reason": "active_job_for_worktree",
                        "existing_job_id": active_worktree.job_id,
                    }
                )
            )
        else:
            click.echo(
                f"Error: Active job {active_worktree.job_id} already exists for worktree {worktree_path}",
                err=True,
            )
        sys.exit(3)

    job = store.create_job(
        idempotency_key=idempotency_key,
        work_order=work_order,
        worktree_path=worktree_path,
        manager_identity="unknown",
    )

    if not supervisor.spawn_worker(job.job_id):
        if output_json:
            click.echo(json.dumps({"error": "spawn_failed", "job_id": job.job_id}))
        else:
            click.echo(f"Error: Failed to spawn worker for job {job.job_id}", err=True)
        sys.exit(1)

    if output_json:
        click.echo(json.dumps({"job_id": job.job_id}))
    else:
        click.echo(job.job_id)


@main.command()
@click.argument("job_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--data-dir", envvar="DSW_DATA_DIR", help="Data directory override")
def status(job_id: str, output_json: bool, data_dir: Optional[str]):
    """Get status of a job."""
    store = get_store(data_dir)
    supervisor = WorkerSupervisor(store)

    supervisor.check_completion(job_id)

    job = store.get_job(job_id)
    if not job:
        if output_json:
            click.echo(json.dumps({"error": "not_found"}))
        else:
            click.echo(f"Error: Job {job_id} not found", err=True)
        sys.exit(4)

    if output_json:
        output = job.model_dump()
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"Job ID: {job.job_id}")
        click.echo(f"State: {job.state.value}")
        click.echo(f"PT Task: {job.pt_task_id}")
        click.echo(f"Branch: {job.branch}")
        click.echo(f"Created: {job.created_at}")
        if job.started_at:
            click.echo(f"Started: {job.started_at}")
        if job.finished_at:
            click.echo(f"Finished: {job.finished_at}")
        if job.handoff_path:
            click.echo(f"Handoff: {job.handoff_path}")
            click.echo(f"Head SHA: {job.handoff_sha}")


@main.command()
@click.argument("job_id")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--data-dir", envvar="DSW_DATA_DIR", help="Data directory override")
def logs(job_id: str, follow: bool, data_dir: Optional[str]):
    """Show logs for a job."""
    store = get_store(data_dir)
    job = store.get_job(job_id)

    if not job:
        click.echo(f"Error: Job {job_id} not found", err=True)
        sys.exit(4)

    events = store.get_events(job_id)
    click.echo("=== Events ===")
    for event in events:
        click.echo(f"[{event['timestamp']}] {event['type']}: {event['data']}")

    job_dir = store.jobs_dir / job_id
    stdout_log = job_dir / "worker.stdout.log"

    if stdout_log.exists():
        click.echo("\n=== Worker Output ===")
        with open(stdout_log) as f:
            click.echo(f.read())

    if follow and job.state in {JobState.RUNNING, JobState.SPAWNING}:
        click.echo("\n=== Following (Ctrl+C to stop) ===")
        try:
            with open(stdout_log) as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        click.echo(line, nl=False)
                    else:
                        time.sleep(0.5)
                        job = store.get_job(job_id)
                        if job.state not in {JobState.RUNNING, JobState.SPAWNING}:
                            break
        except KeyboardInterrupt:
            pass


@main.command()
@click.argument("job_id")
@click.option("--data-dir", envvar="DSW_DATA_DIR", help="Data directory override")
def cancel(job_id: str, data_dir: Optional[str]):
    """Cancel a running job."""
    store = get_store(data_dir)
    job = store.get_job(job_id)

    if not job:
        click.echo(f"Error: Job {job_id} not found", err=True)
        sys.exit(4)

    if job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
        click.echo(f"Job {job_id} is already in terminal state: {job.state.value}")
        sys.exit(0)

    store.transition_state(job_id, JobState.CANCELLED, reason="user_requested")
    click.echo(f"Job {job_id} marked as cancelled")


@main.command()
@click.option("--data-dir", envvar="DSW_DATA_DIR", help="Data directory override")
def doctor(data_dir: Optional[str]):
    """Check system health and configuration."""
    store = get_store(data_dir)

    click.echo("=== DeepSeek Worker Doctor ===")
    click.echo(f"Data directory: {store.data_dir}")
    click.echo(f"Jobs directory: {store.jobs_dir}")
    click.echo(f"Data dir exists: {store.data_dir.exists()}")
    click.echo(f"Jobs dir exists: {store.jobs_dir.exists()}")

    job_count = len(list(store.jobs_dir.iterdir())) if store.jobs_dir.exists() else 0
    click.echo(f"Total jobs: {job_count}")

    click.echo("\n✓ Store is accessible")


if __name__ == "__main__":
    main()
