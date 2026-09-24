"""Filesystem-based job store."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from ulid import ULID

from .schemas import JobRecord, JobState, WorkOrderSchema, HandoffSchema


class JobStore:
    """Filesystem-based job persistence."""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path.home() / ".deepseek-worker"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir = self.data_dir / "jobs"
        self.jobs_dir.mkdir(exist_ok=True)

    def _job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id

    def _job_file(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "job.json"

    def _events_file(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "events.jsonl"

    def create_job(
        self,
        idempotency_key: str,
        work_order: WorkOrderSchema,
        worktree_path: str,
        manager_identity: str = "unknown",
    ) -> JobRecord:
        """Create a new job record."""
        job_id = str(ULID())
        now = datetime.now(timezone.utc).isoformat()

        job = JobRecord(
            job_id=job_id,
            idempotency_key=idempotency_key,
            pt_task_id=work_order.pt_task_id,
            repo_path=work_order.repo_path,
            worktree_path=worktree_path,
            branch=work_order.branch,
            manager_identity=manager_identity,
            worker_model=work_order.constraints.get("model", "deepseek-v4-pro"),
            state=JobState.QUEUED,
            created_at=now,
            updated_at=now,
        )

        job_dir = self._job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        self._write_job(job)
        self._write_work_order(job_id, work_order)
        self._add_event(job_id, "job_created", {"idempotency_key": idempotency_key})

        return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieve a job by ID."""
        job_file = self._job_file(job_id)
        if not job_file.exists():
            return None

        with open(job_file) as f:
            data = json.load(f)
        return JobRecord.model_validate(data)

    def find_by_idempotency_key(self, key: str) -> Optional[JobRecord]:
        """Find a job by idempotency key."""
        for job_dir in self.jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue
            job = self.get_job(job_dir.name)
            if job and job.idempotency_key == key:
                return job
        return None

    def find_active_by_worktree(self, worktree_path: str) -> Optional[JobRecord]:
        """Find an active job using the same worktree."""
        active_states = {
            JobState.QUEUED,
            JobState.SPAWNING,
            JobState.RUNNING,
            JobState.HANDOFF_PENDING,
        }
        for job_dir in self.jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue
            job = self.get_job(job_dir.name)
            if (
                job
                and job.worktree_path == worktree_path
                and job.state in active_states
            ):
                return job
        return None

    def find_active_by_task(self, pt_task_id: int) -> Optional[JobRecord]:
        """Find an active job for the same pt task."""
        active_states = {
            JobState.QUEUED,
            JobState.SPAWNING,
            JobState.RUNNING,
            JobState.HANDOFF_PENDING,
        }
        for job_dir in self.jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue
            job = self.get_job(job_dir.name)
            if job and job.pt_task_id == pt_task_id and job.state in active_states:
                return job
        return None

    def update_job(self, job: JobRecord) -> None:
        """Update a job record."""
        job.updated_at = datetime.now(timezone.utc).isoformat()
        self._write_job(job)

    def transition_state(self, job_id: str, new_state: JobState, **event_data) -> None:
        """Transition job to a new state."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        old_state = job.state
        job.state = new_state

        if new_state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}:
            job.finished_at = datetime.now(timezone.utc).isoformat()

        self.update_job(job)
        self._add_event(
            job_id,
            "state_transition",
            {"from": old_state.value, "to": new_state.value, **event_data},
        )

    def _write_job(self, job: JobRecord) -> None:
        """Write job record to disk."""
        job_file = self._job_file(job.job_id)
        with open(job_file, "w") as f:
            json.dump(job.model_dump(), f, indent=2)

    def _write_work_order(self, job_id: str, work_order: WorkOrderSchema) -> None:
        """Write work order to job directory."""
        order_file = self._job_dir(job_id) / "work_order.json"
        with open(order_file, "w") as f:
            json.dump(work_order.model_dump(by_alias=True), f, indent=2)

    def get_work_order(self, job_id: str) -> Optional[WorkOrderSchema]:
        """Read work order for a job."""
        order_file = self._job_dir(job_id) / "work_order.json"
        if not order_file.exists():
            return None
        with open(order_file) as f:
            data = json.load(f)
        return WorkOrderSchema.model_validate(data)

    def write_handoff(self, job_id: str, handoff: HandoffSchema) -> None:
        """Write handoff result to job directory."""
        handoff_file = self._job_dir(job_id) / "handoff.json"
        with open(handoff_file, "w") as f:
            json.dump(handoff.model_dump(by_alias=True), f, indent=2)

        job = self.get_job(job_id)
        if job:
            job.handoff_path = str(handoff_file)
            job.handoff_sha = handoff.head_sha
            self.update_job(job)

    def get_handoff(self, job_id: str) -> Optional[HandoffSchema]:
        """Read handoff for a job."""
        handoff_file = self._job_dir(job_id) / "handoff.json"
        if not handoff_file.exists():
            return None
        with open(handoff_file) as f:
            data = json.load(f)
        return HandoffSchema.model_validate(data)

    def _add_event(self, job_id: str, event_type: str, data: dict) -> None:
        """Append an event to the job's event log."""
        events_file = self._events_file(job_id)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "data": data,
        }
        with open(events_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def get_events(self, job_id: str) -> list[dict]:
        """Read all events for a job."""
        events_file = self._events_file(job_id)
        if not events_file.exists():
            return []

        events = []
        with open(events_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events
