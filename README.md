# Developer Tools (_tools)

Builder utilities and helper scripts for working across all projects.

---

## 🛠️ Active Tools

### 🤖 AI Router (`ai_router/`)
Cost-optimized routing between local Ollama and cloud AI models.
- **Documentation:** [[ai_router/README|AI Router README]]
- **Logic:** [[router.py|AIRouter Library]]

### 🛡️ Integrity Warden (`integrity-warden/`)
Ecosystem health checks and automated remediation.
- **Documentation:** [[integrity-warden/README|Integrity Warden README]]
- **Core Logic:** [[integrity_warden.py|Integrity Warden Core]]

### 🔌 Ollama MCP (`ollama-mcp/`)
Model Context Protocol integration for local Ollama instances.
- **Documentation:** [[ollama-mcp/README|Ollama MCP README]]

### 🔑 SSH Agent (`ssh_agent/`)
Automated SSH management and host routing.
- **Documentation:** [[ssh_agent/README|SSH Agent README]]
- **Agent:** [[agent.py|SSH Agent Logic]]

### 📄 PDF to Markdown Converter (`pdf-converter/`)
Convert PDFs to clean markdown for processing.
- **Converter:** [[pdf_to_markdown_converter.py|PDF Converter]]
- **Cleanup:** [[cleanup_converted_pdfs.py|Cleanup Utility]]

### 💬 Claude CLI (`claude-cli/`)
Legacy command-line interface to Claude.
- **Script:** [[claude-cli.py|Claude CLI Script]]

### 🏗️ Agent Hub (`agent-hub/`)
Central orchestration point for agent communication.
- **Index:** [[agent-hub/00_Index_agent-hub|Agent Hub Index]]
- **Hub:** [[hub.py|Hub Core]]

---

## 📋 Planning Templates
- [[create-prd|Create PRD Template]]
- [[baseline_metrics_plan|Baseline Metrics Plan]]
- [[project_lifecycle_tracking_blueprint|Project Lifecycle Tracking]]

---

## Setup

### Add to PYTHONPATH (Recommended)

To use tools from any project:

```bash
# Add to ~/.zshrc (or ~/.bashrc)
echo 'export PYTHONPATH="[USER_HOME]/projects:$PYTHONPATH"' >> ~/.zshrc
source ~/.zshrc
```

Then import from anywhere:

```python
from _tools.ai_router import AIRouter
```

### Install Dependencies

Each tool has its own environment:

```bash
# AI Router
cd ai_router
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# PDF Converter (already set up)
source pdf_converter_env/bin/activate
```

---

## Creating New Tools

When adding a new tool:

1. Create directory: `_tools/your_tool/`
2. Add `README.md` with usage instructions
3. Add `requirements.txt` or venv if needed
4. Update this README with a section

**Tools should be:**
- ✅ Reusable across projects
- ✅ Well-documented with examples
- ✅ Self-contained (own dependencies)
- ✅ Builder utilities, not project code

---

## Directory Structure

```
_tools/
├── ai_router/              # AI routing system (NEW)
│   ├── router.py
│   ├── README.md
│   └── venv/
├── pdf_to_markdown_converter.py
├── cleanup_converted_pdfs.py
├── claude-cli.py
├── pdf_converter_env/      # Venv for PDF tools
├── logs/                   # PDF conversion logs
└── *.md                    # Planning templates
```

---

## Philosophy

`_tools/` contains **builder utilities** - scripts and libraries you use **while building projects**, not the projects themselves.

**Examples:**
- ✅ AI router library (used by multiple projects)
- ✅ PDF converter (preprocessing documents)
- ✅ PRD templates (planning new projects)
- ❌ Cortana (that's a project, not a tool)
- ❌ actionable-ai-intel (that's a project)

**Rule of thumb:** If it's used **BY** your projects, it's a tool. If it's used **BY** end-users, it's a project.

---

Part of the `..` workspace.

## Related Documentation

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[cost_management]] - cost management
- [[dashboard_architecture]] - dashboard/UI
- [[prompt_engineering_guide]] - prompt engineering
- [[ai_model_comparison]] - AI models
- [[case_studies]] - examples
- [[cortana_architecture]] - Cortana AI
- [[cortana-personal-ai/README]] - Cortana AI

## Development Resources
- [[_tools/integrity-warden/integrity_warden.py|integrity_warden.py]]
- [[_tools/integrity-warden/deep_cleanup.py|deep_cleanup.py]]
- [[_tools/integrity-warden/remediate_renames.py|remediate_renames.py]]
- [[_tools/integrity-warden/rename_indices.py|rename_indices.py]]
- [[_tools/ollama-mcp/cursor_mcp_config_example.json|cursor_mcp_config_example.json]]
- [[_tools/ollama-mcp/package-lock.json|package-lock.json]]
- [[_tools/ollama-mcp/tsconfig.json|tsconfig.json]]
- [[_tools/ollama-mcp/config/routing.yaml|routing.yaml]]
- [[_tools/agent-hub/hub.py|hub.py]]
- [[_tools/ai_router/router.py|router.py]]
- [[_tools/ai_router/Documents/README.md|README.md]]
- [[_tools/pdf-converter/pdf_to_markdown_converter.py|pdf_to_markdown_converter.py]]
- [[_tools/claude-cli/claude-cli.py|claude-cli.py]]
- [[_tools/ssh_agent/ssh_hosts.yaml|ssh_hosts.yaml]]
- [[_tools/ssh_agent/README.md|README.md]]
- [[_tools/ssh_agent/agent.py|agent.py]]
- [[_tools/ssh_agent/queue/.agent_state.json|.agent_state.json]]
