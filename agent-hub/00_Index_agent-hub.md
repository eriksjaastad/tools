# 00_Index_agent-hub

> **Type:** Tool / Infrastructure
> **Status:** Planning
> **Created:** January 12, 2026

---

## What This Is

Agent Hub is a command-line AI orchestration system. You talk to one interface, and it delegates work to the right models - smart cloud models for planning, free local models for grunt work.

## Key Concept

Local models can't write files on their own. But wrapped in an agent framework with tools, they can. Hub gives local models "hands" (file tools) while a smart model acts as the "brain" (decides what to do).

## Tech Stack

- **Language:** Python
- **Agent Framework:** Swarm (OpenAI)
- **Model Proxy:** LiteLLM
- **Local Inference:** Ollama

## Related

- `_tools/ai_router/` - May merge into Hub
- `_tools/ollama-mcp/` - Separate (Cursor integration)
