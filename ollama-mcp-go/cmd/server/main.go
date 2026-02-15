package main

import (
	"encoding/json"
	"os"
	"os/signal"
	"syscall"

	"github.com/eriksjaastad/ollama-mcp-go/internal/agent"
	"github.com/eriksjaastad/ollama-mcp-go/internal/executor"
	"github.com/eriksjaastad/ollama-mcp-go/internal/logger"
	"github.com/eriksjaastad/ollama-mcp-go/internal/mcp"
	"github.com/eriksjaastad/ollama-mcp-go/internal/ollama"
	"github.com/eriksjaastad/ollama-mcp-go/internal/parser"
	"github.com/eriksjaastad/ollama-mcp-go/internal/sandbox"
	"github.com/eriksjaastad/ollama-mcp-go/internal/tools"
)

func main() {
	// 1. Config
	logLevel := os.Getenv("LOG_LEVEL")
	if logLevel != "" {
		logger.SetLevel(logLevel)
	}

	ollamaHost := os.Getenv("OLLAMA_HOST")
	if ollamaHost == "" {
		ollamaHost = "http://localhost:11434"
	}

	sandboxRoot := os.Getenv("SANDBOX_ROOT")
	if sandboxRoot == "" {
		// For development, use current dir if not set, but production should require it
		sandboxRoot = "."
		logger.Warn("SANDBOX_ROOT not set, defaulting to current directory")
	}

	logger.Info("Starting ollama-mcp-go server", "ollama_host", ollamaHost, "sandbox_root", sandboxRoot)

	// 2. Initialize Components
	sb, err := sandbox.NewSandbox(sandboxRoot)
	if err != nil {
		logger.Error("Failed to initialize sandbox", err)
		os.Exit(1)
	}

	ollamaClient := ollama.NewClient(ollamaHost)
	toolParser := parser.NewParser()
	toolExecutor := executor.NewExecutor()

	// 3. Initialize Handlers
	draftHandler := tools.NewDraftHandler(sb)
	runHandler := tools.NewRunHandler(ollamaClient)
	agentLoop := agent.NewAgentLoop(ollamaClient, toolExecutor, toolParser)

	// 4. Register Tools in Executor
	toolExecutor.Register("ollama_run", runHandler.Run)
	toolExecutor.Register("ollama_run_many", runHandler.RunMany)
	toolExecutor.Register("ollama_list_models", runHandler.ListModels)
	toolExecutor.Register("draft_read", draftHandler.Read)
	toolExecutor.Register("draft_write", draftHandler.Write)
	toolExecutor.Register("draft_patch", draftHandler.Patch)
	toolExecutor.Register("draft_list", draftHandler.List)
	toolExecutor.Register("agent_loop", agentLoop.Handler)

	// 5. Initialize MCP Handler
	mcpHandler := mcp.NewHandler()

	// Register tools in MCP
	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "ollama_run",
		Description: "Run a single Ollama model with a prompt",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"model": {"type": "string", "description": "Model name"},
				"prompt": {"type": "string", "description": "Prompt text"},
				"system": {"type": "string", "description": "System prompt"},
				"options": {"type": "object", "description": "Optional parameters"}
			},
			"required": ["model", "prompt"]
		}`),
		Handler: runHandler.Run,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "ollama_run_many",
		Description: "Run multiple Ollama models concurrently",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"requests": {
					"type": "array",
					"items": {
						"type": "object",
						"properties": {
							"model": {"type": "string"},
							"prompt": {"type": "string"},
							"system": {"type": "string"},
							"options": {"type": "object"}
						},
						"required": ["model", "prompt"]
					}
				},
				"maxConcurrency": {"type": "number", "default": 4}
			},
			"required": ["requests"]
		}`),
		Handler: runHandler.RunMany,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "ollama_list_models",
		Description: "List all locally available Ollama models",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {},
			"required": []
		}`),
		Handler: runHandler.ListModels,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "draft_read",
		Description: "Read a file from the sandbox",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"path": {"type": "string", "description": "Path to the file"}
			},
			"required": ["path"]
		}`),
		Handler: draftHandler.Read,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "draft_write",
		Description: "Write content to a file in the sandbox",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"path": {"type": "string", "description": "Path to the file"},
				"content": {"type": "string", "description": "Content to write"}
			},
			"required": ["path", "content"]
		}`),
		Handler: draftHandler.Write,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "draft_patch",
		Description: "Apply line-based patches to a file in the sandbox",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"path": {"type": "string"},
				"patches": {
					"type": "array",
					"items": {
						"type": "object",
						"properties": {
							"start_line": {"type": "number"},
							"end_line": {"type": "number"},
							"content": {"type": "string"}
						},
						"required": ["start_line", "content"]
					}
				}
			},
			"required": ["path", "patches"]
		}`),
		Handler: draftHandler.Patch,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "draft_list",
		Description: "List files in a sandbox directory",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"path": {"type": "string"}
			},
			"required": ["path"]
		}`),
		Handler: draftHandler.List,
	})

	mcpHandler.RegisterTool(mcp.Tool{
		Name:        "agent_loop",
		Description: "Run an iterative agent loop with tool-calling capabilities",
		InputSchema: json.RawMessage(`{
			"type": "object",
			"properties": {
				"prompt": {"type": "string"},
				"system": {"type": "string"},
				"model": {"type": "string"},
				"max_iterations": {"type": "number", "default": 10},
				"task_id": {"type": "string", "description": "Task identifier for draft redirection"},
				"project_root": {"type": "string", "description": "Absolute path to the target project directory. When set, draft_read resolves relative paths against this root."}
			},
			"required": ["prompt", "model"]
		}`),
		Handler: agentLoop.Handler,
	})

	// 6. Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		logger.Info("Shutting down")
		os.Exit(0)
	}()

	// 7. Serve
	if err := mcpHandler.Serve(os.Stdin, os.Stdout); err != nil {
		logger.Error("Server error", err)
		os.Exit(1)
	}
}
