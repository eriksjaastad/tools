import pytest
from unittest.mock import MagicMock
from src.budget_manager import BudgetManager

def test_budget_estimation():
    logger = MagicMock()
    mgr = BudgetManager(logger)
    
    # Local should be 0
    cost = mgr.estimate_cost("ollama/llama3", 1000, 500)
    assert cost == 0.0
    
    # Cloud should be > 0
    cost = mgr.estimate_cost("gemini-flash", 1000, 500)
    assert cost > 0

def test_budget_limit_enforcement():
    logger = MagicMock()
    # 4.9 spent, 5.0 limit.
    logger.get_session_totals.return_value = {"cloud_cost_usd": 4.9}
    logger.daily_totals = {"cloud_cost_usd": 0.0}
    
    mgr = BudgetManager(logger)
    mgr.config = {"limits": {"session_usd": 5.0, "daily_usd": 10.0}}
    
    # Affordable: gemini-flash with 100 tokens ~ 0.00001
    allowed, _ = mgr.can_afford("gemini-flash", 50, 50)
    assert allowed is True
    
    # Exceeding: cloud-premium with 50000 tokens ~ 0.15
    allowed, reason = mgr.can_afford("cloud-premium", 25000, 25000)
    assert allowed is False
    assert "Session budget exceeded" in reason
