# Agentic Blueprint Setup V4: Sandbox Draft Pattern (SDP)

**Version:** 4.0 (Planning)
**Status:** Specification
**Last Updated:** 2026-01-17
**Changelog:** Adds controlled file writing capability to local models via sandboxed drafts.

---

## 0. The Evolution: From V3 to V4

| Component | V3 (Direct Agent Communication) | V4 (Sandbox Draft Pattern) |
|-----------|--------------------------------|---------------------------|
| **Local Model Capability** | Text generation only | Text generation + draft file writes |
| **File Operations** | Floor Manager parses text, writes files | Local model writes drafts, Floor Manager gates |
| **Parsing** | Regex extraction from text output | Direct file comparison (diff) |
| **Fragility** | High (output format dependent) | Low (file-to-file comparison) |
| **Worker Agency** | Passive (generates text) | Active (proposes changes) |

---

## 1. The Problem V4 Solves

### Current State (V3)
```
Local Model                     Floor Manager
    │                                │
    ├─── Generate text ─────────────►│
    │    "Here's the code..."        │
    │                                │
    │                    ┌───────────┤
    │                    │ Parse it  │◄── FRAGILE
    │                    │ Extract   │    (regex dependent)
    │                    │ Write it  │
    │                    └───────────┤
```

**Issues:**
- Parsing failures when output format varies (DeepSeek issue)
- Local models have no "hands" - can't iterate on files directly
- Floor Manager does heavy lifting that workers should do
- Workers feel like "chatbots that don't do real work"

### V4 State (Sandbox Draft Pattern)
```
Local Model                     Floor Manager
    │                                │
    ├─── Request draft ─────────────►│
    │    "I need to edit foo.py"     │
    │                                │
    │◄── Copy to sandbox ────────────┤
    │    _handoff/drafts/foo.py.draft│
    │                                │
    ├─── Edit the draft directly     │
    │    (using ollama_write_draft)  │
    │                                │
    ├─── "Draft ready" ─────────────►│
    │                                │
    │                    ┌───────────┤
    │                    │ Diff it   │◄── ROBUST
    │                    │ Validate  │    (file comparison)
    │                    │ Gate it   │
    │                    └───────────┤
    │                                │
    │◄── Accept/Reject ──────────────┤
```

---

## 2. New Ollama MCP Tools

### 2.1 `ollama_request_draft`

**Purpose:** Request a copy of a file to edit in the sandbox.

**Input:**
```typescript
{
  source_path: string,      // Path to the file to edit
  task_id: string           // Current task context
}
```

**Action:**
1. Validate source_path exists
2. Validate source_path is in allowed directories (workspace only)
3. Copy to `_handoff/drafts/{basename}.{task_id}.draft`
4. Return draft path

**Output:**
```typescript
{
  draft_path: string,       // Full path to the draft
  original_hash: string,    // SHA256 of original (for conflict detection)
  line_count: number        // For context
}
```

### 2.2 `ollama_write_draft`

**Purpose:** Write content to a draft file (sandbox only).

**Input:**
```typescript
{
  draft_path: string,       // Must be in _handoff/drafts/
  content: string           // New file content
}
```

**Action:**
1. Validate draft_path is in `_handoff/drafts/` (CRITICAL SECURITY CHECK)
2. Write content atomically (tmp + rename)
3. Return success with new hash

**Output:**
```typescript
{
  success: boolean,
  new_hash: string,
  line_count: number
}
```

### 2.3 `ollama_read_draft`

**Purpose:** Read current draft content (for iteration).

**Input:**
```typescript
{
  draft_path: string
}
```

**Output:**
```typescript
{
  content: string,
  line_count: number
}
```

### 2.4 `ollama_submit_draft`

**Purpose:** Signal that draft is ready for Floor Manager review.

**Input:**
```typescript
{
  draft_path: string,
  original_path: string,
  task_id: string,
  change_summary: string    // Brief description of changes
}
```

**Action:**
1. Validate paths
2. Generate diff between original and draft
3. Write `_handoff/drafts/{task_id}.submission.json`
4. Send `DRAFT_READY` message to Floor Manager via MCP Hub

---

## 3. Floor Manager Draft Gate

### 3.1 On Receiving `DRAFT_READY`

```python
def handle_draft_submission(submission: DraftSubmission) -> GateResult:
    """
    Gate all draft submissions before they touch production files.
    """
    # 1. Load submission metadata
    original = Path(submission.original_path)
    draft = Path(submission.draft_path)

    # 2. Security checks
    if not is_in_workspace(original):
        return GateResult.REJECT("Original path outside workspace")

    if not draft.is_relative_to(HANDOFF_DRAFTS_DIR):
        return GateResult.REJECT("Draft not in sandbox - SECURITY VIOLATION")

    # 3. Generate diff
    diff = generate_unified_diff(original, draft)

    # 4. Safety analysis
    safety = analyze_diff_safety(diff)
    if safety.has_secrets:
        return GateResult.REJECT("Draft contains potential secrets")
    if safety.has_hardcoded_paths:
        return GateResult.REJECT("Draft contains hardcoded paths")
    if safety.deletion_ratio > 0.5:
        return GateResult.ESCALATE("Destructive diff - needs human review")

    # 5. Scope check
    if len(diff.changed_lines) > MAX_LINES_PER_DRAFT:
        return GateResult.ESCALATE("Draft exceeds scope limit")

    # 6. Accept and apply
    return GateResult.ACCEPT(diff)
```

### 3.2 Gate Results

| Result | Action |
|--------|--------|
| `ACCEPT` | Copy draft over original, delete draft, log transition |
| `REJECT` | Delete draft, send `DRAFT_REJECTED` with reason to worker |
| `ESCALATE` | Keep draft, send `DRAFT_ESCALATED` to Super Manager/Erik |

---

## 4. Security Constraints

### 4.1 Sandbox Directory Structure

```
_handoff/
├── drafts/                    # THE SANDBOX - workers can ONLY write here
│   ├── foo.py.task123.draft   # Draft files
│   ├── bar.js.task123.draft
│   └── task123.submission.json # Submission metadata
├── TASK_CONTRACT.json         # Read-only for workers
└── transition.ndjson          # Append-only audit log
```

### 4.2 Path Validation (CRITICAL)

```python
def validate_draft_write(path: Path) -> bool:
    """
    SECURITY: Only allow writes to sandbox directory.
    This is the ONLY place workers can write.
    """
    sandbox = Path("_handoff/drafts").resolve()
    target = path.resolve()

    # Must be inside sandbox
    if not target.is_relative_to(sandbox):
        log.error(f"SECURITY: Attempted write outside sandbox: {target}")
        return False

    # No path traversal
    if ".." in str(path):
        log.error(f"SECURITY: Path traversal attempt: {path}")
        return False

    return True
```

### 4.3 What Workers CANNOT Do

- Write to any path outside `_handoff/drafts/`
- Delete files (only Floor Manager can clean up)
- Read files outside the workspace
- Execute shell commands
- Access network resources

---

## 5. Workflow Example

### Task: "Add --version flag to watchdog.py"

**Step 1: Implementer requests draft**
```
Implementer → ollama_request_draft({
  source_path: "src/watchdog.py",
  task_id: "phase10_version_flag"
})
← { draft_path: "_handoff/drafts/watchdog.py.phase10_version_flag.draft" }
```

**Step 2: Implementer edits draft**
```
Implementer → ollama_write_draft({
  draft_path: "_handoff/drafts/watchdog.py.phase10_version_flag.draft",
  content: "#!/usr/bin/env python3\n... [full file with --version added] ..."
})
← { success: true, new_hash: "abc123..." }
```

**Step 3: Implementer submits draft**
```
Implementer → ollama_submit_draft({
  draft_path: "_handoff/drafts/watchdog.py.phase10_version_flag.draft",
  original_path: "src/watchdog.py",
  task_id: "phase10_version_flag",
  change_summary: "Added --version/-v flag handling in main()"
})
← { submitted: true, message_id: "msg_456" }
```

**Step 4: Floor Manager gates**
```
Floor Manager receives DRAFT_READY
→ Runs security checks (PASS)
→ Generates diff (12 lines added)
→ Validates scope (PASS)
→ Copies draft over original
→ Logs transition
→ Sends DRAFT_ACCEPTED to Implementer
```

---

## 6. Implementation Phases

### Phase 11: Sandbox Infrastructure
- [ ] Create `_handoff/drafts/` directory structure
- [ ] Add path validation utilities
- [ ] Update `.gitignore` for drafts

### Phase 12: Ollama MCP Tools
- [ ] Implement `ollama_request_draft`
- [ ] Implement `ollama_write_draft`
- [ ] Implement `ollama_read_draft`
- [ ] Implement `ollama_submit_draft`
- [ ] Add security tests

### Phase 13: Floor Manager Draft Gate
- [ ] Implement `handle_draft_submission()`
- [ ] Add diff generation
- [ ] Add safety analysis
- [ ] Add gate result handling
- [ ] Integration tests

### Phase 14: E2E Draft Workflow
- [ ] Test full draft cycle with real task
- [ ] Verify security constraints hold
- [ ] Performance benchmarking
- [ ] Documentation

---

## 7. Rollback Plan

If V4 introduces issues:

1. **Disable draft tools**: Remove from Ollama MCP server
2. **Fall back to V3**: Workers generate text, Floor Manager parses
3. **Clean sandbox**: Delete `_handoff/drafts/`

The V3 text-parsing path remains available as fallback.

---

## 8. Success Metrics

| Metric | V3 Baseline | V4 Target |
|--------|-------------|-----------|
| Parse failure rate | ~15% (estimated) | <1% |
| Worker iteration speed | N/A (no iteration) | <5s per edit |
| Security violations | 0 | 0 (MUST maintain) |
| Lines of parsing code | ~200 | <50 (diff only) |

---

## 9. Open Questions

1. **Draft retention**: How long to keep drafts after acceptance/rejection?
2. **Concurrent drafts**: Can a worker have multiple drafts open?
3. **Conflict resolution**: What if original changes while draft is in progress?
4. **Draft preview**: Should Floor Manager show diff to Erik before accepting?

---

*V4 gives local models "hands" while keeping the Floor Manager as the safety gate. The sandbox ensures workers can iterate freely without risking production files.*
