# Floor Manager Task: Implement Telemetry Review Trigger

**Model:** Floor Manager (implementation task)
**Objective:** Add automatic reminder when telemetry review is due

---

## ⚠️ DOWNSTREAM HARM ESTIMATE

- **If this fails:** No reminder ever fires. Phase 3 learned routing never happens. We keep using suboptimal routing forever.
- **Known pitfalls:** Date comparison bugs. File not found on first run. Forgetting to update last_review after reviewing.
- **Recovery:** Fix logic, rebuild. Low blast radius - this is a reminder, not core functionality.

---

## 📚 LEARNINGS APPLIED

- [x] Structural enforcement > calendar reminders
- [x] Floor Manager already reads metadata, so put trigger there
- [x] SSOT: config lives in YAML, not hardcoded

---

## CONSTRAINTS (READ FIRST)

- DO NOT break existing routing logic
- DO NOT make telemetry review blocking (just a flag, not an error)
- DO NOT require manual date entry - use current date when reviewing
- KEEP IT SIMPLE - this is a reminder, not complex logic

---

## 🎯 [ACCEPTANCE CRITERIA]

### Config Addition
- [x] Add `telemetry_review` section to `config/routing.yaml`:
```yaml
telemetry_review:
  last_review: "2026-01-10"
  review_interval_days: 30
  min_runs_before_review: 50
```
- [x] Config loads without error after addition

### Telemetry Check Function
- [x] Create function `checkTelemetryReviewDue(): { due: boolean, runsSinceReview: number }`
- [x] Reads `~/.ollama-mcp/runs.jsonl` to count runs since `last_review` date
- [x] Returns `due: true` if BOTH conditions met:
  - Days since last_review >= review_interval_days
  - Runs since last_review >= min_runs_before_review
- [x] Handles missing telemetry file gracefully (returns `due: false, runsSinceReview: 0`)

### Response Metadata
- [x] Add to response metadata interface:
```typescript
telemetry_review_due: boolean;
runs_since_last_review: number;
```
- [x] Fields included in BOTH `ollama_run` and `ollama_run_many` responses
- [x] Fields populated from `checkTelemetryReviewDue()` result

### Update Mechanism
- [x] Create script `scripts/mark_telemetry_reviewed.js`:
```bash
node scripts/mark_telemetry_reviewed.js
# Updates last_review in config/routing.yaml to today's date
```
- [x] Script updates YAML file in place
- [x] Script prints confirmation message

### Edge Cases
- [x] First run ever (no telemetry file): `due: false`
- [x] Just reviewed (0 runs since): `due: false`
- [x] Enough runs but not enough days: `due: false`
- [x] Enough days but not enough runs: `due: false`
- [x] Both thresholds met: `due: true`

### Verification
```bash
# Build succeeds
npm run build

# Check that config loads
node -e "const yaml = require('js-yaml'); const fs = require('fs'); const cfg = yaml.load(fs.readFileSync('config/routing.yaml')); console.log('Review interval:', cfg.telemetry_review.review_interval_days, 'days')"

# Test the mark-reviewed script
node scripts/mark_telemetry_reviewed.js
```

---

## FLOOR MANAGER PROTOCOL

1. Read current `config/routing.yaml`
2. Add the `telemetry_review` section
3. Implement `checkTelemetryReviewDue()` function in `src/server.ts`
4. Add fields to response metadata
5. Create the mark-reviewed script
6. Test each edge case mentally
7. Rebuild: `npm run build`
8. Mark all criteria with [x] when complete

---

## Expected Floor Manager Experience

After implementation, when Floor Manager calls `ollama_run`:

```json
{
  "content": [{"type": "text", "text": "...model response..."}],
  "metadata": {
    "model_used": "qwen3:14b",
    "task_type": "code",
    "telemetry_review_due": true,
    "runs_since_last_review": 127
  }
}
```

When they see `telemetry_review_due: true`, they know to:
1. Run Phase 3 learned routing analysis
2. Update routes based on findings
3. Run `node scripts/mark_telemetry_reviewed.js`

---
