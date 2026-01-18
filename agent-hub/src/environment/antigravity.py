"""Anti-Gravity IDE environment adapter."""

import os
import time
from pathlib import Path

from .base import EnvironmentAdapter

class AntigravityAdapter(EnvironmentAdapter):
    """Adapter for Anti-Gravity IDE environment (best effort)."""

    name = "antigravity"

    # File-based handoff location
    HANDOFF_DIR = Path.home() / ".antigravity" / "handoff"

    @classmethod
    def detect(cls) -> bool:
        """Detect by checking for AG config or process."""
        ag_config = Path.home() / ".antigravity"
        return ag_config.exists()

    def get_config_path(self) -> Path:
        """Config at ~/.antigravity/"""
        return Path.home() / ".antigravity"

    def trigger(self, message: str) -> bool:
        """
        Trigger via file-based handoff.
        Write to handoff directory for AG to pick up.
        """
        try:
            self.HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
            handoff_file = self.HANDOFF_DIR / f"message_{int(time.time() * 1000)}.txt"
            handoff_file.write_text(message)
            return True
        except Exception:
            return False

    def read_response(self, timeout: float = 30.0) -> str | None:
        """
        Poll for response file.
        AG should write response_*.txt files.
        """
        response_pattern = "response_*.txt"
        start = time.time()

        while time.time() - start < timeout:
            responses = list(self.HANDOFF_DIR.glob(response_pattern))
            if responses:
                # Get most recent
                latest = max(responses, key=lambda p: p.stat().st_mtime)
                content = latest.read_text()
                latest.unlink()  # Clean up after reading
                return content
            time.sleep(0.5)

        return None
