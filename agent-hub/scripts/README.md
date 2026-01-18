# MCP Config Generator

This tool synchronizes MCP (Model Context Protocol) server configurations across different environments (Claude CLI, Cursor, and Anti-Gravity).

## Purpose
Managing multiple MCP config files is error-prone. This script provides a single source of truth for all MCP servers used in the Unified Agent System.

## Usage
Sync across all environments (dry run):
```bash
python scripts/generate_mcp_config.py --dry-run
```

Apply changes to all environments:
```bash
python scripts/generate_mcp_config.py
```

Target a specific environment:
```bash
python scripts/generate_mcp_config.py --env cursor
```

List configured servers:
```bash
python scripts/generate_mcp_config.py --list
```

## Adding New Servers
Edit `MCP_SERVERS` in `scripts/generate_mcp_config.py` to add or modify server definitions. 

```python
"new-server": {
    "command": "node",
    "args": ["/path/to/server.js"],
    "description": "What this server does",
}
```

## Environment Config Locations
- **Claude CLI**: `~/.claude/claude_desktop_config.json`
- **Cursor**: `~/.cursor/mcp.json`
- **Anti-Gravity**: `~/.antigravity/mcp_config.json`
