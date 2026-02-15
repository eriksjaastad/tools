# Subagent Bi-Directional Protocol

This reference documents the bi-directional messaging protocol adopted from the **mcp-server-subagent** project.

## Purpose
In standard MCP, communication is strictly "one-way": a client calls a tool on a server. This protocol adds an asynchronous "callback" mechanism, allowing a Worker (the MCP server) to pause and ask questions to the Parent (the MCP client).

## Source Reference
- **Repo:** [github.com/dvcrn/mcp-server-subagent](https://github.com/dvcrn/mcp-server-subagent)
- **Author:** dvcrn

## Adoption vs. Modification
- **Adopting:** The core loop of `ask_parent` → `pause` → `poll` → `continue`.
- **Modifying:** Instead of purely in-memory message passing, we will implement this protocol using a **SQLite Message Bus** (in Phase 3) to support cross-process communication and persistence.
- **Extending:** Adding `run_id` tracking to support multiple concurrent agent tasks from the same parent.
