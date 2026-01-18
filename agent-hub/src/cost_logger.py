"""
Cost Logger - Track model usage and tokens.

Logs to NDJSON format for analysis and budget tracking.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default log location
DEFAULT_LOG_PATH = Path("data/logs/transition.ndjson")


class CostLogger:
    """
    Logger for model call costs and metrics.

    Usage:
        cost_logger = CostLogger()

        # Log successful call
        cost_logger.log_call(
            model="llama3.2:1b",
            tokens_in=150,
            tokens_out=50,
            latency_ms=423,
            success=True,
        )

        # Log failed call
        cost_logger.log_call(
            model="llama3.2:1b",
            tokens_in=150,
            tokens_out=0,
            latency_ms=5000,
            success=False,
            error="timeout",
        )
    """

    def __init__(self, log_path: Path | str | None = None, session_id: str | None = None):
        """
        Args:
            log_path: Path to NDJSON log file (default: data/logs/transition.ndjson)
            session_id: Unique session identifier (auto-generated if not provided)
        """
        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
        self.session_id = session_id or self._generate_session_id()

        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Session totals
        self._total_tokens_in = 0
        self._total_tokens_out = 0
        self._total_calls = 0
        self._failed_calls = 0

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import hashlib
        return hashlib.sha256(f"{time.time()}{os.getpid()}".encode()).hexdigest()[:12]

    def log_call(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        success: bool,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a model call.

        Args:
            model: Model name (e.g., "llama3.2:1b")
            tokens_in: Input token count
            tokens_out: Output token count
            latency_ms: Call latency in milliseconds
            success: Whether the call succeeded
            error: Error message if failed
            metadata: Additional metadata to include
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "success": success,
        }

        if error:
            record["error"] = error

        if metadata:
            record["metadata"] = metadata

        # Update totals
        self._total_tokens_in += tokens_in
        self._total_tokens_out += tokens_out
        self._total_calls += 1
        if not success:
            self._failed_calls += 1

        # Write to log file
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write cost log: {e}")

    def session_summary(self) -> dict:
        """Get summary statistics for current session."""
        return {
            "session_id": self.session_id,
            "total_calls": self._total_calls,
            "failed_calls": self._failed_calls,
            "success_rate": (self._total_calls - self._failed_calls) / max(self._total_calls, 1),
            "total_tokens_in": self._total_tokens_in,
            "total_tokens_out": self._total_tokens_out,
            "total_tokens": self._total_tokens_in + self._total_tokens_out,
        }


# Global logger instance
_cost_logger: CostLogger | None = None

def get_cost_logger() -> CostLogger:
    """Get the global cost logger."""
    global _cost_logger
    if _cost_logger is None:
        _cost_logger = CostLogger()
    return _cost_logger

def log_model_call(
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    success: bool,
    error: str | None = None,
    **metadata: Any,
) -> None:
    """Convenience function to log a model call."""
    get_cost_logger().log_call(
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        success=success,
        error=error,
        metadata=metadata if metadata else None,
    )
