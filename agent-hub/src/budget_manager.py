"""
Budget Manager - Enforces session and daily limits.
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
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def estimate_cost(self, model: str, input_tokens: int, estimated_output_tokens: int) -> float:
        """
        Estimate USD cost for a model call.
        Prices from PRD:
        - Local: $0
        - Gemini Flash: $0.0001 per 1K tokens
        - Claude Sonnet: $0.003 per 1K tokens
        """
        is_local = "ollama" in model or "local" in model
        if is_local:
            return 0.0
            
        rate = 0.003  # Default to premium
        if "gemini" in model.lower() and "flash" in model.lower():
            rate = 0.0001
        
        total_tokens = input_tokens + estimated_output_tokens
        return (total_tokens / 1000.0) * rate

    def can_afford(self, estimated_cost: float) -> Dict[str, Any]:
        """
        Check if session/daily limits allow a call.
        """
        totals = self.cost_logger.get_session_totals()
        daily_totals = self.cost_logger.daily_totals
        
        session_limit = self.config.get("limits", {}).get("session_usd", 5.0)
        daily_limit = self.config.get("limits", {}).get("daily_usd", 10.0)
        
        # Apply override
        effective_session_limit = session_limit + self.overrides["amount"]
        
        current_session = totals["cloud_cost_usd"]
        current_daily = daily_totals["cloud_cost_usd"]
        
        if (current_session + estimated_cost) > effective_session_limit:
            return {
                "allowed": False, 
                "reason": f"Session budget exceeded (${current_session:.4f} + ${estimated_cost:.4f} > ${effective_session_limit:.2f})",
                "remaining_budget": effective_session_limit - current_session
            }
            
        if (current_daily + estimated_cost) > daily_limit:
            return {
                "allowed": False, 
                "reason": f"Daily budget exceeded (${current_daily:.4f} + ${estimated_cost:.4f} > ${daily_limit:.2f})",
                "remaining_budget": daily_limit - current_daily
            }
            
        return {
            "allowed": True, 
            "reason": "OK",
            "remaining_budget": effective_session_limit - current_session
        }

    def record_spend(self, model: str, tokens: int, cost: float, is_local: bool):
        # Delegate logging to cost_logger
        # The prompt says 'record_spend' but cost_logger has 'log_call'
        # I'll use input/output token split if possible, otherwise split 50/50 for logging
        self.cost_logger.log_call(model, tokens // 2, tokens // 2, cost, is_local)
        
        # Check alerts
        status = self.get_status()
        if status["percent_used"] > self.config.get("alerts", {}).get("warn_at_percent", 80):
            logger.warning(f"Budget Alert: {status['percent_used']}% of session limit used!")

    def get_status(self) -> Dict[str, Any]:
        totals = self.cost_logger.get_session_totals()
        session_spent = totals["cloud_cost_usd"]
        session_limit = self.config.get("limits", {}).get("session_usd", 5.0)
        
        daily_spent = self.cost_logger.daily_totals["cloud_cost_usd"]
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
