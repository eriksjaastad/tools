import pytest
import os
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
from src.environment import detect_environment, ClaudeCLIAdapter, CursorAdapter, AntigravityAdapter

def test_detect_claude_cli():
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session"}):
        adapter = detect_environment()
        assert isinstance(adapter, ClaudeCLIAdapter)
        assert adapter.name == "claude-cli"
        assert adapter.get_session_id() == "test-session"

def test_detect_cursor():
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(Path, "exists", side_effect=lambda self: str(self).endswith(".cursor/mcp.json")):
            with patch.object(CursorAdapter, "detect", return_value=True):
                adapter = detect_environment()
                # Priority: Claude CLI > Cursor
                assert isinstance(adapter, CursorAdapter)

def test_detect_antigravity():
    with patch.dict(os.environ, {}, clear=True):
        with patch.object(ClaudeCLIAdapter, "detect", return_value=False):
            with patch.object(CursorAdapter, "detect", return_value=False):
                with patch.object(AntigravityAdapter, "detect", return_value=True):
                    adapter = detect_environment()
                    assert isinstance(adapter, AntigravityAdapter)

def test_claude_cli_trigger():
    adapter = ClaudeCLIAdapter()
    with patch("builtins.print") as mock_print:
        assert adapter.trigger("hello") is True
        mock_print.assert_called_with("hello")

def test_cursor_trigger_success():
    adapter = CursorAdapter()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert adapter.trigger("hello") is True
        mock_run.assert_called_once()

def test_antigravity_trigger():
    adapter = AntigravityAdapter()
    with patch.object(Path, "mkdir"):
        with patch.object(Path, "write_text") as mock_write:
            assert adapter.trigger("hello") is True
            mock_write.assert_called_once_with("hello")
