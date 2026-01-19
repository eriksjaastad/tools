# Agent Hub - TODO

> **What this is:** An autonomous multi-agent orchestration system with proposal-driven workflows.
> **Location:** `_tools/agent-hub/`
> **PRD:** See `PRD_UNIFIED_AGENT_SYSTEM.md` (root of `_tools/`)
> **Design:** See `Documents/Agentic Blueprint Setup V2.md`
> **Created:** January 12, 2026
> **Updated:** January 19, 2026

---

## 🌅 NEXT PRIORITIES (Jan 19, 2026)

**Completed Jan 18:** Phases 0-5 of Unified Agent System (~13,200 lines of code in one day via Antigravity multi-agent workflow)

### Morning Session
- [x] **Documentation polish** — Update README, API docs, config examples (Jan 19)
- [x] **Benchmarking** — All targets PASS (see BENCHMARK_RESULTS_2026-01-19.md)
- [x] **Integration smoke test** — 201 passed, core system stable (Jan 19)

### Librarian Adaptive Memory
- [x] Implement EmbeddingService (Ollama + nomic-embed-text) (Jan 19)
- [x] Implement MemoryStore (SQLite-Lite Vector Store) (Jan 19)
- [x] Implement MemoryDB (SQLite tier system) (Jan 19)
- [x] Wire into librarian-mcp query flow (Phase 2 & 3 implementation) (Jan 19)

### Infrastructure
- [x] **Expand SSH tool for Antigravity** — Make `ssh_agent` MCP-compatible (Jan 19)
- [x] **Research Antigravity orchestration patterns** — Documented in `Documents/ANTIGRAVITY_ORCHESTRATION_PATTERNS.md` (Jan 19)

### Test Debt
- [x] Resolve 22 remaining subagent protocol test failures (Jan 19)

### Then: Real Project Work
- Flex agent-hub on actual tasks
- Identify gaps from real usage

---

## The Vision (Updated)

```
Erik + Super Manager (Claude CLI)
         │
         ▼ PROPOSAL_FINAL.md
Floor Manager (Cursor/Gemini)
         │ understands task, decomposes for local models
         ▼
Implementer (Qwen) ──► Local Reviewer (DeepSeek) ──► Judge (Claude CLI)
         │                                                    │
         └────────────── Refinement Loop ─────────────────────┘
                                │
                                ▼
                         Merge to main
```

---

## Phase 0: Skills & Knowledge Capture ✅

- [x] **0.1** Create Floor Manager skill in agent-skills-library
  - Location: `agent-skills-library/claude-skills/floor-manager-orchestration/SKILL.md`
  - Includes: model capabilities, task decomposition, stall recovery
- [x] **0.2** Create cursor rules for Floor Manager trigger
  - Location: `agent-skills-library/cursor-rules/floor-manager-orchestration/rules.md`
  - Trigger: `PROPOSAL_FINAL.md` detection
- [x] **0.3** Create playbook for Floor Manager procedures
  - Location: `agent-skills-library/playbooks/floor-manager-orchestration/README.md`

---

## Phase 1: Foundation ✅ (Partially Complete)

- [x] **1.1** Install dependencies: `pip install swarm litellm`
- [x] **1.2** Create `hub.py` - main CLI script
- [x] **1.3** Define tools: `read_file`, `write_file`, `list_files`, `move_file`
- [x] **1.4** Create Worker agent (local model + tools)
- [x] **1.5** Create Manager agent (smart model + delegation ability)
- [x] **1.6** Basic REPL loop (input → process → output)
- [x] **1.7** Test: Ask manager to write a file via worker (Jan 19)

---

## Phase 2: Contract-Driven Pipeline ✅

- [x] **2.1** Implement `TASK_CONTRACT.json` schema validation
  - See: `Documents/Agentic Blueprint Setup V2.md` §2
- [x] **2.2** Create `watchdog.py` state machine
  - Transitions, lock mechanism, circuit breakers
- [x] **2.3** Create `watcher.sh` for Claude CLI loop
  - Detects `REVIEW_REQUEST.md`, invokes Judge
- [x] **2.4** Implement atomic file writes (temp → rename)
- [x] **2.5** Implement `PROPOSAL_FINAL.md` → contract conversion
- [x] **2.6** Test: Full pipeline on a simple doc merge task

---

## Phase 3: Stall Recovery & Resilience (Partially Complete)

- [x] **3.1** Implement Two-Strike Rule in Floor Manager (in `watchdog.py`)
  - Strike 1: Diagnose, rework, retry
  - Strike 2: Escalate with `STALL_REPORT.md`
- [x] **3.2** Add timeout detection for all phases (in `watchdog.py`)
- [x] **3.3** Implement circuit breakers (9/9 triggers implemented) (Jan 19)
  - See: `Documents/Planning/Phase3_Prompts.md` Prompt 3.1
- [x] **3.4** Create `HALT.md` generation
- [x] **3.5** Test: Force a stall, verify recovery flow (in `test_e2e.py`)

---

## Phase 4: Git Integration ✅

- [x] **4.1** Implement `git_manager.py` utility
  - See: `Documents/Planning/Phase4_Prompts.md` Prompt 4.1
- [x] **4.2** Integrate Git checkpoints into Watchdog
- [x] **4.3** Implement auto-merge on PASS verdict
- [x] **4.4** Rollback capability via checkpoint

---

## Phase 5: Observability ✅

- [x] **5.1** Implement token/cost tracking
- [x] **5.2** Post-task cleanup and archiving
- [x] **5.3** Beautiful CLI status output

---

## 🏁 PROJECT READY
**Agent Hub Core Infrastructure is complete.**
- Contract-driven pipeline: **ACTIVE**
- Safety & Circuit Breakers: **ARMED**
- Git Automation: **ACTIVE**
- Financial Tracking: **ACTIVE**
- CLI Tools: **ACTIVE**

**Next Move:** Create your first "real" proposal in `_handoff/PROPOSAL_FINAL.md`.

---

## Questions to Answer

1. ~~Which smart model for the Manager?~~ → **Gemini 3 Flash (Floor Manager), Claude CLI (Super Manager/Judge)**
2. ~~Which local model for Workers?~~ → **Qwen 2.5 Coder (implementation), DeepSeek-R1 (review/reasoning)**
3. ~~Do we need LiteLLM?~~ → **Yes, for model routing**
4. ~~How does Cursor detect `PROPOSAL_FINAL.md`?~~ → **Manual handoff for now**
5. ~~Should the skill be Cursor-specific or Claude-specific?~~ → **Both are defined in skills library**

---

## Reference

| Document | Purpose |
|----------|---------|
| `PRD.md` | What and why |
| `Documents/Agentic Blueprint Setup V2.md` | Detailed design |
| `Documents/Agentic Blueprint.md` | High-level vision |
| `hub.py` | Phase 1 foundation code |
| `templates/PROPOSAL_FINAL.template.md` | Proposal format |

---

**Next step:** Real project work - flex agent-hub on actual tasks

## Related Documentation

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[architecture_patterns]] - architecture
- [[cost_management]] - cost management
- [[prompt_engineering_guide]] - prompt engineering
- [[ai_model_comparison]] - AI models
