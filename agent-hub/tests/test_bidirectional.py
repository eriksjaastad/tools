import pytest
from src.message_bus import MessageBus
from src.bidirectional import BidirectionalMessenger

def test_ask_reply_flow(tmp_path):
    bus = MessageBus(db_path=tmp_path/"db")
    messenger = BidirectionalMessenger(bus)
    
    q_id = messenger.ask_parent("worker", "parent", "What is 2+2?", run_id="run1")
    
    # Parent sees it
    pending = messenger.get_pending_questions("parent")
    assert len(pending) == 1
    assert pending[0]["payload"]["question"] == "What is 2+2?"
    
    # Parent replies
    messenger.reply_to_worker("parent", "worker", q_id, "It is 4")
    
    # Worker checks
    answer = messenger.check_answer("worker", q_id)
    assert answer == "It is 4"
