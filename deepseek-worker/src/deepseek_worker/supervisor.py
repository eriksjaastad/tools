"""Process supervisor for worker execution."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .schemas import JobState, WorkOrderSchema
from .store import JobStore


class WorkerSupervisor:
    """Manages worker process lifecycle."""

    def __init__(self, store: JobStore):
        self.store = store

    def spawn_worker(self, job_id: str) -> bool:
        """Spawn a worker subprocess for the given job."""
        job = self.store.get_job(job_id)
        if not job:
            return False

        work_order = self.store.get_work_order(job_id)
        if not work_order:
            return False

        self.store.transition_state(job_id, JobState.SPAWNING)

        job_dir = self.store.jobs_dir / job_id
        work_order_path = job_dir / "work_order.json"
        stdout_log = job_dir / "worker.stdout.log"

        try:
            with open(stdout_log, "w") as log_file:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "deepseek_worker.worker_main",
                        job_id,
                        str(work_order_path),
                        str(job_dir),
                    ],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )

                job.pid = process.pid
                self.store.update_job(job)
                self.store.transition_state(job_id, JobState.RUNNING, pid=process.pid)

            return True

        except Exception as e:
            self.store.transition_state(
                job_id, JobState.FAILED, error=str(e), reason="spawn_failed"
            )
            return False

    def finalize_job(self, job_id: str) -> bool:
        """Check for handoff and finalize job state."""
        job = self.store.get_job(job_id)
        if not job:
            return False

        if job.state != JobState.RUNNING:
            return False

        handoff = self.store.get_handoff(job_id)
        if not handoff:
            return False

        job.handoff_path = str(self.store.jobs_dir / job_id / "handoff.json")
        job.handoff_sha = handoff.head_sha
        self.store.update_job(job)

        if handoff.status.value == "completed":
            self.store.transition_state(job_id, JobState.COMPLETED)
        elif handoff.status.value == "failed":
            self.store.transition_state(job_id, JobState.FAILED)
        elif handoff.status.value == "blocked":
            self.store.transition_state(job_id, JobState.BLOCKED)
        else:
            self.store.transition_state(job_id, JobState.COMPLETED)

        return True

    def check_completion(self, job_id: str) -> Optional[str]:
        """Check if job has completed and return final state."""
        job = self.store.get_job(job_id)
        if not job:
            return None

        if job.state == JobState.RUNNING:
            if self.store.get_handoff(job_id):
                self.finalize_job(job_id)
                job = self.store.get_job(job_id)

        if job.state in {
            JobState.COMPLETED,
            JobState.FAILED,
            JobState.BLOCKED,
            JobState.CANCELLED,
            JobState.REJECTED,
        }:
            return job.state.value

        return None
