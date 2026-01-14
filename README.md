# Developer Tools (_tools)

Builder utilities and helper scripts for working across all projects.

## 🤖 AI Router (`ai_router/`)

**Cost-optimized routing between local Ollama and cloud AI models**

Routes AI requests automatically:
- Simple tasks → Local Ollama (FREE)
- Medium tasks → gpt-4o-mini (cheap)
- Complex tasks → gpt-4o (expensive)

With automatic escalation on failures.

**Documentation:** [`ai_router/README.md`](ai_router/README.md)

**Quick start:**
```python
from _tools.ai_router import AIRouter

router = AIRouter()
result = router.chat([{"role": "user", "content": "Is this spam?"}])
print(result.text)  # Uses local model (FREE)
```

---

## 📄 PDF to Markdown Converter

Convert PDFs to clean markdown for processing.

**Usage:**
```bash
cd _tools
source pdf_converter_env/bin/activate
python3 pdf_to_markdown_converter.py input.pdf output.md
```

**Cleanup after conversion:**
```bash
python3 cleanup_converted_pdfs.py
```

---

## 💬 Claude CLI

Command-line interface to Claude (legacy - consider using Cursor instead).

**Usage:**
```bash
python3 claude-cli.py "Your prompt here"
```

---

## 📋 Planning Templates

- **`create-prd.md`** - Template for Product Requirements Documents
- **`baseline_metrics_plan.md`** - Framework for measuring project baselines
- **`project_lifecycle_tracking_blueprint.md`** - Tracking project progress

---

## Setup

### Add to PYTHONPATH (Recommended)

To use tools from any project:

```bash
# Add to ~/.zshrc (or ~/.bashrc)
echo 'export PYTHONPATH="/Users/eriksjaastad/projects:$PYTHONPATH"' >> ~/.zshrc
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

Part of the `/Users/eriksjaastad/projects/` workspace.
