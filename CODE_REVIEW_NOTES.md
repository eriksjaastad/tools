# Code Review Notes

> Observations captured during active development. Review when work completes.

---

## 2026-01-19: ollama-mcp-go/internal/agent/loop.go

**Change:** Added draft path mangling at MCP layer

**File:** `ollama-mcp-go/internal/agent/loop.go`

**What it does:**
When `TaskID` is present and a draft tool is called (`draft_write`, `draft_patch`, `draft_read`), redirects writes to `_handoff/drafts/{filename}.{task_id}.draft`.

```go
draftPath := filepath.Join("agent-hub", "_handoff", "drafts", fmt.Sprintf("%s.%s.draft", filename, input.TaskID))
```

### Positives

1. Enforces sandbox at MCP layer - defense in depth
2. Task ID in filename provides audit trail
3. Workers can't accidentally write outside drafts directory

### Concerns

1. **Hardcoded path:** `"agent-hub", "_handoff", "drafts"` is baked into the Go binary. Should come from config or environment variable. What if ollama-mcp-go is used from a different working directory?

2. **Read path mismatch:** `draft_read` is in the condition list but redirection only applies to write/patch (inner if block). If a worker tries to read their own draft after writing, will the path resolve correctly?

3. **Naming convention mismatch:** The `{filename}.{task_id}.draft` pattern may not align with `agent-hub/src/sandbox.py` expectations. The Draft Gate needs to find and validate these files - check if `Sandbox.get_draft_path()` produces compatible paths.

4. **filepath.Base() strips directory:** If the original path was `src/module/file.py`, the draft becomes just `file.py.{task_id}.draft`. Directory structure is lost - could cause collisions if two files have the same name in different directories.

### Follow-up Actions

- [ ] Check `agent-hub/src/sandbox.py` for expected draft naming
- [ ] Check `agent-hub/src/draft_gate.py` for how it locates drafts
- [ ] Verify read path works after write redirect
- [ ] Consider making base path configurable

### Context

Change was made by Floor Manager/Workers during Librarian Adaptive Memory implementation. They hit a problem and solved it by adding sandbox enforcement at the MCP layer.

---

*Add new review notes below this line*
