# Project Pitch: Ollama MCP

## 🎯 The Core Mission
**Ollama MCP** is the "Local reasoning engine" for the entire Erik Sjaastad project ecosystem. It serves as a secure, zero-cost bridge between high-performance local LLMs (like DeepSeek-R1 and Llama 3) and AI agents operating via the Model Context Protocol (MCP).

## 💡 Why It Matters
In an ecosystem with 36+ projects, "token burn" is a significant bottleneck. Ollama MCP allows us to offload 30-40% of standard reasoning, drafting, and code review tasks to local hardware, preserving cloud credits for complex verification and multi-file orchestration.

## 🛠 Strategic Value
- **Zero-Cost Iteration:** Draft logic, unit tests, and documentation without hitting API limits.
- **Privacy First:** Process sensitive data (like `Tax Processing` or `ai-journal`) entirely on-device.
- **Agentic Workers:** Enables "Floor Managers" to dispatch sub-tasks to a fleet of local worker models concurrently.

## 🚀 Key Capabilities
1. **Parallel Reasoning:** `ollama_run_many` allows multiple models to debate or work on different files simultaneously.
2. **Telemetry-Driven Optimization:** Automatically logs performance data to `~/.ollama-mcp/runs.jsonl` to identify which local models are "fastest" for specific tasks.
3. **Plug-and-Play Integration:** Standardized MCP interface makes it immediately accessible to Cursor, Claude Code, and custom agents.

---
*Status: Production Ready | Domain: Infrastructure*

