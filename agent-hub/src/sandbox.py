#!/usr/bin/env python3
"""
Sandbox path validation for V4 Draft Pattern.

SECURITY CRITICAL: This module is the gatekeeper for all worker file operations.
Any bypass here compromises the entire sandbox model.
"""

from pathlib import Path
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass
from typing import NamedTuple

logger = logging.getLogger(__name__)

# The ONE directory workers can write to
# Adjusted to be absolute/relative correctly: parent.parent is project root
SANDBOX_DIR = Path(__file__).parent.parent / "_handoff" / "drafts"


class ValidationResult(NamedTuple):
    """Result of path validation."""
    valid: bool
    reason: str
    resolved_path: Path | None = None


def validate_sandbox_write(path: str | Path) -> ValidationResult:
    """
    Validate that a path is safe for worker writes.

    SECURITY: This is the ONLY place workers can write.

    Args:
        path: The path to validate

    Returns:
        ValidationResult with valid=True if write is allowed
    """
    try:
        target = Path(path).resolve()
        sandbox = SANDBOX_DIR.resolve()

        # Check 1: Must be inside sandbox
        if not target.is_relative_to(sandbox):
            logger.warning(f"SECURITY: Write blocked - outside sandbox: {target}")
            return ValidationResult(
                valid=False,
                reason=f"Path outside sandbox: {target}"
            )

        # Check 2: No path traversal tricks
        if ".." in str(path):
            logger.warning(f"SECURITY: Write blocked - path traversal: {path}")
            return ValidationResult(
                valid=False,
                reason="Path traversal not allowed"
            )

        # Check 3: Must have .draft or .submission.json extension
        valid_extensions = {".draft", ".json"}
        if target.suffix not in valid_extensions:
            # Allow .submission.json specifically
            if not str(target).endswith(".submission.json"):
                logger.warning(f"SECURITY: Write blocked - invalid extension: {target}")
                return ValidationResult(
                    valid=False,
                    reason=f"Invalid extension: {target.suffix}"
                )

        logger.debug(f"Sandbox write validated: {target}")
        return ValidationResult(
            valid=True,
            reason="OK",
            resolved_path=target
        )

    except Exception as e:
        logger.error(f"SECURITY: Validation error: {e}")
        return ValidationResult(
            valid=False,
            reason=f"Validation error: {e}"
        )


def validate_source_read(path: str | Path, workspace_root: Path) -> ValidationResult:
    """
    Validate that a source file can be read for drafting.

    Args:
        path: The source file path
        workspace_root: The project workspace root

    Returns:
        ValidationResult with valid=True if read is allowed
    """
    try:
        target = Path(path).resolve()
        workspace = workspace_root.resolve()

        # Check 1: Must be inside workspace
        if not target.is_relative_to(workspace):
            logger.warning(f"SECURITY: Read blocked - outside workspace: {target}")
            return ValidationResult(
                valid=False,
                reason=f"Path outside workspace: {target}"
            )

        # Check 2: File must exist
        if not target.exists():
            return ValidationResult(
                valid=False,
                reason=f"File not found: {target}"
            )

        # Check 3: Must be a file, not directory
        if not target.is_file():
            return ValidationResult(
                valid=False,
                reason=f"Not a file: {target}"
            )

        # Check 4: Block sensitive files
        sensitive_patterns = [".env", "credentials", "secret", ".key", ".pem"]
        if any(pattern in target.name.lower() for pattern in sensitive_patterns):
            logger.warning(f"SECURITY: Read blocked - sensitive file: {target}")
            return ValidationResult(
                valid=False,
                reason=f"Cannot draft sensitive files: {target.name}"
            )

        logger.debug(f"Source read validated: {target}")
        return ValidationResult(
            valid=True,
            reason="OK",
            resolved_path=target
        )

    except Exception as e:
        logger.error(f"SECURITY: Validation error: {e}")
        return ValidationResult(
            valid=False,
            reason=f"Validation error: {e}"
        )


def get_draft_path(source_path: Path, task_id: str) -> Path:
    """
    Generate the sandbox draft path for a source file.

    Args:
        source_path: Original file path
        task_id: Current task identifier

    Returns:
        Path to the draft file in sandbox
    """
    # Sanitize task_id (alphanumeric and underscore only)
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)

    draft_name = f"{source_path.name}.{safe_task_id}.draft"
    return SANDBOX_DIR / draft_name


def get_submission_path(task_id: str) -> Path:
    """
    Generate the submission metadata path.

    Args:
        task_id: Current task identifier

    Returns:
        Path to the submission JSON in sandbox
    """
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)
    return SANDBOX_DIR / f"{safe_task_id}.submission.json"


def compute_file_hash(path: Path) -> str:
    """
    Compute SHA256 hash of a file for conflict detection.

    Args:
        path: File to hash

    Returns:
        Hex digest of SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def ensure_sandbox_exists() -> None:
    """Ensure the sandbox directory exists."""
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Sandbox directory ready: {SANDBOX_DIR}")


def cleanup_task_drafts(task_id: str) -> int:
    """
    Clean up all drafts for a completed task.

    Args:
        task_id: Task identifier

    Returns:
        Number of files cleaned up
    """
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)
    pattern = f"*.{safe_task_id}.*"

    count = 0
    for draft_file in SANDBOX_DIR.glob(pattern):
        try:
            draft_file.unlink()
            count += 1
            logger.debug(f"Cleaned up: {draft_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up {draft_file}: {e}")

    logger.info(f"Cleaned up {count} draft files for task {task_id}")
    return count


class GateDecision(Enum):
    """Possible outcomes of the draft gate."""
    ACCEPT = "accept"
    REJECT = "reject"
    ESCALATE = "escalate"


@dataclass
class SafetyAnalysis:
    """Results of safety analysis on a diff."""
    has_secrets: bool = False
    has_hardcoded_paths: bool = False
    deletion_ratio: float = 0.0
    added_lines: int = 0
    removed_lines: int = 0
    issues: list[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


@dataclass
class GateResult:
    """Result of the draft gate decision."""
    decision: GateDecision
    reason: str
    diff_summary: str = ""
    safety_analysis: SafetyAnalysis | None = None

    @classmethod
    def accept(cls, diff_summary: str, safety: SafetyAnalysis) -> "GateResult":
        return cls(
            decision=GateDecision.ACCEPT,
            reason="All checks passed",
            diff_summary=diff_summary,
            safety_analysis=safety
        )

    @classmethod
    def reject(cls, reason: str) -> "GateResult":
        return cls(
            decision=GateDecision.REJECT,
            reason=reason
        )

    @classmethod
    def escalate(cls, reason: str, diff_summary: str = "") -> "GateResult":
        return cls(
            decision=GateDecision.ESCALATE,
            reason=reason,
            diff_summary=diff_summary
        )
