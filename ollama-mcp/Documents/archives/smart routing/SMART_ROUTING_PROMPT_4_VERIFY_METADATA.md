# Floor Manager Task: Verify Enhanced Metadata Response

**Model:** Floor Manager (verification task)
**Objective:** Verify response metadata structure matches the spec

---

## ⚠️ DOWNSTREAM HARM ESTIMATE

- **If this fails:** Floor Manager can't see escalation flag. Can't track which models were tried. Can't make informed retry decisions.
- **Known pitfalls:** Metadata not included in all code paths. Fields misspelled. Types wrong.
- **Recovery:** Fix response structure, rebuild.

---

## 📚 LEARNINGS APPLIED

- [x] Metadata enables Floor Manager decision-making
- [x] `escalate: true` is the structural enforcement signal
- [x] `models_tried` provides debugging visibility

---

## CONSTRAINTS (READ FIRST)

- DO NOT change the content response format
- DO NOT remove existing telemetry
- ONLY verify metadata is correctly attached

---

## 🎯 [ACCEPTANCE CRITERIA]

### Metadata Interface
- [x] Response includes `metadata` object
- [x] TypeScript interface defines all required fields

### Required Fields
- [x] `model_used: string` - The model that produced the response
- [x] `task_type: string` - The task type used for routing
- [x] `duration_ms: number` - Execution time
- [x] `timed_out: boolean` - Whether timeout occurred
- [x] `models_tried: string[]` - Array of models attempted
- [x] `escalate: boolean` - Whether Floor Manager should take over
- [x] `escalation_reason?: string` - Why escalation triggered (optional)

### Success Path
- [x] On success: `escalate: false`
- [x] On success: `models_tried` contains attempted models
- [x] On success: `model_used` matches successful model

### Failure Path
- [x] When all models fail: `escalate: true`
- [x] When all models fail: `escalation_reason: "all_local_models_failed"`
- [x] When all models fail: `models_tried` contains ALL attempted models
- [x] When all models fail: `model_used` is last model tried

### Both Tools
- [x] `ollama_run` returns metadata
- [x] `ollama_run_many` returns metadata (per job)

### Verification
```bash
# Check the TypeScript interface
grep -A 10 "interface.*Metadata\|metadata:" src/server.ts
```

---

## FLOOR MANAGER PROTOCOL

1. Find the response construction code in `src/server.ts`
2. Verify metadata is attached in BOTH success and failure paths
3. Check that all required fields are present
4. Verify types match (string vs number vs boolean)
5. If any criterion fails, fix the code
6. Rebuild and verify
7. Mark all criteria with [x] when verified

---
