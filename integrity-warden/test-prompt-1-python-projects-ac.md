# Test Validation: Python Projects A-C (Agent 1 of 5)

**Your batch:** 7 Python projects (alphabetical A-C)

---

## Projects to Test

1. `3d-pose-factory` - /Users/eriksjaastad/projects/3d-pose-factory
2. `ai-journal` - /Users/eriksjaastad/projects/ai-journal
3. `ai-usage-billing-tracker` - /Users/eriksjaastad/projects/ai-usage-billing-tracker
4. `analyze-youtube-videos` - /Users/eriksjaastad/projects/analyze-youtube-videos
5. `automation-consulting` - /Users/eriksjaastad/projects/automation-consulting
6. `cortana-personal-ai` - /Users/eriksjaastad/projects/cortana-personal-ai
7. `country-ai-futures-tracker` - /Users/eriksjaastad/projects/country-ai-futures-tracker

---

## For Each Project, Run These Tests

### L1: Smoke Test (Can it load?)

```bash
cd /Users/eriksjaastad/projects/[PROJECT]

# 1. Check for venv
ls -d venv .venv 2>/dev/null || echo "NO VENV"

# 2. Check for requirements
cat requirements.txt 2>/dev/null | head -10 || cat pyproject.toml 2>/dev/null | head -20 || echo "NO REQUIREMENTS FILE"

# 3. If venv exists, activate and verify deps installed
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
pip list 2>/dev/null | wc -l  # Should be > 10 if deps installed

# 4. Try importing main module (look for main .py files first)
ls *.py src/*.py 2>/dev/null | head -5
python -c "import [MAIN_MODULE]" 2>&1
```

### L2: E2E Test (Does it run?)

```bash
# Find entry point
cat README.md 2>/dev/null | grep -A5 -i "usage\|run\|start" | head -10

# Try running (adjust based on what you find)
python main.py --help 2>&1 || python app.py --help 2>&1 || python -m [module] --help 2>&1
```

### L3: Dependency Health

```bash
pip check 2>&1
```

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

**pip check shows conflicts:**
Document the conflict, don't fix (might break things)

---

## Report Your Results

After testing all 7, update the checklist in `/Users/eriksjaastad/projects/TODO.md`:

Find this section:
```markdown
#### Projects (24 Coding Projects)
```

Update these rows with [x] for pass or note issues:
```
| 3d-pose-factory | Python | [x] | [x] | [x] | |
| ai-journal | Python | [x] | [ ] | [x] | No entry point found |
```

---

## Summary Template

When done, provide a summary:

```
## Agent 1 Results: Python Projects A-C

Tested: 7/7
Passed all tests: X/7
Issues found: X

| Project | L1 | L2 | L3 | Notes |
|---------|----|----|-----|-------|
| 3d-pose-factory | PASS | PASS | PASS | |
| ai-journal | PASS | FAIL | PASS | No main.py |
...
```
