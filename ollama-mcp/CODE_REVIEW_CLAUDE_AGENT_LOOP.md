# Code Review: Agent Loop Dispatcher

**Reviewer:** Claude Opus 4.5 (Super Manager)
**Date:** 2026-01-17
**Files Reviewed:** 7 files (5 new, 2 modified)
**Verdict:** PASS with minor issues

---

## Summary

The Agent Loop Dispatcher implementation is **solid and well-structured**. It successfully enables local Ollama models to execute tool calls in a loop, which was the critical missing piece for V4.

**Overall Grade: B+**

---

## What Was Done Well

### 1. Clean Architecture
- Clear separation of concerns (types, parser, executor, loop driver)
- Dependency injection pattern in `runAgentLoop` (ollamaRunFn parameter)
- Follows existing project conventions

### 2. Security Maintained
- Tool whitelist enforced in parser (`VALID_TOOLS`)
- Sandbox validation preserved in draft-tools
- Path traversal still blocked

### 3. Robust Circuit Breakers
- Max iterations (default 10) ✓
- Timeout (default 5 min) ✓
- Infinite loop detection (same call 3x) ✓
- Consecutive error handling (3 strikes) ✓

### 4. Good Test Coverage
- 12 tests covering parser, executor, and loop
- Edge cases tested (malformed JSON, unknown tools, loop detection)
- Uses Node's built-in test runner as requested

### 5. Atomic Writes
- `writeDraft()` uses tmp + rename pattern correctly (line 107-110)

---

## Issues Found

### HIGH Priority

#### H1: Multi-line JSON Parsing
**File:** `src/tool-call-parser.ts:57-59`
**Issue:** Parser only handles single-line JSON. Multi-line JSON objects fail.

```typescript
// Current: only checks lines starting with '{'
if (!trimmed.startsWith('{')) continue;
const parsed = JSON.parse(trimmed);
```

**Example that fails:**
```json
{
  "name": "ollama_write_draft",
  "arguments": {"draft_path": "/path", "content": "multi\nline"}
}
```

**Fix:** Add a regex-based JSON extraction that handles multi-line:
```typescript
// Look for JSON blocks between { and matching }
const jsonRegex = /\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g;
```

---

### MEDIUM Priority

#### M1: Incomplete ollama_list_models Handler
**File:** `src/tool-executor.ts:52-58`
**Issue:** Returns hardcoded error instead of actual functionality.

```typescript
case 'ollama_list_models': {
  output = {
    success: false,
    error: 'ollama_list_models not yet supported in agent loop'
  };
  break;
}
```

**Fix:** Either implement properly or remove from `VALID_TOOLS` whitelist.

---

#### M2: Unbounded Context Growth
**File:** `src/agent-loop.ts:177`
**Issue:** Conversation context grows without limit.

```typescript
conversationContext += `\n${modelOutput}${resultsText}`;
```

For long-running tasks with many tool calls, this could exceed model context windows.

**Fix:** Implement sliding window or summarization:
```typescript
const MAX_CONTEXT_CHARS = 50000;
if (conversationContext.length > MAX_CONTEXT_CHARS) {
  conversationContext = conversationContext.slice(-MAX_CONTEXT_CHARS);
}
```

---

#### M3: Hardcoded Default Model
**File:** `src/agent-loop.ts:65`
**Issue:** Defaults to `qwen3:14b` which may not be available.

```typescript
const model = options.model ?? 'qwen3:14b';
```

**Fix:** Either check model availability or use the routing config:
```typescript
const model = options.model ?? getDefaultModel(options.task_type);
```

---

### LOW Priority

#### L1: Non-atomic Write in requestDraft
**File:** `src/draft-tools.ts:68`
**Issue:** Uses direct `writeFileSync` instead of tmp+rename pattern.

```typescript
fs.writeFileSync(draftPath, sourceContent, 'utf-8');
```

**Risk:** Low (draft creation, not critical data), but inconsistent with writeDraft.

---

#### L2: Argument Validation Missing
**File:** `src/tool-executor.ts:32-47`
**Issue:** Arguments cast without validation.

```typescript
output = requestDraft(toolCall.arguments as unknown as RequestDraftInput);
```

If model sends malformed arguments (missing required fields), this could throw at runtime.

**Fix:** Add runtime validation or use zod schemas.

---

#### L3: Tests Import from dist/
**File:** `tests/test-agent-loop.ts:8-10`
**Issue:** Tests require build step to run.

```typescript
import { parseToolCalls } from '../dist/tool-call-parser.js';
```

**Fix:** Consider using ts-node or vitest for direct TypeScript testing.

---

## Verification Performed

```bash
✓ npm run build - 0 TypeScript errors
✓ npm test - Smoke tests pass
✓ node --test tests/test-agent-loop.ts - 12/12 pass
✓ ollama_agent_run tool appears in list
✓ Existing tools still work
```

---

## Acceptance Criteria Status

| Criteria | Status |
|----------|--------|
| Parser extracts JSON tool calls | ✓ (single-line only) |
| Parser extracts XML tool calls | ✓ |
| Parser returns [] for no tool calls | ✓ |
| Parser handles malformed JSON | ✓ |
| Agent loop executes single tool call | ✓ |
| Agent loop handles multi-step | ✓ |
| Agent loop halts at max_iterations | ✓ |
| Agent loop halts on infinite loop | ✓ |
| Security constraints maintained | ✓ |
| Only whitelisted tools callable | ✓ |

---

## Recommendations

### Before Production Use:
1. **Fix H1** (multi-line JSON parsing) - models often format JSON across lines
2. **Fix M2** (context growth) - will cause failures on complex tasks

### Nice to Have:
3. **Fix M1** - complete or remove ollama_list_models
4. **Fix M3** - don't hardcode default model

### Can Defer:
5. L1, L2, L3 - low risk, cleanup items

---

## Conclusion

**APPROVED** for testing the V4 pipeline. The implementation is functional and well-structured. The HIGH priority issue (H1 - multi-line JSON) should be fixed before production use, but won't block initial testing with simple prompts.

The Agent Loop Dispatcher is ready to test with the original `TASK_PIN_DEPENDENCIES.md` task.

---

*Code Review by Claude Opus 4.5 - 2026-01-17*
