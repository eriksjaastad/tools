---
tags:
  - map/project
  - p/ssh-agent
  - type/tool
  - domain/infrastructure
  - status/active
created: 2026-01-16
updated: 2026-01-19
---

# SSH Agent

Tool for managing SSH connections and executing commands across remote hosts. Now includes a full MCP server for direct integration with AI agents like Antigravity, Cursor, and Claude CLI.

## Key Components

### MCP Server (New - Jan 19, 2026)
- `src/ssh_mcp/server.py` - MCP server exposing `ssh_execute` and `ssh_list_hosts` tools
- `src/ssh_mcp/ssh_ops.py` - Shared SSH operations (Paramiko, CLI, Persistent Shell)
- `mcp_config.json` - MCP configuration for integration

### Legacy Queue System
- [[agent.py]] - Queue-based agent loop (still functional, uses shared ssh_ops)
- [[start_agent.sh]] - Script to initialize and run the agent

### Configuration
- [[ssh_hosts.yaml]] - Inventory of remote hosts and connection parameters
- [[requirements.txt]] - Python dependencies

### Data
- `queue/` - Directory for requests and results (JSON Lines)
- [[agent_log.txt]] - Runtime activity logs

## MCP Tools

| Tool | Description |
|------|-------------|
| `ssh_execute` | Execute command on remote host via SSH |
| `ssh_list_hosts` | List configured SSH hosts from ssh_hosts.yaml |

## Status
**Status:** #status/active
**Purpose:** Secure remote command execution via MCP or queue
**Last Update:** January 19, 2026 - MCP server added for Antigravity compatibility
