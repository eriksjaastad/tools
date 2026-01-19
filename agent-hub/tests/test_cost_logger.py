import json
import pytest
from pathlib import Path
from src.cost_logger import CostLogger

def test_cost_logger_log_call(tmp_path):
    log_file = tmp_path / "audit.ndjson"
    persist_file = tmp_path / "state.json"
    logger = CostLogger(log_file=log_file, persist_file=persist_file)
    
    logger.log_call("test-model", 100, 50, 0.05, False)
    
    assert log_file.exists()
    content = log_file.read_text()
    data = json.loads(content.strip())
    assert data["model"] == "test-model"
    assert data["cost_usd"] == 0.05
    assert data["is_local"] is False

def test_cost_logger_totals(tmp_path):
    logger = CostLogger(log_file=tmp_path/"a", persist_file=tmp_path/"b")
    logger.log_call("local", 50, 50, 0.0, True)
    logger.log_call("cloud", 100, 100, 0.1, False)
    
    totals = logger.get_session_totals()
    assert totals["local_calls"] == 1
    assert totals["cloud_calls"] == 1
    assert totals["cloud_cost_usd"] == 0.1
