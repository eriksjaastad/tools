"""
Circuit Breakers - Extended halt conditions for UAS components.

Integrates with watchdog.py to provide automatic halt on:
- Router exhaustion (all models failed)
- SQLite bus failures
- Budget exceeded
- Ollama unavailable
"""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Callable
from enum import Enum

logger = logging.getLogger(__name__)

# Halt file location
HALT_FILE = Path(os.getenv("UAS_HALT_FILE", "ERIK_HALT.md"))


class HaltReason(Enum):
    """Reasons for circuit breaker activation."""
    ROUTER_EXHAUSTED = "router_exhausted"
    SQLITE_FAILURE = "sqlite_failure"
    BUDGET_EXCEEDED = "budget_exceeded"
    OLLAMA_UNAVAILABLE = "ollama_unavailable"
    MODEL_COOLDOWN_CASCADE = "model_cooldown_cascade"
    MESSAGE_BUS_CORRUPT = "message_bus_corrupt"


@dataclass
class CircuitBreakerState:
    """Tracks circuit breaker state."""
    router_failures: int = 0
    sqlite_failures: int = 0
    ollama_failures: int = 0
    last_ollama_check: str = ""
    is_halted: bool = False
    halt_reason: str = ""


# Thresholds
ROUTER_FAILURE_THRESHOLD = int(os.getenv("UAS_ROUTER_FAILURE_LIMIT", "5"))
SQLITE_FAILURE_THRESHOLD = int(os.getenv("UAS_SQLITE_FAILURE_LIMIT", "3"))
OLLAMA_FAILURE_THRESHOLD = int(os.getenv("UAS_OLLAMA_FAILURE_LIMIT", "3"))


class CircuitBreaker:
    """
    Extended circuit breaker for UAS components.

    Usage:
        breaker = CircuitBreaker()

        # Record events
        breaker.record_router_failure("All models exhausted")
        breaker.record_sqlite_failure("Connection refused")

        # Check status
        if breaker.should_halt():
            breaker.trigger_halt(HaltReason.ROUTER_EXHAUSTED, context)
    """

    def __init__(self, state_path: Path | None = None):
        self.state_path = state_path or Path("data/circuit_breaker_state.json")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()
        self._halt_callbacks: list[Callable] = []

    def _load_state(self) -> CircuitBreakerState:
        """Load or create circuit breaker state."""
        if self.state_path.exists():
            try:
                import json
                data = json.loads(self.state_path.read_text())
                return CircuitBreakerState(**data)
            except Exception as e:
                logger.warning(f"Failed to load circuit breaker state: {e}")
        return CircuitBreakerState()

    def _save_state(self) -> None:
        """Persist state to disk."""
        import json
        from dataclasses import asdict
        self.state_path.write_text(json.dumps(asdict(self._state), indent=2))

    def register_halt_callback(self, callback: Callable) -> None:
        """Register callback to be called on halt."""
        self._halt_callbacks.append(callback)

    def record_router_failure(self, error: str) -> None:
        """Record a router failure (all models in chain failed)."""
        self._state.router_failures += 1
        logger.warning(f"Router failure #{self._state.router_failures}: {error}")
        self._save_state()

        if self._state.router_failures >= ROUTER_FAILURE_THRESHOLD:
            self.trigger_halt(
                HaltReason.ROUTER_EXHAUSTED,
                f"Router failed {self._state.router_failures} times. Last error: {error}"
            )

    def record_router_success(self) -> None:
        """Reset router failure count on success."""
        if self._state.router_failures > 0:
            self._state.router_failures = 0
            self._save_state()

    def record_sqlite_failure(self, error: str) -> None:
        """Record a SQLite message bus failure."""
        self._state.sqlite_failures += 1
        logger.warning(f"SQLite failure #{self._state.sqlite_failures}: {error}")
        self._save_state()

        if self._state.sqlite_failures >= SQLITE_FAILURE_THRESHOLD:
            self.trigger_halt(
                HaltReason.SQLITE_FAILURE,
                f"SQLite bus failed {self._state.sqlite_failures} times. Last error: {error}"
            )

    def record_sqlite_success(self) -> None:
        """Reset SQLite failure count on success."""
        if self._state.sqlite_failures > 0:
            self._state.sqlite_failures = 0
            self._save_state()

    def record_ollama_failure(self, error: str) -> None:
        """Record Ollama unavailability."""
        self._state.ollama_failures += 1
        self._state.last_ollama_check = datetime.now(timezone.utc).isoformat()
        logger.warning(f"Ollama failure #{self._state.ollama_failures}: {error}")
        self._save_state()

        if self._state.ollama_failures >= OLLAMA_FAILURE_THRESHOLD:
            # Don't halt, trigger degraded mode instead
            logger.error("Ollama unavailable - entering degraded mode")

    def record_ollama_success(self) -> None:
        """Reset Ollama failure count on success."""
        if self._state.ollama_failures > 0:
            self._state.ollama_failures = 0
            self._save_state()

    def is_ollama_degraded(self) -> bool:
        """Check if we're in Ollama-degraded mode."""
        return self._state.ollama_failures >= OLLAMA_FAILURE_THRESHOLD

    def should_halt(self) -> bool:
        """Check if any halt condition is met."""
        return self._state.is_halted

    def trigger_halt(self, reason: HaltReason, context: str) -> None:
        """Trigger a halt and create ERIK_HALT.md."""
        self._state.is_halted = True
        self._state.halt_reason = reason.value
        self._save_state()

        # Create halt file
        halt_content = f"""# HALT - Circuit Breaker Triggered

**Time:** {datetime.now(timezone.utc).isoformat()}
**Reason:** {reason.value}

## Context

{context}

## State at Halt

- Router failures: {self._state.router_failures}
- SQLite failures: {self._state.sqlite_failures}
- Ollama failures: {self._state.ollama_failures}

## Resolution

1. Investigate the root cause above
2. Fix the underlying issue
3. Delete this file to resume operations
4. Run `python -c "from src.circuit_breakers import get_circuit_breaker; get_circuit_breaker().reset()"`

---
*Generated by UAS Circuit Breaker*
"""
        HALT_FILE.write_text(halt_content)
        logger.critical(f"HALT triggered: {reason.value}. See {HALT_FILE}")

        # Call registered callbacks
        for callback in self._halt_callbacks:
            try:
                callback(reason, context)
            except Exception as e:
                logger.error(f"Halt callback failed: {e}")

    def reset(self) -> None:
        """Reset circuit breaker state (after manual intervention)."""
        self._state = CircuitBreakerState()
        self._save_state()

        # Remove halt file if exists
        if HALT_FILE.exists():
            HALT_FILE.unlink()

        logger.info("Circuit breaker reset")

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "is_halted": self._state.is_halted,
            "halt_reason": self._state.halt_reason,
            "router_failures": self._state.router_failures,
            "sqlite_failures": self._state.sqlite_failures,
            "ollama_failures": self._state.ollama_failures,
            "ollama_degraded": self.is_ollama_degraded(),
            "thresholds": {
                "router": ROUTER_FAILURE_THRESHOLD,
                "sqlite": SQLITE_FAILURE_THRESHOLD,
                "ollama": OLLAMA_FAILURE_THRESHOLD,
            }
        }


# Global instance
_circuit_breaker: CircuitBreaker | None = None

def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


def check_halt_file() -> bool:
    """Check if halt file exists (quick check for callers)."""
    return HALT_FILE.exists()
