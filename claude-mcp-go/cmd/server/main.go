package main

import (
	"context"
	"fmt"
	"os"

	"github.com/eriksjaastad/claude-mcp-go/internal/prompts"
	"github.com/eriksjaastad/claude-mcp-go/internal/tools"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func main() {
	// Create a new MCP server
	s := server.NewMCPServer(
		"claude-mcp-go",
		"1.0.0",
		server.WithLogging(),
	)

	// Register tools
	tools.RegisterHubTools(s)
	tools.RegisterClaudeTools(s)
	tools.RegisterReviewTools(s)

	// Register prompts
	registerPrompts(s)

	// Start the server using stdio transport
	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
		os.Exit(1)
	}
}

func registerPrompts(s *server.MCPServer) {
	// draft_review prompt
	s.AddPrompt(mcp.NewPrompt("draft_review",
		mcp.WithPromptDescription("Request Claude to review a sandboxed draft"),
	), func(ctx context.Context, request mcp.GetPromptRequest) (*mcp.GetPromptResult, error) {
		return &mcp.GetPromptResult{
			Description: "Request Claude to review a sandboxed draft",
			Messages: []mcp.PromptMessage{
				mcp.NewPromptMessage(mcp.RoleUser, mcp.NewTextContent(prompts.GetDraftReviewTemplate())),
			},
		}, nil
	})

	// judge prompt
	s.AddPrompt(mcp.NewPrompt("judge",
		mcp.WithPromptDescription("Perform architectural review of completed work"),
	), func(ctx context.Context, request mcp.GetPromptRequest) (*mcp.GetPromptResult, error) {
		return &mcp.GetPromptResult{
			Description: "Perform architectural review of completed work",
			Messages: []mcp.PromptMessage{
				mcp.NewPromptMessage(mcp.RoleUser, mcp.NewTextContent(prompts.GetJudgeTemplate())),
			},
		}, nil
	})
}
