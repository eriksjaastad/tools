package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"path/filepath"
	"strings"

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
			Tools:    draftToolDefinitions(),
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
			// Check if this is a code task that should have produced writes.
			// If we haven't made any draft_write/draft_patch calls yet and this
			// isn't the final iteration, nudge the model to actually use tools.
			if i < input.MaxIterations-1 && !hasWriteCalls(result.ExecutionTrace) {
				logger.Info("No tool calls and no writes yet — nudging model to use tools", "iteration", i+1)
				messages = append(messages, ollama.Message{
					Role:    "user",
					Content: "You provided only a text summary. You MUST call draft_write or draft_patch to make the actual code changes. Text descriptions are not acceptable. Try again — make the edits now.",
				})
				continue
			}
			result.Response = content
			return result, nil
		}

		result.ToolCallsMade += len(toolCalls)
		logger.Info("Tool calls detected", "count", len(toolCalls))

		// 3. Execute tool calls
		// Mangle draft tools if TaskID is present
		if input.TaskID != "" {
			for idx := range toolCalls {
				tc := &toolCalls[idx]
				if tc.Name == "draft_write" || tc.Name == "draft_patch" || tc.Name == "draft_read" {
					var raw map[string]interface{}
					if err := json.Unmarshal(tc.Arguments, &raw); err == nil {
						if path, ok := raw["path"].(string); ok {
							if tc.Name == "draft_read" {
								// Resolve relative paths against ProjectRoot so workers
								// can read files from the target project, not just agent-hub.
								if input.ProjectRoot != "" && !filepath.IsAbs(path) {
									resolved := filepath.Join(input.ProjectRoot, path)
									raw["path"] = resolved
									logger.Info("Resolving draft_read against project root", "original", path, "resolved", resolved)
								}
							} else if tc.Name == "draft_write" || tc.Name == "draft_patch" {
								// Redirect writes to _handoff/drafts/ staging area.
								// Preserve relative path structure using __ separator
								// so drafts can be mapped back to the correct project location.
								safeName := strings.ReplaceAll(filepath.Clean(path), string(filepath.Separator), "__")
								draftPath := filepath.Join("agent-hub", "_handoff", "drafts", fmt.Sprintf("%s.%s.draft", safeName, input.TaskID))
								raw["path"] = draftPath
								logger.Info("Redirecting tool call to draft", "tool", tc.Name, "original", path, "redirect", draftPath)
							}

							newArgs, _ := json.Marshal(raw)
							tc.Arguments = newArgs
						}
					}
				}
			}
		}

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

// hasWriteCalls checks if any draft_write or draft_patch calls have been made.
func hasWriteCalls(trace []executor.ExecutionResult) bool {
	for _, r := range trace {
		if r.ToolName == "draft_write" || r.ToolName == "draft_patch" {
			return true
		}
	}
	return false
}

// draftToolDefinitions returns Ollama-native tool definitions for the draft tools.
func draftToolDefinitions() json.RawMessage {
	tools := `[
  {
    "type": "function",
    "function": {
      "name": "draft_read",
      "description": "Read the contents of a file at the given path.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Relative path to the file to read."
          }
        },
        "required": ["path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "draft_write",
      "description": "Write content to a file at the given path. Creates or overwrites the file.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Relative path to the file to write."
          },
          "content": {
            "type": "string",
            "description": "The full content to write to the file."
          }
        },
        "required": ["path", "content"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "draft_patch",
      "description": "Apply line-based patches to a file. Each patch replaces lines from start_line to end_line with new content.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Relative path to the file to patch."
          },
          "patches": {
            "type": "array",
            "description": "Array of patches to apply.",
            "items": {
              "type": "object",
              "properties": {
                "start_line": {
                  "type": "integer",
                  "description": "1-indexed start line to replace."
                },
                "end_line": {
                  "type": "integer",
                  "description": "1-indexed end line to replace (inclusive)."
                },
                "content": {
                  "type": "string",
                  "description": "Replacement content for the specified line range."
                }
              },
              "required": ["start_line", "end_line", "content"]
            }
          }
        },
        "required": ["path", "patches"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "draft_list",
      "description": "List files and directories at the given path.",
      "parameters": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "description": "Relative path to the directory to list."
          }
        },
        "required": ["path"]
      }
    }
  }
]`
	return json.RawMessage(tools)
}
