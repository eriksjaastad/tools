"""
Graceful Degradation - Handle Ollama unavailability.

Provides:
- Health check for Ollama
- Low Power Mode with cloud fallback
- User notification
"""

import os
import logging
import time
import httpx
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
HEALTH_CHECK_TIMEOUT = float(os.getenv("UAS_HEALTH_CHECK_TIMEOUT", "5.0"))
LOW_POWER_NOTIFICATION_FILE = Path("data/LOW_POWER_MODE.txt")


@dataclass
class DegradationState:
    """Current degradation state."""
    is_degraded: bool = False
    degraded_since: str = ""
    last_health_check: str = ""
    consecutive_failures: int = 0
    fallback_model: str = "cloud-fast"


class DegradationManager:
    """
    Manages graceful degradation when Ollama unavailable.

    Usage:
        manager = DegradationManager()

        # Check health before local calls
        if not manager.is_ollama_healthy():
            # Use fallback
            model = manager.get_fallback_model()

        # Or use wrapper
        model = manager.get_best_available_model("local-coder")
    """

    def __init__(self):
        self._state = DegradationState()
        self._notification_callbacks: list[Callable] = []

    def check_ollama_health(self) -> bool:
        """
        Check if Ollama is responding.

        Returns:
            True if healthy, False if unavailable
        """
        self._state.last_health_check = datetime.now(timezone.utc).isoformat()

        try:
            with httpx.Client(timeout=HEALTH_CHECK_TIMEOUT) as client:
                response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    self._record_healthy()
                    return True
        except Exception as e:
            logger.debug(f"Ollama health check failed: {e}")

        self._record_unhealthy()
        return False

    def _record_healthy(self) -> None:
        """Record successful health check."""
        if self._state.is_degraded:
            logger.info("Ollama recovered - exiting Low Power Mode")
            self._notify_recovery()

        self._state.is_degraded = False
        self._state.degraded_since = ""
        self._state.consecutive_failures = 0

        # Remove notification file
        if LOW_POWER_NOTIFICATION_FILE.exists():
            LOW_POWER_NOTIFICATION_FILE.unlink()

    def _record_unhealthy(self) -> None:
        """Record failed health check."""
        from .circuit_breakers import get_circuit_breaker

        self._state.consecutive_failures += 1

        # Record to circuit breaker
        get_circuit_breaker().record_ollama_failure(
            f"Health check failed (attempt {self._state.consecutive_failures})"
        )

        if not self._state.is_degraded and self._state.consecutive_failures >= 2:
            self._enter_degraded_mode()

    def _enter_degraded_mode(self) -> None:
        """Enter Low Power Mode."""
        self._state.is_degraded = True
        self._state.degraded_since = datetime.now(timezone.utc).isoformat()

        logger.warning("Entering Low Power Mode - Ollama unavailable")

        # Create notification file
        LOW_POWER_NOTIFICATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOW_POWER_NOTIFICATION_FILE.write_text(
            f"""LOW POWER MODE ACTIVE

Ollama is unavailable. Using cloud fallback ({self._state.fallback_model}).

Entered: {self._state.degraded_since}
Consecutive failures: {self._state.consecutive_failures}

To check status:
  python -c "from src.degradation import get_degradation_manager; print(get_degradation_manager().get_status())"

This file will be removed when Ollama recovers.
"""
        )

        self._notify_degraded()

    def _notify_degraded(self) -> None:
        """Notify callbacks about entering degraded mode."""
        for callback in self._notification_callbacks:
            try:
                callback("degraded", self._state)
            except Exception as e:
                logger.error(f"Degradation callback failed: {e}")

    def _notify_recovery(self) -> None:
        """Notify callbacks about recovery."""
        for callback in self._notification_callbacks:
            try:
                callback("recovered", self._state)
            except Exception as e:
                logger.error(f"Recovery callback failed: {e}")

    def register_notification(self, callback: Callable) -> None:
        """Register callback for degradation events."""
        self._notification_callbacks.append(callback)

    def is_degraded(self) -> bool:
        """Check if currently in degraded mode."""
        return self._state.is_degraded

    def is_ollama_healthy(self) -> bool:
        """Check Ollama health (cached for 30s)."""
        # Quick check - if degraded, recheck periodically
        if self._state.is_degraded:
            return self.check_ollama_health()

        # If not degraded, trust cached state
        if self._state.last_health_check:
            last_check = datetime.fromisoformat(self._state.last_health_check.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last_check).total_seconds()
            if age < 30:  # Cache for 30 seconds
                return True

        return self.check_ollama_health()

    def get_fallback_model(self) -> str:
        """Get the fallback model for degraded mode."""
        return self._state.fallback_model

    def get_best_available_model(self, preferred: str) -> str:
        """
        Get best available model, considering degradation.

        Args:
            preferred: The model we'd prefer to use

        Returns:
            preferred if Ollama healthy, fallback otherwise
        """
        if preferred.startswith("local-") or preferred.startswith("ollama/"):
            if not self.is_ollama_healthy():
                logger.info(f"Degraded mode: using {self._state.fallback_model} instead of {preferred}")
                return self._state.fallback_model
        return preferred

    def get_status(self) -> dict:
        """Get current degradation status."""
        return {
            "is_degraded": self._state.is_degraded,
            "degraded_since": self._state.degraded_since,
            "last_health_check": self._state.last_health_check,
            "consecutive_failures": self._state.consecutive_failures,
            "fallback_model": self._state.fallback_model,
            "ollama_url": OLLAMA_BASE_URL,
        }


# Global instance
_degradation_manager: DegradationManager | None = None

def get_degradation_manager() -> DegradationManager:
    """Get the global degradation manager instance."""
    global _degradation_manager
    if _degradation_manager is None:
        _degradation_manager = DegradationManager()
    return _degradation_manager
