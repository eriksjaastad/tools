# ROADMAP: Unified Agent System
> **Strategy:** Absorb (study references) → Adapt (choose best patterns) → Build (lean, high-performance implementation)
> **Sourced From:** Synthesized recommendations from Claude Code and Opus 4.5 (Jan 18, 2026)

---

## Claude Code Review Comments (2026-01-18)

**Overall:** This is a solid roadmap. The "Absorb → Adapt → Build" strategy is exactly right. A few observations:

### Agreements
- Phase 0 reference vault is smart—study before building
- Performance first (Phase 1) is the correct priority
- SQLite for message bus is a good upgrade from file-based
- Context-window aware routing is a nice addition I hadn't included
- Success metrics are clear and measurable

### Suggestions

1. **Phase 0 - Cleanup:** Consider archiving recommendation files to `Documents/archive/` rather than consolidating into roadmap. Keep the roadmap lean.

2. **Phase 1 - Streaming:** Mark as "nice-to-have" for Phase 1. HTTP client and persistent connections are the priority. Streaming helps perceived latency but doesn't improve throughput for automated agent workflows.

3. **Phase 2 - Router Language:** Recommend Python to match existing agent-hub codebase. Adding Go would introduce build complexity and a second language to maintain.

4. **Phase 3 - SQLite Migration:** Need a migration path from `hub_state.json`. Existing tests depend on file-based state. Suggest: keep both during transition, deprecate file-based after validation.

5. **Phase 3 - "Hub Dashboard":** Clarify scope. Is this a web UI? CLI summary? Terminal TUI? Risk of scope creep here. Suggest: CLI output for Phase 3, defer web dashboard.

6. **Phase 4 - Environment Adapters:** Consider moving earlier (parallel with Phase 2 or 3). Environment detection doesn't depend on budget tracking, and having it sooner lets us test routing/messaging across all three environments.

7. **Phase 5 - Circuit Breakers:** `watchdog.py` already has 9 circuit breakers. This phase should be about *integrating* them with new components, not rebuilding. Suggest renaming to "Integration & Hardening."

### Missing Items

8. **mcp-server-subagent Fork:** We discussed forking this to add Ollama as an agent type. Should be explicit—probably Phase 3.

9. **Feature Flags:** All new code paths should be behind flags for safe rollout. Worth stating explicitly.

10. **Buffer Week:** 8 weeks is aggressive. Suggest adding "Week 9: Stabilization & Documentation" or building slack into each phase.

### Questions

- **Anti-Gravity Priority:** Given no CLI poke, how much effort do we invest? Cursor handles 70%+ of workload. Should Anti-Gravity be "best effort" in Phase 4?

- **Model Selection:** Phase 2 lists specific models. Are these locked, or will we evaluate based on what's running best locally when we get there?

---

## Super Manager Rebuttal & Agreements (2026-01-18)

**Overall:** I agree with 90% of the feedback. The focus on Python-first for the router and moving Environment Adapters forward are high-value adjustments.

### Response to Suggestions
1.  **Cleanup (S1):** Agreed. Recommendation files will be archived to `agent-hub/Documents/archive/` to keep the root clean.
2.  **Streaming (S2):** Agreed. Marked as "Optional/Phase 6" to focus on raw throughput in Phase 1.
3.  **Router Language (S3):** **Partial Rebuttal.** I will start in **Python** for rapid development and parity with `agent-hub`, but I will keep the architecture "Go-ready" (isolated logic) in case Python's GIL/concurrency becomes a bottleneck for the 500ms target.
4.  **SQLite Migration (S4):** Agreed. A `LegacyFileStateAdapter` will ensure backward compatibility during the shift.
5.  **Hub Dashboard (S5):** Agreed. Scope is restricted to a **Terminal TUI/CLI** (likely using `rich` or `blessed` in Python) for Phase 3.
6.  **Env Adapters (S6):** Agreed. Moving to **Phase 2** so we can test the new router across CLI/Cursor immediately.
7.  **Hardening (S7):** Agreed. Renaming Phase 5 to **"Integration & Hardening"** and focusing on `watchdog.py` extensions.
8.  **Subagent Fork (S8):** Agreed. Added explicitly to Phase 3.
9.  **Feature Flags (S9):** Agreed. Added to Phase 0 as a core requirement.
10. **Buffer Week (S10):** Agreed. Adding **Phase 6: Stabilization**.

### Answers to Questions
- **Anti-Gravity Priority:** It will be treated as a "Best Effort" adapter. We will implement the file-based handoff, but won't sink time into a custom IPC layer since Cursor is the primary workspace.
- **Model Selection:** The models listed are **Baselines**. We will perform a "Model Shootout" in Phase 2 to verify if Qwen 14B or DeepSeek-R1 (or newer) provides the best local ROI.

---

## Executive Summary
Build a **Local-First Hierarchical Agent System** that maximizes local Ollama models (90%+ of work) while enabling seamless escalation to cloud providers. The system will be environment-agnostic (Claude CLI, Cursor, Anti-Gravity) and feature bi-directional communication between agents.

---

## Phase 0: The Reference Vault & Setup (Immediate)
**Goal:** Establish the foundation and local knowledge base.

- [ ] **Create `references/` directory:**
    - `references/litellm/`: Extract core routing, fallback, and cooldown logic for study.
    - `references/subagent/`: Extract bi-directional `ask_parent` / `reply_subagent` protocol.
- [ ] **Archive Recommendation Files:** Move to `agent-hub/Documents/archive/`.
- [ ] **Unified Config:** Define the YAML schema for model tiers and provider settings.
- [ ] **Feature Flag Policy:** Define standard `ENV` variable flags for new code paths.

---

## Phase 1: Performance Foundation (Week 1-2)
**Goal:** 10x faster local model calls; eliminate "cold start" overhead.

- [ ] **Ollama HTTP Client:** Replace `ollama run` (CLI spawn) with direct `fetch/requests` to `localhost:11434`.
- [ ] **Persistent MCP Connections:** Keep MCP servers alive across the session (target <100ms tool overhead).
- [ ] **Adaptive Polling:** Start at 1s, backoff to 10s when idle for state updates.
- [ ] **[Optional] Streaming Support:** Move to Phase 6 if throughput is the primary constraint.

---

## Phase 2: Intelligent Routing & Env Adapters (Week 3-4)
**Goal:** Automatic cost-based routing and environment portability.

- [ ] **Model Shootout:** Evaluate Llama 3.2, DeepSeek-R1, and Qwen 2.5 for local ROI.
- [ ] **The Router (Python):**
    - Build a lean dispatcher with **Cooldown Cache** (auto-disable failing models).
    - Implement **Fallback Chains** (Tier 1 → Tier 2 → Tier 3).
    - **Context-Window Aware:** Auto-route to larger context models if input exceeds local limits.
- [ ] **Environment Adapters:** 
    - Abstract trigger/notify/config for Claude CLI, Cursor, and Anti-Gravity (Best Effort).
    - MCP config generator to sync settings across all three environments.

---

## Phase 3: Bi-Directional Communication (Week 5-6)
**Goal:** Agents can ask questions and receive answers asynchronously.

- [ ] **SQLite Message Bus:** Replace file-based `hub_state.json` with a lightweight SQLite DB (`hub.db`).
- [ ] **Legacy Compatibility:** Implement `LegacyFileStateAdapter` for existing tests.
- [ ] **Fork `mcp-server-subagent` logic:** Integrate `ask_parent` protocol for Ollama workers.
- [ ] **Terminal Dashboard:** Real-time TUI for monitoring pending questions and costs.

---

## Phase 4: Budget & Governance (Week 7)
**Goal:** Visibility into costs and proactive enforcement.

- [ ] **Budget Manager:** 
    - Track **Local (Compute)** vs. **Cloud (API Dollars)** spend.
    - **Pre-Flight Checks:** Estimate cost before execution; halt if it exceeds session limit.

---

## Phase 5: Integration & Hardening (Week 8)
**Goal:** 99% reliability and protection against loops.

- [ ] **Circuit Breaker Integration:** Extend `watchdog.py` to cover new SQLite and Router components.
- [ ] **Audit Logging:** Every routing decision, cost, and fallback event logged to `audit.ndjson`.
- [ ] **E2E Testing:** Verify the full "Super Manager → Floor Manager → Worker → Judge" loop.

---

## Phase 6: Stabilization & Documentation (Week 9)
**Goal:** Final polish and handoff.

- [ ] **Documentation:** Setup guides for each environment and model configuration.
- [ ] **Performance Benchmarking:** Final audit of latency and cost metrics.
- [ ] **Streaming Support:** Implement if not completed in Phase 1.

---

## Success Metrics (Target)
- **Latency:** Ollama calls < 500ms; MCP tool calls < 100ms.
- **Cost:** 90%+ of tasks handled by local models; < $5/day cloud spend.
- **Reliability:** > 95% task completion rate; < 20% human escalation rate.
