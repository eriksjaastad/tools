# Test Validation Prompt for Gemini

**Purpose:** Validate a coding project actually works (deps installed, can run, no conflicts).

---

## Instructions

You are validating that a project works. Run each test level and report results.

**PROJECT:** `[PROJECT_NAME]`
**PATH:** `/Users/eriksjaastad/projects/[PROJECT_NAME]`

---

## L1: Smoke Test (Can it load?)

### For Python projects:
```bash
cd /Users/eriksjaastad/projects/[PROJECT_NAME]

# Check for venv
ls -la venv/ .venv/ 2>/dev/null || echo "NO VENV FOUND"

# If venv exists, activate and check imports
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null

# Check if deps are installed
pip list 2>/dev/null | head -20

# Try importing main modules (adjust based on project)
python -c "import [MAIN_MODULE]" 2>&1
```

### For Node.js projects:
```bash
cd /Users/eriksjaastad/projects/[PROJECT_NAME]

# Check for node_modules
ls -la node_modules/ 2>/dev/null || echo "NO NODE_MODULES - run npm install"

# Check package.json exists
cat package.json | head -20

# Try a dry run
npm run build --dry-run 2>&1 || echo "No build script"
```

### For Go projects:
```bash
cd /Users/eriksjaastad/projects/[PROJECT_NAME]

# Check go.mod
cat go.mod

# Verify deps
go mod verify

# Try building
go build ./... 2>&1
```

---

## L2: E2E Happy Path (Does it run?)

### Identify the main entry point:
- Look for: `main.py`, `app.py`, `server.py`, `cli.py`, `index.ts`, `main.go`
- Check `package.json` scripts or `pyproject.toml` entry points
- Check README for "how to run"

### Run it:
```bash
# Python example
python main.py --help 2>&1 || python -m [module] --help 2>&1

# Node.js example
npm start 2>&1 || npm run dev 2>&1

# Go example
./[binary] --help 2>&1 || go run main.go --help 2>&1
```

**Success criteria:** Doesn't crash. Shows help/usage or starts briefly.

---

## L3: Dependency Health Check

### Python:
```bash
pip check 2>&1
```

### Node.js:
```bash
npm audit 2>&1 | head -30
npm ls --depth=0 2>&1 | grep -E "ERR|WARN" | head -10
```

### Go:
```bash
go mod tidy
go mod verify
```

---

## Report Format

After testing, update the checklist in `/Users/eriksjaastad/projects/TODO.md`:

```markdown
| [PROJECT_NAME] | [Stack] | [x] | [x] | [x] | [Notes if any issues] |
```

If issues found:
1. Document what failed
2. If fixable in <5 min, fix it
3. If not, add to project's TODO.md

---

## Batch Mode

To test multiple projects, run this prompt for each project in order:

**Python Projects (16):**
1. 3d-pose-factory
2. ai-journal
3. ai-usage-billing-tracker
4. analyze-youtube-videos
5. automation-consulting
6. cortana-personal-ai
7. country-ai-futures-tracker
8. image-workflow
9. muffinpanrecipes
10. national-cattle-brands
11. project-scaffolding
12. project-tracker
13. smart-invoice-workflow
14. trading-copilot
15. agent-hub (_tools/)
16. ai_router (_tools/)
17. claude-cli (_tools/)
18. integrity-warden (_tools/)
19. pdf-converter (_tools/)
20. ssh_agent (_tools/)

**Node.js Projects (8):**
1. flo-fi
2. holoscape
3. hypocrisynow
4. portfolio-ai
5. synth-insight-labs
6. tax-organizer
7. van-build
8. gsd (_tools/)
9. ollama-mcp (_tools/)

**Go Projects (1):**
1. audit-agent

**Chrome Extensions (2):**
1. plugin-duplicate-detection
2. plugin-find-names-chrome

---

## Quick Fixes Reference

**Missing venv:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Missing node_modules:**
```bash
npm install
```

**Missing Go deps:**
```bash
go mod download
```

**Outdated lock file:**
```bash
# Python
pip install -r requirements.txt --upgrade

# Node.js
rm package-lock.json && npm install
```
