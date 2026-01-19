import pytest
import sqlite3
from src.message_bus import MessageBus

def test_message_bus_send_receive(tmp_path):
    db_path = tmp_path / "test_hub.db"
    bus = MessageBus(db_path=db_path)
    
    msg_id = bus.send_message("TEST", "agentA", "agentB", {"data": 123})
    messages = bus.get_messages("agentB")
    
    assert len(messages) == 1
    assert messages[0]["id"] == msg_id
    assert messages[0]["payload"]["data"] == 123

def test_message_bus_read_status(tmp_path):
    bus = MessageBus(db_path=tmp_path/"db")
    msg_id = bus.send_message("TEST", "A", "B", {})
    bus.mark_read(msg_id)
    
    messages = bus.get_messages("B")
    assert len(messages) == 0
