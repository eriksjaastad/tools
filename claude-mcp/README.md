# claude-mcp

MCP server that wraps Claude CLI with **constrained tools** for Agent Hub.

## Purpose

Allows Gemini (Floor Manager) to invoke Claude (Judge) through a controlled interface. Gemini picks from a predefined menu of operations - no freeform prompts allowed.

## Architecture

```
Gemini (Floor Manager)
       │
       │ JSON-RPC over stdio
       ▼
claude-mcp (this server)
       │
       │ subprocess
       ▼
claude CLI
```

## Available Tools

| Tool | Purpose |
|------|---------|
| `claude_judge_review` | Code review with structured verdict |
| `claude_validate_proposal` | Check proposal completeness |
| `claude_security_audit` | Deep security review |
| `claude_resolve_conflict` | Decide Floor Manager vs Judge disputes |
| `claude_health` | Check CLI availability |

## Access Control

- **Floor Manager (Gemini):** YES - can use all tools
- **Local models (Qwen, DeepSeek):** NO - workers don't talk to Claude
- **Arbitrary prompts:** NO - menu only, no freeform access

## Setup

```bash
npm install
npm run build
```

## Usage

The server communicates via stdio (JSON-RPC). Typically spawned by an MCP client:

```javascript
const proc = spawn('node', ['dist/server.js']);
// Send JSON-RPC requests via proc.stdin
// Read responses from proc.stdout
```

## Related

- [claude-mcp-spec.md](../agent-hub/Documents/Planning/claude-mcp-spec.md) - Full specification
- [ollama-mcp](../ollama-mcp) - Sister project for Ollama integration
- [agent-hub](../agent-hub) - The orchestration system that uses both
