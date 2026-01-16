# 🏗️ Agentic Blueprint Setup: Multi-Agent Pipeline

This document outlines the step-by-step implementation of the **Agentic Blueprint**, transitioning from "AI as a consultant" to "AI as a factory line." It utilizes a **State Machine** based on a JSON contract to ensure seamless handoffs between Cloud and Local models.

---

## 1. The Pipeline Roles

| Role | Agent / Model | Responsibility |
| --- | --- | --- |
| **The Architect** | Erik (Conductor) | Sets the vision and approves the `PROPOSAL.md`. |
| **The Floor Manager** | Gemini 3 Flash (Cursor) | **Orchestration:** Converts proposals into `TASK_CONTRACT.json`. Analyzes reports and decides to Merge, Fix, or Rebut. |
| **The Implementer** | Ollama (Qwen2.5-Coder) | **The Worker:** Physically writes the code/configs based on the contract. |
| **The Local Reviewer** | Ollama (DeepSeek-R1) | **The Critic:** Performs immediate syntax/security audits locally. |
| **The Judge** | Claude Code CLI | **The Gatekeeper:** Performs deep architectural audits and generates the final `JUDGE_REPORT.md`. |

---

## 2. The `TASK_CONTRACT.json` Schema

The source of truth for the state machine.

```json
{
  "schema_version": "1.0",
  "task_id": "DOC-001-AUTH-MERGE",
  "project": "Project-A",
  "status": "pending_implementer", 
  "status_reason": "Awaiting implementation",
  "timestamps": {
    "created_at": "2026-01-16T12:00:00Z",
    "updated_at": "2026-01-16T12:00:00Z"
  },
  "roles": {
    "implementer": "qwen2.5-coder",
    "local_reviewer": "deepseek-r1",
    "judge": "claude-code-cli"
  },
  "limits": {
    "max_rebuttals": 2,
    "max_review_cycles": 5,
    "timeout_minutes": 10
  },
  "constraints": {
    "allowed_paths": ["Project-A/docs/"],
    "forbidden_paths": [".env", "AGENTS.md"],
    "allow_deletes": false,
    "max_diff_size": 200
  },
  "specification": {
    "source_files": [
      {"path": "auth_v1.md", "hash": "sha256-abc..."},
      {"path": "auth_v2.md", "hash": "sha256-def..."}
    ],
    "target_file": "auth_final.md",
    "requirements": [
      "Merge core logic",
      "Standardize heading hierarchy (H1 -> H2 -> H3)",
      "Maintain internal links"
    ]
  },
  "handoff_data": {
    "implementer_notes": "",
    "changed_files": [],
    "judge_report_path": "_handoff/JUDGE_REPORT.md",
    "judge_report_json": "_handoff/JUDGE_REPORT.json",
    "rebuttal_path": "_handoff/REBUTTAL.md"
  },
  "breaker": {
    "status": "armed",
    "rebuttal_count": 0,
    "max_delete_ratio": 0.05
  },
  "history": []
}
```

---

## 3. The Control Plane (State Machine)

| Transition | Status | Trigger Condition | Action Taken |
| --- | --- | --- | --- |
| **Start Work** | `pending_implementer` | Contract exists | **Watchdog** calls `ollama run qwen2.5-coder` (Implementer). |
| **Local Audit** | `pending_local_review` | Code written | **Watchdog** calls `ollama run deepseek-r1` (Local Reviewer) for syntax/security check. |
| **Request Review** | `pending_judge_review` | Local Audit passed | **Watchdog** updates status and creates `_handoff/REVIEW_REQUEST.md`. |
| **Execute Audit** | `review_in_progress` | `REVIEW_REQUEST.md` exists | **Claude Code CLI** (in Watcher Mode) runs the architectural audit. |
| **Finalize/Loop** | `review_complete` | `JUDGE_REPORT.md` written | **Gemini** (Floor Manager) analyzes the grade and either Merges or Restarts the cycle. |
| **Circuit Breaker** | `erik_consultation` | Edge case detected | **Watchdog** halts all automation and creates `_handoff/ERIK_HALT.md`. |

---

## 4. The "Circuit Breaker" (When to hit the Brakes)

The automation is powerful, but it needs a "Dead Man's Switch." A circuit breaker is triggered when the AI reaches a **Complexity/Security Threshold** that requires human judgment.

### What triggers the Brakes?
1. **The Rebuttal Limit:** If Gemini and Claude Code have disagreed (Rebuttal phase) more than **2 times** on the same task. (Preventing an infinite AI argument).
2. **The Destructive Action Check:** If the task requires deleting more than **5% of a project's codebase** or exceeding a `max_diff_size` threshold.
3. **The Logical Paradox:** If the Judge gives a `PASS` but the Local Reviewer detects a `CRITICAL_SECURITY_FLAW` (e.g., hardcoded API key).
4. **The Hallucination Loop:** If the Watchdog detects that the code is being reverted to an older version that was already rejected.
5. **The GPT-Energy Guardrail:** If the review becomes "freakishly picky" over non-architectural style issues.
6. **The Stalled Process:** If a task stays in `review_in_progress` or `pending_implementer` for more than 10 minutes (indicating a crashed agent or infinite loop).
7. **Budget Ceiling:** If the tokens/cost for a single `task_id` exceeds a predefined budget.

### How does the halt happen?
1. The agent detecting the issue updates the contract status to `erik_consultation` and writes the `status_reason`.
2. The **Watchdog** immediately stops the loop, renames the active contract to `TASK_CONTRACT.json.lock`, and creates **`_handoff/ERIK_HALT.md`**.
3. **ERIK_HALT.md** contains:
   - **The Conflict:** Why the brakes were hit.
   - **The Two Paths:** "Agent A wants X, Agent B wants Y."
   - **The State:** A snapshot of the contract and the diff.

---

## 5. The Autonomous Handoff (The Trigger)

### Step 5: "Watcher Mode" for Claude Code CLI
Since Claude Code CLI doesn't have a daemon mode, we use a simple bash loop in a separate terminal. **Crucial:** The bash loop owns the "looping," and Claude runs **once** per request to ensure atomicity.

**The Watcher Bash Loop:**
```bash
while true; do
  if [ -f "_handoff/REVIEW_REQUEST.md" ]; then
    echo "🔍 Review request detected. Starting Claude Code..."
    # Update status in contract to prevent double-triggering
    mv _handoff/REVIEW_REQUEST.md _handoff/REVIEW_IN_PROGRESS.md
    
    # Run Claude for a SINGLE atomic review
    claude-code --non-interactive "Read _handoff/TASK_CONTRACT.json, review the target files, write JUDGE_REPORT.md and JUDGE_REPORT.json, then exit."
    
    rm _handoff/REVIEW_IN_PROGRESS.md
  fi
  sleep 5
done
```

**The "Watcher" Prompt for Claude:**
> "Read `TASK_CONTRACT.json`. Perform a deep architectural review of the newly edited files listed in `artifacts`. Write your findings to `JUDGE_REPORT.md` (prose) and `JUDGE_REPORT.json` (structured: grade, blocking_issues, required_fixes). When finished, exit."

---

## 6. The Feedback Loop (Refinement)

The **Floor Manager** (Gemini/Cursor) handles the post-review logic using **Branch Isolation**:

1. **Isolation:** Each task runs on a dedicated branch `task/<task_id>`.
2. **Analysis:** Gemini reads `JUDGE_REPORT.json`.
3. **Scenario A (PASS):** Merge `task/<task_id>` to `main` and mark `TODO.md` as complete.
4. **Scenario B (FAIL - Fix Needed):** If the Judge is right, Gemini creates a new **Refinement Contract** for Ollama on the same branch.
5. **Scenario C (REBUTTAL):** If Gemini disagrees, it writes `_handoff/REBUTTAL.md` and triggers a re-review with the new context.

---

## 6. Why This Works

1. **Decoupled Intelligence:** Local Reviewers (DeepSeek) handle the "low-level" syntax, saving Claude's tokens for high-level architectural review.
2. **Asynchronous Progress:** Multiple projects can run this loop simultaneously in different directories.
3. **Auditability:** The `TASK_CONTRACT.json` history provides a perfect trail of how a document evolved from a proposal to a "Golden Document."

---

## 7. Next Actions

- [ ] Create `_handoff/` directory at the project root.
- [ ] Implement the `TASK_CONTRACT.json` schema in `agent-hub/hub.py`.
- [ ] Write the Python **Watchdog** script to manage the State Machine transitions.
- [ ] Set up a dedicated terminal for the **Claude Code CLI Watcher**.
