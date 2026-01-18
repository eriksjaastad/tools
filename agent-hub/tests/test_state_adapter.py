import os
import pytest
from pathlib import Path
from unittest.mock import patch
from src.state_adapter import get_state_adapter, SQLiteStateAdapter, LegacyFileStateAdapter

@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path

def test_get_state_adapter_legacy():
    with patch("src.utils.feature_flags.is_enabled", return_value=False):
        adapter = get_state_adapter()
        assert isinstance(adapter, LegacyFileStateAdapter)

def test_get_state_adapter_sqlite():
    with patch("src.utils.feature_flags.is_enabled", return_value=True):
        adapter = get_state_adapter()
        assert isinstance(adapter, SQLiteStateAdapter)

def test_legacy_adapter_smoke(temp_dir):
    adapter = LegacyFileStateAdapter(temp_dir)
    msg_id = adapter.ask_parent("run-1", "worker-1", "Q?")
    assert msg_id is not None
    
    pending = adapter.get_pending_questions("run-1")
    assert len(pending) == 1
    
    adapter.reply_to_worker(msg_id, "A!")
    assert adapter.check_answer(msg_id) == "A!"

def test_sqlite_adapter_smoke(temp_dir):
    db_path = temp_dir / "test.db"
    adapter = SQLiteStateAdapter(db_path)
    msg_id = adapter.ask_parent("run-1", "worker-1", "Q?")
    assert msg_id is not None
    
    pending = adapter.get_pending_questions("run-1")
    assert len(pending) == 1
    
    adapter.reply_to_worker(msg_id, "A!")
    assert adapter.check_answer(msg_id) == "A!"
