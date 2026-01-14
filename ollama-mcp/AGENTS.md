# AGENTS.md - Source of Truth for AI Agents

## 🎯 Project Overview
Bridge between the MCP protocol and local Ollama models. Provides tools for AI assistants to interact with local LLMs safely and efficiently. Includes **Smart Local Routing** to automatically select the best local model for a task (classification, code, reasoning, etc.).

## 🛠 Tech Stack
- Language: TypeScript
- Runtime: Node.js
- Protocol: Model Context Protocol (MCP)
- AI Models: Ollama (local)

## 📋 Definition of Done (DoD)
- [ ] Code is documented with explicit types (no `any`).
- [ ] Technical changes are logged to `_obsidian/WARDEN_LOG.yaml`.
- [ ] `00_Index_ollama-mcp.md` is updated with recent activity.
- [ ] Telemetry logging is verified for any new tool or model interaction.
- [ ] All model names and inputs are sanitized to prevent command injection.

## 🚀 Execution Commands
- Build: `npm run build`
- Run Server: `node dist/server.js`
- Run Analytics (Telemetry): `node scripts/analyze-runs.js`
- Run Analytics (Routing): `node scripts/analyze_routing_performance.js`
- Mark Telemetry Reviewed: `node scripts/mark_telemetry_reviewed.js`
- Test: `node scripts/smoke_test.js`
- Test Routing: `node scripts/test_routing.js`

## ⚠️ Critical Constraints
- NEVER waste context reading `node_modules/` or large `*.jsonl` files.
- ALWAYS use explicit types over `any` in TypeScript.
- ALL model executions MUST be logged via `logRun`.
- ALWAYS validate inputs before passing to shell commands (Ollama CLI).

## 📖 Reference Links
- [[00_Index_ollama-mcp]]
- [[Project Philosophy]]
- [[Documents/README]]

