# Go Migration Prompts: ollama-mcp

**Target:** Rewrite `ollama-mcp/` (TypeScript) → `ollama-mcp-go/` (Go)
**Estimated Effort:** 2-3 days
**Actual Effort:** <10 minutes ⚡⚡
**Tracking:** Timed migration

---

## Progress Tracker

| Prompt | Status | Notes |
|--------|--------|-------|
| Prompt 1: Scaffolding & MCP Protocol | ✅ DONE | |
| Prompt 2: Ollama HTTP Client | ✅ DONE | Connection pooling, errgroup |
| Prompt 3: Core Tools (run, run_many) | ✅ DONE | |
| Prompt 4: Sandbox & Path Validation | ✅ DONE | Symlink + absolute path handling |
| Prompt 5: Draft Tools | ✅ DONE | 4 tools |
| Prompt 6: Tool Call Parser | ✅ DONE | XML + JSON formats |
| Prompt 7: Tool Executor | ✅ DONE | Thread-safe |
| Prompt 8: Agent Loop | ✅ DONE | Iteration limits |
| Prompt 9: Structured Logging | ✅ DONE | slog to stderr |
| Prompt 10: Integration | ✅ DONE | 7 tools registered |
| **Code Review #1** | ✅ DONE | Only go.mod fix needed |
| Prompt 11: Port Tests | 🔲 TODO | |
| **Code Review #2** | 🔲 TODO | Verify tests pass |

---

## Overview

The ollama-mcp server is ~2000 lines of TypeScript handling:
- `ollama_run` - Single model call
- `ollama_run_many` - Concurrent batch calls  
- Draft tools - File operations with sandbox
- Agent loop - Tool call parsing and execution

### Source Files to Port

| TypeScript File | Purpose | Go Destination |
|-----------------|---------|----------------|
| `server.ts` | MCP JSON-RPC stdio handler | `cmd/server/main.go` |
| `agent-loop.ts` | Tool call orchestration | `internal/agent/loop.go` |
| `agent-types.ts` | Type definitions | `internal/agent/types.go` |
| `draft-tools.ts` | File read/write/patch | `internal/tools/draft.go` |
| `draft-types.ts` | Draft type definitions | `internal/tools/types.go` |
| `sandbox-utils.ts` | Path validation | `internal/sandbox/sandbox.go` |
| `tool-call-parser.ts` | Parse LLM tool calls | `internal/parser/parser.go` |
| `tool-executor.ts` | Execute tool calls | `internal/executor/executor.go` |
| `logger.ts` | Structured logging | `internal/logger/logger.go` |

---

## Prompt 1: Project Scaffolding & MCP Protocol

### Task
Create the Go project structure and implement the MCP JSON-RPC protocol layer.

### Instructions

```
Create the ollama-mcp-go project with proper Go module structure.

1. Create directory structure:
   ollama-mcp-go/
   ├── cmd/
   │   └── server/
   │       └── main.go
   ├── internal/
   │   ├── mcp/
   │   │   ├── protocol.go
   │   │   └── handler.go
   │   ├── ollama/
   │   ├── tools/
   │   ├── sandbox/
   │   ├── agent/
   │   ├── parser/
   │   ├── executor/
   │   └── logger/
   ├── go.mod
   └── go.sum

2. Initialize go.mod:
   module github.com/eriksjaastad/ollama-mcp-go
   go 1.22

3. Implement MCP protocol in internal/mcp/protocol.go:
   - JSONRPCRequest struct (jsonrpc, id, method, params)
   - JSONRPCResponse struct (jsonrpc, id, result, error)
   - JSONRPCError struct (code, message, data)
   - MCP method constants: "initialize", "tools/list", "tools/call", "notifications/initialized"

4. Implement stdio handler in internal/mcp/handler.go:
   - Read newline-delimited JSON from stdin
   - Parse as JSONRPCRequest
   - Route to appropriate handler based on method
   - Write JSONRPCResponse to stdout
   - Handle graceful shutdown on SIGINT/SIGTERM

5. Create main.go entry point:
   - Parse config from environment (OLLAMA_HOST, SANDBOX_ROOT)
   - Initialize handler
   - Start stdio loop
   - Log startup with slog

Reference existing TypeScript:
- ollama-mcp/src/server.ts for MCP handling pattern
```

### Definition of Done
- [ ] `go build ./cmd/server` compiles without errors
- [ ] Server starts and responds to `initialize` method
- [ ] Server responds to `tools/list` with empty array
- [ ] Graceful shutdown on SIGINT

---

## Prompt 2: Ollama HTTP Client

### Task
Implement the HTTP client for communicating with the Ollama API.

### Instructions

```
Implement the Ollama HTTP client in internal/ollama/client.go.

1. Create OllamaClient struct:
   - baseURL string (default: http://localhost:11434)
   - httpClient *http.Client with connection pooling
   - timeout time.Duration

2. Implement Generate method:
   - POST to /api/generate
   - Request body: model, prompt, system, options, stream (false)
   - Response: model, response, done, context, total_duration, etc.
   - Return response text and metadata

3. Implement Chat method:
   - POST to /api/chat  
   - Request body: model, messages[], tools[], stream (false)
   - Response: message with role/content/tool_calls
   - Support tool_calls parsing in response

4. Implement batch execution helper:
   - RunMany(requests []Request) []Response
   - Use goroutine pool with configurable concurrency (default 4)
   - Use errgroup for error handling
   - Collect results in order

5. Connection pooling configuration:
   - MaxIdleConns: 10
   - MaxIdleConnsPerHost: 10
   - IdleConnTimeout: 90s

Reference existing TypeScript:
- Look at how ollama-mcp/src/server.ts calls Ollama
- Check ollama-mcp/config/ for any config patterns
```

### Definition of Done
- [ ] Client compiles and exports public API
- [ ] Generate method signature matches Ollama API
- [ ] Chat method handles tool_calls response format
- [ ] RunMany uses goroutines, not sequential calls

---

## Prompt 3: Core Tools (ollama_run, ollama_run_many)

### Task
Implement the main ollama_run and ollama_run_many MCP tools.

### Instructions

```
Implement the core Ollama tools in internal/tools/run.go and batch.go.

1. In internal/tools/run.go, implement ollama_run:
   - Input schema: model (string), prompt (string), system (optional string), options (optional object)
   - Validate model is not empty
   - Call OllamaClient.Generate or Chat based on presence of tools
   - Return: { response: string, model: string, total_duration: number }

2. In internal/tools/batch.go, implement ollama_run_many:
   - Input schema: requests (array of { model, prompt, system, options })
   - Validate all requests have required fields
   - Call OllamaClient.RunMany
   - Return: { responses: []{ response, model, index } }
   - Preserve order by index

3. Register tools in internal/mcp/handler.go:
   - Add to tools/list response with proper JSON schema
   - Route tools/call to appropriate handler

4. Tool registration pattern:
   type Tool struct {
       Name        string
       Description string
       InputSchema json.RawMessage
       Handler     func(params json.RawMessage) (any, error)
   }

Reference existing TypeScript:
- ollama-mcp/src/server.ts for tool definitions and input schemas
```

### Definition of Done
- [ ] ollama_run appears in tools/list response
- [ ] ollama_run_many appears in tools/list response
- [ ] Tools have correct JSON schemas matching TypeScript
- [ ] Handler routing works for tools/call

---

## Prompt 4: Sandbox & Path Validation

### Task
Port the sandbox utilities for safe file operations.

### Instructions

```
Implement sandbox path validation in internal/sandbox/sandbox.go.

1. Create Sandbox struct:
   - root string (absolute path)
   - allowedExtensions []string (optional whitelist)

2. Implement ValidatePath method:
   - Input: relative or absolute path
   - Resolve to absolute using filepath.Abs
   - Check path is within sandbox root using filepath.Rel
   - Reject paths with ".." that escape
   - Reject symlinks that point outside sandbox
   - Return: validated absolute path or error

3. Implement SafeRead method:
   - Validate path first
   - Read file contents
   - Return contents or error

4. Implement SafeWrite method:
   - Validate path first  
   - Create parent directories if needed
   - Write atomically (write to temp, rename)
   - Return error if any

5. Edge cases to handle:
   - Path traversal attacks: ../../etc/passwd
   - Symlink escapes
   - Non-existent parent directories
   - Permission errors

Reference existing TypeScript:
- ollama-mcp/src/sandbox-utils.ts for validation logic
```

### Definition of Done
- [ ] ValidatePath rejects `../` escapes
- [ ] ValidatePath rejects symlinks outside root
- [ ] SafeWrite uses atomic write pattern
- [ ] All methods return descriptive errors

---

## Prompt 5: Draft Tools (read, write, patch)

### Task
Implement the draft file operation tools.

### Instructions

```
Implement draft tools in internal/tools/draft.go.

1. Implement draft_read tool:
   - Input: path (string)
   - Validate path in sandbox
   - Read file contents
   - Return: { content: string, path: string }

2. Implement draft_write tool:
   - Input: path (string), content (string)
   - Validate path in sandbox
   - Write file atomically
   - Return: { path: string, bytes_written: number }

3. Implement draft_patch tool:
   - Input: path (string), patches (array of { start_line, end_line, content })
   - Validate path in sandbox
   - Read existing file
   - Apply patches in reverse order (highest line first)
   - Write result
   - Return: { path: string, patches_applied: number }

4. Implement draft_list tool:
   - Input: path (string, directory)
   - Validate path in sandbox
   - List directory contents
   - Return: { files: []{ name, is_dir, size } }

5. Register all draft tools in handler with schemas.

Reference existing TypeScript:
- ollama-mcp/src/draft-tools.ts for implementation details
- ollama-mcp/src/draft-types.ts for type definitions
```

### Definition of Done
- [ ] All 4 draft tools appear in tools/list
- [ ] draft_patch applies patches in correct order
- [ ] All operations respect sandbox boundaries
- [ ] Error messages include path context

---

## Prompt 6: Tool Call Parser

### Task
Port the LLM tool call parsing logic.

### Instructions

```
Implement tool call parsing in internal/parser/parser.go.

1. Define ToolCall struct:
   - ID string
   - Name string  
   - Arguments json.RawMessage

2. Implement ParseToolCalls function:
   - Input: LLM response text (string)
   - Detect tool call format (XML-style, JSON, or native)
   - Parse and extract tool calls
   - Return: []ToolCall

3. Handle multiple formats:
   a. XML-style: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
   b. JSON array: [{"name": "...", "arguments": {...}}]
   c. Ollama native: tool_calls array in response

4. Edge cases:
   - Malformed JSON inside tags
   - Multiple tool calls in one response
   - Mixed text and tool calls
   - Empty or whitespace-only responses

5. Return empty slice (not error) for responses with no tool calls.

Reference existing TypeScript:
- ollama-mcp/src/tool-call-parser.ts for parsing patterns
```

### Definition of Done
- [ ] Parses XML-style tool calls
- [ ] Parses JSON array tool calls
- [ ] Handles malformed input gracefully
- [ ] Returns empty slice for plain text responses

---

## Prompt 7: Tool Executor

### Task
Implement the tool execution layer.

### Instructions

```
Implement tool execution in internal/executor/executor.go.

1. Create Executor struct:
   - tools map[string]ToolHandler
   - sandbox *Sandbox
   - ollamaClient *OllamaClient

2. Implement Register method:
   - Register a tool by name with its handler function

3. Implement Execute method:
   - Input: ToolCall
   - Look up handler by name
   - Call handler with arguments
   - Wrap result or error in standard format
   - Return: { tool_call_id, result, error }

4. Implement ExecuteMany method:
   - Input: []ToolCall
   - Execute all (can be parallel or sequential based on config)
   - Collect results maintaining order
   - Return: []ExecutionResult

5. Error handling:
   - Unknown tool: return error result, don't panic
   - Handler error: wrap with context
   - Timeout: configurable per-tool timeout

Reference existing TypeScript:
- ollama-mcp/src/tool-executor.ts for execution logic
```

### Definition of Done
- [ ] Executor routes to correct handlers
- [ ] Unknown tools return error, don't crash
- [ ] ExecuteMany preserves order
- [ ] Errors include tool name context

---

## Prompt 8: Agent Loop

### Task
Port the agent loop orchestration.

### Instructions

```
Implement the agent loop in internal/agent/loop.go.

1. Create AgentLoop struct:
   - model string
   - maxIterations int
   - executor *Executor
   - ollamaClient *OllamaClient
   - parser *Parser

2. Implement Run method:
   - Input: initial prompt, system prompt
   - Loop:
     a. Call LLM with current messages
     b. Parse response for tool calls
     c. If no tool calls, return final response
     d. Execute tool calls
     e. Append results to messages
     f. Continue until max iterations or done
   - Return: { response, tool_calls_made, iterations }

3. Message accumulation:
   - Maintain conversation history
   - Include tool results in format LLM expects
   - Truncate if too long (configurable)

4. Stopping conditions:
   - No tool calls in response (task complete)
   - Max iterations reached
   - Error threshold exceeded
   - Context too long

5. Implement as MCP tool: agent_loop
   - Input: prompt, system, model, max_iterations
   - Return: final response and execution trace

Reference existing TypeScript:
- ollama-mcp/src/agent-loop.ts for loop logic
- ollama-mcp/src/agent-types.ts for types
```

### Definition of Done
- [ ] Loop executes tool calls iteratively
- [ ] Stops on max iterations
- [ ] Stops when LLM returns no tool calls
- [ ] Returns execution trace for debugging

---

## Prompt 9: Structured Logging

### Task
Implement structured logging with slog.

### Instructions

```
Implement logging in internal/logger/logger.go.

1. Create logger with slog:
   - JSON output to stderr (stdout is for MCP protocol)
   - Include timestamp, level, message, and structured fields
   - Support log levels: DEBUG, INFO, WARN, ERROR

2. Configure from environment:
   - LOG_LEVEL: set minimum level
   - LOG_FORMAT: json or text

3. Create helper functions:
   - Info(msg string, args ...any)
   - Debug(msg string, args ...any)
   - Warn(msg string, args ...any)
   - Error(msg string, err error, args ...any)

4. Standard fields to include:
   - component: which module is logging
   - request_id: for tracing MCP requests
   - duration: for timing operations

5. Log key events:
   - Server startup/shutdown
   - Tool calls (name, duration)
   - Ollama requests (model, duration)
   - Errors with full context

Reference existing TypeScript:
- ollama-mcp/src/logger.ts for logging patterns
```

### Definition of Done
- [ ] Logs go to stderr, not stdout
- [ ] JSON format parseable by log aggregators
- [ ] Log level configurable via environment
- [ ] Request durations logged

---

## Prompt 10: Integration & Final Assembly

### Task
Wire everything together and ensure the server runs end-to-end.

### Instructions

```
Complete the integration in cmd/server/main.go.

1. Main function flow:
   - Parse environment config
   - Initialize logger
   - Create sandbox with SANDBOX_ROOT
   - Create Ollama client with OLLAMA_HOST
   - Create executor and register all tools
   - Create MCP handler
   - Start stdio loop
   - Handle shutdown signals

2. Configuration from environment:
   - OLLAMA_HOST (default: http://localhost:11434)
   - SANDBOX_ROOT (required)
   - LOG_LEVEL (default: info)
   - MAX_CONCURRENT (default: 4)

3. Tool registration order:
   - ollama_run
   - ollama_run_many
   - draft_read
   - draft_write
   - draft_patch
   - draft_list
   - agent_loop

4. Health check:
   - On startup, ping Ollama API
   - Log warning if unavailable (don't fail)

5. Create Makefile:
   - build: go build -o bin/ollama-mcp-go ./cmd/server
   - test: go test ./...
   - lint: golangci-lint run
   - clean: rm -rf bin/

Reference existing TypeScript:
- ollama-mcp/src/server.ts for initialization pattern
```

### Definition of Done
- [ ] `make build` produces working binary
- [ ] Binary starts and handles MCP protocol
- [ ] All tools appear in tools/list
- [ ] Configuration from environment works

---

## Code Review Checklist

**IMPORTANT:** Run these checks during code review, NOT during implementation.

### Automated Checks

```bash
# Build verification
cd ollama-mcp-go && go build ./cmd/server

# Run all tests
go test ./... -v

# Check for race conditions
go test ./... -race

# Lint
golangci-lint run

# Check binary size
ls -lh bin/ollama-mcp-go
```

### Manual Testing

```bash
# Start server and send initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | ./bin/ollama-mcp-go

# List tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | ./bin/ollama-mcp-go

# Test ollama_run (requires Ollama running)
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ollama_run","arguments":{"model":"qwen3:0.6b","prompt":"Say hello"}}}' | ./bin/ollama-mcp-go
```

### Comparison with TypeScript

```bash
# Memory usage comparison
# Start both servers, measure with: ps aux | grep mcp

# Latency comparison  
# Time 100 ollama_run calls through each server

# Verify identical tool schemas
# Compare tools/list output from both servers
```

### Integration with Python Layer

```bash
# Update mcp_connection_pool.py to spawn Go binary
# Run agent-hub E2E tests
# Verify no regressions
```

---

## Rollback Plan

Keep the TypeScript server available for 2 weeks post-cutover:
1. Both binaries can coexist
2. Environment variable selects which to spawn
3. If issues found, revert to TypeScript immediately
