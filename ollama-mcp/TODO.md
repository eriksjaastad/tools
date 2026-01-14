# Ollama MCP - TODO

**Last Updated:** January 10, 2026
**Project Status:** Production Ready
**Current Phase:** Smart Routing Complete - Awaiting Telemetry Data

---

## 📍 Current State

### What's Working ✅
- **MCP Server:** Successfully exposes 3 tools to Cursor/Claude
- **ollama_list_models:** Lists all locally installed Ollama models
- **ollama_run:** Executes single model with prompt + options + task_type routing
- **ollama_run_many:** Concurrent execution with configurable concurrency (max 8)
- **🧠 Smart Routing:** Task-type based model selection with fallback chains (config/routing.yaml)
- **🔍 Response Quality:** isGoodResponse() detects poor/refused responses and triggers fallback
- **🚨 Escalation:** Returns `escalate: true` when all local models fail
- **Validation:** Model names, prompts, options all validated
- **Safety:** Command injection prevention, timeout handling
- **TypeScript Build:** Compiles cleanly to `dist/server.js`
- **📊 Telemetry Logging:** All runs logged to `~/.ollama-mcp/runs.jsonl`
- **📈 Analysis Scripts:** `analyze-runs.js` + `analyze_routing_performance.js`
- **⏰ Self-Reminder:** Telemetry review trigger (30 days + 50 runs)

### What's Missing ❌
- **Real-world usage data:** Need 50+ runs with task_type to validate routing effectiveness
- **Learned routing iteration:** First telemetry review will happen after 30 days + 50 runs (auto-triggered)

### 🚨 INCIDENT LOG: 2026-01-04
- **Issue:** Server failed to start in Cursor with `ERR_MODULE_NOT_FOUND` (missing `@modelcontextprotocol/sdk`).
- **Root Cause:** `node_modules` were missing from the production directory.
- **Fix:** Ran `npm install` and `npm run build`. Verified with `smoke_test.js`.
- **Lesson:** Project needs a reliability check to ensure it's "production ready" beyond just code completion.

### Blockers & Dependencies
- None

---

## ✅ Smart Routing Enhancement (January 10, 2026)

**Implemented & Verified:**
- [x] Task-type routing (classification, extraction, code, reasoning, file_mod, auto)
- [x] YAML-based fallback chains (config/routing.yaml)
- [x] Response quality detection (isGoodResponse)
- [x] Escalation flag when all local models fail
- [x] Telemetry review trigger (auto-reminder after 30 days + 50 runs)
- [x] Learned routing analysis script (scripts/analyze_routing_performance.js)

**Prompts used:** `Documents/planning/SMART_ROUTING_PROMPTS_INDEX.md`

## ✅ Completed Tasks

### Phase 3: Project Structure Standardization (January 1, 2026)
- [x] Restructured documentation into `Documents/` directory
- [x] Created `ARCHITECTURE_OVERVIEW.md` and `OPERATIONS_GUIDE.md`
- [x] Created `00_Index_ollama-mcp.md` (Obsidian index)
- [x] Created `AGENTS.md` (Source of truth)
- [x] Created `CLAUDE.md` (AI collaboration instructions)
- [x] Created `ROADMAP.md` (Project vision)
- [x] Implemented `.cursorrules` and `.cursorignore`
- [x] Updated `.gitignore` to match standards
- [x] Registered project in `EXTERNAL_RESOURCES.md`
- [x] Standardized `TODO.md` format
- [x] Registered in `project-tracker` via scan

### Phase 2: Telemetry Implementation (December 31, 2025)
- [x] Add JSON Lines logger utility (`src/logger.ts`)
- [x] Create log directory (`~/.ollama-mcp/`)
- [x] Implement append-only writer
- [x] Export simple API: `logRun(metadata)`, `generateBatchId()`
- [x] Instrument `ollamaRun()` function
  - [x] Capture start/end timestamps (ISO 8601)
  - [x] Calculate duration_ms
  - [x] Count output characters from stdout
  - [x] Record exit code
  - [x] Record timed_out flag
  - [x] Log to JSON Lines file
- [x] Instrument `ollamaRunMany()` function
  - [x] Generate batch_id for grouping
  - [x] Record concurrency level used
  - [x] Log each job separately
- [x] Create analysis script (`scripts/analyze-runs.js`)
  - [x] Show average duration per model
  - [x] Show timeout rate per model
  - [x] Show character output stats
  - [x] Batch analysis (grouping, concurrency)
  - [x] Recent runs display
  - [x] Overall summary statistics

### Phase 1: Initial Implementation (December 2025)
- [x] Create MCP server with stdio transport
- [x] Implement `ollama_list_models` tool
- [x] Implement `ollama_run` tool with validation
- [x] Implement `ollama_run_many` with concurrency control
- [x] Add timeout handling (default 120s)
- [x] Add command injection prevention
- [x] Write setup documentation
- [x] Test with all 4 local models (deepseek-r1:14b, qwen3:4b, qwen3:14b, llama3.2:3b)

---

## 📋 Pending Tasks

### 🔴 CRITICAL - Tech Debt
- [ ] **Flat Root Transition:** Move contents of `Documents/core/` to `Documents/` root and delete the core directory.

### 🟡 HIGH PRIORITY - Important

#### Task Group 2: Testing & Validation
- [x] Test logging with single model runs
- [x] Test logging with concurrent runs
- [x] Verify log file format (valid JSON Lines)
- [x] Test with different model sizes (3b, 4b, 14b)
- [x] Test timeout scenarios (ensure logged correctly)
- [x] Run analysis script after collecting some data

#### Task Group 3: Documentation
- [x] Update README with telemetry feature
- [x] Document log file location (`~/.ollama-mcp/runs.jsonl`)
- [x] Document log format/schema
- [x] Add example analytics usage
- [x] Create TELEMETRY_GUIDE.md walkthrough
- [x] Update IMPLEMENTATION_SUMMARY.md

## 🎯 Success Criteria

### Telemetry Feature Complete When:
- [x] All ollama_run calls write to log file
- [x] All ollama_run_many jobs logged individually with batch_id
- [x] Log file is valid JSON Lines format
- [x] Analysis script created with key metrics
- [x] After testing: Can answer "Which model is fastest for task X?"
- [x] After 1 week: Can identify timeout patterns (logic verified)
- [x] Documentation updated with examples

### Project Complete When:
- [x] Telemetry working reliably
- [x] Smart Local Routing implemented and verified
- [x] Analysis shows actionable insights
- [x] Pattern documented for extraction to project-scaffolding

---

## 📊 Notes

### AI Agents in Use
- **Claude Sonnet 4.5:** Initial MCP implementation, telemetry design
- **Cursor:** Code implementation and testing

### Cron Jobs / Automation
- None (manual testing with Cursor MCP integration)

### External Services Used
- **Ollama:** Local model execution (free)
- **MCP SDK:** @modelcontextprotocol/sdk (open source)

### Cost Estimates
- **Development:** 2-4 hours for telemetry feature
- **Monthly:** $0 (all local)
- **One-time:** None

### Time Estimates
- **Telemetry Implementation:** 1-2 hours
- **Testing & Validation:** 30-60 minutes
- **Documentation:** 30 minutes
- **Total:** 2-4 hours

### Related Projects & Documentation
- **project-scaffolding:** Pattern library and TODO standards
- **Ollama:** https://ollama.ai/
- **MCP Protocol:** Model Context Protocol specification

### Technical Stack
- **Language:** TypeScript
- **Runtime:** Node.js
- **Build:** tsc (TypeScript compiler)
- **Protocol:** MCP (Model Context Protocol) over stdio
- **Models:** Ollama (local execution)
- **Log Format:** JSON Lines (`.jsonl`)

### Key Decisions Made
1. **JSON Lines over SQLite:** Simpler, append-only, easily parseable with jq/Python (2025-12-31)
2. **Log location:** `~/.ollama-mcp/runs.jsonl` for centralized logging (2025-12-31)
3. **No prompt logging:** Only metrics, not content (privacy + file size) (2025-12-31)
4. **Character count over tokens:** Simpler, no tokenizer dependency (2025-12-31)

### Open Questions
- ❓ Should we log the prompt length (chars) for correlation analysis?
- ❓ Log file rotation needed, or is append-only sufficient?
- ❓ Include system info (CPU, RAM) in logs for performance debugging?

---

## 🔄 Change Log

### 2025-12-31 - Telemetry Implementation Complete
- Added JSON Lines logger (`src/logger.ts`)
- Instrumented all model runs with metrics
- Created analysis script (`scripts/analyze-runs.js`)
- Updated documentation (README, TELEMETRY_GUIDE)
- Feature ready for testing
- Compiled successfully, no build errors

### 2025-12-31 - Telemetry Planning
- Created TODO following project-scaffolding standards
- Designed JSON Lines logging approach
- Identified logging points in codebase

### 2025-12 - Initial Implementation
- Built MCP server with 3 tools
- Tested with 4 local models
- Documented setup process

---

<!--
=============================================================================
LOGGING SCHEMA (for reference):
=============================================================================

Each log entry is a single line of JSON:

{
  "timestamp": "2025-12-31T10:30:00.000Z",
  "model": "llama3.2:3b",
  "start": "2025-12-31T10:30:00.000Z",
  "end": "2025-12-31T10:30:15.234Z",
  "duration_ms": 15234,
  "exit_code": 0,
  "output_chars": 1250,
  "timed_out": false,
  "task_type": "unit_tests",  // optional
  "batch_id": "abc123",        // for ollama_run_many
  "concurrency": 2             // for ollama_run_many
}

Example queries after implementation:

# Average duration per model
cat ~/.ollama-mcp/runs.jsonl | jq -s 'group_by(.model) | map({model: .[0].model, avg_duration: (map(.duration_ms) | add / length)})'

# Timeout rate
cat ~/.ollama-mcp/runs.jsonl | jq -s 'group_by(.model) | map({model: .[0].model, timeout_rate: (map(select(.timed_out)) | length) / (. | length)})'

# Output size by model
cat ~/.ollama-mcp/runs.jsonl | jq -s 'group_by(.model) | map({model: .[0].model, avg_chars: (map(.output_chars) | add / length)})'

=============================================================================
-->

---

*Template Version: 1.0*  
*Last Modified: December 31, 2025*  
*Source: project-scaffolding/templates/TODO.md.template*

