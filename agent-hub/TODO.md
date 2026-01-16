# Agent Hub - TODO

> **What this is:** An autonomous multi-agent orchestration system with proposal-driven workflows.  
> **Location:** `_tools/agent-hub/`  
> **PRD:** See `PRD.md` for requirements  
> **Design:** See `Documents/Agentic Blueprint Setup V2.md`  
> **Created:** January 12, 2026  
> **Updated:** January 16, 2026

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
- [ ] **1.7** Test: Ask manager to write a file via worker

---

## Phase 2: Contract-Driven Pipeline (NEW)

- [ ] **2.1** Implement `TASK_CONTRACT.json` schema validation
  - See: `Documents/Agentic Blueprint Setup V2.md` §2
- [ ] **2.2** Create `watchdog.py` state machine
  - Transitions, lock mechanism, circuit breakers
- [ ] **2.3** Create `watcher.sh` for Claude CLI loop
  - Detects `REVIEW_REQUEST.md`, invokes Judge
- [ ] **2.4** Implement atomic file writes (temp → rename)
- [ ] **2.5** Implement `PROPOSAL_FINAL.md` → contract conversion
- [ ] **2.6** Test: Full pipeline on a simple doc merge task

---

## Phase 3: Stall Recovery & Resilience

- [ ] **3.1** Implement Two-Strike Rule in Floor Manager
  - Strike 1: Diagnose, rework, retry
  - Strike 2: Escalate with `STALL_REPORT.md`
- [ ] **3.2** Add timeout detection for all phases
- [ ] **3.3** Implement circuit breakers (all 9 triggers from V2 doc)
- [ ] **3.4** Create `ERIK_HALT.md` generation
- [ ] **3.5** Test: Force a stall, verify recovery flow

---

## Phase 4: Git Integration

- [ ] **4.1** Branch-per-task creation (`task/<task_id>`)
- [ ] **4.2** Checkpoint commits at each state transition
- [ ] **4.3** Merge on PASS verdict
- [ ] **4.4** Rollback capability via checkpoint

---

## Phase 5: Observability

- [ ] **5.1** NDJSON transition logging (`transition.ndjson`)
- [ ] **5.2** Token/cost tracking per task
- [ ] **5.3** Metrics dashboard (or CLI summary)
- [ ] **5.4** Log rotation

---

## Questions to Answer

1. ~~Which smart model for the Manager?~~ → **Gemini 3 Flash (Floor Manager), Claude CLI (Super Manager/Judge)**
2. ~~Which local model for Workers?~~ → **Qwen 2.5 Coder (implementation), DeepSeek-R1 (review/reasoning)**
3. ~~Do we need LiteLLM?~~ → **Yes, for model routing**
4. **NEW:** How does Cursor detect `PROPOSAL_FINAL.md`? Polling? Workspace watcher?
5. **NEW:** Should the skill be Cursor-specific or Claude-specific (or both)?

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

**Next step:** Phase 2.1 - Implement TASK_CONTRACT.json schema validation

## Related Documentation

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[architecture_patterns]] - architecture
- [[cost_management]] - cost management
- [[prompt_engineering_guide]] - prompt engineering
- [[ai_model_comparison]] - AI models
