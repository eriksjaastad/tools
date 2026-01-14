# Test Validation: Node.js Projects (Agent 4 of 5)

**Your batch:** 7 Node.js/TypeScript projects

---

## Projects to Test

1. `flo-fi` - /Users/eriksjaastad/projects/flo-fi
2. `holoscape` - /Users/eriksjaastad/projects/holoscape
3. `hypocrisynow` - /Users/eriksjaastad/projects/hypocrisynow
4. `portfolio-ai` - /Users/eriksjaastad/projects/portfolio-ai
5. `synth-insight-labs` - /Users/eriksjaastad/projects/synth-insight-labs
6. `tax-organizer` - /Users/eriksjaastad/projects/tax-organizer
7. `van-build` - /Users/eriksjaastad/projects/van-build

---

## For Each Project, Run These Tests

### L1: Smoke Test (Can it load?)

```bash
cd /Users/eriksjaastad/projects/[PROJECT]

# 1. Find package.json (might be in subdirectory)
find . -name "package.json" -maxdepth 2 2>/dev/null

# 2. Check for node_modules
ls -d node_modules 2>/dev/null || ls -d */node_modules 2>/dev/null || echo "NO NODE_MODULES"

# 3. Check package.json scripts
cat package.json 2>/dev/null | grep -A20 '"scripts"' | head -25

# 4. Verify node version
node --version
```

### L2: E2E Test (Does it run?)

```bash
# Try build first (catches most issues)
npm run build 2>&1 || echo "No build script or build failed"

# Try start/dev
npm start 2>&1 &
sleep 3
kill %1 2>/dev/null

# Or for dev servers
npm run dev 2>&1 &
sleep 3
kill %1 2>/dev/null
```

### L3: Dependency Health

```bash
npm audit 2>&1 | head -30
npm ls --depth=0 2>&1 | grep -E "ERR|WARN|missing" | head -10
```

---

## Project-Specific Notes

- **hypocrisynow**: Frontend is in `frontend/` subdirectory
- **tax-organizer**: Frontend is in `frontend/` subdirectory
- **van-build**: Dashboard is in `van-dashboard/` subdirectory

For projects with subdirectories:
```bash
cd frontend/  # or van-dashboard/
npm install
npm run build
```

---

## Quick Fixes (Do These If Needed)

**No node_modules:**
```bash
npm install
```

**Lock file conflicts:**
```bash
rm package-lock.json
npm install
```

**Audit vulnerabilities (high/critical only):**
```bash
npm audit fix
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
## Agent 4 Results: Node.js Projects

Tested: 7/7
Passed all tests: X/7
Issues found: X

| Project | L1 | L2 | L3 | Notes |
|---------|----|----|-----|-------|
| flo-fi | PASS | PASS | PASS | |
| holoscape | PASS | FAIL | PASS | Build error: missing types |
...
```
