import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open
from scripts.generate_mcp_config import generate_claude_cli_config, generate_cursor_config, write_config, MCP_SERVERS

def test_claude_cli_config_generation():
    config = generate_claude_cli_config()
    assert "mcpServers" in config
    assert "agent-hub" in config["mcpServers"]
    # Check that disabled servers are excluded
    assert "librarian-mcp" not in config["mcpServers"]

def test_cursor_config_generation():
    config = generate_cursor_config()
    assert "mcpServers" in config
    assert "ollama-mcp" in config["mcpServers"]

def test_write_config_dry_run():
    config = {"test": "data"}
    with patch("builtins.print") as mock_print:
        path = write_config("cursor", config, dry_run=True)
        assert mock_print.called
        assert "[DRY RUN]" in mock_print.call_args_list[0][0][0]

def test_write_config_merge():
    # Mock existing config
    existing = {"other_setting": True, "mcpServers": {"old": {"command": "test"}}}
    new_config = {"mcpServers": {"agent-hub": {"command": "node"}}}
    
    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "read_text", return_value=json.dumps(existing)):
            with patch.object(Path, "write_text") as mock_write:
                with patch.object(Path, "mkdir"):
                    write_config("cursor", new_config)
                    # Should merge mcpServers
                    written = json.loads(mock_write.call_args[0][0])
                    assert written["other_setting"] is True
                    assert "old" in written["mcpServers"]
                    assert "agent-hub" in written["mcpServers"]
