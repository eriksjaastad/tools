import pytest
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from src.budget_manager import BudgetManager

@pytest.fixture
def temp_budget(tmp_path):
    return tmp_path / "test_budget.json"

def test_request_override(temp_budget):
    manager = BudgetManager(budget_path=temp_budget, session_limit=0.0001)

    # Should not afford normally
    can, _ = manager.can_afford("cloud-premium", 10000, 5000)
    assert can is False

    # Request override
    manager.request_override("Testing", duration_minutes=60)
    assert manager.is_override_active() is True

    # Should afford now
    can, reason = manager.can_afford("cloud-premium", 10000, 5000)
    assert can is True
    assert "Override active" in reason

def test_override_expiration(temp_budget):
    manager = BudgetManager(budget_path=temp_budget)

    # Set override with past expiration
    manager._state.override_active = True
    manager._state.override_reason = "Test"
    manager._state.override_expires = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    # Should be expired
    assert manager.is_override_active() is False

def test_clear_override(temp_budget):
    manager = BudgetManager(budget_path=temp_budget)
    manager.request_override("Test", duration_minutes=60)
    assert manager.is_override_active() is True

    manager.clear_override()
    assert manager.is_override_active() is False

def test_env_disable(temp_budget):
    with patch.dict(os.environ, {"UAS_DISABLE_BUDGET_CHECK": "1"}):
        manager = BudgetManager(budget_path=temp_budget, session_limit=0.0001)
        can, reason = manager.can_afford("cloud-premium", 10000, 5000)
        assert can is True
        assert "disabled" in reason.lower()
