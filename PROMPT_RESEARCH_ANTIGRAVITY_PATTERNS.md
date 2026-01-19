# Prompt: Research Antigravity Multi-Agent Orchestration Patterns

> **For:** Floor Manager (Research Task)
> **Reference:** `agent-hub/TODO.md` line 29
> **Priority:** Low - informational

---

## Context

Antigravity (Google's AI IDE) has impressive multi-agent orchestration. When the Floor Manager runs in Antigravity, it can spawn and coordinate agents extremely fast. We want to understand how they do it so we can:

1. Better leverage Antigravity's capabilities
2. Potentially adopt similar patterns in our own agent-hub
3. Document best practices for Floor Manager operations in Antigravity

---

## Task

Research and document how Antigravity coordinates multiple agents.

---

## Research Questions

### 1. Agent Spawning
- How does Antigravity spawn sub-agents?
- Is there an API or is it implicit in the prompts?
- What's the context sharing mechanism between agents?

### 2. Coordination
- How do agents communicate with each other?
- Is there a message bus or shared state?
- How are task dependencies handled?

### 3. Concurrency
- Can multiple agents run in parallel?
- How is resource contention handled (file locks, etc.)?
- What's the execution model (sequential, parallel, DAG)?

### 4. Context Management
- How much context does each sub-agent get?
- Is context trimmed/summarized between agents?
- How do they avoid context explosion?

### 5. Error Handling
- What happens when a sub-agent fails?
- Is there retry logic?
- How are partial results handled?

---

## Research Methods

### 1. Observation
Run complex tasks in Antigravity and observe:
- The agent output/logs
- How it describes what it's doing
- Task decomposition patterns

### 2. Documentation
Search for:
- Antigravity official docs on multi-agent
- Google AI Studio documentation
- Any public APIs or SDKs

### 3. Experimentation
Try prompts that explicitly ask Antigravity to:
- "Use multiple agents for this task"
- "Parallelize this work"
- "Spawn a specialist agent for X"

Document what works and what doesn't.

---

## Deliverable

Create a document: `_tools/Documents/ANTIGRAVITY_ORCHESTRATION_PATTERNS.md`

Include:
1. **Summary** - Key findings (2-3 paragraphs)
2. **Patterns Observed** - Specific techniques with examples
3. **Recommendations** - How to best use Antigravity for Floor Manager tasks
4. **Comparison** - How it differs from our agent-hub approach
5. **Ideas to Adopt** - Patterns we could implement ourselves

---

## Definition of Done

- [ ] Research document created
- [ ] At least 3 specific patterns documented
- [ ] Recommendations for Floor Manager usage
- [ ] Update `agent-hub/TODO.md` to mark complete

---

*Generated for Floor Manager execution (research mode)*
