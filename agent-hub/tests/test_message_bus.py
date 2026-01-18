import os
import pytest
import sqlite3
import threading
import time
from pathlib import Path
from src.message_bus import MessageBus, MessageStatus

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_hub.db"
    return db_path

def test_message_bus_init(temp_db):
    bus = MessageBus(temp_db)
    assert temp_db.exists()
    
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "subagent_messages" in tables
        assert "hub_messages" in tables
        assert "agent_heartbeats" in tables

def test_ask_parent(temp_db):
    bus = MessageBus(temp_db)
    msg_id = bus.ask_parent("run-1", "worker-1", "What is 2+2?")
    
    pending = bus.get_pending_questions("run-1")
    assert len(pending) == 1
    assert pending[0]["message_id"] == msg_id
    assert pending[0]["question"] == "What is 2+2?"
    assert pending[0]["subagent_id"] == "worker-1"

def test_reply_to_worker(temp_db):
    bus = MessageBus(temp_db)
    msg_id = bus.ask_parent("run-1", "worker-1", "Question?")
    
    success = bus.reply_to_worker(msg_id, "Answer.")
    assert success is True
    
    pending = bus.get_pending_questions("run-1")
    assert len(pending) == 0

def test_check_answer(temp_db):
    bus = MessageBus(temp_db)
    msg_id = bus.ask_parent("run-1", "worker-1", "Question?")
    
    # Still pending
    assert bus.check_answer(msg_id) is None
    
    # Parent replies
    bus.reply_to_worker(msg_id, "The Answer")
    
    # Worker retrieves
    answer = bus.check_answer(msg_id)
    assert answer == "The Answer"
    
    # Already retrieved
    assert bus.check_answer(msg_id) is None

def test_get_pending_questions_filtering(temp_db):
    bus = MessageBus(temp_db)
    bus.ask_parent("run-1", "worker-1", "Q1")
    bus.ask_parent("run-2", "worker-1", "Q2")
    
    assert len(bus.get_pending_questions()) == 2
    assert len(bus.get_pending_questions("run-1")) == 1
    assert len(bus.get_pending_questions("run-2")) == 1

def test_hub_messages(temp_db):
    bus = MessageBus(temp_db)
    bus.send_hub_message("alice", "bob", "alert", {"text": "hello"})
    
    messages = bus.receive_hub_messages("bob")
    assert len(messages) == 1
    assert messages[0]["from"] == "alice"
    assert messages[0]["type"] == "alert"
    assert messages[0]["payload"] == {"text": "hello"}
    
    # Already read
    assert len(bus.receive_hub_messages("bob")) == 0

def test_heartbeats(temp_db):
    bus = MessageBus(temp_db)
    bus.record_heartbeat("agent-1", "working")
    
    status = bus.get_agent_status()
    assert len(status) == 1
    assert status[0]["agent_id"] == "agent-1"
    assert status[0]["progress"] == "working"

def test_concurrent_access(temp_db):
    bus = MessageBus(temp_db)
    num_threads = 10
    num_msgs = 20
    
    def worker(tid):
        for i in range(num_msgs):
            bus.ask_parent(f"run-{tid}", f"worker-{tid}", f"Q-{i}")
            time.sleep(0.01)
            
    threads = []
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    pending = bus.get_pending_questions()
    assert len(pending) == num_threads * num_msgs

def test_expire_old_messages(temp_db):
    bus = MessageBus(temp_db)
    bus.ask_parent("run-1", "worker-1", "Old Q")
    
    # Mock date would be better, but we can't easily here without patching datetime.
    # We'll just test that it returns 0 for fresh messages.
    count = bus.expire_old_messages(max_age_hours=24)
    assert count == 0
