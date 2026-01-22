Here is the updated **Multi-Agent Debate (MAD)** framework, now enhanced with the **Project Brain Layer** integration you've just established. This version moves away from "searching" and toward "graph-informed reasoning."

---

# **Multi-Agent Debate (MAD) Framework: Brain-Integrated Edition**

> **Purpose:** High-level strategic planning and architectural consensus-building.
> **Context:** Utilizes the Unified Agent System's project brain layer for grounded, zero-search intelligence.
> **Date:** 2026-01-18

---

## **⚠️ Open Questions (Keep in Mind While Reading)**

### The "Raising Hand" Problem
How do models signal they want to speak? Options to explore:
- **Round-robin** — Simple but boring and templatized
- **Token-based** — Model holds a "speaking token," passes when done
- **Interrupt-driven** — Model signals "I have something to say," moderator decides
- **Confidence-weighted** — Model with strongest opinion on current topic speaks next

### The Steamroller Problem
What if one model consistently dominates the conversation? This might reveal:
- That model is genuinely better at the task (useful signal)
- Other models need different prompting to be more assertive
- The conversation structure favors a certain style
- Need to investigate: Is dominance a bug or a feature?

### Recording and Extracting
The raw debate will likely be messy. How do we capture value?
- Record full transcripts for analysis
- Build extraction layer: "What did they agree on? Where did they disagree? What's the final recommendation?"
- Could Cortana or the Librarian help distill debates into actionable summaries?
- Goal: Real-time emergent discussion, not templatized back-and-forth

*Added: 2026-01-18 by Claude (Super Manager) — Questions raised during ecosystem planning discussion*

---

## **1. The Trinity of Agents**

To ensure an odd-numbered tie-breaker and role specialization, the system instantiates three distinct high-tier models:

* **Agent A: The Architect (Proponent)**
* **Focus:** System design and feature implementation.
* **Access:** Granted read-access to the "Implementation" and "Utility" clusters of the Project Brain.


* **Agent B: The Auditor (Devil’s Advocate)**
* **Focus:** Security, edge cases, and architectural debt.
* **Access:** Granted read-access to the "Safety," "Tests," and "Audit" clusters of the Project Brain.


* **Agent C: The Arbitrator (Judge)**
* **Focus:** Logic validation, synthesis, and consensus.
* **Access:** Global view of the Project Brain to ensure proposals align with the core system vision.



---

## **2. Brain-Grounded Protocol**

Instead of the models guessing at file relationships, the debate is fueled by the Project Brain Layer:

1. **Independent Graph Traversal:** Each agent queries the Project Brain for the "relevant neighborhood" of the task.
2. **Isolated Proposal Generation:** Agents produce a plan grounded in the actual dependency nodes shown in the brain map.
3. **Cross-Critique (Peer Review):** Agents exchange plans. The Auditor *must* use the project brain to prove why the Architect's plan might break a distant node in another cluster.
4. **The Adjudication:** The Arbitrator reviews the reasoning traces and either selects a winner or generates a synthesized "Master Handoff" for the worker agents.

---

## **3. Guardrails & Anti-Stall Mechanisms**

To prevent agents from going in circles or hallucinating links that aren't in the brain:

* **Graph-Constraint Enforcement:** If an agent cites a dependency that does not exist in the Project Brain, the Arbitrator automatically rejects that round of reasoning.
* **The Consensus Circuit Breaker:**
* **Limit:** Maximum 3 rounds of debate.
* **Stall Detection:** If the "Similarity Score" between Round 2 and Round 3 responses is > 85%, the debate is considered "circular."
* **Result:** The Arbitrator halts the debate and triggers a **Human-in-the-Loop (HITL)** request via the `ask_parent` tool.


* **Lock-in Logic:** Once a specific component is agreed upon (e.g., "We will use the HTTP API for Ollama"), it is moved to a "Resolved" state and cannot be re-opened for debate in that session.

---

## **4. Strategic Benefits**

| Benefit | How MAD + Project Brain Solves It |
| --- | --- |
| **No "Searching"** | Agents receive a subgraph of relevant nodes instantly. |
| **Zero Groupthink** | The Auditor is mathematically incentivized to find flaws. |
| **High Grounding** | All arguments must be backed by "Node X connects to Node Y." |
| **Cost Control** | High-spend models only talk during this phase; worker models execute later. |

---

### **Next Steps for your Hub**

Once you have finished the current Agent Hub upgrade, this MAD document serves as the "System Prompt" for your Planning Mode.

**Would you like me to help you define the specific "Graph Query Tool" that these agents will use to pull data from your project brain layer?**