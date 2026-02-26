package executor

import (
	"fmt"
	"sync"

	"github.com/eriksjaastad/ollama-mcp-go/internal/mcp"
	"github.com/eriksjaastad/ollama-mcp-go/internal/parser"
)

// ExecutionResult represents the result of a tool execution.
type ExecutionResult struct {
	ToolCallID string `json:"tool_call_id"`
	ToolName   string `json:"tool_name,omitempty"`
	Result     any    `json:"result,omitempty"`
	Error      string `json:"error,omitempty"`
}

// Executor manages tool execution.
type Executor struct {
	handlers map[string]mcp.ToolHandler
	mu       sync.RWMutex
}

// NewExecutor creates a new Executor.
func NewExecutor() *Executor {
	return &Executor{
		handlers: make(map[string]mcp.ToolHandler),
	}
}

// Register registers a tool handler.
func (e *Executor) Register(name string, handler mcp.ToolHandler) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.handlers[name] = handler
}

// Execute runs a single tool call.
func (e *Executor) Execute(tc parser.ToolCall) ExecutionResult {
	e.mu.RLock()
	handler, ok := e.handlers[tc.Name]
	e.mu.RUnlock()

	if !ok {
		return ExecutionResult{
			ToolCallID: tc.ID,
			ToolName:   tc.Name,
			Error:      fmt.Sprintf("unknown tool: %s", tc.Name),
		}
	}

	result, err := handler(tc.Arguments)
	if err != nil {
		return ExecutionResult{
			ToolCallID: tc.ID,
			ToolName:   tc.Name,
			Error:      err.Error(),
		}
	}

	return ExecutionResult{
		ToolCallID: tc.ID,
		ToolName:   tc.Name,
		Result:     result,
	}
}

// ExecuteMany runs multiple tool calls in parallel.
func (e *Executor) ExecuteMany(tcs []parser.ToolCall) []ExecutionResult {
	results := make([]ExecutionResult, len(tcs))
	var wg sync.WaitGroup
	wg.Add(len(tcs))

	for i, tc := range tcs {
		go func(i int, tc parser.ToolCall) {
			defer wg.Done()
			results[i] = e.Execute(tc)
		}(i, tc)
	}

	wg.Wait()
	return results
}
