# Go Migration Prompts: claude-mcp

**Target:** Rewrite `claude-mcp/` (TypeScript) → `claude-mcp-go/` (Go)
**Estimated Effort:** 0.5 days
**Actual Effort:** ~10 minutes ⚡
**Tracking:** Timed migration - COMPLETE

---

## Progress Tracker

| Prompt | Status | Notes |
|--------|--------|-------|
| Prompt 1: Scaffolding & MCP Protocol | ✅ DONE | Used mark3labs/mcp-go |
| Prompt 2: Hub Tools | ✅ DONE | 6 tools ported |
| Prompt 3: Claude-Specific Tools | ✅ DONE | 5 tools ported |
| Prompt 4: Review Tool & Prompts | ✅ DONE | 2 tools + 2 prompts |
| Prompt 5: Integration | ✅ DONE | Build verified |
| **Code Review #1** | ✅ DONE | Fixed go.mod, error handling |
| Prompt 6: Port Tests | ✅ DONE | 14 tests across 3 files |
| **Code Review #2** | ✅ DONE | All tests pass, no races |

---

## Overview

The claude-mcp server is ~100 lines core + tools, serving as the hub for agent communication. Much simpler than ollama-mcp.

### Source Files to Port

| TypeScript File | Purpose | Go Destination |
|-----------------|---------|----------------|
| `src/server.ts` | MCP server entry | `cmd/server/main.go` |
| `src/tools/index.ts` | Tool exports | `internal/tools/tools.go` |
| `src/tools/hub.ts` | Hub messaging | `internal/tools/hub.go` |
| `src/tools/draft_review.ts` | Review tool | `internal/tools/review.go` |
| `src/tools/claude_*.ts` | Claude-specific tools | `internal/tools/claude.go` |
| `src/prompts/*.ts` | Prompt templates | `internal/prompts/` |

---

## Prompt 1: Project Scaffolding & MCP Protocol ✅

### Task
Create the Go project and implement MCP protocol handling.

### Instructions

```
Create the claude-mcp-go project with proper Go module structure.

1. Create directory structure:
   claude-mcp-go/
   ├── cmd/
   │   └── server/
   │       └── main.go
   ├── internal/
   │   ├── mcp/
   │   │   ├── protocol.go
   │   │   └── handler.go
   │   ├── tools/
   │   └── prompts/
   ├── go.mod
   └── go.sum

2. Initialize go.mod:
   module github.com/eriksjaastad/claude-mcp-go
   go 1.22

3. Implement MCP protocol (same pattern as ollama-mcp-go):
   - JSONRPCRequest/Response structs
   - Stdio loop reading/writing JSON
   - Method routing

4. Key difference from ollama-mcp-go:
   - This server also handles prompts/list and prompts/get
   - Simpler tool set

5. Create main.go:
   - Initialize handler
   - Register tools
   - Start stdio loop

Reference existing TypeScript:
- claude-mcp/src/server.ts for MCP setup
```

### Definition of Done
- [x] `go build ./cmd/server` compiles
- [x] Server responds to initialize
- [x] Server responds to tools/list
- [x] Server responds to prompts/list

---

## Prompt 2: Hub Tools ✅

### Task
Implement the core hub messaging tools.

### Instructions

```
Implement hub tools in internal/tools/hub.go.

1. Review claude-mcp/src/tools/hub.ts for the hub interface.

2. Implement these tools based on what hub.ts exports:
   - Any message publishing tools
   - Any subscription tools
   - Any status query tools

3. These tools likely interact with:
   - SQLite message bus (if used)
   - File-based messaging
   - In-memory state

4. Create proper MCP tool schemas for each.

5. Error handling:
   - Return structured errors
   - Include context about what failed

Reference existing TypeScript:
- claude-mcp/src/tools/hub.ts for exact tool definitions
```

### Definition of Done
- [x] All hub tools from TypeScript are ported (6 tools)
- [x] Tools appear in tools/list with correct schemas
- [x] Error messages are descriptive

---

## Prompt 3: Claude-Specific Tools ✅

### Task
Port the Claude-specific tools (health, judge, security, etc.).

### Instructions

```
Implement Claude tools in internal/tools/claude.go.

Port these tools from claude-mcp/src/tools/:
1. claude_health.ts → health check tool
2. claude_judge_review.ts → judge review functionality
3. claude_resolve_conflict.ts → conflict resolution
4. claude_security_audit.ts → security audit
5. claude_validate_proposal.ts → proposal validation

For each tool:
1. Read the TypeScript implementation
2. Translate logic to Go
3. Match input/output schemas exactly
4. Register with MCP handler

These tools may call external APIs or perform file operations.
Ensure proper error handling and timeouts.

Reference existing TypeScript:
- claude-mcp/src/tools/claude_*.ts files
```

### Definition of Done
- [x] All 5 claude_* tools ported
- [x] Schemas match TypeScript versions
- [x] Tools appear in tools/list

---

## Prompt 4: Review Tool & Prompts ✅

### Task
Port the draft review tool and prompt templates.

### Instructions

```
Implement review functionality.

1. Port draft_review.ts to internal/tools/review.go:
   - Read the implementation
   - Translate to Go
   - Register as MCP tool

2. Port prompt templates to internal/prompts/:
   - draft_review_template.ts → review.go
   - judge_template.ts → judge.go
   - Export as functions returning template strings

3. Prompts should:
   - Be Go template strings or constants
   - Support variable substitution if needed
   - Match the exact structure from TypeScript

4. Register prompts for prompts/list and prompts/get:
   - MCP prompts/list returns available prompt names
   - MCP prompts/get returns specific prompt content

Reference existing TypeScript:
- claude-mcp/src/tools/draft_review.ts
- claude-mcp/src/prompts/*.ts
```

### Definition of Done
- [x] draft_review tool ported (+ submit_review_verdict)
- [x] Both prompt templates ported
- [x] prompts/list returns template names
- [x] prompts/get returns template content

---

## Prompt 5: Integration & Final Assembly ✅

### Task
Wire everything together.

### Instructions

```
Complete the integration in cmd/server/main.go.

1. Main function:
   - Initialize logger (slog to stderr)
   - Create MCP handler
   - Register all tools (hub, claude_*, review)
   - Register prompts
   - Start stdio loop
   - Handle shutdown

2. Configuration (minimal for this server):
   - LOG_LEVEL (default: info)
   - Any paths for message bus if applicable

3. Create Makefile:
   - build: go build -o bin/claude-mcp-go ./cmd/server
   - test: go test ./...
   - lint: golangci-lint run
   - clean: rm -rf bin/

4. Verify tool count matches TypeScript:
   - List all tools from both servers
   - Confirm 1:1 mapping

Reference existing TypeScript:
- claude-mcp/src/server.ts
```

### Definition of Done
- [x] `make build` produces working binary
- [x] All tools from TypeScript are present (13/13)
- [x] All prompts from TypeScript are present (2/2)
- [x] Server handles MCP protocol correctly

---

## Prompt 6: Port Tests

### Task
Port the TypeScript test suite to Go for full test parity.

### Instructions

```
Port tests from claude-mcp/tests/ to Go.

Reference: claude-mcp-go/ISSUE_PORT_TESTS.md

1. Create internal/tools/hub_test.go:
   - Port tests from claude-mcp/tests/hub.test.ts
   - Test hub_connect registers agent
   - Test hub_send_message adds message to state
   - Test hub_receive_messages filters by agent_id
   - Test hub_receive_messages filters by "since" timestamp
   - Test hub_heartbeat updates heartbeat map
   - Test atomic file write (temp file + rename)
   - Test mutex prevents race conditions

2. Create internal/tools/claude_test.go:
   - Port tests from claude-mcp/tests/safePath.test.ts
   - Test SafePath() accepts valid relative paths
   - Test SafePath() rejects "../" traversal attempts
   - Test SafePath() rejects absolute path escapes
   - Test SafePath() rejects paths that resolve outside base

3. Create internal/tools/review_test.go:
   - Port tests from claude-mcp/tests/toolDispatch.test.ts
   - Test request_draft_review returns structured prompt
   - Test submit_review_verdict creates report files
   - Test error handling for missing files

4. Use standard Go testing package:
   - func TestXxx(t *testing.T)
   - Use t.Run() for subtests
   - Use t.TempDir() for file operation tests

Do NOT run the tests - that will be done during code review.
```

### Definition of Done
- [x] internal/tools/hub_test.go exists with hub tests (9 tests)
- [x] internal/tools/claude_test.go exists with SafePath tests (5 tests)
- [x] internal/tools/review_test.go exists with review tool tests (3 tests)
- [x] All test files compile (go build ./...)

---

## Code Review Checklist

**IMPORTANT:** These checks are run by Erik/Super Manager, NOT the Floor Manager.
The Floor Manager does not have terminal access.

---

### Code Review #1 (After Prompts 1-5) ✅ COMPLETED

**Automated Checks (run by Super Manager):**

```bash
# Build verification
cd claude-mcp-go && go build ./cmd/server

# Check binary size
ls -lh bin/claude-mcp-go
```

**Results:**
- Build: ✅ PASS
- Binary size: 6.5 MB ✅

**Manual Testing (run by Super Manager):**

```bash
# Initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | ./bin/claude-mcp-go

# List tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | ./bin/claude-mcp-go

# List prompts
echo '{"jsonrpc":"2.0","id":3,"method":"prompts/list","params":{}}' | ./bin/claude-mcp-go
```

**Results:**
- initialize: ✅ Returns valid serverInfo
- tools/list: ✅ Returns 13 tools
- prompts/list: ✅ Returns 2 prompts

**Issues Found & Fixed:**
- BI-001: go.mod had invalid version (1.25.5 → 1.23.0) ✅ FIXED
- BI-004: review.go returned Go errors instead of MCP errors ✅ FIXED

---

### Code Review #2 (After Prompt 6) ✅ COMPLETED

**Test Execution (run by Super Manager):**

```bash
# Run all tests
cd claude-mcp-go && go test ./... -v

# Check for race conditions
go test ./... -race
```

**Results:**
- `go test ./... -v`: ✅ 14/14 tests pass
- `go test ./... -race`: ✅ No race conditions detected
- Build: ✅ 6.5 MB binary

**Test Coverage:**

| Test File | Tests | Status |
|-----------|-------|--------|
| hub_test.go | 9 subtests | ✅ PASS |
| claude_test.go | 5 subtests | ✅ PASS |
| review_test.go | 3 subtests | ✅ PASS |

**Issues Found & Fixed:**
- SafePath() didn't reject absolute paths → Fixed by adding `filepath.IsAbs()` check

---

## Shared Code Opportunity

If implementing after ollama-mcp-go, consider:

1. **Shared MCP protocol package**
   - Extract `internal/mcp/` to shared module
   - Both servers import same protocol code

2. **Shared logger**
   - Same slog configuration
   - Same output format

3. **Mono-repo structure option**
   ```
   mcp-servers-go/
   ├── cmd/
   │   ├── ollama-mcp/
   │   └── claude-mcp/
   ├── internal/
   │   └── mcp/  (shared)
   ├── go.mod
   └── go.sum
   ```

This reduces code duplication if desired.

---

## Rollback Plan

Same as ollama-mcp:
1. Keep TypeScript server for 2 weeks
2. Environment variable selects which binary
3. Quick revert if issues found
