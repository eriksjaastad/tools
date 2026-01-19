"""
Budget Manager - Enforces session and daily limits.
Updated for UAS overhaul.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from .cost_logger import CostLogger

logger = logging.getLogger(__name__)

class BudgetManager:
    """
    FR-4.2, 4.3: Budget tracking and enforcement.
    """

    def __init__(self, cost_logger: CostLogger, config_path: str = "config/budget.yaml"):
        self.cost_logger = cost_logger
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.overrides = {"amount": 0.0, "reason": ""}

    def _load_config(self) -> Dict:
        if not self.config_path.exists():
            return {"limits": {"session_usd": 5.0, "daily_usd": 10.0}}
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f) or {"limits": {"session_usd": 5.0, "daily_usd": 10.0}}
        except Exception as e:
            logger.warning(f"Failed to load budget config: {e}")
            return {"limits": {"session_usd": 5.0, "daily_usd": 10.0}}

    def estimate_cost(self, model: str, input_tokens: int, estimated_output_tokens: int) -> float:
        """
        Estimate USD cost for a model call.
        Prices from PRD:
        - Local: $0
        - Gemini Flash: $0.0001 per 1K tokens
        - Claude Sonnet: $0.003 per 1K tokens
        """
        is_local = "ollama" in model.lower() or "local" in model.lower()
        if is_local:
            return 0.0
            
        rate = 0.003  # Default to premium
        if "gemini" in model.lower() and "flash" in model.lower():
            rate = 0.0001
        
        total_tokens = input_tokens + estimated_output_tokens
        return (total_tokens / 1000.0) * rate

    def can_afford(self, model: str, estimated_tokens_in: int, estimated_tokens_out: int) -> Tuple[bool, str]:
        """
        Check if budget allows a call to the specified model.
        Returns (allowed, reason).
        """
        # Feature flag check
        import os
        if os.getenv("UAS_DISABLE_BUDGET_CHECK") == "1":
            return True, "Budget check disabled by environment"

        estimated_cost = self.estimate_cost(model, estimated_tokens_in, estimated_tokens_out)
        
        totals = self.cost_logger.get_session_totals()
        daily_totals = self.cost_logger.daily_totals
        
        session_limit = self.config.get("limits", {}).get("session_usd", 5.0)
        daily_limit = self.config.get("limits", {}).get("daily_usd", 10.0)
        
        # Apply override
        effective_session_limit = session_limit + self.overrides["amount"]
        
        current_session = totals.get("cloud_cost_usd", 0.0)
        current_daily = daily_totals.get("cloud_cost_usd", 0.0)
        
        if (current_session + estimated_cost) > effective_session_limit:
            return False, f"Session budget exceeded (${current_session:.4f} + ${estimated_cost:.4f} > ${effective_session_limit:.2f})"
            
        if (current_daily + estimated_cost) > daily_limit:
            return False, f"Daily budget exceeded (${current_daily:.4f} + ${estimated_cost:.4f} > ${daily_limit:.2f})"
            
        return True, "OK"

    def record_cost(self, model: str, tokens_in: int, tokens_out: int, task_type: str = "default", was_fallback: bool = False):
        """
        Record actual cost after a successful call.
        """
        is_local = "ollama" in model.lower() or "local" in model.lower()
        cost = self.estimate_cost(model, tokens_in, tokens_out)
        
        # Delegate logging to cost_logger
        self.cost_logger.log_call(model, tokens_in, tokens_out, cost, is_local)
        
        # Log alerts
        status = self.get_status()
        if status["percent_used"] > self.config.get("alerts", {}).get("warn_at_percent", 80):
            logger.warning(f"Budget Alert: {status['percent_used']:.1f}% of session limit used!")

    def get_status(self) -> Dict[str, Any]:
        totals = self.cost_logger.get_session_totals()
        session_spent = totals.get("cloud_cost_usd", 0.0)
        session_limit = self.config.get("limits", {}).get("session_usd", 5.0) + self.overrides["amount"]
        
        daily_spent = self.cost_logger.daily_totals.get("cloud_cost_usd", 0.0)
        daily_limit = self.config.get("limits", {}).get("daily_usd", 10.0)
        
        return {
            "session_spent": session_spent,
            "session_limit": session_limit,
            "daily_spent": daily_spent,
            "daily_limit": daily_limit,
            "percent_used": (session_spent / session_limit * 100) if session_limit > 0 else 0
        }

    def override_budget(self, amount: float, reason: str):
        self.overrides["amount"] += amount
        self.overrides["reason"] = reason
        logger.info(f"Budget override applied: ${amount} for '{reason}'")

# Global singleton
_instance: Optional[BudgetManager] = None

def get_budget_manager() -> BudgetManager:
    global _instance
    if _instance is None:
        from .cost_logger import get_cost_logger
        _instance = BudgetManager(cost_logger=get_cost_logger())
    return _instance
