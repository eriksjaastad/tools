# Floor Manager Task: Implement Learned Routing Analysis

**Model:** Floor Manager (implementation task)
**Objective:** Analyze telemetry data and optimize routing based on actual performance

---

## ⚠️ DOWNSTREAM HARM ESTIMATE

- **If this fails:** Routing stays static. We never learn which models actually work for which tasks. Suboptimal routing continues.
- **Known pitfalls:** Not enough data to be statistically meaningful. Overfitting to recent runs. Breaking working routes.
- **Recovery:** Revert config changes. This is analysis + config update, not code change.

---

## 📚 LEARNINGS APPLIED

- [x] Let data drive decisions, not assumptions
- [x] Success = exit_code 0 + good response + no timeout
- [x] Different models have different strengths

---

## CONSTRAINTS (READ FIRST)

- DO NOT modify src/server.ts in this task (analysis only)
- DO NOT remove models from chains entirely (keep fallbacks)
- DO NOT change routing logic - only update config/routing.yaml
- REQUIRE at least 10 runs per task_type before drawing conclusions
- PRESERVE the YAML structure - only reorder models within chains

---

## 🎯 [ACCEPTANCE CRITERIA]

### Analysis Script
- [x] Create `scripts/analyze_routing_performance.js`
- [x] Script reads `~/.ollama-mcp/runs.jsonl`
- [x] Script filters to runs since `last_review` date in config
- [x] Script groups by `task_type` and `model`

### Success Rate Calculation
- [x] For each (task_type, model) pair, calculate:
  - Total runs
  - Successful runs (exit_code 0, not timed_out, output_chars > threshold)
  - Success rate percentage
- [x] Output format matches required structure

### Recommendation Output
- [x] Script outputs recommended chain order per task type
- [x] Recommendation based on: highest success rate first
- [x] Only recommend changes if >= 10 runs for that task_type
- [x] Flag task types with insufficient data: "Need more data (only N runs)"

### Config Update (Manual Step)
- [x] Documented that Floor Manager should manually update `config/routing.yaml`
- [x] No auto-update of config (human review required)

### Verification Commands
```bash
# Run analysis
node scripts/analyze_routing_performance.js

# Expected output shows success rates per model per task type
# Plus recommendations for chain reordering
```

---

## FLOOR MANAGER PROTOCOL

1. Create the analysis script
2. Run it against current telemetry
3. Review the recommendations
4. If recommendations make sense:
   - Update `config/routing.yaml` with new chain orders
   - Rebuild: `npm run build`
5. Run `node scripts/mark_telemetry_reviewed.js` to reset the review timer
6. Mark all criteria with [x] when complete

---

## Example Workflow

**Before (default config):**
```yaml
fallback_chains:
  code:
    - qwen3:14b
    - deepseek-r1
```

**Analysis shows:**
```
Task Type: code
  deepseek-r1    - 35/40 runs (87% success)
  qwen3:14b      - 25/40 runs (62% success)
```

**After (optimized config):**
```yaml
fallback_chains:
  code:
    - deepseek-r1   # promoted: 87% success
    - qwen3:14b     # demoted: 62% success
```

---

## When To Run This

This task should be run when:
- `telemetry_review_due: true` appears in response metadata
- OR manually when investigating routing issues
- OR after adding new models to the system

After running:
- Mark the review complete with `mark_telemetry_reviewed.js`
- Next reminder will fire in 30 days (or 50 runs, whichever is later)

---
