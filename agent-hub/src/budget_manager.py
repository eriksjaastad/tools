"""
Budget Manager - Track and enforce cost limits.

Separates local compute costs from cloud API costs.
Provides pre-flight checks and real-time budget status.
"""

import os
import json
import logging
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Default budget file location
DEFAULT_BUDGET_PATH = Path("data/budget_state.json")

# Cost per 1M tokens (from ROADMAP.md)
MODEL_COSTS = {
    # Tier 1: Free (local)
    "ollama/llama3.2:1b": {"input": 0.0, "output": 0.0, "tier": "local"},
    "ollama/qwen2.5-coder:14b": {"input": 0.0, "output": 0.0, "tier": "local"},
    "ollama/deepseek-r1-distill-qwen:32b": {"input": 0.0, "output": 0.0, "tier": "local"},
    "local-fast": {"input": 0.0, "output": 0.0, "tier": "local"},
    "local-coder": {"input": 0.0, "output": 0.0, "tier": "local"},
    "local-reasoning": {"input": 0.0, "output": 0.0, "tier": "local"},

    # Tier 2: Cheap (cloud)
    "gemini/gemini-2.0-flash": {"input": 0.075, "output": 0.30, "tier": "cloud"},
    "cloud-fast": {"input": 0.075, "output": 0.30, "tier": "cloud"},

    # Tier 3: Premium (cloud)
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00, "tier": "cloud"},
    "cloud-premium": {"input": 3.00, "output": 15.00, "tier": "cloud"},
}

# Default limits
DEFAULT_SESSION_LIMIT = float(os.getenv("UAS_SESSION_BUDGET", "1.00"))  # $1.00
DEFAULT_DAILY_LIMIT = float(os.getenv("UAS_DAILY_BUDGET", "5.00"))  # $5.00


@dataclass
class BudgetState:
    """Current budget state."""
    session_id: str
    session_start: str

    # Cloud costs (actual dollars)
    session_cloud_cost: float = 0.0
    daily_cloud_cost: float = 0.0

    # Local compute (tracked separately, not dollars)
    session_local_calls: int = 0
    session_local_tokens: int = 0

    # Limits
    session_limit: float = DEFAULT_SESSION_LIMIT
    daily_limit: float = DEFAULT_DAILY_LIMIT

    # Tracking
    last_updated: str = ""
    current_date: str = ""

    # Escape tracking (tasks that went to cloud)
    cloud_escapes: list = field(default_factory=list)

    # Override support
    override_active: bool = False
    override_reason: str = ""
    override_expires: str = ""  # ISO timestamp



class BudgetManager:
    """
    Manages cost budgets for agent operations.

    Usage:
        budget = BudgetManager()

        # Check if we can afford a call
        if budget.can_afford(model="cloud-fast", estimated_tokens=1000):
            # Make the call
            result = make_api_call(...)
            budget.record_cost(model="cloud-fast", tokens_in=500, tokens_out=200)

        # Get current status
        status = budget.get_status()
        print(f"Session: ${status['session_cloud_cost']:.4f} / ${status['session_limit']:.2f}")
    """

    def __init__(
        self,
        budget_path: Path | str | None = None,
        session_id: str | None = None,
        session_limit: float | None = None,
        daily_limit: float | None = None,
    ):
        self.budget_path = Path(budget_path) if budget_path else DEFAULT_BUDGET_PATH
        self.budget_path.parent.mkdir(parents=True, exist_ok=True)

        # Load or create state
        self._state = self._load_or_create_state(
            session_id=session_id,
            session_limit=session_limit,
            daily_limit=daily_limit,
        )

    def _load_or_create_state(
        self,
        session_id: str | None,
        session_limit: float | None,
        daily_limit: float | None,
    ) -> BudgetState:
        """Load existing state or create new one."""
        today = date.today().isoformat()

        if self.budget_path.exists():
            try:
                data = json.loads(self.budget_path.read_text())
                state = BudgetState(**data)

                # Reset daily costs if new day
                if state.current_date != today:
                    state.daily_cloud_cost = 0.0
                    state.current_date = today
                    state.cloud_escapes = []

                # Apply any overrides
                if session_limit is not None:
                    state.session_limit = session_limit
                if daily_limit is not None:
                    state.daily_limit = daily_limit

                return state
            except Exception as e:
                logger.warning(f"Failed to load budget state: {e}, creating new")

        # Create new state
        import hashlib
        import time
        sid = session_id or hashlib.sha256(f"{time.time()}{os.getpid()}".encode()).hexdigest()[:12]

        return BudgetState(
            session_id=sid,
            session_start=datetime.now(timezone.utc).isoformat(),
            session_limit=session_limit or DEFAULT_SESSION_LIMIT,
            daily_limit=daily_limit or DEFAULT_DAILY_LIMIT,
            current_date=today,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    def _save_state(self) -> None:
        """Persist state to disk."""
        self._state.last_updated = datetime.now(timezone.utc).isoformat()
        self.budget_path.write_text(json.dumps(asdict(self._state), indent=2))

    def _get_model_cost(self, model: str) -> dict:
        """Get cost info for a model, with fallback."""
        if model in MODEL_COSTS:
            return MODEL_COSTS[model]

        # Try to match by prefix
        for key, cost in MODEL_COSTS.items():
            if model.startswith(key.split("/")[0]) or key in model:
                return cost

        # Default to cloud-fast pricing as conservative estimate
        logger.warning(f"Unknown model {model}, assuming cloud pricing")
        return {"input": 0.10, "output": 0.40, "tier": "cloud"}

    def estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost for a call in dollars."""
        cost_info = self._get_model_cost(model)

        if cost_info["tier"] == "local":
            return 0.0

        input_cost = (tokens_in / 1_000_000) * cost_info["input"]
        output_cost = (tokens_out / 1_000_000) * cost_info["output"]
        return input_cost + output_cost

    def can_afford(
        self,
        model: str,
        estimated_tokens_in: int = 1000,
        estimated_tokens_out: int = 500,
    ) -> tuple[bool, str]:
        """
        Check if we can afford a model call.

        Returns:
            (can_afford, reason)
        """
        # Check for global disable
        if os.getenv("UAS_DISABLE_BUDGET_CHECK", "").lower() in ("1", "true", "yes"):
            return True, "Budget checks disabled via UAS_DISABLE_BUDGET_CHECK"

        # Check for active override
        if self.is_override_active():
            return True, f"Override active: {self._state.override_reason}"

        cost_info = self._get_model_cost(model)


        # Local models always allowed
        if cost_info["tier"] == "local":
            return True, "Local model - no cost"

        estimated_cost = self.estimate_cost(model, estimated_tokens_in, estimated_tokens_out)

        # Check session limit
        if self._state.session_cloud_cost + estimated_cost > self._state.session_limit:
            return False, f"Session limit exceeded (${self._state.session_cloud_cost:.4f} + ${estimated_cost:.4f} > ${self._state.session_limit:.2f})"

        # Check daily limit
        if self._state.daily_cloud_cost + estimated_cost > self._state.daily_limit:
            return False, f"Daily limit exceeded (${self._state.daily_cloud_cost:.4f} + ${estimated_cost:.4f} > ${self._state.daily_limit:.2f})"

        return True, f"Within budget (estimated: ${estimated_cost:.4f})"

    def record_cost(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        task_type: str | None = None,
        was_fallback: bool = False,
    ) -> float:
        """
        Record actual cost of a completed call.

        Returns actual cost in dollars.
        """
        cost_info = self._get_model_cost(model)
        actual_cost = self.estimate_cost(model, tokens_in, tokens_out)

        if cost_info["tier"] == "local":
            self._state.session_local_calls += 1
            self._state.session_local_tokens += tokens_in + tokens_out
        else:
            self._state.session_cloud_cost += actual_cost
            self._state.daily_cloud_cost += actual_cost

            # Track cloud escapes
            if was_fallback:
                self._state.cloud_escapes.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": model,
                    "task_type": task_type,
                    "cost": actual_cost,
                    "tokens": tokens_in + tokens_out,
                })

        self._save_state()
        return actual_cost

    def get_status(self) -> dict:
        """Get current budget status."""
        return {
            "session_id": self._state.session_id,
            "session_cloud_cost": self._state.session_cloud_cost,
            "session_limit": self._state.session_limit,
            "session_remaining": self._state.session_limit - self._state.session_cloud_cost,
            "session_percent_used": (self._state.session_cloud_cost / self._state.session_limit * 100) if self._state.session_limit > 0 else 0,
            "daily_cloud_cost": self._state.daily_cloud_cost,
            "daily_limit": self._state.daily_limit,
            "daily_remaining": self._state.daily_limit - self._state.daily_cloud_cost,
            "local_calls": self._state.session_local_calls,
            "local_tokens": self._state.session_local_tokens,
            "cloud_escapes": len(self._state.cloud_escapes),
            "last_updated": self._state.last_updated,
        }

    def get_cloud_escapes(self) -> list[dict]:
        """Get list of tasks that escaped to cloud."""
        return self._state.cloud_escapes.copy()

    def reset_session(self) -> None:
        """Reset session costs (keeps daily)."""
        self._state.session_cloud_cost = 0.0
        self._state.session_local_calls = 0
        self._state.session_local_tokens = 0
        self._state.cloud_escapes = []
        self._save_state()

    def request_override(
        self,
        reason: str,
        duration_minutes: int = 60,
    ) -> None:
        """
        Request a temporary budget override.

        Args:
            reason: Why the override is needed
            duration_minutes: How long the override lasts
        """
        from datetime import timedelta

        expires = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        self._state.override_active = True
        self._state.override_reason = reason
        self._state.override_expires = expires.isoformat()

        logger.warning(f"Budget override activated: {reason} (expires: {expires})")
        self._save_state()

    def clear_override(self) -> None:
        """Clear any active override."""
        self._state.override_active = False
        self._state.override_reason = ""
        self._state.override_expires = ""
        self._save_state()

    def is_override_active(self) -> bool:
        """Check if override is currently active."""
        if not self._state.override_active:
            return False

        # Check expiration
        if self._state.override_expires:
            try:
                expires = datetime.fromisoformat(self._state.override_expires.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expires:
                    self.clear_override()
                    return False
            except Exception:
                self.clear_override()
                return False

        return True



# Global instance
_budget_manager: BudgetManager | None = None

def get_budget_manager() -> BudgetManager:
    """Get the global budget manager instance."""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager()
    return _budget_manager
