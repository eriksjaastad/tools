import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from src.dashboard import (
    format_time_ago, build_agents_table, build_questions_table, 
    build_cost_panel, build_budget_panel, build_escapes_table
)

def test_format_time_ago():
    now = datetime.now(timezone.utc)
    
    # 10 seconds ago
    ts_10s = (now - timedelta(seconds=10)).isoformat()
    assert format_time_ago(ts_10s) == "10s ago"
    
    # 5 minutes ago
    ts_5m = (now - timedelta(minutes=5)).isoformat()
    assert format_time_ago(ts_5m) == "5m ago"
    
    # 2 hours ago
    ts_2h = (now - timedelta(hours=2)).isoformat()
    assert format_time_ago(ts_2h) == "2h ago"
    
    # Invalid
    assert format_time_ago("invalid") == "unknown"

def test_build_agents_table():
    bus_mock = MagicMock()
    bus_mock.get_agent_status.return_value = [
        {"agent_id": "worker-1", "last_seen": datetime.now(timezone.utc).isoformat(), "progress": "Implementing"}
    ]
    
    table = build_agents_table(bus_mock)
    assert table.title == "Active Agents"
    assert len(table.rows) == 1

def test_build_questions_table():
    bus_mock = MagicMock()
    bus_mock.get_pending_questions.return_value = [
        {"subagent_id": "worker-1", "question": "Short question?", "created_at": datetime.now(timezone.utc).isoformat()}
    ]
    
    table = build_questions_table(bus_mock)
    assert table.title == "Pending Questions"
    assert len(table.rows) == 1

@patch("src.dashboard.get_cost_logger")
def test_build_cost_panel(mock_get_logger):
    logger_mock = MagicMock()
    logger_mock.session_summary.return_value = {
        "total_calls": 10,
        "success_rate": 0.9,
        "total_tokens_in": 1000,
        "total_tokens_out": 500,
        "total_tokens": 1500
    }
    mock_get_logger.return_value = logger_mock
    
    panel = build_cost_panel()
@patch("src.dashboard.get_budget_manager")
def test_build_budget_panel(mock_get_budget):
    budget_mock = MagicMock()
    budget_mock.get_status.return_value = {
        "session_cloud_cost": 0.50,
        "session_limit": 1.00,
        "session_percent_used": 50.0,
        "daily_cloud_cost": 2.00,
        "daily_limit": 5.00,
        "local_calls": 100,
        "local_tokens": 50000,
        "cloud_escapes": 3,
    }
    mock_get_budget.return_value = budget_mock

    panel = build_budget_panel()
    assert panel.title == "Budget Status"
    assert "50%" in str(panel.renderable)

@patch("src.dashboard.get_budget_manager")
def test_build_escapes_table(mock_get_budget):
    budget_mock = MagicMock()
    budget_mock.get_cloud_escapes.return_value = [
        {"timestamp": "2026-01-18T12:00:00", "model": "cloud-fast", "task_type": "code", "cost": 0.01}
    ]
    mock_get_budget.return_value = budget_mock

    table = build_escapes_table()
    assert table.title == "Cloud Escapes (Fallbacks)"
    assert len(table.rows) == 1

