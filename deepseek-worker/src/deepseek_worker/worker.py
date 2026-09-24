"""Worker subprocess implementation."""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schemas import HandoffSchema, HandoffStatus, WorkOrderSchema


class StubWorker:
    """Stub worker that proves isolation and finalize path."""

    def __init__(self, job_id: str, work_order: WorkOrderSchema, job_dir: Path):
        self.job_id = job_id
        self.work_order = work_order
        self.job_dir = job_dir

    def run(self) -> HandoffSchema:
        """Execute stub work and produce handoff."""
        time.sleep(2)

        head_sha = self._get_head_sha()

        handoff = HandoffSchema(
            job_id=self.job_id,
            pt_task_id=self.work_order.pt_task_id,
            status=HandoffStatus.COMPLETED,
            branch=self.work_order.branch,
            head_sha=head_sha or "0" * 40,
            notes="Stub worker completed successfully",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

        handoff_path = self.job_dir / "handoff.json"
        with open(handoff_path, "w") as f:
            json.dump(handoff.model_dump(by_alias=True), f, indent=2)

        return handoff

    def _get_head_sha(self) -> Optional[str]:
        """Get current HEAD SHA from the repo."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.work_order.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return None


def run_stub_worker(job_id: str, work_order_path: Path, job_dir: Path) -> int:
    """Entry point for stub worker subprocess."""
    with open(work_order_path) as f:
        order_data = json.load(f)

    work_order = WorkOrderSchema.model_validate(order_data)
    worker = StubWorker(job_id, work_order, job_dir)

    try:
        worker.run()
        return 0
    except Exception as e:
        error_handoff = HandoffSchema(
            job_id=job_id,
            pt_task_id=work_order.pt_task_id,
            status=HandoffStatus.FAILED,
            branch=work_order.branch,
            head_sha="0" * 40,
            notes=f"Worker failed: {e}",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        handoff_path = job_dir / "handoff.json"
        with open(handoff_path, "w") as f:
            json.dump(error_handoff.model_dump(by_alias=True), f, indent=2)
        return 1
