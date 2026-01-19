# Antigravity Multi-Agent Orchestration Patterns

## Summary
Antigravity (Google's AI IDE) employs a sophisticated multi-tier orchestration model that balances strategic planning with tactical execution. It utilizes the Model Context Protocol (MCP) as a central nervous system, connecting a "Super Manager" (Claude) to various specialized "Workers" and "Subagents." The system is characterized by its high concurrency, robust state management via file-based handoffs, and tiered intelligence levels that optimize for both cost and reasoning depth.

---

## 1. Patterns Observed

### Pattern A: The Supervisor-Subagent Pattern (The "Russian Doll" Model)
Antigravity can spawn specialized sub-agents for specific domains. A prime example is the `browser_subagent`.
- **Mechanism**: The main agent provides a high-level goal. The subagent receives a specialized toolset and context window tailored to that goal.
- **Benefit**: Keeps the main agent's context clean and prevents "context explosion" from domain-specific noise (like HTML DOM structures).

### Pattern B: The Contract-Driven Handoff
Context is preserved across agent boundaries through a controlled implementation pipeline.
- **Mechanism**: Agents communicate through standardized artifacts in `_handoff/`.
- **Workflow**: `PROPOSAL_FINAL.md` (Strategic) -> `TASK_CONTRACT.json` (Contract) -> `WORKER_DRAFT.md` (Tactical).
- **Benefit**: Allows for asynchronous collaboration and provides a permanent audit trail of decisions.

### Pattern C: MCP-as-a-Service (Expert Delegation)
Rather than trying to know everything, Antigravity delegates to specialized MCP servers.
- **Examples**: `librarian-mcp` for knowledge, `ssh-agent` for remote execution, `git-mcp` for version control.
- **Benefit**: Decouples the "brain" from the "hands," allowing the tools to evolve independently of the core model logic.

### Pattern D: Tiered Model Routing (Intelligence-to-Task Matching)
The `AIRouter` pattern optimizes which model performs which task.
- **Logic**: 
    - **Strategic (Claude-3.5-Sonnet)**: Architecture design, complex reasoning, judging.
    - **Tactical (Gemini-1.5-Flash)**: Orchestration, coordination, long-context parsing.
    - **Implementation (Qwen-2.5-Coder)**: Code generation, small patch sets.
    - **Reasoning/Review (DeepSeek-R1)**: Troubleshooting, security audits.

---

## 2. Recommendations for Floor Manager Usage

To best leverage Antigravity's orchestration:
1.  **Be Tool-First**: Always prefer delegating to an MCP tool rather than writing raw shell commands. This maintains the "cleanliness" of the orchestration loop.
2.  **Standardize Artifacts**: Use the patterns in `PROPOSAL_FINAL.template.md` to ensure the "Super Manager" (Antigravity) can parse and hand off tasks cleanly.
3.  **Spawn Early**: If a sub-task involves a high-noise environment (like extensive web searches or long file reads), ask for a subagent or a specialized tool run.
4.  **Monitor the Bus**: Pay attention to MCP heartbeats and circuit breakers. If a tool fails, it's often a signal for an architectural adjustment rather than just a retry.

---

## 3. Comparison to Agent Hub

| Feature | Antigravity Orchestration | Agent Hub (V4) |
|---------|---------------------------|----------------|
| **Core Connection** | Native MCP | LiteLLM + MCP Bridges |
| **Concurrency** | Parallel Subagents | Sequential Task Pipeline |
| **State Management** | Internal + File-based | Strictly File-based (Contracts) |
| **Error Handling** | Native Hub Guardrails | Watchdog Heartbeats/Breakers |

---

## 4. Ideas to Adopt in Agent Hub

1.  **Parallel Worker Pools**: Currently, Agent Hub is largely sequential. Implementation of a parallel worker DAG based on Antigravity's subagent model would significantly speed up large refactors.
2.  **Semantic Context Injection**: Adopting the `librarian-mcp` approach of semantic RAG vs. raw file reading to prevent context explosion in long-running tasks.
3.  **The "Judge-in-the-Loop"**: formalizing the "Judge Model" from `AIRouter` as a mandatory step in the subagent lifecycle (as seen in Antigravity's reflection phases).

---
*Documented by Floor Manager (Antigravity Edition)*
