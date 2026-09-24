"""Test schema validation."""

import json
from datetime import datetime, timezone

import pytest

from deepseek_worker.schemas import (
    HandoffSchema,
    HandoffStatus,
    WorkOrderSchema,
    JobState,
    JobRecord,
)


def test_work_order_minimal():
    """Test minimal valid work order."""
    order = WorkOrderSchema(
        pt_task_id=1234,
        goal="Test goal",
        repo_path="/tmp/test",
        branch="test-branch",
    )
    assert order.pt_task_id == 1234
    assert order.base_ref == "main"
    assert order.off_peak_policy == "require_off_peak"


def test_work_order_with_constraints():
    """Test work order with constraints."""
    order = WorkOrderSchema(
        pt_task_id=1234,
        goal="Test goal",
        repo_path="/tmp/test",
        branch="test-branch",
        constraints={"model": "deepseek-v4-pro", "max_cost_usd": 1.0},
    )
    assert order.constraints["model"] == "deepseek-v4-pro"
    assert order.constraints["max_cost_usd"] == 1.0


def test_work_order_schema_alias():
    """Test that schema field uses alias."""
    order = WorkOrderSchema(
        pt_task_id=1234,
        goal="Test",
        repo_path="/tmp",
        branch="test",
    )
    dumped = order.model_dump(by_alias=True)
    assert "schema" in dumped
    assert dumped["schema"] == "deepseek-worker.work_order.v1"


def test_handoff_minimal():
    """Test minimal valid handoff."""
    handoff = HandoffSchema(
        job_id="abc123",
        pt_task_id=1234,
        status=HandoffStatus.COMPLETED,
        branch="test-branch",
        head_sha="a" * 40,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    assert handoff.status == HandoffStatus.COMPLETED
    assert len(handoff.head_sha) == 40


def test_handoff_with_details():
    """Test handoff with file changes and checks."""
    handoff = HandoffSchema(
        job_id="abc123",
        pt_task_id=1234,
        status=HandoffStatus.COMPLETED,
        branch="test-branch",
        head_sha="b" * 40,
        files_changed=[{"path": "test.py", "change": "M"}],
        checks_run=[{"cmd": "pytest", "exit_code": 0, "summary": "All tests passed"}],
        notes="Completed successfully",
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    assert len(handoff.files_changed) == 1
    assert len(handoff.checks_run) == 1
    assert handoff.notes == "Completed successfully"


def test_handoff_schema_alias():
    """Test that handoff schema field uses alias."""
    handoff = HandoffSchema(
        job_id="abc",
        pt_task_id=123,
        status=HandoffStatus.COMPLETED,
        branch="test",
        head_sha="c" * 40,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    dumped = handoff.model_dump(by_alias=True)
    assert "schema" in dumped
    assert dumped["schema"] == "deepseek-worker.handoff.v1"


def test_job_record():
    """Test job record creation."""
    now = datetime.now(timezone.utc).isoformat()
    job = JobRecord(
        job_id="test-123",
        idempotency_key="key123",
        pt_task_id=1234,
        repo_path="/tmp/test",
        worktree_path="/tmp/test",
        branch="test-branch",
        state=JobState.QUEUED,
        created_at=now,
        updated_at=now,
    )
    assert job.job_id == "test-123"
    assert job.state == JobState.QUEUED
    assert job.worker_model == "deepseek-v4-pro"


def test_job_state_enum():
    """Test job state enum values."""
    assert JobState.QUEUED.value == "queued"
    assert JobState.RUNNING.value == "running"
    assert JobState.COMPLETED.value == "completed"
    assert JobState.FAILED.value == "failed"


def test_handoff_status_enum():
    """Test handoff status enum values."""
    assert HandoffStatus.COMPLETED.value == "completed"
    assert HandoffStatus.FAILED.value == "failed"
    assert HandoffStatus.BLOCKED.value == "blocked"
    assert HandoffStatus.PARTIAL.value == "partial"
