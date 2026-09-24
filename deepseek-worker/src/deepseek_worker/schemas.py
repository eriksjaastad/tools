"""Work order and handoff JSON schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class WorkOrderSchema(BaseModel):
    """Work order: manager → worker."""

    schema_: str = Field(
        default="deepseek-worker.work_order.v1",
        alias="schema"
    )
    pt_task_id: int
    goal: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    context_paths: list[str] = Field(default_factory=list)
    repo_path: str
    base_ref: str = "main"
    branch: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    test_commands: list[str] = Field(default_factory=list)
    off_peak_policy: str = "require_off_peak"
    peak_exception: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class HandoffStatus(str, Enum):
    """Worker completion status."""

    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    PARTIAL = "partial"


class FileChange(BaseModel):
    """A file change recorded in handoff."""

    path: str
    change: str


class CheckResult(BaseModel):
    """A test/check result."""

    cmd: str
    exit_code: int
    summary: str


class TokenUsage(BaseModel):
    """Token usage and cost estimate."""

    prompt: int = 0
    completion: int = 0
    cache_hit: int = 0
    usd_estimate: float = 0.0


class HandoffSchema(BaseModel):
    """Handoff: worker → manager."""

    schema_: str = Field(
        default="deepseek-worker.handoff.v1",
        alias="schema"
    )
    job_id: str
    pt_task_id: int
    status: HandoffStatus
    branch: str
    head_sha: str
    files_changed: list[FileChange] = Field(default_factory=list)
    checks_run: list[CheckResult] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    notes: str = ""
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    worker_model: str = "deepseek-v4-pro"
    finished_at: str

    model_config = {"populate_by_name": True}


class JobState(str, Enum):
    """Job lifecycle states."""

    QUEUED = "queued"
    SPAWNING = "spawning"
    RUNNING = "running"
    HANDOFF_PENDING = "handoff_pending"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CRASHED = "crashed"
    MALFORMED_HANDOFF = "malformed_handoff"


class JobRecord(BaseModel):
    """Persisted job record."""

    job_id: str
    idempotency_key: str
    pt_task_id: int
    repo_path: str
    repo_remote: Optional[str] = None
    worktree_path: str
    branch: str
    manager_identity: str = "unknown"
    worker_model: str = "deepseek-v4-pro"
    worker_provider: str = "deepseek"
    state: JobState
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    pid: Optional[int] = None
    handoff_path: Optional[str] = None
    handoff_sha: Optional[str] = None
