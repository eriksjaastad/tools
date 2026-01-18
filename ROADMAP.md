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

## Claude Code Web Review (2026-01-18)

**Reviewer:** Claude Code Web (Opus 4.5)
**Focus:** Cost savings, speed, reliability — evaluated for Erik's specific workflow, not general-purpose tooling.

### What's Solid

1. **The 90% local target is achievable and economically sound.** At typical dev workloads (500K-2M tokens/day), local inference is genuinely 10-50x cheaper than cloud APIs. The math works.

2. **Qwen2.5-Coder-32B as your Implementer is the right call.** Current benchmarks (73.7% on Aider, competitive with GPT-4o) confirm it's the best open-source coding model. No change needed.

3. **SQLite over file-based state (Phase 3) is correct.** File-based state will become a reliability bottleneck under concurrent operations. This is a necessary upgrade.

4. **MCP architecture aligns with industry direction.** MCP was donated to the Linux Foundation (Dec 2025). The Tasks API added in Nov 2025 aligns with your `DRAFT_READY`/`DRAFT_ACCEPTED` pattern.

### Push-Back / Concerns

1. **The Router (Phase 2) — Build vs. Buy?**
   The roadmap specifies building a custom Python router with cooldown cache, fallback chains, and context-window awareness. **LiteLLM already does all of this** and is mature, battle-tested, and free. Unless there's a specific deficiency for your workflow, wrapping LiteLLM is likely less work and more reliable than building from scratch.
   - *Counter-argument:* If you need tight integration with your MCP message bus, a thin custom layer on top of LiteLLM might make sense. But building core routing logic yourself? Questionable ROI.

2. **The "500ms Ollama call" target may be misleading.**
   500ms is achievable for short completions with a warm model. But first token latency on a 32B model is often 1-3 seconds, and full code generation can take 10-30 seconds. Recommend redefining this metric (first token? short responses? warm model only?) to avoid chasing a number that doesn't reflect real performance.

3. **DeepSeek as Local Reviewer — Consider the R1 Distill variant.**
   DeepSeek-R1-Distill-Qwen-32B outperforms standard DeepSeek for review tasks because it produces explicit reasoning traces. This makes parsing review rationale more reliable for automated pipelines.

4. **Phase 4 (Budget & Governance) feels late.**
   Cost visibility should come earlier. If local models handle 90% of work, you need to know *which* tasks escape to cloud and *why* from the start. Consider pulling basic cost logging into Phase 1 or 2.

5. **Anti-Gravity as "Best Effort" — Agree, but document the contingency.**
   What happens if Cursor becomes unusable or paywalled? Is Anti-Gravity the fallback, or is there another plan? Worth documenting.

### Missing Items

1. **Model hot-swapping / A-B testing infrastructure.**
   No mechanism to continuously evaluate new models. Qwen 3 MoE variants just dropped. You want a way to swap in a new model for 10% of traffic and compare without rebuilding.

2. **Graceful degradation path.**
   What happens when Ollama crashes, GPU overheats, or you're on battery? The roadmap assumes the happy path. For reliability, define explicit fallback behavior when local inference is unavailable.

3. **Memory pressure handling.**
   32B models on consumer hardware are memory-hungry. If you open a large project while running inference, you could OOM. Consider: auto-quantization, model unloading when idle, or hard memory limits.

### The Big Question

**Why is Gemini the Floor Manager?**

If cost is the driver, Gemini 2.5 Flash is cheap. But you're already running capable local models. Could a local model (Qwen2.5-Coder-32B or a smaller variant) handle Floor Manager duties? That would push you closer to 95%+ local and remove another cloud dependency.

If Gemini is there because it has better instruction-following or tool use than local models, that's valid — but the roadmap doesn't justify the choice.

### Recommendations Summary

| Priority | Recommendation |
|----------|----------------|
| **Immediate** | Evaluate LiteLLM as router foundation before building custom |
| **Immediate** | Clarify 500ms latency metric definition |
| **Short-term** | Switch Local Reviewer to DeepSeek-R1-Distill-Qwen-32B |
| **Short-term** | Pull basic cost logging into Phase 1 |
| **Medium-term** | Add model hot-swap infrastructure for continuous evaluation |
| **Medium-term** | Document graceful degradation when local inference unavailable |

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
