package tools

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"github.com/eriksjaastad/ollama-mcp-go/internal/sandbox"
)

// DraftHandler provides methods for draft operations.
type DraftHandler struct {
	sb *sandbox.Sandbox
}

// NewDraftHandler creates a new DraftHandler.
func NewDraftHandler(sb *sandbox.Sandbox) *DraftHandler {
	return &DraftHandler{sb: sb}
}

// Read handles the draft_read tool.
func (h *DraftHandler) Read(params json.RawMessage) (any, error) {
	var input DraftReadInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	content, err := h.sb.SafeRead(input.Path)
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"path":    input.Path,
		"content": string(content),
	}, nil
}

// Write handles the draft_write tool.
func (h *DraftHandler) Write(params json.RawMessage) (any, error) {
	var input DraftWriteInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	err := h.sb.SafeWrite(input.Path, []byte(input.Content))
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"path":          input.Path,
		"bytes_written": len(input.Content),
	}, nil
}

// Patch handles the draft_patch tool.
func (h *DraftHandler) Patch(params json.RawMessage) (any, error) {
	var input DraftPatchInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	content, err := h.sb.SafeRead(input.Path)
	if err != nil {
		return nil, err
	}

	lines := strings.Split(string(content), "\n")

	// Sort patches in reverse order (highest line first) to avoid shifting indices
	sort.Slice(input.Patches, func(i, j int) bool {
		return input.Patches[i].StartLine > input.Patches[j].StartLine
	})

	for _, p := range input.Patches {
		if p.StartLine < 1 || p.StartLine > len(lines)+1 {
			return nil, fmt.Errorf("invalid start_line: %d", p.StartLine)
		}

		endLine := p.EndLine
		if endLine < p.StartLine {
			endLine = p.StartLine
		}
		if endLine > len(lines) {
			endLine = len(lines)
		}

		// Patching logic (1-indexed)
		newLines := make([]string, 0)
		newLines = append(newLines, lines[:p.StartLine-1]...)
		newLines = append(newLines, strings.Split(p.Content, "\n")...)
		newLines = append(newLines, lines[endLine:]...)
		lines = newLines
	}

	newContent := strings.Join(lines, "\n")
	err = h.sb.SafeWrite(input.Path, []byte(newContent))
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"path":            input.Path,
		"patches_applied": len(input.Patches),
	}, nil
}

// List handles the draft_list tool.
func (h *DraftHandler) List(params json.RawMessage) (any, error) {
	var input DraftListInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	entries, err := h.sb.SafeList(input.Path)
	if err != nil {
		return nil, err
	}

	files := make([]map[string]any, 0, len(entries))
	for _, entry := range entries {
		info, _ := entry.Info()
		files = append(files, map[string]any{
			"name":   entry.Name(),
			"is_dir": entry.IsDir(),
			"size":   info.Size(),
		})
	}

	return map[string]any{
		"files": files,
	}, nil
}
