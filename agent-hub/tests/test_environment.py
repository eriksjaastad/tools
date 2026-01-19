import os
import pytest
from unittest.mock import patch
from src.environment import detect_environment, Environment, get_adapter, ClaudeCLIAdapter, CursorAdapter

def test_detect_claude_cli():
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}):
        adapter = detect_environment()
        assert isinstance(adapter, ClaudeCLIAdapter)

def test_detect_cursor():
    with patch.dict(os.environ, {"CURSOR_SESSION": "test"}):
        adapter = detect_environment()
        assert isinstance(adapter, CursorAdapter)

def test_get_adapter():
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}):
        adapter = get_adapter()
        assert isinstance(adapter, ClaudeCLIAdapter)
