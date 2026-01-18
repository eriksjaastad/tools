# Phase 13: Floor Manager Draft Gate

**Goal:** Add draft submission handling to the Floor Manager. This is the gatekeeper that decides whether to accept or reject worker drafts.

**Prerequisites:** Phase 11 (sandbox infrastructure) and Phase 12 (Ollama draft tools) complete.

**Important:** This phase modifies `agent-hub`. We're back in `/Users/eriksjaastad/projects/_tools/agent-hub/`.

---

## The Gate Logic

```
Worker submits draft
        │
        ▼
┌───────────────────┐
│  Floor Manager    │
│   Draft Gate      │
├───────────────────┤
│ 1. Load submission│
│ 2. Validate paths │
│ 3. Generate diff  │
│ 4. Safety checks  │
│ 5. Scope check    │
│ 6. Decision       │
└───────┬───────────┘
        │
   ┌────┴────┐
   │         │
   ▼         ▼
ACCEPT    REJECT
   │         │
   ▼         ▼
Copy to   Delete
original  draft
```

---

## Prompt 13.1: Add Gate Result Types

### Context
We need types for the gate decision results.

### Task
Update `src/sandbox.py` to add gate result types at the end of the file:

```python
# Add these imports at the top if not present
from enum import Enum
from dataclasses import dataclass

# Add these classes at the end of the file

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
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/sandbox.py`

---

## Prompt 13.2: Create Draft Gate Module

### Context
The draft gate is the core of Phase 13. It reviews submissions and decides accept/reject/escalate.

### Task
Create `src/draft_gate.py`:

```python
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
        if temp_path.exists():
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
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/draft_gate.py`

---

## Prompt 13.3: Integrate Gate into Watchdog

### Context
The watchdog needs to handle `DRAFT_READY` messages and invoke the draft gate.

### Task
Update `src/watchdog.py` to add draft handling.

**Step 1:** Add import at top of file:
```python
from .draft_gate import handle_draft_submission, apply_draft, reject_draft, GateDecision
```

**Step 2:** Add a new message handler method to the `FloorManager` class:
```python
def handle_draft_ready(self, message: dict) -> None:
    """
    Handle DRAFT_READY message from a worker.

    Args:
        message: The MCP message with draft submission info
    """
    payload = message.get("payload", {})
    task_id = payload.get("task_id")

    if not task_id:
        logger.error("DRAFT_READY missing task_id")
        return

    logger.info(f"Processing DRAFT_READY for task: {task_id}")

    # Run the gate
    result = handle_draft_submission(task_id)

    if result.decision == GateDecision.ACCEPT:
        logger.info(f"Draft ACCEPTED: {result.diff_summary}")
        if apply_draft(task_id):
            self._log_transition("draft_accepted", task_id)
            # Notify worker of success
            self._send_message(
                message.get("from", "worker"),
                "DRAFT_ACCEPTED",
                {"task_id": task_id, "summary": result.diff_summary}
            )
        else:
            logger.error("Failed to apply accepted draft")
            self._log_transition("draft_apply_failed", task_id)

    elif result.decision == GateDecision.REJECT:
        logger.warning(f"Draft REJECTED: {result.reason}")
        reject_draft(task_id, result.reason)
        self._log_transition("draft_rejected", task_id)
        # Notify worker of rejection
        self._send_message(
            message.get("from", "worker"),
            "DRAFT_REJECTED",
            {"task_id": task_id, "reason": result.reason}
        )

    elif result.decision == GateDecision.ESCALATE:
        logger.warning(f"Draft ESCALATED: {result.reason}")
        self._log_transition("draft_escalated", task_id)
        # Notify Erik
        self._send_message(
            "super_manager",
            "DRAFT_ESCALATED",
            {
                "task_id": task_id,
                "reason": result.reason,
                "diff_summary": result.diff_summary
            }
        )
```

**Step 3:** Add `DRAFT_READY` to the message handler dispatch (in the message handling section):
```python
# In the message handling logic, add:
elif message_type == "DRAFT_READY":
    self.handle_draft_ready(message)
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/src/watchdog.py`

---

## Prompt 13.4: Create Gate Tests

### Context
The draft gate is security-critical. We need thorough tests.

### Task
Create `tests/test_draft_gate.py`:

```python
#!/usr/bin/env python3
"""
Tests for the draft gate.

These tests verify the gate correctly accepts, rejects, and escalates drafts.
"""

import pytest
import json
from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from draft_gate import (
    analyze_safety,
    generate_diff,
    MAX_DELETION_RATIO,
    SECRET_PATTERNS,
    HARDCODED_PATH_PATTERNS,
)
from sandbox import SafetyAnalysis


class TestSafetyAnalysis:
    """Test the safety analysis function."""

    def test_detects_api_key(self):
        """Should detect API keys in content."""
        content = 'api_key = "sk-abc123xyz456"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_secrets is True

    def test_detects_password(self):
        """Should detect passwords in content."""
        content = 'password = "super_secret_123"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_secrets is True

    def test_detects_hardcoded_path_unix(self):
        """Should detect hardcoded Unix paths."""
        content = 'path = "/Users/erik/projects/file.py"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_hardcoded_paths is True

    def test_detects_hardcoded_path_linux(self):
        """Should detect hardcoded Linux home paths."""
        content = 'path = "/home/user/documents/file.txt"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_hardcoded_paths is True

    def test_allows_relative_paths(self):
        """Should allow relative paths."""
        content = 'path = "./config/settings.json"'
        safety = analyze_safety(content, 1, 0, 10)
        assert safety.has_hardcoded_paths is False

    def test_calculates_deletion_ratio(self):
        """Should calculate deletion ratio correctly."""
        safety = analyze_safety("content", added_lines=5, removed_lines=50, original_lines=100)
        assert safety.deletion_ratio == 0.5

    def test_flags_high_deletion(self):
        """Should flag high deletion ratio."""
        safety = analyze_safety("content", added_lines=0, removed_lines=60, original_lines=100)
        assert safety.deletion_ratio > MAX_DELETION_RATIO
        assert len(safety.issues) > 0

    def test_clean_content_passes(self):
        """Clean content should pass all checks."""
        content = '''
def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
'''
        safety = analyze_safety(content, added_lines=5, removed_lines=2, original_lines=10)
        assert safety.has_secrets is False
        assert safety.has_hardcoded_paths is False
        assert safety.deletion_ratio < MAX_DELETION_RATIO


class TestDiffGeneration:
    """Test diff generation."""

    def test_generates_diff(self, tmp_path):
        """Should generate unified diff."""
        original = tmp_path / "original.py"
        draft = tmp_path / "draft.py"

        original.write_text("line1\nline2\nline3\n")
        draft.write_text("line1\nmodified\nline3\nnew_line\n")

        diff_text, added, removed = generate_diff(original, draft)

        assert added == 2  # "modified" and "new_line"
        assert removed == 1  # "line2"
        assert "modified" in diff_text

    def test_handles_identical_files(self, tmp_path):
        """Should handle identical files."""
        original = tmp_path / "original.py"
        draft = tmp_path / "draft.py"

        content = "same content\n"
        original.write_text(content)
        draft.write_text(content)

        diff_text, added, removed = generate_diff(original, draft)

        assert added == 0
        assert removed == 0


class TestSecretPatterns:
    """Test that secret patterns catch real secrets."""

    @pytest.mark.parametrize("secret", [
        'api_key = "sk-abcdef1234567890abcdef"',
        "API_KEY='sk-1234567890abcdefghij1234567890ab'",
        'password = "my_super_secret"',
        'secret = "dont_tell_anyone"',
        'key = "AIzaSyABC123def456GHI789jkl012MNO345pqr"',
    ])
    def test_catches_secrets(self, secret):
        """Should catch various secret patterns."""
        matched = any(
            __import__('re').search(pattern, secret)
            for pattern in SECRET_PATTERNS
        )
        assert matched, f"Should catch: {secret}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/tests/test_draft_gate.py`

---

## Prompt 13.5: Integration Smoke Test

### Context
Before moving to Phase 14, verify the gate works end-to-end.

### Task
Create `scripts/test_draft_gate.py`:

```python
#!/usr/bin/env python3
"""
Smoke test for draft gate.
Creates a mock submission and runs it through the gate.
"""

import sys
import json
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sandbox import SANDBOX_DIR, ensure_sandbox_exists
from src.draft_gate import (
    handle_draft_submission,
    apply_draft,
    reject_draft,
    GateDecision,
)


def setup_test_submission(task_id: str, original_content: str, draft_content: str) -> tuple[Path, Path]:
    """Create test files for a submission."""
    # Ensure sandbox exists
    ensure_sandbox_exists()

    # Create a temp original file
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "_test_workspace"
    test_dir.mkdir(exist_ok=True)

    original_path = test_dir / "test_file.py"
    original_path.write_text(original_content)

    # Create draft in sandbox
    draft_path = SANDBOX_DIR / f"test_file.py.{task_id}.draft"
    draft_path.write_text(draft_content)

    # Create submission metadata
    import hashlib
    original_hash = hashlib.sha256(original_content.encode()).hexdigest()

    submission = {
        "task_id": task_id,
        "draft_path": str(draft_path),
        "original_path": str(original_path),
        "change_summary": "Test change",
        "submitted_at": "2026-01-17T12:00:00Z",
        "original_hash": original_hash,
        "draft_hash": hashlib.sha256(draft_content.encode()).hexdigest(),
        "original_lines": len(original_content.splitlines()),
        "draft_lines": len(draft_content.splitlines()),
    }

    submission_path = SANDBOX_DIR / f"{task_id}.submission.json"
    submission_path.write_text(json.dumps(submission))

    return original_path, draft_path


def cleanup_test(task_id: str):
    """Clean up test files."""
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "_test_workspace"
    if test_dir.exists():
        shutil.rmtree(test_dir)

    # Clean sandbox
    for f in SANDBOX_DIR.glob(f"*{task_id}*"):
        f.unlink()


def main():
    print("=" * 50)
    print("DRAFT GATE SMOKE TEST")
    print("=" * 50)
    print()

    passed = 0
    failed = 0

    # Test 1: Clean change should be accepted
    print("Test 1: Clean change should be ACCEPTED...")
    task_id = "test_clean_001"
    try:
        original = "def hello():\n    print('hello')\n"
        draft = "def hello():\n    print('Hello, World!')\n"
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.ACCEPT:
            print("  PASS: Clean change accepted")
            passed += 1
        else:
            print(f"  FAIL: Expected ACCEPT, got {result.decision}: {result.reason}")
            failed += 1
    finally:
        cleanup_test(task_id)

    # Test 2: Secret in draft should be rejected
    print("Test 2: Secret in draft should be REJECTED...")
    task_id = "test_secret_002"
    try:
        original = "config = {}\n"
        draft = 'config = {"api_key": "sk-1234567890abcdefghij"}\n'
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.REJECT:
            print("  PASS: Secret detected and rejected")
            passed += 1
        else:
            print(f"  FAIL: Expected REJECT, got {result.decision}")
            failed += 1
    finally:
        cleanup_test(task_id)

    # Test 3: Hardcoded path should be rejected
    print("Test 3: Hardcoded path should be REJECTED...")
    task_id = "test_path_003"
    try:
        original = "path = './config.json'\n"
        draft = "path = '/Users/erik/projects/config.json'\n"
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.REJECT:
            print("  PASS: Hardcoded path detected and rejected")
            passed += 1
        else:
            print(f"  FAIL: Expected REJECT, got {result.decision}")
            failed += 1
    finally:
        cleanup_test(task_id)

    # Test 4: Large deletion should be escalated
    print("Test 4: Large deletion should be ESCALATED...")
    task_id = "test_delete_004"
    try:
        original = "\n".join([f"line {i}" for i in range(100)]) + "\n"
        draft = "# Deleted most of the file\n"
        setup_test_submission(task_id, original, draft)

        result = handle_draft_submission(task_id)
        if result.decision == GateDecision.ESCALATE:
            print("  PASS: Large deletion escalated")
            passed += 1
        else:
            print(f"  FAIL: Expected ESCALATE, got {result.decision}")
            failed += 1
    finally:
        cleanup_test(task_id)

    print()
    print("=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed > 0:
        print("\nPhase 13 has issues - review failures above.")
        return 1
    else:
        print("\nPhase 13 COMPLETE. Ready for Phase 14 (E2E Draft Workflow).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/test_draft_gate.py`

---

## Execution Order

1. **13.1** - Add gate result types to sandbox.py
2. **13.2** - Create draft_gate.py
3. **13.3** - Integrate into watchdog.py
4. **13.4** - Create gate tests
5. **13.5** - Run smoke test

### Verification

```bash
# After all prompts:
cd /Users/eriksjaastad/projects/_tools/agent-hub

# Run unit tests
pytest tests/test_draft_gate.py -v

# Run smoke test
python scripts/test_draft_gate.py
```

---

## Success Criteria

Phase 13 is DONE when:
- [ ] `GateResult` types added to sandbox.py
- [ ] `draft_gate.py` created with full gate logic
- [ ] Watchdog handles `DRAFT_READY` messages
- [ ] Gate correctly accepts clean changes
- [ ] Gate rejects secrets and hardcoded paths
- [ ] Gate escalates destructive changes
- [ ] All tests pass

---

## Security Checklist

Before marking Phase 13 complete, verify:
- [ ] Secrets are detected by regex patterns
- [ ] Hardcoded paths are detected
- [ ] High deletion ratio triggers escalation
- [ ] Conflict detection works (hash mismatch)
- [ ] All decisions are logged to transition.ndjson
- [ ] Rejected drafts are cleaned up

---

*Phase 13 is the gatekeeper. No draft reaches production without its approval.*
