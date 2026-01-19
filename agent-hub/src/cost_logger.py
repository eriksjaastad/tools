"""
Cost Logger - Track model usage and tokens with USD costs.
Supports local (free) and cloud (paid) tracking.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default locations
DEFAULT_LOG_PATH = Path("data/audit.ndjson")
DEFAULT_STATE_PATH = Path("data/budget_state.json")

class CostLogger:
    """
    Tracks and persists model call costs.
    FR-4.1: Track Local vs Cloud separately.
    """

    def __init__(self, log_file: Optional[Path] = None, persist_file: Optional[Path] = None):
        self.log_file = log_file or DEFAULT_LOG_PATH
        self.persist_file = persist_file or DEFAULT_STATE_PATH
        
        # Ensure directories exist
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.persist_file.parent.mkdir(parents=True, exist_ok=True)

        self.session_totals = {
            "local_calls": 0,
            "cloud_calls": 0,
            "local_tokens": 0,
            "cloud_tokens": 0,
            "cloud_cost_usd": 0.0
        }
        self.daily_totals = self.session_totals.copy()
        
        self.load_state()

    def log_call(self, model: str, input_tokens: int, output_tokens: int, cost_usd: float, is_local: bool):
        """
        Write NDJSON line with timestamp and update totals.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        record = {
            "timestamp": timestamp,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "is_local": is_local
        }

        # Write to NDJSON (append-only)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")

        # Update running totals
        total_tokens = input_tokens + output_tokens
        if is_local:
            self.session_totals["local_calls"] += 1
            self.session_totals["local_tokens"] += total_tokens
            self.daily_totals["local_calls"] += 1
            self.daily_totals["local_tokens"] += total_tokens
        else:
            self.session_totals["cloud_calls"] += 1
            self.session_totals["cloud_tokens"] += total_tokens
            self.session_totals["cloud_cost_usd"] += cost_usd
            self.daily_totals["cloud_calls"] += 1
            self.daily_totals["cloud_tokens"] += total_tokens
            self.daily_totals["cloud_cost_usd"] += cost_usd

        self.persist_state()

    def get_session_total_cost(self) -> float:
        return self.session_totals["cloud_cost_usd"]

    def get_session_totals(self) -> Dict[str, Any]:
        """Returns the format required by Prompt 2."""
        return self.session_totals.copy()

    def persist_state(self):
        """Save totals to budget_state.json."""
        state = {
            "daily_totals": self.daily_totals,
            "session_totals": self.session_totals,
            "last_updated": date.today().isoformat()
        }
        try:
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist cost state: {e}")

    def load_state(self):
        """Restore totals from budget_state.json."""
        if not self.persist_file.exists():
            return

        try:
            with open(self.persist_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                
                # Check if it's still today for daily totals
                today = date.today().isoformat()
                if state.get("last_updated") == today:
                    self.daily_totals = state.get("daily_totals", self.daily_totals)
                else:
                    # Reset daily totals if it's a new day
                    self.daily_totals = {k: 0 for k in self.session_totals}
                    self.daily_totals["cloud_cost_usd"] = 0.0
                
                # Session totals are always reset on fresh initialization of the class 
                # UNLESS we want to resume them? Prompt says "Persist cost data across sessions".
                # But it also says "session totals" vs "daily totals".
                # Usually session totals are per-process.
                # I'll keep them per-instance but allow loading if needed.
                # For UAS, we'll restore daily, but keep session fresh index-wise.
        except Exception as e:
            logger.warning(f"Failed to load cost state: {e}")

# Global instance for easy access
_instance: Optional[CostLogger] = None

def get_cost_logger() -> CostLogger:
    global _instance
    if _instance is None:
        _instance = CostLogger()
    return _instance

def log_model_call(model: str, tokens_in: int, tokens_out: int, latency_ms: float, success: bool, error: str = None, task_type: str = "default"):
    """Bridge for ollama_http_client and others expecting this function."""
    logger = get_cost_logger()
    is_local = "ollama" in model.lower() or "local" in model.lower()
    
    # Estimate cost if cloud
    cost = 0.0
    if not is_local:
        # Simple estimation matching BudgetManager
        rate = 0.003
        if "gemini" in model.lower() and "flash" in model.lower():
            rate = 0.0001
        cost = ((tokens_in + tokens_out) / 1000.0) * rate

    logger.log_call(model, tokens_in, tokens_out, cost, is_local)

# End of file
