# Agentic Blueprint Review & Recommendations

This document captures feedback on the proposed **Agentic Blueprint** for a multi-agent pipeline. It focuses on operational clarity, safety, and maintainability while preserving the strengths of the current design.

## What’s working well

- **Clear role separation**: The pipeline separates strategic, orchestration, implementation, and review responsibilities, which makes the handoffs explicit and reduces “overlapping agent authority.”
- **State-machine grounding**: A contract-first workflow (`TASK_CONTRACT.json`) creates a single source of truth for state transitions and auditing.
- **Circuit breaker concept**: Having explicit stop conditions is essential for automated systems that can otherwise loop indefinitely.
- **Auditability**: The history trail plus `_handoff/` artifacts give a strong basis for review and post-mortems.

## Top recommendations (high impact)

### 1) Version and validate the contract
Add `schema_version` and explicit validation constraints so each actor can fail fast if the contract is malformed.

**Suggested additions**
```json
{
  "schema_version": "1.0",
  "timestamps": {
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  },
  "checksum": {
    "contract_sha256": "...",
    "target_files": {
      "auth_final.md": "..."
    }
  }
}
```

Why: This protects against stale or corrupted state, enables replays, and prevents two agents from working on divergent assumptions.

### 2) Make transitions idempotent and explicit
Each transition should be a **function of (state, event)**, and should be safe to re-run.

- Track `last_event_id` (or `last_transition`) and `event_log` in `history`.
- Use a `status_reason` for human-readable context.

### 3) Require bounded retries for rebuttals
You already cap rebuttals at 2. Make this a **first-class contract field**:

```json
"limits": {
  "max_rebuttals": 2,
  "max_review_cycles": 5
}
```

Why: prevents open-ended loops even if an external watcher or script changes.

### 4) Define “files under review” precisely
Add a `changed_files` array in the contract once the implementer finishes. Avoid watcher-side ambiguity.

```json
"handoff_data": {
  "changed_files": ["auth_final.md", "agent-hub/hub.py"]
}
```

### 5) Make `_handoff/` artifacts atomic
Write to temp files and move into place to avoid partial reads by watcher loops.

- Example: write `JUDGE_REPORT.md.tmp` then `mv` → `JUDGE_REPORT.md`.

## Circuit breaker clarifications
The circuit breaker is strong, but it needs **observable thresholds**.

Consider adding a `breaker` section in the contract to track metrics and reasons:

```json
"breaker": {
  "status": "armed",
  "triggered_by": null,
  "rebuttal_count": 0,
  "max_delete_ratio": 0.05
}
```

Also consider defining **critical issues** as:

- A specific severity taxonomy (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- A minimal set of conditions that **must** halt automation.

## Operational recommendations

### Observability
- Emit all transitions and errors as NDJSON to a single log file.
- Include `task_id`, `status`, `agent`, and `duration_ms` for each step.

### Security and data integrity
- Require hash comparison of target files (or repo commit) before merging.
- Protect `_handoff/` with a `.gitignore` policy (don’t let transient state leak into version control).

### Reliability
- Watcher loops should include backoff and a watchdog timeout.
- If the implementer is local (Ollama), capture the exact model version for reproducibility.

## Suggested schema additions (full example)

```json
{
  "schema_version": "1.0",
  "task_id": "DOC-001-AUTH-MERGE",
  "project": "Project-A",
  "status": "pending_implementer",
  "status_reason": "awaiting implementer",
  "roles": {
    "implementer": "qwen2.5-coder",
    "judge": "claude-code-cli"
  },
  "limits": {
    "max_rebuttals": 2,
    "max_review_cycles": 5
  },
  "specification": {
    "source_files": ["auth_v1.md", "auth_v2.md"],
    "target_file": "auth_final.md",
    "requirements": [
      "Merge core logic",
      "Standardize to 14pt readability",
      "Maintain internal links"
    ]
  },
  "handoff_data": {
    "implementer_notes": "",
    "changed_files": [],
    "judge_report_path": "_handoff/JUDGE_REPORT.md",
    "rebuttal_path": "_handoff/REBUTTAL.md"
  },
  "breaker": {
    "status": "armed",
    "triggered_by": null,
    "rebuttal_count": 0,
    "max_delete_ratio": 0.05
  },
  "timestamps": {
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z"
  },
  "history": []
}
```

## Next steps you can take now

1. Add `schema_version`, `limits`, and `breaker` fields to the contract definition.
2. Define transition rules as a small, pure function in the watchdog (unit-testable).
3. Log all state transitions as NDJSON and checkpoint them for post-mortem analysis.

---

If you’d like, I can also draft the initial `TASK_CONTRACT.json` validator and a minimal watchdog state machine in `agent-hub/hub.py`.
