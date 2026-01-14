# AGENTS.md - Source of Truth for AI Agents

## 🎯 Project Overview
AI Router is a tool to optimize AI costs and performance by routing requests between local (Ollama) and cloud (OpenAI) models based on prompt complexity and context requirements.

## 🛠 Tech Stack
- Language: Python 3.14+
- Frameworks: OpenAI SDK (compatible with Ollama)
- AI Strategy: Local-first with cloud fallback and automatic escalation.

## 🏗️ Chain of Command
1. **The Architect (Human/Architect AI):** Cross-project strategy, high-level context, and brainstorming.
2. **The Floor Manager (Project AI):** This is **YOU**. You manage this project, interpret the Architect's instructions, and delegate work.
3. **The AI Router (The Worker):** The tool used by the Floor Manager to execute atomic tasks across local/cloud models.

## 📋 Definition of Done (DoD)
- [ ] Code is documented with type hints.
- [ ] Technical changes are logged to `_obsidian/WARDEN_LOG.yaml`.
- [ ] `00_Index_ai-router.md` is updated with recent activity.
- [ ] Telemetry logging is verified for any new features.

## 🚀 Execution Commands
- Environment: `source venv/bin/activate`
- Run: `export PYTHONPATH="/Users/eriksjaastad/projects:$PYTHONPATH" && python scripts/examples.py`
- Test: `python scripts/test_gauntlet.py`

## ⚠️ Critical Constraints
- NEVER hard-code API keys, secrets, or credentials in script files. Use `.env` and `os.getenv()`.
- NEVER use absolute paths (e.g., `/Users/eriksjaastad/...`). ALWAYS use relative paths or `PROJECT_ROOT` env var.
- Local models MUST have `num_ctx` explicitly set in the Ollama API call to ensure context window support.

## 📖 Reference Links
- [[00_Index_ai-router]]
- [[Project Philosophy]]

