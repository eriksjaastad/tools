package tools

// Patch represents a single line-based replacement.
type Patch struct {
	StartLine int    `json:"start_line"`
	EndLine   int    `json:"end_line"`
	Content   string `json:"content"`
}

// DraftReadInput represents the input for draft_read.
type DraftReadInput struct {
	Path string `json:"path"`
}

// DraftWriteInput represents the input for draft_write.
type DraftWriteInput struct {
	Path    string `json:"path"`
	Content string `json:"content"`
}

// DraftPatchInput represents the input for draft_patch.
type DraftPatchInput struct {
	Path    string  `json:"path"`
	Patches []Patch `json:"patches"`
}

// DraftListInput represents the input for draft_list.
type DraftListInput struct {
	Path string `json:"path"`
}
