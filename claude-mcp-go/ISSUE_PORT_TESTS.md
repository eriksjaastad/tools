# ISSUE: Port TypeScript Tests to Go

Currently, the `claude-mcp-go` project has been ported for functionality, but the test suite from the original TypeScript implementation (`claude-mcp/tests/`) has not yet been ported to Go.

## Source Tests to Port
- `claude-mcp/tests/hub.test.ts` -> `internal/tools/hub_test.go`
- `claude-mcp/tests/safePath.test.ts` -> `internal/tools/claude_test.go`
- `claude-mcp/tests/toolDispatch.test.ts` -> `internal/tools/tools_test.go`

## Implementation Details
Use the standard Go `testing` package or a library like `testify` (already in `go.mod`) to implement these tests. Ensure the MCP protocol interactions are tested by mocking the server or using the `mcp-go` testing utilities if available.

## Status: PENDING
Created: 2026-01-18
Target: Full parity with TypeScript test coverage.
