"""
Audit Logger - Comprehensive event logging for UAS.

Logs all significant events in NDJSON format for later analysis.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Default audit log location
DEFAULT_AUDIT_PATH = Path(os.getenv("UAS_AUDIT_LOG", "data/audit.ndjson"))


class EventType(Enum):
    """Types of auditable events."""
    # Model events
    MODEL_CALL_START = "model_call_start"
    MODEL_CALL_SUCCESS = "model_call_success"
    MODEL_CALL_FAILURE = "model_call_failure"
    MODEL_FALLBACK = "model_fallback"

    # Circuit breaker events
    CIRCUIT_BREAKER_FAILURE = "circuit_breaker_failure"
    CIRCUIT_BREAKER_HALT = "circuit_breaker_halt"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"

    # Degradation events
    DEGRADATION_ENTERED = "degradation_entered"
    DEGRADATION_RECOVERED = "degradation_recovered"

    # Budget events
    BUDGET_CHECK_PASSED = "budget_check_passed"
    BUDGET_CHECK_FAILED = "budget_check_failed"
    BUDGET_OVERRIDE_REQUESTED = "budget_override_requested"
    BUDGET_OVERRIDE_CLEARED = "budget_override_cleared"
    BUDGET_LIMIT_CHANGED = "budget_limit_changed"

    # Message bus events
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    QUESTION_ASKED = "question_asked"
    QUESTION_ANSWERED = "question_answered"

    # Session events
    SESSION_START = "session_start"
    SESSION_END = "session_end"


@dataclass
class AuditEvent:
    """An auditable event."""
    timestamp: str
    event_type: str
    source: str  # Component that generated the event
    data: dict
    session_id: str = ""
    run_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class AuditLogger:
    """
    Centralized audit logging for UAS.

    Usage:
        audit = AuditLogger()

        # Log events
        audit.log(EventType.MODEL_CALL_SUCCESS, "litellm_bridge", {
            "model": "local-coder",
            "tokens_in": 500,
            "tokens_out": 200,
            "latency_ms": 1500
        })

        # Query events
        events = audit.get_events(event_type=EventType.MODEL_FALLBACK)
    """

    def __init__(
        self,
        audit_path: Path | str | None = None,
        session_id: str | None = None
    ):
        self.audit_path = Path(audit_path) if audit_path else DEFAULT_AUDIT_PATH
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        import hashlib
        import time
        self.session_id = session_id or hashlib.sha256(
            f"{time.time()}{os.getpid()}".encode()
        ).hexdigest()[:12]

        self._current_run_id = ""

    def set_run_id(self, run_id: str) -> None:
        """Set current run ID for context."""
        self._current_run_id = run_id

    def log(
        self,
        event_type: EventType,
        source: str,
        data: dict,
        run_id: str | None = None
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            source: Component name
            data: Event-specific data
            run_id: Optional run ID override
        """
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type.value,
            source=source,
            data=data,
            session_id=self.session_id,
            run_id=run_id or self._current_run_id,
        )

        # Append to NDJSON file
        with self.audit_path.open("a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

        logger.debug(f"Audit: {event_type.value} from {source}")

    def log_model_call(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        success: bool,
        error: str | None = None,
        was_fallback: bool = False,
        task_type: str | None = None
    ) -> None:
        """Convenience method for logging model calls."""
        event_type = EventType.MODEL_CALL_SUCCESS if success else EventType.MODEL_CALL_FAILURE

        data = {
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "task_type": task_type,
        }

        if error:
            data["error"] = error

        self.log(event_type, "litellm_bridge", data)

        if was_fallback and success:
            self.log(EventType.MODEL_FALLBACK, "litellm_bridge", {
                "model": model,
                "task_type": task_type,
            })

    def get_events(
        self,
        event_type: EventType | None = None,
        source: str | None = None,
        since: str | None = None,
        limit: int = 100
    ) -> list[dict]:
        """
        Query audit events.

        Args:
            event_type: Filter by event type
            source: Filter by source component
            since: Filter events after this ISO timestamp
            limit: Maximum events to return

        Returns:
            List of matching events (newest first)
        """
        if not self.audit_path.exists():
            return []

        events = []

        with self.audit_path.open("r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())

                    # Apply filters
                    if event_type and event["event_type"] != event_type.value:
                        continue
                    if source and event["source"] != source:
                        continue
                    if since and event["timestamp"] < since:
                        continue

                    events.append(event)
                except json.JSONDecodeError:
                    continue

        # Return newest first, limited
        return list(reversed(events))[:limit]

    def get_session_summary(self) -> dict:
        """Get summary of current session's events."""
        events = self.get_events()
        session_events = [e for e in events if e["session_id"] == self.session_id]

        # Count by type
        type_counts = {}
        for event in session_events:
            t = event["event_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "session_id": self.session_id,
            "total_events": len(session_events),
            "event_counts": type_counts,
        }


# Global instance
_audit_logger: AuditLogger | None = None

def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Convenience functions
def audit_event(event_type: EventType, source: str, data: dict) -> None:
    """Log an audit event (convenience function)."""
    get_audit_logger().log(event_type, source, data)
