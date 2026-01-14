# Test Validation: Node.js Tools + Go + Chrome (Agent 5 of 5)

**Your batch:** 5 items (mixed stack)

---

## Items to Test

### Node.js/TypeScript Tools (2)
1. `gsd` - /Users/eriksjaastad/projects/_tools/gsd
2. `ollama-mcp` - /Users/eriksjaastad/projects/_tools/ollama-mcp

### Go Project (1)
3. `audit-agent` - /Users/eriksjaastad/projects/audit-agent

### Chrome Extensions (2)
4. `plugin-duplicate-detection` - /Users/eriksjaastad/projects/plugin-duplicate-detection
5. `plugin-find-names-chrome` - /Users/eriksjaastad/projects/plugin-find-names-chrome

---

## Node.js Tools Tests

### For gsd and ollama-mcp:

#### L1: Smoke Test
```bash
cd /Users/eriksjaastad/projects/_tools/[TOOL]

# Check for node_modules
ls -d node_modules 2>/dev/null || echo "NO NODE_MODULES"

# Check package.json
cat package.json | grep -A15 '"scripts"'

# For TypeScript, check if compiled
ls dist/ build/ 2>/dev/null || echo "Not compiled"
```

#### L2: E2E Test
```bash
# gsd - check if install script works
node bin/install.js --help 2>&1 || echo "No help flag"

# ollama-mcp - try building
npm run build 2>&1
```

#### L3: Dependency Health
```bash
npm audit 2>&1 | head -20
npm ls --depth=0 2>&1 | grep -E "ERR|WARN" | head -5
```

---

## Go Project Tests

### For audit-agent:

#### L1: Smoke Test
```bash
cd /Users/eriksjaastad/projects/audit-agent

# Check go.mod
cat go.mod

# Verify deps
go mod verify
```

#### L2: E2E Test
```bash
# Build the binary
go build -o audit ./...

# Or if there's a cmd/ directory
go build -o audit ./cmd/audit

# Try running
./audit --help 2>&1 || ./audit version 2>&1
```

#### L3: Dependency Health
```bash
go mod tidy
go mod verify
go vet ./...
```

---

## Chrome Extension Tests

### For plugin-duplicate-detection and plugin-find-names-chrome:

Chrome extensions are different - no runtime deps to install.

#### L1: Smoke Test
```bash
cd /Users/eriksjaastad/projects/[PLUGIN]

# Check manifest exists
cat manifest.json 2>/dev/null | head -20

# Check main JS files exist
ls *.js content/*.js background/*.js 2>/dev/null
```

#### L2: E2E Test
```bash
# Check JS syntax (no runtime test possible without browser)
node --check *.js 2>&1 || echo "Syntax check not applicable"

# For extensions, "works" = loads in Chrome without errors
# Document: "Manual test required - load unpacked in chrome://extensions"
```

#### L3: Dependency Health
```bash
# Check if there's a package.json (some extensions have build tools)
cat package.json 2>/dev/null && npm audit 2>&1 | head -10

# If no package.json, deps are N/A
echo "No npm deps - standalone extension"
```

---

## Quick Fixes

**Node.js - no node_modules:**
```bash
npm install
```

**Go - missing deps:**
```bash
go mod download
go mod tidy
```

**TypeScript - not compiled:**
```bash
npm run build
```

---

## Report Your Results

After testing all 5, update the checklist in `/Users/eriksjaastad/projects/TODO.md`:

Update both sections:
- `#### Tools (8 in _tools/)` for gsd, ollama-mcp
- `#### Projects (24 Coding Projects)` for audit-agent and plugins

---

## Summary Template

When done, provide a summary:

```
## Agent 5 Results: Node.js Tools + Go + Chrome

Tested: 5/5
Passed all tests: X/5
Issues found: X

| Item | Stack | L1 | L2 | L3 | Notes |
|------|-------|----|----|-----|-------|
| gsd | Node.js | PASS | PASS | PASS | |
| ollama-mcp | TypeScript | PASS | PASS | PASS | |
| audit-agent | Go | PASS | PASS | PASS | |
| plugin-duplicate-detection | Chrome | PASS | N/A | N/A | Manual load test needed |
| plugin-find-names-chrome | Chrome | PASS | N/A | N/A | Manual load test needed |
```
