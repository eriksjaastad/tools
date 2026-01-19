package tools

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/eriksjaastad/claude-mcp-go/internal/prompts"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func SafePath(base, requested string) (string, error) {
	if filepath.IsAbs(requested) {
		return "", fmt.Errorf("path traversal attempt: %s", requested)
	}
	fullPath := filepath.Join(base, requested)
	baseAbs, _ := filepath.Abs(base)
	fullAbs, _ := filepath.Abs(fullPath)

	rel, err := filepath.Rel(baseAbs, fullAbs)
	if err != nil {
		return "", err
	}

	if strings.HasPrefix(rel, "..") || filepath.IsAbs(rel) {
		return "", fmt.Errorf("path traversal attempt: %s", requested)
	}

	return fullAbs, nil
}

func RegisterClaudeTools(s *server.MCPServer) {
	// claude_health
	s.AddTool(mcp.NewTool("claude_health",
		mcp.WithDescription("Check if Claude CLI is available"),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		tctx, cancel := context.WithTimeout(ctx, 30*time.Second)
		defer cancel()

		cmd := exec.CommandContext(tctx, "claude", "--version")
		var stdout, stderr bytes.Buffer
		cmd.Stdout = &stdout
		cmd.Stderr = &stderr

		err := cmd.Run()
		if err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"available": false,
				"error":     fmt.Sprintf("Claude CLI not found or error: %v, stderr: %s", err, stderr.String()),
			}), nil
		}

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"available": true,
			"version":   strings.TrimSpace(stdout.String()),
		}), nil
	})

	// claude_judge_review
	s.AddTool(mcp.NewTool("claude_judge_review",
		mcp.WithDescription("Code review with structured verdict"),
		mcp.WithString("contract_path", mcp.Required(), mcp.Description("Path to the task contract JSON")),
		mcp.WithString("report_dir", mcp.Description("Directory to save reports (default: _handoff)")),
		mcp.WithNumber("timeout_seconds", mcp.Description("Timeout in seconds (default: 900)")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		startTime := time.Now()
		args, _ := request.Params.Arguments.(map[string]interface{})
		contractPath, _ := args["contract_path"].(string)
		reportDir, ok := args["report_dir"].(string)
		if !ok || reportDir == "" {
			reportDir = "_handoff"
		}
		timeoutSeconds, ok := args["timeout_seconds"].(float64)
		if !ok {
			timeoutSeconds = 900
		}

		if _, err := os.Stat(contractPath); os.IsNotExist(err) {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Contract not found: %s", contractPath),
				"duration_ms": time.Since(startTime).Milliseconds(),
				"timed_out":   false,
			}), nil
		}

		contractData, err := os.ReadFile(contractPath)
		if err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Failed to read contract: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
				"timed_out":   false,
			}), nil
		}

		prompt := strings.ReplaceAll(prompts.GetJudgeTemplate(), "{{CONTRACT_JSON}}", string(contractData))
		prompt = strings.ReplaceAll(prompt, "{{REPORT_DIR}}", reportDir)

		tctx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSeconds)*time.Second)
		defer cancel()

		cmd := exec.CommandContext(tctx, "claude", "--dangerously-skip-permissions")
		cmd.Stdin = strings.NewReader(prompt)
		var stderr bytes.Buffer
		cmd.Stderr = &stderr

		err = cmd.Run()
		timedOut := tctx.Err() == context.DeadlineExceeded

		if err != nil {
			if timedOut {
				return mcp.NewToolResultStructuredOnly(map[string]interface{}{
					"success":     false,
					"error":       "Claude timed out",
					"duration_ms": time.Since(startTime).Milliseconds(),
					"timed_out":   true,
				}), nil
			}
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Claude execution error: %v, stderr: %s", err, stderr.String()),
				"duration_ms": time.Since(startTime).Milliseconds(),
				"timed_out":   false,
			}), nil
		}

		reportJsonPath := filepath.Join(reportDir, "JUDGE_REPORT.json")
		reportMdPath := filepath.Join(reportDir, "JUDGE_REPORT.md")

		result := map[string]interface{}{
			"success":          true,
			"report_md_path":   reportMdPath,
			"report_json_path": reportJsonPath,
			"duration_ms":      time.Since(startTime).Milliseconds(),
			"timed_out":        false,
		}

		if data, err := os.ReadFile(reportJsonPath); err == nil {
			var report map[string]interface{}
			if err := json.Unmarshal(data, &report); err == nil {
				result["verdict"] = report["verdict"]
				if issues, ok := report["blocking_issues"].([]interface{}); ok {
					result["blocking_issues_count"] = len(issues)
				}
			}
		}

		return mcp.NewToolResultStructuredOnly(result), nil
	})

	// claude_resolve_conflict
	s.AddTool(mcp.NewTool("claude_resolve_conflict",
		mcp.WithDescription("Resolve disputes between Floor Manager and Judge"),
		mcp.WithString("contract_path", mcp.Required(), mcp.Description("Path to contract")),
		mcp.WithString("rebuttal_path", mcp.Required(), mcp.Description("Path to rebuttal")),
		mcp.WithString("judge_report_path", mcp.Required(), mcp.Description("Path to judge report")),
		mcp.WithNumber("timeout_seconds", mcp.Description("Timeout in seconds (default: 300)")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		startTime := time.Now()
		args, _ := request.Params.Arguments.(map[string]interface{})
		paths := []string{"contract_path", "rebuttal_path", "judge_report_path"}
		contents := make(map[string]string)

		for _, p := range paths {
			path, _ := args[p].(string)
			data, err := os.ReadFile(path)
			if err != nil {
				return mcp.NewToolResultStructuredOnly(map[string]interface{}{
					"success":     false,
					"error":       fmt.Sprintf("%s not found or unreadable: %s", p, path),
					"duration_ms": time.Since(startTime).Milliseconds(),
				}), nil
			}
			contents[p] = string(data)
		}

		timeoutSeconds, ok := args["timeout_seconds"].(float64)
		if !ok {
			timeoutSeconds = 300
		}

		prompt := strings.ReplaceAll(prompts.RESOLVE_CONFLICT_TEMPLATE, "{{CONTRACT_JSON}}", contents["contract_path"])
		prompt = strings.ReplaceAll(prompt, "{{JUDGE_REPORT}}", contents["judge_report_path"])
		prompt = strings.ReplaceAll(prompt, "{{REBUTTAL}}", contents["rebuttal_path"])

		tctx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSeconds)*time.Second)
		defer cancel()

		cmd := exec.CommandContext(tctx, "claude", "--dangerously-skip-permissions", "--print")
		cmd.Stdin = strings.NewReader(prompt)
		var stdout bytes.Buffer
		cmd.Stdout = &stdout

		if err := cmd.Run(); err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Claude error: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		re := regexp.MustCompile(`\{[\s\S]*\}`)
		match := re.FindString(stdout.String())
		if match == "" {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       "Could not parse resolution response",
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		var res map[string]interface{}
		if err := json.Unmarshal([]byte(match), &res); err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("JSON parse error: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"success":        true,
			"side":           res["side"],
			"reasoning":      res["reasoning"],
			"recommendation": res["recommendation"],
			"duration_ms":    time.Since(startTime).Milliseconds(),
		}), nil
	})

	// claude_security_audit
	s.AddTool(mcp.NewTool("claude_security_audit",
		mcp.WithDescription("Deep security review of specific files"),
		mcp.WithArray("files", mcp.Required(), mcp.Description("List of files to review")),
		mcp.WithString("working_directory", mcp.Description("Base directory for files")),
		mcp.WithNumber("timeout_seconds", mcp.Description("Timeout in seconds (default: 300)")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		startTime := time.Now()
		args, _ := request.Params.Arguments.(map[string]interface{})
		filesRaw, _ := args["files"].([]interface{})
		workingDir, ok := args["working_directory"].(string)
		if !ok || workingDir == "" {
			workingDir, _ = os.Getwd()
		}
		timeoutSeconds, ok := args["timeout_seconds"].(float64)
		if !ok {
			timeoutSeconds = 300
		}

		var filesContent strings.Builder
		totalChars := 0
		maxTotalChars := 400000

		for _, f := range filesRaw {
			file := f.(string)
			fullPath, err := SafePath(workingDir, file)
			if err != nil {
				filesContent.WriteString(fmt.Sprintf("\n### %s\n(BLOCKED: %v)\n", file, err))
				continue
			}

			if _, err := os.Stat(fullPath); os.IsNotExist(err) {
				filesContent.WriteString(fmt.Sprintf("\n### %s\n(File not found)\n", file))
				continue
			}

			content, err := os.ReadFile(fullPath)
			if err != nil {
				filesContent.WriteString(fmt.Sprintf("\n### %s\n(Error reading file: %v)\n", file, err))
				continue
			}

			if totalChars+len(content) > maxTotalChars {
				filesContent.WriteString(fmt.Sprintf("\n### %s\n(SKIPPED: Context limit reached)\n", file))
				continue
			}

			totalChars += len(content)
			filesContent.WriteString(fmt.Sprintf("\n### %s\n```\n%s\n```\n", file, string(content)))
		}

		prompt := strings.ReplaceAll(prompts.SECURITY_PROMPT_TEMPLATE, "{{FILES_CONTENT}}", filesContent.String())

		tctx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSeconds)*time.Second)
		defer cancel()

		cmd := exec.CommandContext(tctx, "claude", "--dangerously-skip-permissions", "--print")
		cmd.Stdin = strings.NewReader(prompt)
		var stdout bytes.Buffer
		cmd.Stdout = &stdout

		if err := cmd.Run(); err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Claude error: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		re := regexp.MustCompile(`\{[\s\S]*\}`)
		match := re.FindString(stdout.String())
		if match == "" {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       "Could not parse audit response",
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		var res map[string]interface{}
		if err := json.Unmarshal([]byte(match), &res); err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("JSON parse error: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"success":     true,
			"findings":    res["findings"],
			"duration_ms": time.Since(startTime).Milliseconds(),
		}), nil
	})

	// claude_validate_proposal
	s.AddTool(mcp.NewTool("claude_validate_proposal",
		mcp.WithDescription("Check if a proposal is complete and actionable"),
		mcp.WithString("proposal_path", mcp.Required(), mcp.Description("Path to proposal markdown")),
		mcp.WithNumber("timeout_seconds", mcp.Description("Timeout in seconds (default: 120)")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		startTime := time.Now()
		args, _ := request.Params.Arguments.(map[string]interface{})
		proposalPath, _ := args["proposal_path"].(string)
		timeoutSeconds, ok := args["timeout_seconds"].(float64)
		if !ok {
			timeoutSeconds = 120
		}

		data, err := os.ReadFile(proposalPath)
		if err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Proposal not found: %s", proposalPath),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		prompt := strings.ReplaceAll(prompts.VALIDATE_PROMPT_TEMPLATE, "{{PROPOSAL_CONTENT}}", string(data))

		tctx, cancel := context.WithTimeout(ctx, time.Duration(timeoutSeconds)*time.Second)
		defer cancel()

		cmd := exec.CommandContext(tctx, "claude", "--dangerously-skip-permissions", "--print")
		cmd.Stdin = strings.NewReader(prompt)
		var stdout bytes.Buffer
		cmd.Stdout = &stdout

		if err := cmd.Run(); err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("Claude error: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		re := regexp.MustCompile(`\{[\s\S]*\}`)
		match := re.FindString(stdout.String())
		if match == "" {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       "Could not parse validation response",
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		var res map[string]interface{}
		if err := json.Unmarshal([]byte(match), &res); err != nil {
			return mcp.NewToolResultStructuredOnly(map[string]interface{}{
				"success":     false,
				"error":       fmt.Sprintf("JSON parse error: %v", err),
				"duration_ms": time.Since(startTime).Milliseconds(),
			}), nil
		}

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"success":     true,
			"valid":       res["valid"],
			"issues":      res["issues"],
			"duration_ms": time.Since(startTime).Milliseconds(),
		}), nil
	})
}
