package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/eriksjaastad/claude-mcp-go/internal/prompts"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func RegisterReviewTools(s *server.MCPServer) {
	// request_draft_review
	s.AddTool(mcp.NewTool("request_draft_review",
		mcp.WithDescription("Prepare a review request for Claude"),
		mcp.WithString("submission_path", mcp.Required(), mcp.Description("Path to submission JSON")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		submissionPath, _ := args["submission_path"].(string)
		return HandleRequestDraftReview(ctx, submissionPath)
	})

	// submit_review_verdict
	s.AddTool(mcp.NewTool("submit_review_verdict",
		mcp.WithDescription("Record Claude's verdict"),
		mcp.WithString("submission_path", mcp.Required(), mcp.Description("Path to submission JSON")),
		mcp.WithString("verdict", mcp.Required(), mcp.Description("ACCEPT or REJECT")),
		mcp.WithString("reason", mcp.Required(), mcp.Description("Reason for the verdict")),
		mcp.WithString("reviewer", mcp.Description("Name of the reviewer (default: claude)")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		submissionPath, _ := args["submission_path"].(string)
		verdict, _ := args["verdict"].(string)
		reason, _ := args["reason"].(string)
		reviewer, _ := args["reviewer"].(string)
		if reviewer == "" {
			reviewer = "claude"
		}
		return HandleSubmitReviewVerdict(ctx, submissionPath, verdict, reason, reviewer)
	})
}

func HandleRequestDraftReview(ctx context.Context, submissionPath string) (*mcp.CallToolResult, error) {
	data, err := os.ReadFile(submissionPath)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("submission not found: %s", submissionPath)), nil
	}

	var submission map[string]interface{}
	if err := json.Unmarshal(data, &submission); err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("failed to parse submission: %v", err)), nil
	}

	draftPath, _ := submission["draft_path"].(string)
	originalPath, _ := submission["original_path"].(string)

	draftContent, err := os.ReadFile(draftPath)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("draft file not found: %s", draftPath)), nil
	}

	originalContent, err := os.ReadFile(originalPath)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("original file not found: %s", originalPath)), nil
	}

	submissionJson, _ := json.MarshalIndent(submission, "", "  ")
	changeSummary, _ := submission["change_summary"].(string)
	if changeSummary == "" {
		changeSummary = "No summary provided"
	}

	prompt := prompts.GetDraftReviewTemplate()
	prompt = strings.ReplaceAll(prompt, "{{SUBMISSION_JSON}}", string(submissionJson))
	prompt = strings.ReplaceAll(prompt, "{{ORIGINAL_PATH}}", originalPath)
	prompt = strings.ReplaceAll(prompt, "{{DRAFT_PATH}}", draftPath)
	prompt = strings.ReplaceAll(prompt, "{{CHANGE_SUMMARY}}", changeSummary)

	return mcp.NewToolResultStructuredOnly(map[string]interface{}{
		"prompt":              prompt,
		"original_content":    string(originalContent),
		"draft_content":       string(draftContent),
		"submission_metadata": submission,
	}), nil
}

func HandleSubmitReviewVerdict(ctx context.Context, submissionPath, verdict, reason, reviewer string) (*mcp.CallToolResult, error) {
	data, err := os.ReadFile(submissionPath)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("submission not found: %s", submissionPath)), nil
	}

	var submission map[string]interface{}
	if err := json.Unmarshal(data, &submission); err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("failed to parse submission: %v", err)), nil
	}

	reportDir := filepath.Dir(submissionPath)
	taskId, _ := submission["task_id"].(string)
	if taskId == "" {
		taskId = "unknown_task"
	}

	report := map[string]interface{}{
		"task_id":         taskId,
		"timestamp":       time.Now().UTC().Format(time.RFC3339),
		"verdict":         verdict,
		"reason":          reason,
		"reviewer":        reviewer,
		"submission_path": submissionPath,
	}

	reportJsonPath := filepath.Join(reportDir, fmt.Sprintf("JUDGE_REPORT_%s.json", taskId))
	reportMdPath := filepath.Join(reportDir, fmt.Sprintf("JUDGE_REPORT_%s.md", taskId))

	mdContent := fmt.Sprintf("# Judge Review Report: %s\n\n**Verdict:** %s\n**Reviewer:** %s\n**Timestamp:** %s\n\n## Reason\n\n%s\n",
		taskId, verdict, reviewer, report["timestamp"], reason)

	reportJsonData, _ := json.MarshalIndent(report, "", "  ")
	if err := os.WriteFile(reportJsonPath, reportJsonData, 0644); err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("failed to write report JSON: %v", err)), nil
	}
	if err := os.WriteFile(reportMdPath, []byte(mdContent), 0644); err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("failed to write report MD: %v", err)), nil
	}

	return mcp.NewToolResultStructuredOnly(map[string]interface{}{
		"success":          true,
		"report_json_path": reportJsonPath,
		"report_md_path":   reportMdPath,
	}), nil
}
