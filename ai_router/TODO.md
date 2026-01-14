# AI Router - TODO

**Last Updated:** January 5, 2026 (Routing Philosophy added)
**Project Status:** Active
**Current Phase:** Phase 2: Telemetry & Observability

---

## 📍 Current State

### What's Working ✅
- **CLI Wrapper:** Command-line interface in `scripts/cli.py` for direct model interaction.
- **Routing Logic:** Auto-routing based on complexity and prompt length.
- **Local Context:** Explicit `num_ctx` allocation for Ollama models.
- **Telemetry:** Structured JSONL logging of all calls with performance warnings.
- **Model Support:** Configured for llama3.2, deepseek-r1, and qwen3.
- **Rigor Testing:** Dedicated `test_local_rigor.py` for context stress and reliability.
- **Multi-Provider:** Integrated OpenAI, Anthropic (Claude), and Google (Gemini) support.
- **Resilience:** Health checks for local models and retries for cloud APIs.

### What's Missing ❌
- **Dashboard Integration:** Surfacing telemetry in `project-tracker`.
- **Learned Routing:** Policy-based routing using telemetry data.
- **Multi-provider:** Support for Anthropic or Gemini.

### Blockers & Dependencies
- ⛔ **Blocker:** None currently.
- 🔗 **Dependency:** requires Ollama running locally for `local` tier.

---

## ✅ Completed Tasks

### Phase 2: Telemetry & Context (Jan 5, 2026)
- [x] Implement CLI wrapper (`scripts/cli.py`) for command-line access.
- [x] Audit existing model context window settings.
- [x] Implement explicit context window allocation for local models.
- [x] Update routing logic to be context-window aware.
- [x] Add model metadata (size, max context) to configuration.
- [x] Implement lightweight telemetry logging to JSONL.
- [x] Add performance ceiling detection to telemetry.
- [x] Apply project scaffolding (directory structure, mandatory files).
- [x] Create rigorous local model stress test (`scripts/test_local_rigor.py`).
- [x] Resolve reviewer feedback (imports and legacy paths).
- [x] Implement Multi-Provider support (Anthropic & Google Gemini).
- [x] **Restriction:** Blocked Sonnet and Opus from auto-routing to prevent budget explosions.

### Phase 1: Foundation (Dec 2025 - Jan 2026)
- [x] Core AIRouter class with OpenAI SDK.
- [x] Basic complexity heuristics for routing.
- [x] Escalation logic (local -> cheap -> expensive).
- [x] Basic test suite (`test_setup.py`, `test_gauntlet.py`).

---

## 📋 Pending Tasks

### 🔴 CRITICAL - Must Do First

#### Task Group 1: Cost Safeguards & Budget Protector
- [ ] **Hard Ceiling on Expensive Models:** Implement a default block on high-cost models (Sonnet, Opus). These should require an explicit "unlocked" flag or be reserved for manual Cursor use only.
- [ ] **Global Budget Protector:** Add a daily/monthly cost ceiling to `AIRouter` that stops cloud calls if a threshold is hit.
- [ ] **Tier Restriction:** Ensure `auto` routing never hits "ultra-expensive" models without manual intervention.

#### Task Group 2: Project Tracker Integration
- [ ] Surface "Escalation Rate" in Dashboard.
- [ ] Show model usage breakdown per project.
- [ ] Display performance alerts (slow models, errors).

---

### 🟡 HIGH PRIORITY - Important

#### Task Group 2: Routing Enhancements
- [ ] Implement a "Judge Model" for smarter escalation (small model evaluating response quality).
- [ ] Add support for Anthropic models.
- [ ] Replace keyword-based routing with task-type classification (see notes below).

---

## 🧠 Routing Philosophy: Beyond Keywords

### The Problem with Keyword Matching

The current routing logic pattern-matches on words like "architecture" and "security" to decide tier. This is brittle. Someone asking "is this email about security?" gets routed to expensive, while someone asking "redesign my entire authentication system" without magic words might hit local. The heuristic is backwards—it's looking at *what the prompt mentions* instead of *what the model needs to do*.

### Better Heuristic #1: Prompt Length + Expected Output Length (Token Budget)

The real cost driver isn't prompt complexity—it's total token consumption (input + output). A 500-token prompt asking for a one-word classification costs almost nothing. A 500-token prompt asking for a 10,000-word essay is expensive regardless of tier.

The router should estimate:
- **Input tokens:** What you're sending (we already approximate this)
- **Expected output tokens:** What you're asking for

A prompt containing "explain in detail", "write a comprehensive guide", or "list all possible" signals high output. A prompt containing "yes or no", "classify as", or "which one" signals low output. The *total token budget* (input + expected output) should drive routing, not input alone.

Local models are fine for low-budget tasks (< 1000 total tokens). Cloud models are necessary when the output alone might exceed what local can reliably generate.

### Better Heuristic #2: Generative vs. Extractive Tasks

This is the real unlock. Tasks fall into two categories:

**Extractive tasks** — The answer exists in the prompt or is a simple transformation:
- Classification ("Is this spam?")
- Extraction ("What's the email address in this text?")
- Summarization ("TL;DR this article")
- Yes/No questions ("Does this code have a bug?")
- Format conversion ("Convert this JSON to YAML")

Extractive tasks are *compression*. The output is smaller or equal to the relevant input. Local models handle these well because they don't need to "create"—they need to "find" or "filter."

**Generative tasks** — The answer must be invented:
- Writing ("Draft an email to...")
- Coding ("Write a function that...")
- Brainstorming ("Give me 10 ideas for...")
- Explanation ("Explain quantum computing to a 5-year-old")
- Planning ("Design an architecture for...")

Generative tasks are *expansion*. The output is larger than the input, and quality depends on the model's ability to synthesize coherent, accurate content. This is where local models fall apart—they can generate *something*, but the coherence and correctness degrade fast.

**The routing rule should be:**
- Extractive + short output → Local
- Extractive + long output → Cheap
- Generative + short output → Cheap
- Generative + long output → Expensive

### Better Heuristic #3: Historical Success Rate (Learned Routing)

The telemetry already captures which model handled which prompt and whether it escalated. Over time, you can build a classifier:

1. Hash or embed the prompt
2. Look up similar historical prompts
3. Check what tier succeeded without escalation
4. Route new prompts based on what worked for similar ones

This is "learned routing"—the system gets smarter as it sees more traffic. The keyword list becomes a bootstrap heuristic that gets replaced by data.

### Implementation Sketch

```python
def route(self, messages: list[dict[str, str]]) -> Tier:
    content = "\n".join(m.get("content", "") for m in messages)

    # 1. Classify task type
    task_type = self._classify_task(content)  # "extractive" or "generative"

    # 2. Estimate total token budget
    input_tokens = len(content) // 4
    expected_output = self._estimate_output_length(content)
    total_budget = input_tokens + expected_output

    # 3. Route based on task type + budget
    if task_type == "extractive":
        if total_budget < 500:
            return "local"
        elif total_budget < 2000:
            return "cheap"
        else:
            return "expensive"
    else:  # generative
        if total_budget < 300:
            return "cheap"  # Never local for generative
        else:
            return "expensive"
```

The `_classify_task()` function could be a simple keyword heuristic initially (looking for "classify", "extract", "summarize" vs. "write", "create", "design"), then upgraded to a small local model doing the classification (meta-routing), then eventually replaced by a learned classifier.

### Why This Matters

The current router optimizes for *prompt characteristics*. A better router optimizes for *task requirements*. The difference:

| Prompt | Current Router | Better Router |
|--------|---------------|---------------|
| "Is 'FREE MONEY' spam?" | Local (short) | Local (extractive, tiny budget) |
| "Explain the security implications of JWT tokens" | Expensive (keyword: security) | Cheap (generative but short output) |
| "Write a 2000-word blog post about cooking" | Cheap (medium length) | Expensive (generative, huge output) |
| "Extract all dates from this 50-page document" | Expensive (long input) | Cheap (extractive, output << input) |

The better router makes decisions based on what the model *needs to do*, not what words happen to appear in the prompt.

---

## 🎯 The Floor Manager Playbook: Mastering the AI Router

### 🏗️ The Chain of Command
To use this tool effectively, the AI Agent (Floor Manager) must understand its place in the hierarchy:
1. **The Architect (Human/High-Level AI):** Provides cross-project strategy and complex instructions.
2. **The Floor Manager (Project AI):** Interprets instructions, manages files, and **delegates** atomic tasks.
3. **The AI Router (Worker):** Executes the delegated task using the most cost-effective model possible.

### 📋 Delegation Strategy for Floor Managers

As a Floor Manager, you should use the AI Router for **atomic, self-contained tasks**. Do not send "the whole project" to the router. Break your work down:

| Task Category | Delegation Tier | Why? |
|---------------|-----------------|------|
| **Sanity/Logic Check** | `local` | Is this logic sound? Yes/No. Fast and free. |
| **Code Refactoring** | `cheap` (GPT-4o-mini) | Standard syntax changes, cleaning up imports, type hinting. |
| **Complex Logic/New Features** | `expensive` (GPT-4o) | High-stakes code generation where quality is paramount. |
| **Repetitive Batching** | `local` | Converting 50 files, renaming variables across a dir. |
| **Loud Failures** | `strict=True` | ALWAYS use strict mode when a task result is critical for the next step. |

### 🛠️ Instructions for Any Project AI (Floor Manager)

1. **Be the Expert:** You are the one who knows the codebase. The Router just knows the prompt. **Provide the Router with the exact context it needs** (relevant imports, function signatures, etc.) without bloating the request.
2. **Local-First Bias:** Always ask: "Can a 7B model handle this classification/extraction?" If yes, try `local`. If it fails, the escalation logic will save you.
3. **Protect the Budget:** Be aware of the `expensive` tier. If you find yourself in a loop where the Router is hitting GPT-4o repeatedly for the same task, **STOP** and ask the human for clarification.
4. **Trust but Verify:** Use the `telemetry.jsonl` to see how your "Workers" are performing. If Llama is constantly escalating, stop using it for that specific task type.

---


### 🔵 MEDIUM PRIORITY - Nice to Have

- [ ] **Flat Root Transition:** Move contents of `Documents/core/` to `Documents/` root and delete the core directory.

#### Task Group 3: Optimizations
- [ ] Response caching for identical prompts.
- [ ] Streaming support for local and cloud models.

---

## 🎯 Success Criteria

### Phase 2 Complete When:
- [x] Local models handle 128k context without crashing.
- [x] All calls are recorded with duration and model used.
- [x] Project follows the standard scaffolding structure.

---

## 📊 Notes

### AI Agents in Use
- **Claude (Claude 3.5 Sonnet):** Architecture, implementation, and scaffolding.

### Cron Jobs / Automation
- None.

### External Services Used
- **OpenAI:** GPT-4o, GPT-4o-mini ($0.15-$2.50 per 1M tokens).
- **Ollama:** Local models (FREE).

### Technical Stack
- **Language:** Python 3.14+
- **Infrastructure:** Local Ollama + OpenAI Cloud.

### Key Decisions Made
1. **Decision:** Use `num_ctx` in Ollama options to ensure context window support (Jan 5, 2026).
2. **Decision:** Structured JSONL for telemetry to minimize overhead (Jan 5, 2026).
3. **Decision:** Apply project scaffolding to ensure consistency with other tools (Jan 5, 2026).

---

*Template Version: 1.0*

