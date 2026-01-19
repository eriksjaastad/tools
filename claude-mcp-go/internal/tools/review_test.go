package tools

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestReviewTools(t *testing.T) {
	tempDir := t.TempDir()
	ctx := context.Background()

	// Prepare mock files
	originalPath := filepath.Join(tempDir, "original.ts")
	draftPath := filepath.Join(tempDir, "draft.ts")
	submissionPath := filepath.Join(tempDir, "submission.json")

	os.WriteFile(originalPath, []byte("original content"), 0644)
	os.WriteFile(draftPath, []byte("draft content"), 0644)

	submission := map[string]interface{}{
		"task_id":        "TASK-123",
		"original_path":  originalPath,
		"draft_path":     draftPath,
		"change_summary": "Fixed a bug",
	}
	subData, _ := json.Marshal(submission)
	os.WriteFile(submissionPath, subData, 0644)

	t.Run("request_draft_review returns structured prompt", func(t *testing.T) {
		res, err := HandleRequestDraftReview(ctx, submissionPath)
		if err != nil {
			t.Fatalf("HandleRequestDraftReview failed: %v", err)
		}
		if res.IsError {
			t.Fatalf("HandleRequestDraftReview returned expected error: %v", res.Content[0])
		}

		data := res.StructuredContent.(map[string]interface{})
		prompt := data["prompt"].(string)
		if !strings.Contains(prompt, "TASK-123") || !strings.Contains(prompt, "Fixed a bug") {
			t.Errorf("Prompt does not contain expected metadata")
		}
		if data["original_content"] != "original content" || data["draft_content"] != "draft content" {
			t.Errorf("Content mismatch in response")
		}
	})

	t.Run("submit_review_verdict creates report files", func(t *testing.T) {
		res, err := HandleSubmitReviewVerdict(ctx, submissionPath, "ACCEPT", "Looks good", "test-reviewer")
		if err != nil {
			t.Fatalf("HandleSubmitReviewVerdict failed: %v", err)
		}
		if res.IsError {
			t.Fatalf("HandleSubmitReviewVerdict returned error: %v", res.Content[0])
		}

		data := res.StructuredContent.(map[string]interface{})
		reportJsonPath := data["report_json_path"].(string)
		reportMdPath := data["report_md_path"].(string)

		if _, err := os.Stat(reportJsonPath); os.IsNotExist(err) {
			t.Errorf("Report JSON not created: %s", reportJsonPath)
		}
		if _, err := os.Stat(reportMdPath); os.IsNotExist(err) {
			t.Errorf("Report MD not created: %s", reportMdPath)
		}

		// Verify JSON content
		jsonBytes, _ := os.ReadFile(reportJsonPath)
		var report map[string]interface{}
		json.Unmarshal(jsonBytes, &report)
		if report["verdict"] != "ACCEPT" || report["reviewer"] != "test-reviewer" {
			t.Errorf("Report content mismatch: %v", report)
		}
	})

	t.Run("error handling for missing submission file", func(t *testing.T) {
		res, err := HandleRequestDraftReview(ctx, "non-existent.json")
		if err != nil {
			t.Fatalf("Unexpected Go error: %v", err)
		}
		if !res.IsError {
			t.Errorf("Expected result error for missing file, got success")
		}
	})
}
