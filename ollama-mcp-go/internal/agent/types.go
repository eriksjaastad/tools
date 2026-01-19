package agent

import "github.com/eriksjaastad/ollama-mcp-go/internal/executor"

// AgentLoopInput represents the input for the agent_loop tool.
type AgentLoopInput struct {
	Prompt        string `json:"prompt"`
	System        string `json:"system,omitempty"`
	Model         string `json:"model,omitempty"`
	MaxIterations int    `json:"max_iterations,omitempty"`
	TaskID        string `json:"task_id,omitempty"`
}

// AgentLoopResult represents the final result of the agent loop.
type AgentLoopResult struct {
	Response       string                     `json:"response"`
	ToolCallsMade  int                        `json:"tool_calls_made"`
	Iterations     int                        `json:"iterations"`
	ExecutionTrace []executor.ExecutionResult `json:"execution_trace,omitempty"`
}
