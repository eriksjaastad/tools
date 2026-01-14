# Test Validation: Python Tools (Agent 3 of 5)

**Your batch:** 6 Python tools in _tools/

---

## Tools to Test

1. `agent-hub` - /Users/eriksjaastad/projects/_tools/agent-hub
2. `ai_router` - /Users/eriksjaastad/projects/_tools/ai_router
3. `claude-cli` - /Users/eriksjaastad/projects/_tools/claude-cli
4. `integrity-warden` - /Users/eriksjaastad/projects/_tools/integrity-warden
5. `pdf-converter` - /Users/eriksjaastad/projects/_tools/pdf-converter
6. `ssh_agent` - /Users/eriksjaastad/projects/_tools/ssh_agent

---

## For Each Tool, Run These Tests

### L1: Smoke Test (Can it load?)

```bash
cd /Users/eriksjaastad/projects/_tools/[TOOL]

# 1. Check for venv
ls -d venv .venv 2>/dev/null || echo "NO VENV"

# 2. Check for requirements
cat requirements.txt 2>/dev/null | head -10 || echo "NO REQUIREMENTS FILE"

# 3. If venv exists, activate and verify deps installed
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
pip list 2>/dev/null | wc -l

# 4. Try importing/running the main script
ls *.py 2>/dev/null
python [MAIN_SCRIPT].py --help 2>&1 || python -c "import [MODULE]" 2>&1
```

### L2: E2E Test (Does it run?)

```bash
# Check README for usage
cat README.md 2>/dev/null | grep -A5 -i "usage\|run\|start" | head -10

# Try running
python [MAIN_SCRIPT].py --help 2>&1
```

### L3: Dependency Health

```bash
pip check 2>&1
```

---

## Tool-Specific Notes

- **agent-hub**: Main script is `hub.py`
- **ai_router**: Main script is `router.py`, also has `scripts/cli.py`
- **claude-cli**: Single script `claude-cli.py`
- **integrity-warden**: Main script is `integrity_warden.py`
- **pdf-converter**: Main script is `pdf_to_markdown_converter.py`
- **ssh_agent**: Main script is `agent.py`, has `start_agent.sh`

---

## Quick Fixes (Do These If Needed)

**No venv:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Deps not installed:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## Report Your Results

After testing all 6, update the checklist in `/Users/eriksjaastad/projects/TODO.md`:

Find this section:
```markdown
#### Tools (8 in _tools/)
```

Update these rows with [x] for pass or note issues.

---

## Summary Template

When done, provide a summary:

```
## Agent 3 Results: Python Tools

Tested: 6/6
Passed all tests: X/6
Issues found: X

| Tool | L1 | L2 | L3 | Notes |
|------|----|----|-----|-------|
| agent-hub | PASS | PASS | PASS | |
| ai_router | PASS | PASS | PASS | |
...
```
