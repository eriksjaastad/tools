import pytest
import json
import os
from pathlib import Path
from src.cost_logger import CostLogger, log_model_call, get_cost_logger

@pytest.fixture
def temp_log(tmp_path):
    log_file = tmp_path / "test_cost.ndjson"
    return log_file

def test_cost_logger_init(temp_log):
    """Test logger initialization and file creation."""
    logger = CostLogger(log_path=temp_log)
    assert logger.log_path == temp_log
    assert temp_log.parent.exists()

def test_log_call(temp_log):
    """Test logging a successful call."""
    logger = CostLogger(log_path=temp_log)
    logger.log_call(
        model="test-model",
        tokens_in=100,
        tokens_out=50,
        latency_ms=500,
        success=True
    )
    
    assert temp_log.exists()
    content = temp_log.read_text().strip().split("\n")
    assert len(content) == 1
    
    data = json.loads(content[0])
    assert data["model"] == "test-model"
    assert data["tokens_in"] == 100
    assert data["tokens_out"] == 50
    assert data["latency_ms"] == 500
    assert data["success"] is True
    assert "timestamp" in data
    assert "session_id" in data

def test_log_call_failure(temp_log):
    """Test logging a failed call."""
    logger = CostLogger(log_path=temp_log)
    logger.log_call(
        model="test-model",
        tokens_in=100,
        tokens_out=0,
        latency_ms=1000,
        success=False,
        error="Timeout"
    )
    
    data = json.loads(temp_log.read_text().strip())
    assert data["success"] is False
    assert data["error"] == "Timeout"

def test_session_summary(temp_log):
    """Test summary aggregation."""
    logger = CostLogger(log_path=temp_log)
    logger.log_call("m1", 10, 20, 100, True)
    logger.log_call("m1", 10, 20, 100, True)
    logger.log_call("m1", 10, 0, 100, False)
    
    summary = logger.session_summary()
    assert summary["total_calls"] == 3
    assert summary["failed_calls"] == 1
    assert summary["total_tokens_in"] == 30
    assert summary["total_tokens_out"] == 40
    assert summary["success_rate"] == pytest.approx(0.666, 0.01)

def test_global_log_model_call(temp_log):
    """Test the convenience function with a manual logger override."""
    # We'll patch get_cost_logger to use our temp logger
    logger = CostLogger(log_path=temp_log)
    with patch("src.cost_logger.get_cost_logger", return_value=logger):
        log_model_call("global-model", 5, 5, 50, True)
    
    data = json.loads(temp_log.read_text().strip())
    assert data["model"] == "global-model"

from unittest.mock import patch
