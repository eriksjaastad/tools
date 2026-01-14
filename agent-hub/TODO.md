# Agent Hub - TODO

> **What this is:** A Hub-and-Spoke AI orchestration system. You talk to one interface, it delegates to the right models.
> **Location:** `_tools/agent-hub/`
> **Created:** January 12, 2026

---

## The Vision

```
You → Hub (smart model - orchestrates, plans)
      → Spokes (local models - have tools, execute grunt work)
            → Tools: read_file, write_file, list_files, move_file
      → Hub summarizes result
```

**Why this matters:**
- Local models are FREE but can't act alone (no file access)
- Cloud models are expensive but smart
- Hub lets smart models delegate grunt work to free local models WITH file access
- No more copying prompts between tools

---

## Phase 1: Foundation

- [ ] **1.1** Install dependencies: `pip install swarm litellm`
- [ ] **1.2** Create `hub.py` - main CLI script
- [ ] **1.3** Define tools: `read_file`, `write_file`, `list_files`, `move_file`
- [ ] **1.4** Create Worker agent (local model + tools)
- [ ] **1.5** Create Manager agent (smart model + delegation ability)
- [ ] **1.6** Basic REPL loop (input → process → output)
- [ ] **1.7** Test: Ask manager to write a file via worker

---

## Phase 2: Integration

- [ ] **2.1** Add safety checks (no writes outside project, backup before overwrite)
- [ ] **2.2** Configure LiteLLM proxy for model routing
- [ ] **2.3** Support multiple local models (Qwen, DeepSeek, Llama)
- [ ] **2.4** Add `--project` flag to scope file operations to a directory

---

## Phase 3: Polish

- [ ] **3.1** Merge or deprecate AI Router (Hub does routing now)
- [ ] **3.2** Add telemetry (which model handled what, duration, cost estimate)
- [ ] **3.3** Create README.md with usage examples
- [ ] **3.4** Decide: keep Swarm or roll custom agent loop

---

## Questions to Answer

1. **Which smart model for the Manager?** Claude (via API), GPT-4o, or large local (Llama 70B)?
2. **Which local model for Workers?** Qwen 2.5 Coder, DeepSeek, Llama 3.2?
3. **Do we need LiteLLM?** Or can we route manually in code?

---

## Reference

- Architecture doc: `hub and spoke ai.md`
- AI Router (may merge): `_tools/ai_router/`
- Ollama MCP (separate): `_tools/ollama-mcp/`

---

**Next step:** Phase 1.1 - Install Swarm and LiteLLM, verify they work
