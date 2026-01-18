import pytest
import time
import threading
from pathlib import Path
from src.hub_client import HubClient
from src.worker_client import WorkerClient
from src.state_adapter import SQLiteStateAdapter, get_state_adapter
from unittest.mock import MagicMock, patch

@pytest.fixture
def temp_db(tmp_path):
    return tmp_path / "test_protocol.db"

def test_protocol_e2e(temp_db, monkeypatch):
    # Force SQLite adapter
    monkeypatch.setenv("UAS_SQLITE_BUS", "1")

    # Test via state adapter directly which clients use anyway
    adapter = SQLiteStateAdapter(temp_db)
    
    # 1. Worker asks
    msg_id = adapter.ask_parent("run-1", "worker-1", "Should I use async?")
    
    # 2. Parent sees
    pending = adapter.get_pending_questions("run-1")
    assert len(pending) == 1
    assert pending[0]["message_id"] == msg_id
    
    # 3. Parent answers
    adapter.reply_to_worker(msg_id, "Use async for I/O")
    
    # 4. Worker checks
    answer = adapter.check_answer(msg_id)
    assert answer == "Use async for I/O"

def test_worker_clarification_polling(temp_db, monkeypatch):
    monkeypatch.setenv("UAS_SQLITE_BUS", "1")
    adapter = SQLiteStateAdapter(temp_db)
    
    # Mock adapter in clients or just test logic
    # To test WorkerClient.ask_for_clarification, we need to answer practically in a thread
    
    mcp_mock = MagicMock()
    worker = WorkerClient(mcp_mock)
    worker._current_run_id = "run-poll"
    worker._agent_id = "worker-poll"
    
    def delayed_answer():
        time.sleep(2)
        # We need to find the message_id. Our adapter is real, so we can check pending.
        while True:
            pending = adapter.get_pending_questions("run-poll")
            if pending:
                adapter.reply_to_worker(pending[0]["message_id"], "Threaded Answer")
                break
            time.sleep(0.5)
            
    with patch("src.state_adapter.get_state_adapter", return_value=adapter):
        t = threading.Thread(target=delayed_answer)
        t.start()
        
        answer = worker.ask_for_clarification("Polling Question?", timeout_seconds=10, poll_interval=1.0)
        assert answer == "Threaded Answer"
        t.join()

def test_worker_clarification_timeout(temp_db, monkeypatch):
    monkeypatch.setenv("UAS_SQLITE_BUS", "1")
    adapter = SQLiteStateAdapter(temp_db)
    
    mcp_mock = MagicMock()
    worker = WorkerClient(mcp_mock)
    
    with patch("src.state_adapter.get_state_adapter", return_value=adapter):
        # Poll interval 0.1 for fast timeout test
        answer = worker.ask_for_clarification("Timeout Question?", timeout_seconds=1, poll_interval=0.1)
        assert answer is None

def test_status_transitions(temp_db, monkeypatch):
    monkeypatch.setenv("UAS_SQLITE_BUS", "1")
    adapter = SQLiteStateAdapter(temp_db)
    
    msg_id = adapter.ask_parent("run-trans", "worker-1", "Q")
    
    # Check status PENDING
    with adapter._bus._get_connection() as conn:
        row = conn.execute("SELECT status FROM subagent_messages WHERE message_id=?", (msg_id,)).fetchone()
        assert row["status"] == "PENDING"
        
    adapter.reply_to_worker(msg_id, "A")
    with adapter._bus._get_connection() as conn:
        row = conn.execute("SELECT status FROM subagent_messages WHERE message_id=?", (msg_id,)).fetchone()
        assert row["status"] == "ANSWERED"
        
    adapter.check_answer(msg_id)
    with adapter._bus._get_connection() as conn:
        row = conn.execute("SELECT status FROM subagent_messages WHERE message_id=?", (msg_id,)).fetchone()
        assert row["status"] == "RETRIEVED"
