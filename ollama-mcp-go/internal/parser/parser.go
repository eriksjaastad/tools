package parser

import (
	"encoding/json"
	"regexp"
	"strings"
)

// ToolCall represents a parsed tool call from an LLM response.
type ToolCall struct {
	ID        string          `json:"id"`
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

// Parser handles parsing tool calls from LLM responses.
type Parser struct{}

// NewParser creates a new Parser.
func NewParser() *Parser {
	return &Parser{}
}

var (
	xmlToolCallRegex = regexp.MustCompile(`(?s)<tool_call>(.*?)</tool_call>`)
	jsonBlockRegex   = regexp.MustCompile("(?s)```(?:json)?\n?(.*?)\n?```")
	nakedJsonRegex   = regexp.MustCompile(`(?s)\{.*?"name".*?"arguments".*?\}`)
)

// ParseToolCalls extracts tool calls from the given text.
func (p *Parser) ParseToolCalls(text string) []ToolCall {
	var results []ToolCall

	// 1. Try XML-style: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
	xmlMatches := xmlToolCallRegex.FindAllStringSubmatch(text, -1)
	for _, match := range xmlMatches {
		if len(match) < 2 {
			continue
		}
		var tc ToolCall
		if err := json.Unmarshal([]byte(match[1]), &tc); err == nil {
			results = append(results, tc)
		}
	}

	if len(results) > 0 {
		return results
	}

	// 2. Try Markdown JSON blocks
	blockMatches := jsonBlockRegex.FindAllStringSubmatch(text, -1)
	for _, match := range blockMatches {
		if len(match) < 2 {
			continue
		}
		var tc ToolCall
		if err := json.Unmarshal([]byte(match[1]), &tc); err == nil {
			results = append(results, tc)
		}
	}

	if len(results) > 0 {
		return results
	}

	// 3. Try Naked JSON objects
	nakedMatches := nakedJsonRegex.FindAllString(text, -1)
	for _, match := range nakedMatches {
		var tc ToolCall
		if err := json.Unmarshal([]byte(match), &tc); err == nil && tc.Name != "" {
			results = append(results, tc)
		}
	}

	if len(results) > 0 {
		return results
	}

	// 4. Try JSON array: [{"name": "...", "arguments": {...}}]
	trimmed := strings.TrimSpace(text)
	if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
		var tcs []ToolCall
		if err := json.Unmarshal([]byte(trimmed), &tcs); err == nil {
			return tcs
		}
	}

	return results
}
