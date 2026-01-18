import pytest
import os
from pathlib import Path
from src.budget_manager import BudgetManager, MODEL_COSTS

@pytest.fixture
def temp_budget(tmp_path):
    return tmp_path / "test_budget.json"

def test_budget_manager_init(temp_budget):
    manager = BudgetManager(budget_path=temp_budget)
    assert manager._state.session_cloud_cost == 0.0
    # File is created lazily on first save (record_cost or reset_session)
    assert manager._state.session_id is not None

def test_estimate_cost_local():
    manager = BudgetManager()
    cost = manager.estimate_cost("local-fast", 1000, 500)
    assert cost == 0.0

def test_estimate_cost_cloud():
    manager = BudgetManager()
    # cloud-fast: $0.075/M input, $0.30/M output
    cost = manager.estimate_cost("cloud-fast", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.375, 0.01)

def test_can_afford_local(temp_budget):
    manager = BudgetManager(budget_path=temp_budget, session_limit=0.01)
    can, reason = manager.can_afford("local-fast", 10000, 5000)
    assert can is True
    assert "Local model" in reason

def test_can_afford_within_budget(temp_budget):
    manager = BudgetManager(budget_path=temp_budget, session_limit=1.00)
    can, reason = manager.can_afford("cloud-fast", 1000, 500)
    assert can is True
    assert "Within budget" in reason

def test_cannot_afford_exceeds_session(temp_budget):
    manager = BudgetManager(budget_path=temp_budget, session_limit=0.0001)
    can, reason = manager.can_afford("cloud-premium", 10000, 5000)
    assert can is False
    assert "Session limit exceeded" in reason

def test_record_cost(temp_budget):
    manager = BudgetManager(budget_path=temp_budget)
    cost = manager.record_cost("cloud-fast", 100000, 50000)
    assert cost > 0
    status = manager.get_status()
    assert status["session_cloud_cost"] == cost

def test_record_local_cost(temp_budget):
    manager = BudgetManager(budget_path=temp_budget)
    manager.record_cost("local-fast", 1000, 500)
    status = manager.get_status()
    assert status["local_calls"] == 1
    assert status["local_tokens"] == 1500

def test_cloud_escape_tracking(temp_budget):
    manager = BudgetManager(budget_path=temp_budget)
    manager.record_cost("cloud-fast", 1000, 500, task_type="code", was_fallback=True)
    escapes = manager.get_cloud_escapes()
    assert len(escapes) == 1
    assert escapes[0]["task_type"] == "code"
