"""
Adaptive Polling - Dynamic interval based on activity.

Starts at min_interval, backs off to max_interval when idle.
Feature flag: UAS_ADAPTIVE_POLL
"""

import time
import logging

logger = logging.getLogger(__name__)

class AdaptivePoller:
    """
    Adaptive polling with exponential backoff.

    Usage:
        poller = AdaptivePoller(min_interval=1.0, max_interval=10.0)
        while True:
            had_activity = do_work()
            poller.wait(had_activity)
    """

    def __init__(
        self,
        min_interval: float = 1.0,
        max_interval: float = 10.0,
        backoff_factor: float = 1.5,
    ):
        """
        Args:
            min_interval: Fastest polling interval (seconds)
            max_interval: Slowest polling interval (seconds)
            backoff_factor: Multiplier when backing off (e.g., 1.5 = 50% slower)
        """
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.backoff_factor = backoff_factor
        self._current_interval = min_interval
        self._consecutive_idle = 0

    def wait(self, had_activity: bool) -> float:
        """
        Wait for the appropriate interval based on activity.

        Args:
            had_activity: True if work was done in the last cycle

        Returns:
            The interval that was waited (seconds)
        """
        if had_activity:
            # Reset to fast polling
            self._current_interval = self.min_interval
            self._consecutive_idle = 0
        else:
            # Back off
            self._consecutive_idle += 1
            self._current_interval = min(
                self._current_interval * self.backoff_factor,
                self.max_interval
            )

        interval = self._current_interval
        time.sleep(interval)
        return interval

    def reset(self) -> None:
        """Reset to minimum interval (call when expecting activity)."""
        self._current_interval = self.min_interval
        self._consecutive_idle = 0

    @property
    def current_interval(self) -> float:
        """Current polling interval."""
        return self._current_interval

    @property
    def is_at_max(self) -> bool:
        """True if polling at maximum (slowest) interval."""
        return self._current_interval >= self.max_interval

    def stats(self) -> dict:
        """Get poller statistics."""
        return {
            "current_interval": self._current_interval,
            "consecutive_idle": self._consecutive_idle,
            "at_max_interval": self.is_at_max,
        }


class FixedPoller:
    """Fixed interval poller for backwards compatibility."""

    def __init__(self, interval: float = 5.0):
        self.interval = interval

    def wait(self, had_activity: bool) -> float:
        time.sleep(self.interval)
        return self.interval

    def reset(self) -> None:
        pass

    @property
    def current_interval(self) -> float:
        return self.interval

    def stats(self) -> dict:
        return {"current_interval": self.interval, "fixed": True}


def create_poller(adaptive: bool = True) -> AdaptivePoller | FixedPoller:
    """
    Factory function to create the appropriate poller.

    Args:
        adaptive: If True, create AdaptivePoller; else FixedPoller
    """
    if adaptive:
        return AdaptivePoller()
    else:
        return FixedPoller()
