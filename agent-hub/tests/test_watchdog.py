import pytest
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from src.watchdog import (
    transition, acquire_lock, release_lock, 
    check_circuit_breakers, InvalidTransition,
    load_contract, save_contract, trigger_halt
)

@pytest.fixture
def base_contract():
    now = datetime.now(timezone.utc)
    return {
        "task_id": "TEST-TASK",
        "status": "pending_implementer",
        "timestamps": {
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        },
        "limits": {
            "max_rebuttals": 2,
            "max_review_cycles": 5,
            "timeout_minutes": {"implementer": 10, "local_review": 10, "judge": 10},
            "cost_ceiling_usd": 0.50
        },
        "lock": {"held_by": None, "acquired_at": None, "expires_at": None},
        "breaker": {"rebuttal_count": 0, "review_cycle_count": 0, "cost_usd": 0.0},
        "handoff_data": {"changed_files": []},
        "history": [],
        "specification": {"target_file": "test_file.txt"}
    }

def test_valid_transition(base_contract):
    new_status, reason = transition("pending_implementer", "lock_acquired", base_contract)
    assert new_status == "implementation_in_progress"
    assert "Implementer" in reason

def test_invalid_transition(base_contract):
    with pytest.raises(InvalidTransition):
        transition("pending_implementer", "code_written", base_contract)

def test_lock_acquisition(base_contract):
    # Acquire
    success = acquire_lock(base_contract, "actor1")
    assert success
    assert base_contract["lock"]["held_by"] == "actor1"
    
    # Try alternate actor
    success2 = acquire_lock(base_contract, "actor2")
    assert not success2
    assert base_contract["lock"]["held_by"] == "actor1"

def test_expired_lock_acquisition(base_contract):
    # Set expired lock
    base_contract["lock"] = {
        "held_by": "actor1",
        "acquired_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    }
    
    success = acquire_lock(base_contract, "actor2")
    assert success
    assert base_contract["lock"]["held_by"] == "actor2"

def test_destructive_diff_breaker(base_contract, tmp_path):
    target_file = tmp_path / "destructive.txt"
    target_file.write_text("line1\nline2\nline3\nline4\n")
    base_contract["specification"]["target_file"] = str(target_file)
    base_contract["handoff_data"]["diff_stats"] = {"lines_deleted": 3} # 3/5 deleted (>50%)
    
    # Actually count_lines("line1\nline2\nline3\nline4\n") is 4
    # deleted (3) + total_lines (4) = 7 before? No, wait.
    # Logic in code: total_lines = count_lines(content) + deleted
    # if content is current file (4 lines), deleted is 3, total was 7. 3/7 < 0.5
    
    # Let's make it more than 50%
    base_contract["handoff_data"]["diff_stats"]["lines_deleted"] = 10
    
    should_halt, reason = check_circuit_breakers(base_contract)
    assert should_halt
    assert "destructive diff detected" in reason.lower()

def test_hallucination_loop_breaker(base_contract):
    failed_hash = "abc123hash"
    base_contract["handoff_data"]["current_file_hash"] = failed_hash
    base_contract["history"] = [
        {"file_hash": failed_hash, "verdict": "FAIL"}
    ]
    
    should_halt, reason = check_circuit_breakers(base_contract)
    assert should_halt
    assert "hallucination loop" in reason.lower()

def test_nitpicking_breaker(base_contract, tmp_path):
    base_contract["breaker"]["review_cycle_count"] = 3
    report_path = tmp_path / "JUDGE_REPORT.json"
    report_data = {
        "blocking_issues": [
            {"description": "Too much spacing on line 5"}
        ],
        "suggestions": [
            {"description": "Fix indentation in main.py"}
        ]
    }
    report_path.write_text(json.dumps(report_data))
    base_contract["handoff_data"]["judge_report_json"] = str(report_path)
    
    should_halt, reason = check_circuit_breakers(base_contract)
    assert should_halt
    assert "nitpicking" in reason.lower()

def test_global_timeout_breaker(base_contract):
    base_contract["timestamps"]["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    
    should_halt, reason = check_circuit_breakers(base_contract)
    assert should_halt
    assert "global timeout" in reason.lower()

def test_save_and_load_contract(tmp_path, base_contract):
    contract_path = tmp_path / "TASK_CONTRACT.json"
    save_contract(base_contract, contract_path)
    
    assert contract_path.exists()
    loaded = load_contract(contract_path)
    assert loaded["task_id"] == "TEST-TASK"

def test_trigger_halt(tmp_path, base_contract):
    contract_path = tmp_path / "TASK_CONTRACT.json"
    save_contract(base_contract, contract_path)
    
    trigger_halt(base_contract, "Circuit test", "test_trigger", contract_path)
    
    assert not contract_path.exists()
    assert (tmp_path / "TASK_CONTRACT.json.lock").exists()
    assert (tmp_path / "ERIK_HALT.md").exists()

def test_update_cost(base_contract):
    from src.watchdog import update_cost
    # GPT-4o: $2.50 input, $10.00 output per 1M
    update_cost(base_contract, 100000, 50000, "gpt-4o")
    # 0.1 * 2.5 = 0.25
    # 0.05 * 10.0 = 0.50
    # Total = 0.75
    assert base_contract["breaker"]["cost_usd"] == pytest.approx(0.75)
    assert base_contract["breaker"]["tokens_used"] == 150000

def test_cleanup_task_files(tmp_path, base_contract):
    from src.watchdog import cleanup_task_files
    handoff_dir = tmp_path / "_handoff"
    handoff_dir.mkdir()
    
    contract_path = handoff_dir / "TASK_CONTRACT.json"
    contract_path.write_text("{}")
    report_path = handoff_dir / "JUDGE_REPORT.md"
    report_path.write_text("report")
    log_path = handoff_dir / "transition.ndjson"
    log_path.write_text("log")
    
    cleanup_task_files("TEST-TASK", handoff_dir)
    
    assert not contract_path.exists()
    assert not report_path.exists()
    assert log_path.exists() # Should NOT be archived
    
    archive_dir = handoff_dir / "archive" / "TEST-TASK"
    assert (archive_dir / "TASK_CONTRACT.json").exists()
    assert (archive_dir / "JUDGE_REPORT.md").exists()

def test_ndjson_rotation(tmp_path, base_contract):
    from src.watchdog import log_transition
    handoff_dir = tmp_path / "_handoff"
    handoff_dir.mkdir()
    
    log_file = handoff_dir / "transition.ndjson"
    # Create a 6MB file
    with open(log_file, "wb") as f:
        f.write(b"0" * (6 * 1024 * 1024))
        
    log_transition(base_contract, "event", "old", log_dir=handoff_dir)
    
    assert (handoff_dir / "transition.ndjson.1").exists()
    assert log_file.stat().st_size < 1024 # New small file
