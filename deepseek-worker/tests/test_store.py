"""Test job store operations."""

import tempfile
from pathlib import Path

import pytest

from deepseek_worker.schemas import (
    JobState,
    WorkOrderSchema,
    HandoffSchema,
    HandoffStatus,
)
from deepseek_worker.store import JobStore
from datetime import datetime, timezone


@pytest.fixture
def temp_store():
    """Create a temporary job store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield JobStore(data_dir=tmpdir)


@pytest.fixture
def sample_work_order():
    """Create a sample work order."""
    return WorkOrderSchema(
        pt_task_id=1234,
        goal="Test implementation",
        repo_path="/tmp/test-repo",
        branch="test-branch",
        acceptance_criteria=["Tests pass"],
    )


def test_store_initialization(temp_store):
    """Test that store initializes correctly."""
    assert temp_store.data_dir.exists()
    assert temp_store.jobs_dir.exists()


def test_create_job(temp_store, sample_work_order):
    """Test job creation."""
    job = temp_store.create_job(
        idempotency_key="test-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    assert job.job_id is not None
    assert job.idempotency_key == "test-key-1"
    assert job.pt_task_id == 1234
    assert job.state == JobState.QUEUED
    assert job.created_at is not None


def test_get_job(temp_store, sample_work_order):
    """Test job retrieval."""
    job = temp_store.create_job(
        idempotency_key="test-key-2",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    retrieved = temp_store.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == job.job_id
    assert retrieved.state == JobState.QUEUED


def test_find_by_idempotency_key(temp_store, sample_work_order):
    """Test finding job by idempotency key."""
    job = temp_store.create_job(
        idempotency_key="unique-key-123",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    found = temp_store.find_by_idempotency_key("unique-key-123")
    assert found is not None
    assert found.job_id == job.job_id

    not_found = temp_store.find_by_idempotency_key("nonexistent")
    assert not_found is None


def test_find_active_by_task(temp_store, sample_work_order):
    """Test finding active job by task ID."""
    job = temp_store.create_job(
        idempotency_key="task-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    found = temp_store.find_active_by_task(1234)
    assert found is not None
    assert found.job_id == job.job_id

    temp_store.transition_state(job.job_id, JobState.COMPLETED)

    found_after_complete = temp_store.find_active_by_task(1234)
    assert found_after_complete is None


def test_find_active_by_worktree(temp_store, sample_work_order):
    """Test finding active job by worktree path."""
    job = temp_store.create_job(
        idempotency_key="worktree-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/worktree-1",
    )

    found = temp_store.find_active_by_worktree("/tmp/worktree-1")
    assert found is not None
    assert found.job_id == job.job_id

    not_found = temp_store.find_active_by_worktree("/tmp/other-worktree")
    assert not_found is None


def test_state_transition(temp_store, sample_work_order):
    """Test job state transitions."""
    job = temp_store.create_job(
        idempotency_key="state-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    assert job.state == JobState.QUEUED

    temp_store.transition_state(job.job_id, JobState.SPAWNING)
    job = temp_store.get_job(job.job_id)
    assert job.state == JobState.SPAWNING

    temp_store.transition_state(job.job_id, JobState.RUNNING)
    job = temp_store.get_job(job.job_id)
    assert job.state == JobState.RUNNING

    temp_store.transition_state(job.job_id, JobState.COMPLETED)
    job = temp_store.get_job(job.job_id)
    assert job.state == JobState.COMPLETED
    assert job.finished_at is not None


def test_work_order_persistence(temp_store, sample_work_order):
    """Test work order read/write."""
    job = temp_store.create_job(
        idempotency_key="order-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    retrieved_order = temp_store.get_work_order(job.job_id)
    assert retrieved_order is not None
    assert retrieved_order.pt_task_id == 1234
    assert retrieved_order.goal == "Test implementation"


def test_handoff_persistence(temp_store, sample_work_order):
    """Test handoff read/write."""
    job = temp_store.create_job(
        idempotency_key="handoff-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    handoff = HandoffSchema(
        job_id=job.job_id,
        pt_task_id=1234,
        status=HandoffStatus.COMPLETED,
        branch="test-branch",
        head_sha="a" * 40,
        notes="Test completed",
        finished_at=datetime.now(timezone.utc).isoformat(),
    )

    temp_store.write_handoff(job.job_id, handoff)

    retrieved_handoff = temp_store.get_handoff(job.job_id)
    assert retrieved_handoff is not None
    assert retrieved_handoff.status == HandoffStatus.COMPLETED
    assert retrieved_handoff.notes == "Test completed"

    job = temp_store.get_job(job.job_id)
    assert job.handoff_path is not None
    assert job.handoff_sha == "a" * 40


def test_event_log(temp_store, sample_work_order):
    """Test event logging."""
    job = temp_store.create_job(
        idempotency_key="event-key-1",
        work_order=sample_work_order,
        worktree_path="/tmp/test-repo",
    )

    events = temp_store.get_events(job.job_id)
    assert len(events) >= 1
    assert events[0]["type"] == "job_created"

    temp_store.transition_state(job.job_id, JobState.RUNNING)
    events = temp_store.get_events(job.job_id)
    assert any(e["type"] == "state_transition" for e in events)


def test_multiple_jobs(temp_store):
    """Test creating multiple jobs."""
    order1 = WorkOrderSchema(
        pt_task_id=100,
        goal="Job 1",
        repo_path="/tmp/repo1",
        branch="branch1",
    )
    order2 = WorkOrderSchema(
        pt_task_id=200,
        goal="Job 2",
        repo_path="/tmp/repo2",
        branch="branch2",
    )

    job1 = temp_store.create_job("key1", order1, "/tmp/repo1")
    job2 = temp_store.create_job("key2", order2, "/tmp/repo2")

    assert job1.job_id != job2.job_id
    assert temp_store.get_job(job1.job_id) is not None
    assert temp_store.get_job(job2.job_id) is not None
