# Test Validation: Python Projects I-T (Agent 2 of 5)

**Your batch:** 7 Python projects (alphabetical I-T)

---

## Projects to Test

1. `image-workflow` - /Users/eriksjaastad/projects/image-workflow
2. `muffinpanrecipes` - /Users/eriksjaastad/projects/muffinpanrecipes
3. `national-cattle-brands` - /Users/eriksjaastad/projects/national-cattle-brands
4. `project-scaffolding` - /Users/eriksjaastad/projects/project-scaffolding
5. `project-tracker` - /Users/eriksjaastad/projects/project-tracker
6. `smart-invoice-workflow` - /Users/eriksjaastad/projects/smart-invoice-workflow
7. `trading-copilot` - /Users/eriksjaastad/projects/trading-copilot

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

## Project-Specific Notes

- **image-workflow**: Uses `pyproject.toml`, may need `pip install -e .`
- **national-cattle-brands**: Code is in `texas_brand_scraper/` subdirectory
- **project-scaffolding**: Has `scaffold_cli.py` as main entry
- **project-tracker**: Has `pt` CLI tool

---

## Quick Fixes (Do These If Needed)

**No venv:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**For pyproject.toml projects:**
```bash
pip install -e .
```

**Deps not installed:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## Report Your Results

After testing all 7, update the checklist in `/Users/eriksjaastad/projects/TODO.md`:

Find this section:
```markdown
#### Projects (24 Coding Projects)
```

Update these rows with [x] for pass or note issues.

---

## Summary Template

When done, provide a summary:

```
## Agent 2 Results: Python Projects I-T

Tested: 7/7
Passed all tests: X/7
Issues found: X

| Project | L1 | L2 | L3 | Notes |
|---------|----|----|-----|-------|
| image-workflow | PASS | PASS | PASS | |
...
```
