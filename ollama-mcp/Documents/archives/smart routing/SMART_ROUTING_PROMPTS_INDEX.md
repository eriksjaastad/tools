# Smart Routing: Verification Prompts Index

**For Floor Manager Use**

> **Context:** Phase 1 & 2 were implemented from a spec (not detailed prompts). These verification prompts ensure the implementation meets our quality standards.

---

## Task Overview

### Phase 1 & 2 Verification (Do First)

| Task | File | Objective |
|------|------|-----------|
| **1** | `SMART_ROUTING_PROMPT_1_VERIFY_CONFIG.md` | Verify YAML config is correct |
| **2** | `SMART_ROUTING_PROMPT_2_VERIFY_ROUTING_LOGIC.md` | Verify routing logic in server.ts |
| **3** | `SMART_ROUTING_PROMPT_3_VERIFY_QUALITY_CHECK.md` | Verify isGoodResponse() function |
| **4** | `SMART_ROUTING_PROMPT_4_VERIFY_METADATA.md` | Verify response metadata structure |

### Phase 3: Learned Routing (After Verification Complete)

| Task | File | Objective |
|------|------|-----------|
| **5** | `SMART_ROUTING_PROMPT_5_TELEMETRY_TRIGGER.md` | Add automatic reminder when review is due |
| **6** | `SMART_ROUTING_PROMPT_6_LEARNED_ROUTING.md` | Analyze telemetry and optimize routes |

---

## Verification Order

Run these in sequence. Each builds on the previous:

1. **Config** - YAML must be valid before routing can work
2. **Routing Logic** - Core logic depends on valid config
3. **Quality Check** - Called by routing logic
4. **Metadata** - Final response structure

---

## What This Validates

The implementation was built from `OLLAMA_MCP_SMART_ROUTING_SPEC.md` without detailed prompts. These verification tasks ensure:

- YAML config matches the spec's recommended chains
- Routing logic handles all code paths correctly
- Response quality detection is task-aware
- Metadata enables Floor Manager decision-making
- Escalation flag is set correctly

---

## After Phase 1 & 2 Verification

If all tasks (1-4) pass:
- Phase 1 & 2 are validated ✅
- Proceed to Phase 3 prompts (5 & 6)
- Archive AI Router after Phase 3 complete

If any tasks fail:
- Fix issues found
- Rebuild: `npm run build`
- Re-run verification

---

## Phase 3 Workflow

**Prompt 5 (Telemetry Trigger):**
- Adds `telemetry_review_due` flag to response metadata
- Floor Manager automatically sees when it's time to review
- No calendar reminders needed - it's structural

**Prompt 6 (Learned Routing):**
- Only run when `telemetry_review_due: true` appears
- Analyzes success rates per model per task type
- Outputs recommendations for chain reordering
- Human reviews before updating config

**The Loop:**
```
Use MCP → Telemetry accumulates → 30 days + 50 runs pass
    → telemetry_review_due: true appears
    → Run Prompt 6 analysis
    → Update routing config
    → Run mark_telemetry_reviewed.js
    → Timer resets → Loop continues
```

---

*Created: January 10, 2026*
*Updated: January 10, 2026 - Added Phase 3 prompts*
*Purpose: Validate spec-based implementation + enable learned routing*
