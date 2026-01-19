# Prompt: Expand SSH Tool for Antigravity

> **For:** Floor Manager
> **Working Directory:** `_tools/ssh_agent/`
> **Reference:** `agent-hub/TODO.md` line 28
> **Priority:** Medium

---

## Context

The `ssh_agent` tool exists for SSH key management but isn't MCP-compatible. Antigravity (Google's AI IDE) uses MCP for tool integration. Making `ssh_agent` MCP-compatible would allow Antigravity to use it for remote operations.

---

## Task

Make `ssh_agent` MCP-compatible so Antigravity can use it as an MCP server.

---

## Steps

### 1. Assess current ssh_agent

```bash
cd _tools/ssh_agent
ls -la
cat README.md  # if exists
```

Understand:
- What does it currently do?
- What's the interface (CLI, library, etc.)?
- What operations does it support?

### 2. Define MCP tools

Create tool definitions for SSH operations:

```python
TOOLS = [
    {
        "name": "ssh_connect",
        "description": "Establish SSH connection to a remote host",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "user": {"type": "string"},
                "key_path": {"type": "string", "description": "Path to SSH key"}
            },
            "required": ["host"]
        }
    },
    {
        "name": "ssh_execute",
        "description": "Execute command on remote host",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "command": {"type": "string"}
            },
            "required": ["host", "command"]
        }
    },
    {
        "name": "ssh_list_keys",
        "description": "List available SSH keys",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]
```

### 3. Create MCP server

Follow the pattern from `librarian-mcp`:

```
ssh_agent/
├── src/
│   └── ssh_mcp/
│       ├── __init__.py
│       ├── server.py      # MCP server
│       ├── tools.py       # Tool definitions
│       └── ssh_ops.py     # Actual SSH operations
├── pyproject.toml
└── README.md
```

### 4. Use the `mcp` library

```python
from mcp.server import Server
import mcp.types as types

server = Server("ssh-agent")

@server.list_tools()
async def handle_list_tools():
    return [types.Tool(**t) for t in TOOLS]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    # Route to ssh operations
    pass
```

### 5. Create MCP config entry

```json
{
  "mcpServers": {
    "ssh-agent": {
      "command": "python",
      "args": ["-m", "ssh_mcp.server"],
      "cwd": "/path/to/_tools/ssh_agent"
    }
  }
}
```

### 6. Test with Antigravity

Add to Antigravity's MCP config and verify tools appear.

---

## Security Considerations

- Never log SSH keys or passwords
- Validate host patterns (prevent injection)
- Consider allowlist for permitted hosts
- Timeout on connections

---

## Definition of Done

- [ ] `ssh_agent` has MCP server implementation
- [ ] Tools: `ssh_connect`, `ssh_execute`, `ssh_list_keys` (minimum)
- [ ] MCP config example provided
- [ ] Works with Antigravity
- [ ] Update `agent-hub/TODO.md` to mark complete

---

*Generated for Floor Manager execution*
