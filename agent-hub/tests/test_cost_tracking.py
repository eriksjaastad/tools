import pytest
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from src.watchdog import update_cost, check_circuit_breakers, save_contract, load_contract

@pytest.fixture
def test_contract():
    return {
        "task_id": "TEST-COST",
        "status": "pending_implementer",
        "breaker": {
            "cost_usd": 0.0,
            "tokens_used": 0
        },
        "limits": {
            "cost_ceiling_usd": 0.50,
            "max_rebuttals": 2,
            "max_review_cycles": 5,
            "timeout_minutes": {"any": 30}
        },
        "timestamps": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        "handoff_data": {},
        "history": [],
        "git": {"repo_root": "."}
    }

def test_update_cost_accumulates(test_contract):
    """Cost should accumulate across calls."""
    # Using gpt-4o: $2.50 input, $10.00 output per 1M
    
    # 100k input tokens = $0.25
    update_cost(test_contract, 100000, 0, "gpt-4o")
    assert test_contract["breaker"]["cost_usd"] == pytest.approx(0.25)
    
    # 50k output tokens = $0.50
    update_cost(test_contract, 0, 50000, "gpt-4o")
    assert test_contract["breaker"]["cost_usd"] == pytest.approx(0.75)
    assert test_contract["breaker"]["tokens_used"] == 150000

def test_cost_ceiling_triggers_halt(test_contract):
    """Exceeding cost ceiling should trigger circuit breaker."""
    # Ceiling is 0.50. Set cost to 0.51
    test_contract["breaker"]["cost_usd"] = 0.51
    
    should_halt, reason = check_circuit_breakers(test_contract)
    assert should_halt
    assert "Trigger 7" in reason
    assert "cost ceiling exceeded" in reason.lower()

def test_cost_persists_across_restarts(tmp_path, test_contract):
    """Cost tracking should persist in state file."""
    contract_path = tmp_path / "TASK_CONTRACT.json"
    
    # 1. Update cost and save
    update_cost(test_contract, 200000, 0, "gpt-4o") # $0.50
    save_contract(test_contract, contract_path)
    
    # 2. Load and verify
    loaded = load_contract(contract_path)
    assert loaded["breaker"]["cost_usd"] == pytest.approx(0.50)
    
    # 3. Update again and verify accumulation
    update_cost(loaded, 0, 10000, "gpt-4o") # + $0.10
    assert loaded["breaker"]["cost_usd"] == pytest.approx(0.60)
