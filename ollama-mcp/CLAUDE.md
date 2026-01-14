# CLAUDE.md - AI Collaboration Instructions

## 🛑 IMPORTANT: READ AGENTS.md FIRST
`AGENTS.md` is the universal source of truth for this project. Always consult it for rules, standards, and procedures.

## 📚 Required Reading Before Writing Code

**You MUST read these files:**

1. **README.md** - Project overview and quick start
2. **AGENTS.md** - Universal source of truth and safety rules
3. **Documents/core/ARCHITECTURE_OVERVIEW.md** - System design
4. **.cursorrules** - Project-specific Cursor rules

---

## Project Summary

**What this project does:**
An MCP server that exposes local Ollama models to AI clients. It handles model listing, single/parallel execution, records detailed telemetry, and includes **Smart Local Routing** for automatic model selection based on task type.

**Current status:**
Core MCP tools, telemetry system, and Smart Local Routing are complete. Project structure is standardized according to `project-scaffolding` patterns.

**Key constraints:**
- All local execution ($0 cost).
- Must handle timeouts and potential model hanging.
- Concurrency limited to 8 simultaneous runs.

---

## Coding Standards

### Language & Version
**TypeScript:** Node.js 18+

### Code Style
- Prefer explicit interfaces for tool parameters.
- Use `zod` or similar for runtime validation.
- All tool results must be wrapped in `CallToolResult` format.

### Required Practices
- **Explicit Types:** Avoid `any` at all costs.
- **Telemetry:** Every model execution must call `logRun()`.
- **Safety:** Sanitize all shell arguments.
- **Paths:** Use `path` module for cross-platform compatibility.

---

## Validation Commands

**Run these before committing:**

```bash
# Compile and check for TS errors
npm run build

# Run smoke tests
node scripts/smoke_test.js
node scripts/test_routing.js

# Check telemetry & routing analysis
node scripts/analyze-runs.js
node scripts/analyze_routing_performance.js
```

---

*This file is based on the [project-scaffolding](https://github.com/eriksjaastad/project-scaffolding) CLAUDE.md pattern.*

