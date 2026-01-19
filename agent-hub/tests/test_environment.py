import os
import pytest
from src.environment import detect_environment, Environment, get_adapter, ClaudeCLIAdapter, CursorAdapter

def test_detect_claude_cli():
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}):
        assert detect_environment() == Environment.CLAUDE_CLI

def test_detect_cursor():
    with patch.dict(os.environ, {"CURSOR_SESSION": "test"}):
        assert detect_environment() == Environment.CURSOR

def test_get_adapter():
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test"}):
        adapter = get_adapter()
        assert isinstance(adapter, ClaudeCLIAdapter)

from unittest.mock import patch
