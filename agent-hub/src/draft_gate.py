#!/usr/bin/env python3
"""
Draft Gate for Floor Manager.

This module reviews worker draft submissions and decides whether to
accept (apply changes), reject (discard), or escalate (human review).

SECURITY: This is the last line of defense before changes hit production.
"""

import json
import re
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from difflib import unified_diff

from .sandbox import (
    SANDBOX_DIR,
    validate_sandbox_write,
    validate_source_read,
    compute_file_hash,
    cleanup_task_drafts,
    GateDecision,
    GateResult,
    SafetyAnalysis,
)
from .config import get_config

logger = logging.getLogger(__name__)

# Safety thresholds
MAX_DELETION_RATIO = 0.5  # Reject if >50% of file deleted
MAX_LINES_CHANGED = 500   # Escalate if >500 lines changed
MAX_FILES_PER_TASK = 20   # Escalate if task touches >20 files

# Patterns that indicate potential security issues
SECRET_PATTERNS = [
    r'(?i)api[_-]?key\s*=\s*["\'][^"\']+["\']',
    r'(?i)password\s*=\s*["\'][^"\']+["\']',
    r'(?i)secret\s*=\s*["\'][^"\']+["\']',
    r'sk-[a-zA-Z0-9]{20,}',  # OpenAI keys
    r'AIza[a-zA-Z0-9_-]{35}',  # Google API keys
]

HARDCODED_PATH_PATTERNS = [
    r'/Users/[a-zA-Z0-9_]+/',
    r'/home/[a-zA-Z0-9_]+/',
    r'C:\\Users\\[a-zA-Z0-9_]+\\',
]


def load_submission(task_id: str) -> dict | None:
    """
    Load a draft submission metadata file.

    Args:
        task_id: The task identifier

    Returns:
        Submission dict or None if not found
    """
    # Sanitize task_id
    safe_task_id = "".join(c if c.isalnum() or c == "_" else "_" for c in task_id)
    submission_path = SANDBOX_DIR / f"{safe_task_id}.submission.json"

    if not submission_path.exists():
        logger.warning(f"Submission not found: {submission_path}")
        return None

    try:
        with open(submission_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load submission: {e}")
        return None


def generate_diff(original_path: Path, draft_path: Path) -> tuple[str, int, int]:
    """
    Generate unified diff between original and draft.

    Returns:
        (diff_text, added_lines, removed_lines)
    """
    try:
        original_content = original_path.read_text().splitlines(keepends=True)
        draft_content = draft_path.read_text().splitlines(keepends=True)

        diff_lines = list(unified_diff(
            original_content,
            draft_content,
            fromfile=str(original_path),
            tofile=str(draft_path),
            lineterm=""
        ))

        added = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        diff_text = '\n'.join(diff_lines)
        return diff_text, added, removed

    except Exception as e:
        logger.error(f"Failed to generate diff: {e}")
        return f"Error generating diff: {e}", 0, 0


def analyze_safety(draft_content: str, added_lines: int, removed_lines: int, original_lines: int) -> SafetyAnalysis:
    """
    Analyze draft content for security issues.

    Args:
        draft_content: The draft file content
        added_lines: Number of lines added
        removed_lines: Number of lines removed
        original_lines: Original file line count

    Returns:
        SafetyAnalysis with findings
    """
    issues = []

    # Check for secrets
    has_secrets = False
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, draft_content):
            has_secrets = True
            issues.append(f"Potential secret detected: {pattern[:30]}...")
            break

    # Check for hardcoded paths
    has_hardcoded_paths = False
    for pattern in HARDCODED_PATH_PATTERNS:
        if re.search(pattern, draft_content):
            has_hardcoded_paths = True
            issues.append(f"Hardcoded path detected: {pattern[:30]}...")
            break

    # Calculate deletion ratio
    deletion_ratio = 0.0
    if original_lines > 0:
        deletion_ratio = removed_lines / original_lines

    if deletion_ratio > MAX_DELETION_RATIO:
        issues.append(f"High deletion ratio: {deletion_ratio:.1%} of file removed")

    return SafetyAnalysis(
        has_secrets=has_secrets,
        has_hardcoded_paths=has_hardcoded_paths,
        deletion_ratio=deletion_ratio,
        added_lines=added_lines,
        removed_lines=removed_lines,
        issues=issues
    )


def handle_draft_submission(task_id: str) -> GateResult:
    """
    Process a draft submission and decide whether to accept, reject, or escalate.

    This is the main entry point for the draft gate.

    Args:
        task_id: The task identifier

    Returns:
        GateResult with decision and reasoning
    """
    logger.info(f"Processing draft submission for task: {task_id}")

    # 1. Load submission metadata
    submission = load_submission(task_id)
    if not submission:
        return GateResult.reject(f"Submission not found for task: {task_id}")

    draft_path = Path(submission.get("draft_path", ""))
    original_path = Path(submission.get("original_path", ""))

    # 2. Validate paths
    draft_validation = validate_sandbox_write(str(draft_path))
    if not draft_validation.valid:
        return GateResult.reject(f"Invalid draft path: {draft_validation.reason}")

    config = get_config()
    workspace_root = Path(config.workspace_root) if hasattr(config, 'workspace_root') else Path(__file__).parent.parent

    original_validation = validate_source_read(str(original_path), workspace_root)
    if not original_validation.valid:
        return GateResult.reject(f"Invalid original path: {original_validation.reason}")

    # 3. Check files exist
    if not draft_path.exists():
        return GateResult.reject(f"Draft file not found: {draft_path}")

    if not original_path.exists():
        return GateResult.reject(f"Original file not found: {original_path}")

    # 4. Check for conflict (original changed since draft started)
    current_hash = compute_file_hash(original_path)
    original_hash = submission.get("original_hash", "")

    if current_hash != original_hash:
        return GateResult.escalate(
            "Conflict detected: original file changed since draft was created",
            f"Original hash: {original_hash[:16]}... Current: {current_hash[:16]}..."
        )

    # 5. Generate diff
    diff_text, added, removed = generate_diff(original_path, draft_path)
    original_lines = submission.get("original_lines", 1)

    diff_summary = f"+{added}/-{removed} lines"
    logger.info(f"Diff summary: {diff_summary}")

    # 6. Safety analysis
    draft_content = draft_path.read_text()
    safety = analyze_safety(draft_content, added, removed, original_lines)

    if safety.has_secrets:
        logger.warning(f"SECURITY: Draft contains potential secrets")
        return GateResult.reject("Draft contains potential secrets - manual review required")

    if safety.has_hardcoded_paths:
        logger.warning(f"SECURITY: Draft contains hardcoded paths")
        return GateResult.reject("Draft contains hardcoded user paths - use relative paths")

    if safety.deletion_ratio > MAX_DELETION_RATIO:
        logger.warning(f"Destructive diff: {safety.deletion_ratio:.1%} deletion")
        return GateResult.escalate(
            f"Destructive change: {safety.deletion_ratio:.1%} of file deleted",
            diff_summary
        )

    # 7. Scope check
    total_changed = added + removed
    if total_changed > MAX_LINES_CHANGED:
        return GateResult.escalate(
            f"Large change: {total_changed} lines modified (threshold: {MAX_LINES_CHANGED})",
            diff_summary
        )

    # 8. All checks passed - ACCEPT
    logger.info(f"Draft ACCEPTED for task {task_id}")
    return GateResult.accept(diff_summary, safety)


def apply_draft(task_id: str) -> bool:
    """
    Apply an accepted draft by copying it over the original.

    Args:
        task_id: The task identifier

    Returns:
        True if successful, False otherwise
    """
    submission = load_submission(task_id)
    if not submission:
        logger.error(f"Cannot apply: submission not found for {task_id}")
        return False

    draft_path = Path(submission["draft_path"])
    original_path = Path(submission["original_path"])

    try:
        # Atomic copy: write to temp, then rename
        temp_path = original_path.with_suffix(original_path.suffix + ".tmp")
        shutil.copy2(draft_path, temp_path)
        temp_path.rename(original_path)

        logger.info(f"Draft applied: {original_path}")

        # Log the change
        log_draft_applied(task_id, submission)

        return True

    except Exception as e:
        logger.error(f"Failed to apply draft: {e}")
        # Clean up temp file if it exists
        if 'temp_path' in locals() and temp_path.exists():
            temp_path.unlink()
        return False


def log_draft_applied(task_id: str, submission: dict) -> None:
    """Log draft application to transition.ndjson."""
    config = get_config()
    handoff_dir = Path(config.handoff_dir)
    transition_log = handoff_dir / "transition.ndjson"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "draft_applied",
        "task_id": task_id,
        "original_path": submission.get("original_path"),
        "change_summary": submission.get("change_summary"),
        "original_lines": submission.get("original_lines"),
        "draft_lines": submission.get("draft_lines"),
    }

    try:
        with open(transition_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log draft application: {e}")


def reject_draft(task_id: str, reason: str) -> bool:
    """
    Reject a draft by cleaning it up.

    Args:
        task_id: The task identifier
        reason: Reason for rejection

    Returns:
        True if cleanup successful
    """
    logger.info(f"Rejecting draft for task {task_id}: {reason}")

    # Log the rejection
    config = get_config()
    handoff_dir = Path(config.handoff_dir)
    transition_log = handoff_dir / "transition.ndjson"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "draft_rejected",
        "task_id": task_id,
        "reason": reason,
    }

    try:
        with open(transition_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to log draft rejection: {e}")

    # Clean up draft files
    cleanup_task_drafts(task_id)
    return True
