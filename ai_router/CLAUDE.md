# CLAUDE.md - AI Collaboration Instructions

> **Purpose:** Project-specific instructions for AI assistants (Claude, ChatGPT, etc.)  
> **Audience:** AI collaborators and human developers

---

## 📚 Required Reading Before Writing Code

**You MUST read these files:**

1. **README.md** - Project overview and quick start
2. **This file (CLAUDE.md)** - Coding standards and safety rules
3. **AGENTS.md** - Tech stack and constraints

---

## Project Summary

**What this project does:**
Automates the decision-making process for which AI model to use for a given task. It prioritizes local execution (llama3.2 via Ollama) for simple tasks and escalates to GPT-4o-mini or GPT-4o for complex or failed requests.

**Current status:**
MVP complete with telemetry logging and context-window awareness. Next phase involves surfacing telemetry in the project-tracker dashboard.

**Key constraints:**
- Local-first architecture (must support Ollama).
- Low overhead (telemetry must be fast).
- Portability (no absolute paths).

---

## Project Structure

```
ai_router/
├── 00_Index_ai-router.md      # Project index
├── AGENTS.md                  # Source of truth for AI
├── CLAUDE.md                  # This file
├── TODO.md                    # Task tracking
├── README.md                  # High-level overview
│
├── router.py                  # Core routing logic
├── scripts/                   # Executable tools and tests
│   ├── test_gauntlet.py
│   ├── examples.py
│   └── ...
│
├── data/                      # Persistent data
│   └── logs/                  # Telemetry logs
│
└── Documents/                 # Documentation
```

---

## Coding Standards

### Language & Version
**Python:** 3.14+

### Code Style
- Use modern Python 3.11+ type hints.
- Prefer `pathlib.Path` for file operations.
- Use `logging` for persistent logs, `print()` for CLI feedback.

### Required Practices
- All functions must have type hints.
- Errors must be captured and returned in `AIResult` for escalation logic.
- Telemetry must be logged for all successful and failed `chat()` calls.

---

## 🏗️ Floor Manager Instructions (AI Agent Guidelines)

As the project AI (Floor Manager), you are responsible for executing tasks using the **AI Router**. Your goal is to be a cost-effective expert.

### 📋 Task Management Rules
1. **Chain of Command**: Follow the **Architect's** high-level strategy but manage the **Worker (AI Router)** for atomic tasks.
2. **Atomic Delegation**: Break complex requests into smaller pieces that can be routed. 
    * *Example*: Instead of asking the router to "Refactor the project," ask it to "Add type hints to this specific function."
3. **Context Injection**: Since you (the Floor Manager) have the codebase context, you MUST inject the necessary code snippets or signatures into the prompt before sending it to the Router. The Router is "blind" to the codebase otherwise.
4. **Local-First Verification**: For extractive or simple classification tasks, attempt `tier="local"` first.
5. **Strict Enforcement**: When a task's success is mandatory for your next step, use `strict=True` to ensure you catch failures immediately.

### 🛠️ Working with AIRouter
```python
from router import AIRouter

router = AIRouter()

# Example: Delegating a unit test generation task
result = router.chat(
    tier="cheap",
    messages=[{"role": "user", "content": "Write a unit test for this function: ..."}]
)
```

---

## Validation Commands

**Run these before committing:**

```bash
# Set PYTHONPATH
export PYTHONPATH="/Users/eriksjaastad/projects:$PYTHONPATH"

# Run tests
python scripts/test_gauntlet.py
python scripts/test_setup.py

# Check telemetry
python -c 'from _tools.ai_router import AIRouter; print(AIRouter().get_performance_summary())'
```

---

## Working with This AI

### Context Management
- Be aware of the `MODEL_CONFIG` in `router.py`. It defines the context window for local models.
- If you add a new model to the configuration, ensure it has a reasonable `context_window` setting.

### Data Integrity Rules
- `data/logs/telemetry.jsonl` is append-only.
- Never delete the telemetry log; it's the source of truth for the dashboard.

---

*This project follows the [project-scaffolding](https://github.com/eriksjaastad/project-scaffolding) patterns.*

