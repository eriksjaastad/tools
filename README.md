# Developer Tools (_tools)

Builder utilities and helper scripts for working across all projects.

---

## 🛠️ Active Tools

### 🤖 AI Router (`ai_router/`)
Cost-optimized routing between local Ollama and cloud AI models.
- **Documentation:** [AI Router README](../ai-model-scratch-build/README.md)
- **Logic:** [AIRouter Library](ai_router/router.py)

### 🛡️ Integrity Warden (`integrity-warden/`)
Ecosystem health checks and automated remediation.
- **Documentation:** [Integrity Warden README](../ai-model-scratch-build/README.md)
- **Core Logic:** [Integrity Warden Core](integrity-warden/integrity_warden.py)

### 🔌 Ollama MCP (`ollama-mcp/`)
Model Context Protocol integration for local Ollama instances.
- **Documentation:** [Ollama MCP README](../ai-model-scratch-build/README.md)

### 🔑 SSH Agent (`ssh_agent/`)
Automated SSH management and host routing.
- **Documentation:** [SSH Agent README](../ai-model-scratch-build/README.md)
- **Agent:** [SSH Agent Logic](ssh_agent/agent.py)

### 📄 PDF to Markdown Converter (`pdf-converter/`)
Convert PDFs to clean markdown for processing.
- **Converter:** [PDF Converter](pdf-converter/pdf_to_markdown_converter.py)
- **Cleanup:** [Cleanup Utility](pdf-converter/cleanup_converted_pdfs.py)

### 💬 Claude CLI (`claude-cli/`)
Legacy command-line interface to Claude.
- **Script:** [Claude CLI Script](claude-cli/claude-cli.py)

### 🏗️ Agent Hub (`agent-hub/`)
Central orchestration point for agent communication.
- **Index:** [Agent Hub Index](agent-hub/00_Index_agent-hub.md)
- **Hub:** [Hub Core](agent-hub/hub.py)

---

## 📋 Planning Templates
- Create PRD Template (see agent-hub)
- Baseline Metrics Plan (see agent-hub)
- Project Lifecycle Tracking (see agent-hub)

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

- [LOCAL_MODEL_LEARNINGS](../writing/Documents/reference/LOCAL_MODEL_LEARNINGS.md) - local AI
- [cortana-personal-ai/README](../ai-model-scratch-build/README.md) - Cortana AI

## Development Resources
- [integrity-warden/integrity_warden.py|integrity_warden.py](integrity-warden/integrity_warden.py|integrity_warden.py)
- [integrity-warden/deep_cleanup.py|deep_cleanup.py](integrity-warden/deep_cleanup.py|deep_cleanup.py)
- [integrity-warden/remediate_renames.py|remediate_renames.py](integrity-warden/remediate_renames.py|remediate_renames.py)
- [integrity-warden/rename_indices.py|rename_indices.py](integrity-warden/rename_indices.py|rename_indices.py)
- [ollama-mcp/cursor_mcp_config_example.json|cursor_mcp_config_example.json](ollama-mcp/cursor_mcp_config_example.json|cursor_mcp_config_example.json)
- [ollama-mcp/package-lock.json|package-lock.json](ollama-mcp/package-lock.json|package-lock.json)
- [ollama-mcp/tsconfig.json|tsconfig.json](ollama-mcp/tsconfig.json|tsconfig.json)
- [ollama-mcp/config/routing.yaml|routing.yaml](ollama-mcp/config/routing.yaml|routing.yaml)
- [agent-hub/hub.py|hub.py](agent-hub/hub.py|hub.py)
- [ai_router/router.py|router.py](ai_router/router.py|router.py)
- [README.md](../ai-model-scratch-build/README.md)
- [pdf-converter/pdf_to_markdown_converter.py|pdf_to_markdown_converter.py](pdf-converter/pdf_to_markdown_converter.py|pdf_to_markdown_converter.py)
- [claude-cli/claude-cli.py|claude-cli.py](claude-cli/claude-cli.py|claude-cli.py)
- [ssh_agent/ssh_hosts.yaml|ssh_hosts.yaml](ssh_agent/ssh_hosts.yaml|ssh_hosts.yaml)
- [README.md](../ai-model-scratch-build/README.md)
- [ssh_agent/agent.py|agent.py](ssh_agent/agent.py|agent.py)
- [ssh_agent/queue/.agent_state.json|.agent_state.json](ssh_agent/queue/.agent_state.json|.agent_state.json)
