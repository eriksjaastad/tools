# Floor Manager Task: Verify Smart Routing Logic

**Model:** Floor Manager (verification task)
**Objective:** Verify the routing logic in server.ts matches the spec

---

## ⚠️ DOWNSTREAM HARM ESTIMATE

- **If this fails:** Tasks won't route correctly. Fallback chains won't work. Escalation flag won't trigger.
- **Known pitfalls:** TypeScript compiles but logic is wrong. Fallback loop exits early. Escalate never set.
- **Recovery:** Fix logic, rebuild with `npm run build`.

---

## 📚 LEARNINGS APPLIED

- [x] Consulted OLLAMA_MCP_SMART_ROUTING_SPEC.md
- [x] Routing order: explicit model > task_type chain > auto chain
- [x] Fallback: try each model in chain until success or exhausted

---

## CONSTRAINTS (READ FIRST)

- DO NOT modify config/routing.yaml in this task
- DO NOT add new parameters not in the spec
- FOCUS on verifying existing logic is correct

---

## 🎯 [ACCEPTANCE CRITERIA]

### Parameter Definition
- [x] `task_type` parameter exists on `ollama_run` tool
- [x] `task_type` parameter exists on `ollama_run_many` tool
- [x] Valid values: "classification" | "extraction" | "code" | "reasoning" | "file_mod" | "auto"
- [x] Parameter is optional (model can still be specified directly)

### Routing Resolution
- [x] If `model` is provided explicitly, use only that model (bypass routing)
- [x] If `task_type` is provided, look up chain from routing.yaml
- [x] If neither provided, fall back to "auto" chain
- [x] YAML config is loaded at startup (not on every request)

### Fallback Loop
- [x] Loop iterates through all models in chain
- [x] Tracks `models_tried` array
- [x] Checks exit code (0 = success)
- [x] Checks response quality with `isGoodResponse()`
- [x] Breaks loop on first success
- [x] Continues to next model on failure

### Escalation
- [x] `escalate: true` set when ALL models in chain fail
- [x] `escalation_reason: "all_local_models_failed"` included
- [x] Returns last result with escalation metadata

### Verification Command
```bash
npm run build && echo "Build successful"
```

---

## FLOOR MANAGER PROTOCOL

1. Read `src/server.ts`
2. Find the routing logic (should be near `ollamaRunWithRouting` or similar)
3. Trace the code path for each acceptance criterion
4. Note specific line numbers for each feature
5. If any criterion fails, fix the code
6. Rebuild and verify
7. Mark all criteria with [x] when verified

---
