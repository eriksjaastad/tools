package parser

import (
	"testing"
)

func TestParseQwenFormat(t *testing.T) {
	p := NewParser()
	
	// Test case 1: Qwen format without "assistant"
	text1 := `<|im_start|>{"name": "draft_read", "arguments": {"path": "analyze-youtube-videos/CODE_REVIEW_CLAUDE_OPUS_v3.md"}}`
	results1 := p.ParseToolCalls(text1)
	
	if len(results1) == 0 {
		t.Errorf("Expected to parse Qwen format, got 0 results")
	} else {
		if results1[0].Name != "draft_read" {
			t.Errorf("Expected name 'draft_read', got '%s'", results1[0].Name)
		}
	}
	
	// Test case 2: Qwen format with "assistant"
	text2 := "<|im_start|>assistant\n{\"name\": \"draft_write\", \"arguments\": {\"path\": \"test.txt\", \"content\": \"hello\"}}"
	results2 := p.ParseToolCalls(text2)
	
	if len(results2) == 0 {
		t.Errorf("Expected to parse Qwen format with assistant, got 0 results")
	} else {
		if results2[0].Name != "draft_write" {
			t.Errorf("Expected name 'draft_write', got '%s'", results2[0].Name)
		}
	}
	
	// Test case 3: Standard XML format (should still work)
	text3 := `<tool_call>{"name": "draft_list", "arguments": {"path": "."}}</tool_call>`
	results3 := p.ParseToolCalls(text3)
	
	if len(results3) == 0 {
		t.Errorf("Expected to parse XML format, got 0 results")
	} else {
		if results3[0].Name != "draft_list" {
			t.Errorf("Expected name 'draft_list', got '%s'", results3[0].Name)
		}
	}
}

