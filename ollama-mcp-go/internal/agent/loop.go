package agent

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/eriksjaastad/ollama-mcp-go/internal/executor"
	"github.com/eriksjaastad/ollama-mcp-go/internal/logger"
	"github.com/eriksjaastad/ollama-mcp-go/internal/ollama"
	"github.com/eriksjaastad/ollama-mcp-go/internal/parser"
)

// AgentLoop orchestrates the tool-calling loop.
type AgentLoop struct {
	client   *ollama.Client
	executor *executor.Executor
	parser   *parser.Parser
}

// NewAgentLoop creates a new AgentLoop.
func NewAgentLoop(client *ollama.Client, exec *executor.Executor, p *parser.Parser) *AgentLoop {
	return &AgentLoop{
		client:   client,
		executor: exec,
		parser:   p,
	}
}

// Run executes the agent loop.
func (a *AgentLoop) Run(ctx context.Context, input AgentLoopInput) (AgentLoopResult, error) {
	if input.MaxIterations <= 0 {
		input.MaxIterations = 10
	}

	messages := []ollama.Message{
		{Role: "system", Content: input.System},
		{Role: "user", Content: input.Prompt},
	}

	result := AgentLoopResult{}

	for i := 0; i < input.MaxIterations; i++ {
		result.Iterations = i + 1
		logger.Info("Agent iteration", "iteration", i+1, "model", input.Model)

		// 1. Call LLM
		chatReq := ollama.ChatRequest{
			Model:    input.Model,
			Messages: messages,
		}

		chatResp, err := a.client.Chat(ctx, chatReq)
		if err != nil {
			return result, fmt.Errorf("llm call failed: %w", err)
		}

		content := chatResp.Message.Content
		messages = append(messages, chatResp.Message)

		// 2. Parse tool calls
		toolCalls := a.parser.ParseToolCalls(content)
		if len(toolCalls) == 0 {
			result.Response = content
			return result, nil
		}

		result.ToolCallsMade += len(toolCalls)
		logger.Info("Tool calls detected", "count", len(toolCalls))

		// 3. Execute tool calls
		execResults := a.executor.ExecuteMany(toolCalls)
		result.ExecutionTrace = append(result.ExecutionTrace, execResults...)

		// 4. Format results for next iteration
		for j, res := range execResults {
			resData, _ := json.Marshal(res.Result)
			if res.Error != "" {
				resData = []byte(fmt.Sprintf(`{"error": "%s"}`, res.Error))
			}

			messages = append(messages, ollama.Message{
				Role:    "tool",
				Content: string(resData),
				// Ollama expects tool_call_id or similar in some cases,
				// but for basic message history, content is often enough if tagged.
			})
			_ = j // avoid unused
		}
	}

	result.Response = "Max iterations reached"
	return result, nil
}

// Handler returns a mcp.ToolHandler for the agent_loop tool.
func (a *AgentLoop) Handler(params json.RawMessage) (any, error) {
	var input AgentLoopInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	return a.Run(context.Background(), input)
}
