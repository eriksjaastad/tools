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
    logger.get_session_totals.return_value = {"cloud_cost_usd": 4.9}
    logger.daily_totals = {"cloud_cost_usd": 0.0}
    
    mgr = BudgetManager(logger)
    mgr.config = {"limits": {"session_usd": 5.0}}
    
    # affordable
    assert mgr.can_afford(0.05)["allowed"] is True
    # exceeding
    assert mgr.can_afford(0.2)["allowed"] is False
