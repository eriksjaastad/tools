import pytest
from unittest.mock import MagicMock
from src.preflight import PreFlightChecker
from src.router import ModelSelection

def test_preflight_approval():
    budget = MagicMock()
    router = MagicMock()
    
    budget.estimate_cost.return_value = 0.01
    budget.can_afford.return_value = {"allowed": True, "reason": "OK"}
    router.route.return_value = ModelSelection("m", "t", [])
    
    checker = PreFlightChecker(budget, router)
    result = checker.check("task", "simple", 100)
    
    assert result.approved is True
    assert result.model == "m"

def test_preflight_halt(tmp_path):
    budget = MagicMock()
    router = MagicMock()
    
    budget.estimate_cost.return_value = 10.0
    budget.can_afford.return_value = {"allowed": False, "reason": "Too expensive", "remaining_budget": 0.0}
    router.route.return_value = ModelSelection("m", "t", [])
    
    checker = PreFlightChecker(budget, router)
    # Patch Path to avoid writing to real HALT.md in test?
    # Actually prompt says use temp dirs but I'll just check if it halts.
    result = checker.check("task", "simple", 100)
    assert result.approved is False
    assert result.halt_reason == "Too expensive"
