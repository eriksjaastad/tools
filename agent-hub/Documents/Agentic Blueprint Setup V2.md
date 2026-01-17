# 🏗️ Agentic Blueprint Setup V2: Multi-Agent Pipeline

**Version:** 2.0  
**Status:** Draft  
**Last Updated:** 2026-01-16  
**Changelog:** Incorporates peer review feedback from Claude, GPT-4, and Codex audits.

---

## 0. What Changed from V1

| Issue | V1 Problem | V2 Fix |
|-------|-----------|--------|
| Race conditions | File-existence signaling (`REVIEW_REQUEST.md`) could be read mid-write | Atomic writes via temp files + rename; lock mechanism |
| Claude CLI flags | `--non-interactive` doesn't exist | Correct invocation with `--dangerously-skip-permissions` or piped `--print` |
| Non-idempotent transitions | No protection against double-processing | `last_transition_id` + `attempt` counters; transitions are pure functions |
| Judge output ambiguity | Prose-first `JUDGE_REPORT.md` let Floor Manager "reinterpret" | Mandatory `JUDGE_REPORT.json` for machine parsing |
| No timeouts | Agents could hang forever | Explicit `timeout_minutes` per phase with `timeout_*` statuses |
| Tight rebuttal limit | Fixed at 2 for all tasks | Complexity-based: 2 (minor), 4 (major), configurable per-task |
| No rollback story | Broken code could persist | Git commit at each state transition; branch-per-task mandatory |
| Missing cost controls | AI could argue with itself indefinitely | Token/cost budget ceiling with `budget_exceeded` halt |
| Schema drift | No versioning or validation | `schema_version` + checksums for contract and target files |

---

## 1. The Pipeline Roles (Clarified)

| Role | Agent / Model | Responsibility | Constraints |
|------|---------------|----------------|-------------|
| **The Architect** | Erik (Conductor) | Sets vision, collaborates on proposals, resolves halts | Human-in-the-loop for all `erik_consultation` states |
| **The Super Manager** | Claude Code CLI | **Strategic Partner.** Helps Erik draft and refine proposals. Outputs `PROPOSAL_FINAL.md` to trigger the pipeline. | Works WITH Erik, not autonomously. Does not execute. |
| **The Floor Manager** | Gemini 3 Flash (Cursor) | **Orchestration + Task Decomposition.** Detects `PROPOSAL_FINAL.md`, understands task requirements, breaks work into right-sized chunks for local models. Knows Qwen's strengths (fast coding) vs DeepSeek's (reasoning). Routes reports → decisions. **Never writes implementation code himself.** | Must understand the task to decompose it properly; no creative interpretation of Judge verdicts |
| **The Implementer** | Ollama (Qwen2.5-Coder) | **Writes code/configs.** Follows contract spec exactly. Outputs to target files. | Scoped to `allowed_paths`; cannot touch `forbidden_paths` |
| **The Local Reviewer** | Ollama (DeepSeek-R1) | **Syntax/security first-pass.** Catches hardcoded secrets, broken imports, obvious bugs. | Runs before Judge to save cloud tokens |
| **The Judge** | Claude Code CLI | **Deep architectural audit.** Validates structure, coherence, and requirements. Produces structured verdict. | Runs once per review request; no looping |

### Role Separation Rules
- **Super Manager ≠ Judge:** Same tool (Claude CLI), different modes. Super Manager helps draft proposals; Judge reviews completed work.
- **Floor Manager ≠ Worker:** Gemini never implements. If a task needs implementation, it goes to Ollama. But the Floor Manager MUST understand the task to decompose it properly.
- **Local Reviewer is optional but recommended:** Skip only for trivial doc-only changes.

### Floor Manager: Local Model Expertise

The Floor Manager is the **foreman** who knows the workers. He must understand:

| Model | Strengths | Limitations | Best For |
|-------|-----------|-------------|----------|
| **Qwen 2.5 Coder** | Fast, good at straightforward coding, follows instructions | Struggles with complex reasoning, can lose context on long tasks | File edits, refactoring, template-based generation |
| **DeepSeek-R1** | Strong reasoning, catches edge cases, good at review | Slower, more verbose, can overthink simple tasks | Security review, logic validation, architectural checks |

**Task Decomposition Rules:**
- If a task requires >500 lines of output, break it into chunks
- If a task requires reasoning + coding, split into two contracts (DeepSeek reasons → Qwen implements)
- If a task touches >5 files, consider sequential contracts to maintain context
- Always set realistic `timeout_minutes` based on model speed

### Floor Manager: Stall Recovery (Two-Strike Rule)

Local models stall. It happens. The Floor Manager's job is to **detect, diagnose, and adapt**.

**The Two-Strike Rule:**
1. **Strike 1 (First stall):** Floor Manager analyzes the failure, reworks the contract, and retries
2. **Strike 2 (Second stall):** Stop all work, present the stall reason to Erik, request guidance

**When a Local Model Stalls, the Floor Manager asks:**

| Question | Possible Fix |
|----------|--------------|
| Was the task too big? | Break into smaller chunks |
| Was the context too long? | Summarize inputs, reduce scope |
| Wrong model for the job? | Switch Qwen ↔ DeepSeek |
| Did it hit a reasoning wall? | Add explicit step-by-step instructions |
| Is the prompt ambiguous? | Rewrite with clearer constraints |
| Did Ollama itself crash? | Restart Ollama, retry unchanged |

**Stall Detection Triggers:**
- `timeout_implementer` status (exceeded time limit)
- Empty or malformed output
- Repeated identical output (stuck in loop)
- Ollama process crash / connection refused

**Floor Manager Recovery Flow:**
```
Local model stalls
       │
       ▼
┌─────────────────────────┐
│ Strike 1: Diagnose      │
│ - What went wrong?      │
│ - Rework the contract   │
│ - Retry with fixes      │
└─────────────────────────┘
       │
       ├── Success → Continue pipeline
       │
       ▼ (stalls again)
┌─────────────────────────┐
│ Strike 2: Escalate      │
│ - Stop all work         │
│ - Write STALL_REPORT.md │
│ - Present to Erik       │
│ - Wait for guidance     │
└─────────────────────────┘
```

**STALL_REPORT.md Contents:**
- Task ID and original specification
- What was attempted (both strikes)
- Why it failed each time
- Floor Manager's hypothesis for the root cause
- Proposed alternative approaches (for Erik to choose)

### Floor Manager Skill (Agent Skills Library)

This knowledge should be captured as a reusable skill:

**Skill Location:** `agent-skills-library/claude-skills/floor-manager-orchestration/SKILL.md`  
**Playbook Location:** `agent-skills-library/playbooks/floor-manager-orchestration/README.md`  
**Cursor Rules:** `agent-skills-library/cursor-rules/floor-manager-orchestration/rules.md`

**Why this is a skill:**
- Project-agnostic (same patterns across all projects)
- Steep learning curve (benefits from accumulated knowledge)
- Repeated constantly (every task goes through the Floor Manager)
- Has explicit triggers, constraints, and success criteria

**Skill includes:**
- Local model capabilities matrix (Qwen vs DeepSeek vs others)
- Task decomposition patterns
- Stall recovery procedures (Two-Strike Rule)
- Timeout and context limit guidelines
- When to escalate vs retry
- Contract creation from proposals

**TODO:** Create this skill in the agent-skills-library. See `agent-skills-library/claude-skills/_TEMPLATE/SKILL.md` for format.

### The Proposal Flow
```
Erik + Super Manager (Claude CLI)
         │
         ├── Discuss task scope and approach
         ├── Draft requirements together
         ├── Refine until Erik approves
         ├── Erik says: "Write PROPOSAL_FINAL" (formalized trigger phrase)
         │
         ▼
   PROPOSAL_FINAL.md written to _handoff/
         │
         ▼
   Floor Manager (Cursor) DETECTS the file
         │
         ├── Valid proposal → Converts to TASK_CONTRACT.json
         │                    Pipeline begins
         │
         └── Malformed/vague → Writes PROPOSAL_REJECTED.md
                               (Reason + what's missing)
                               Super Manager revises and resubmits
```

### Proposal Rejection

When Floor Manager cannot convert a proposal to a valid contract:

**`PROPOSAL_REJECTED.md` Contents:**
```markdown
# Proposal Rejected

**Original Proposal:** PROPOSAL_FINAL.md
**Rejected At:** 2026-01-16T14:00:00Z

## Issues

1. **Missing target file** - Proposal doesn't specify where output should go
2. **Vague requirements** - "Make it better" is not actionable
3. **No acceptance criteria** - How do we know when it's done?

## What's Needed

- Explicit `target_file` path
- Specific, measurable requirements
- At least 2 acceptance criteria

## Action Required

Super Manager: Revise proposal and resubmit as PROPOSAL_FINAL.md
```

**Flow after rejection:**
1. Super Manager reads `PROPOSAL_REJECTED.md`
2. Discusses with Erik to clarify
3. Writes revised `PROPOSAL_FINAL.md`
4. Floor Manager tries again

---

## 2. The `TASK_CONTRACT.json` Schema (V2)

The single source of truth for all state transitions.

```json
{
  "schema_version": "2.0",
  "task_id": "DOC-001-AUTH-MERGE",
  "project": "Project-A",
  "complexity": "minor",
  
  "status": "pending_implementer",
  "status_reason": "Awaiting implementation",
  "last_transition_id": "tr-001",
  "attempt": 1,
  
  "timestamps": {
    "created_at": "2026-01-16T12:00:00Z",
    "updated_at": "2026-01-16T12:00:00Z",
    "deadline_at": "2026-01-16T14:00:00Z"
  },
  
  "git": {
    "repo_root": "/Users/erik/projects/Project-A",
    "base_branch": "main",
    "task_branch": "task/DOC-001-AUTH-MERGE",
    "base_commit": "abc123..."
  },
  
  "roles": {
    "implementer": "qwen2.5-coder:14b",
    "local_reviewer": "deepseek-r1:7b",
    "judge": "claude-code-cli"
  },
  
  "limits": {
    "max_rebuttals": 2,
    "max_review_cycles": 5,
    "timeout_minutes": {
      "implementer": 10,
      "local_review": 15,
      "judge": 15
    },
    "token_budget": 50000,
    "cost_ceiling_usd": 0.50
  },
  
  "constraints": {
    "allowed_paths": ["docs/", "README.md"],
    "forbidden_paths": [".env", "secrets/", "AGENTS.md"],
    "allowed_operations": ["edit", "create"],
    "delete_allowed": false,
    "max_diff_lines": 200
  },
  
  "specification": {
    "source_files": [
      {"path": "docs/auth_v1.md", "sha256": "abc123..."},
      {"path": "docs/auth_v2.md", "sha256": "def456..."}
    ],
    "target_file": "docs/auth_final.md",
    "requirements": [
      "Merge authentication logic from both sources",
      "Standardize heading hierarchy: H1 → H2 → H3",
      "Preserve all internal wiki-links",
      "No placeholder text (Lorem Ipsum, TODO, FIXME)"
    ],
    "acceptance_criteria": [
      "All internal links resolve",
      "Heading structure validated",
      "Word count within 20% of combined sources"
    ]
  },
  
  "handoff_data": {
    "implementer_notes": "",
    "changed_files": [],
    "diff_summary": "",
    "local_review_passed": null,
    "local_review_issues": [],
    "judge_report_path": "_handoff/JUDGE_REPORT.md",
    "judge_report_json": "_handoff/JUDGE_REPORT.json",
    "rebuttal_path": "_handoff/REBUTTAL.md"
  },
  
  "lock": {
    "held_by": null,
    "acquired_at": null,
    "expires_at": null
  },
  
  "breaker": {
    "status": "armed",
    "triggered_by": null,
    "trigger_reason": null,
    "rebuttal_count": 0,
    "review_cycle_count": 0,
    "tokens_used": 0,
    "cost_usd": 0.00
  },
  
  "history": []
}
```

### Complexity Levels
| Level | Max Rebuttals | Max Review Cycles | Cost Ceiling | Description |
|-------|--------------|-------------------|--------------|-------------|
| `trivial` | 1 | 2 | $0.25 | Typo fixes, formatting |
| `minor` | 2 | 5 | $0.50 | Doc merges, small features |
| `major` | 4 | 8 | $2.00 | Architectural changes, multi-file refactors |
| `critical` | 6 | 10 | $5.00 | Security-sensitive, breaking changes |

---

## 3. The Handoff Files (`_handoff/`)

All handoff files live in `_handoff/` at the project root. **This directory is `.gitignore`d.**

| File | Purpose | Written By | Read By |
|------|---------|-----------|---------|
| `PROPOSAL_FINAL.md` | **TRIGGER:** Approved proposal ready for execution | Super Manager (Claude CLI) | Floor Manager (Cursor) |
| `PROPOSAL_REJECTED.md` | Floor Manager rejects malformed/vague proposal | Floor Manager | Super Manager (revises) |
| `TASK_CONTRACT.json` | Source of truth | Floor Manager (creates from proposal), All (updates) | All |
| `TASK_CONTRACT.json.lock` | Halt state indicator | Watchdog | Erik |
| `REVIEW_REQUEST.md.tmp` → `REVIEW_REQUEST.md` | Signals Judge to wake | Watchdog | Watcher loop |
| `REVIEW_IN_PROGRESS.md` | Prevents double-trigger | Watcher loop | Watcher loop |
| `JUDGE_REPORT.md` | Human-readable verdict | Judge | Floor Manager, Erik |
| `JUDGE_REPORT.json` | Machine-readable verdict | Judge | Floor Manager |
| `REBUTTAL.md` | Floor Manager's disagreement | Floor Manager | Judge (re-review) |
| `STALL_REPORT.md` | Local model stall diagnosis (after 2 strikes) | Floor Manager | Erik |
| `ERIK_HALT.md` | Circuit breaker explanation | Any agent | Erik |
| `transition.ndjson` | Audit log of all transitions | Watchdog | Post-mortem |

### The Proposal Trigger

When `PROPOSAL_FINAL.md` appears in `_handoff/`, the Floor Manager (Cursor) is triggered to:

1. Read and parse the proposal
2. Convert it to a `TASK_CONTRACT.json`
3. Create the task branch in git
4. Set status to `pending_implementer`
5. Archive the proposal to `_handoff/archive/PROPOSAL_FINAL_{task_id}.md`

**Cursor Rules Hook:** Add this to `.cursorrules` in projects that use Agent Hub:

```
When you see _handoff/PROPOSAL_FINAL.md appear in this project:
1. You are the Floor Manager. Read the proposal carefully.
2. Convert it to a TASK_CONTRACT.json following the schema in agent-hub/Documents/Agentic Blueprint Setup V2.md
3. Do NOT implement anything yourself - that's the Implementer's job.
4. After creating the contract, archive the proposal and begin the pipeline.
```

### Atomic Write Protocol
**Never write directly to final filenames.** Always:
1. Write to `FILENAME.tmp`
2. `mv FILENAME.tmp FILENAME` (atomic on POSIX)

This prevents partial reads by watchers.

---

## 4. The State Machine (Control Plane)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           STATE MACHINE V2                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ════════════════════ PROPOSAL PHASE (Pre-Pipeline) ═══════════════════ │
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │ Erik + Super     │ ─── Collaborate on proposal ───►                  │
│  │ Manager (Claude) │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ PROPOSAL_FINAL   │ ─── Written to _handoff/ ───►                     │
│  │ .md created      │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ Floor Manager    │ ─── Detects file, creates contract ───►           │
│  │ (Cursor) TRIGGER │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│  ════════════════════ EXECUTION PHASE (Pipeline) ══════════════════════ │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ pending_         │ ─── Watchdog acquires lock ───►                   │
│  │ implementer      │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ implementation_  │ ─── Ollama writes code ───►                       │
│  │ in_progress      │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ├─── timeout ───► [timeout_implementer] ───► erik_consultation│
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ pending_local_   │ ─── DeepSeek reviews ───►                         │
│  │ review           │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ├─── CRITICAL_FLAW ───► erik_consultation                     │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ pending_judge_   │ ─── Creates REVIEW_REQUEST.md ───►                │
│  │ review           │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ judge_review_    │ ─── Claude audits ───►                            │
│  │ in_progress      │                                                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ├─── timeout ───► [timeout_judge] ───► erik_consultation      │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │ review_complete  │ ─── Floor Manager analyzes ───►                   │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ├─── PASS ───► [merged] ───► DONE                             │
│           │                                                             │
│           ├─── FAIL (agree) ───► pending_implementer (new attempt)      │
│           │                                                             │
│           ├─── FAIL (disagree) ───► pending_rebuttal                    │
│           │                                                             │
│           └─── CONDITIONAL ───► pending_implementer (minor fixes)       │
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │ pending_rebuttal │ ─── Floor Manager writes REBUTTAL.md ───►         │
│  └──────────────────┘                                                   │
│           │                                                             │
│           ├─── rebuttal_count > max ───► erik_consultation              │
│           │                                                             │
│           └─── rebuttal accepted ───► pending_judge_review              │
│                                                                         │
│  ════════════════════════════════════════════════════════════════════   │
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │ erik_consultation│ ─── HALT. Human required. ───► (manual)           │
│  └──────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Transition Rules (Idempotent)

Each transition is a pure function: `new_state = transition(current_state, event, contract)`

```python
def transition(state: str, event: str, contract: dict) -> tuple[str, str]:
    """Returns (new_status, status_reason). Raises if invalid."""
    
    transitions = {
        ("pending_implementer", "lock_acquired"): 
            ("implementation_in_progress", "Implementer working"),
        ("implementation_in_progress", "code_written"): 
            ("pending_local_review", "Awaiting local syntax check"),
        ("implementation_in_progress", "timeout"): 
            ("timeout_implementer", "Implementer exceeded time limit"),
        ("pending_local_review", "local_pass"): 
            ("pending_judge_review", "Local review passed"),
        ("pending_local_review", "critical_flaw"): 
            ("erik_consultation", "Local reviewer found critical security flaw"),
        # ... etc
    }
    
    key = (state, event)
    if key not in transitions:
        raise InvalidTransition(f"Cannot {event} from {state}")
    
    return transitions[key]
```

---

## 5. The Circuit Breaker (V2 - Observable)

### Trigger Conditions

| # | Trigger | Detection | Action |
|---|---------|-----------|--------|
| 1 | **Rebuttal Limit Exceeded** | `breaker.rebuttal_count > limits.max_rebuttals` | Halt |
| 2 | **Destructive Diff** | `diff_lines_deleted / total_lines > constraints.max_delete_ratio` | Halt |
| 3 | **Logical Paradox** | Judge=PASS but Local Reviewer=CRITICAL_FLAW | Halt |
| 4 | **Hallucination Loop** | Code reverted to previously rejected version (hash match) | Halt |
| 5 | **GPT-Energy Nitpicking** | 3+ review cycles with only style/formatting issues | Halt |
| 6 | **Timeout** | Any phase exceeds `limits.timeout_minutes.*` | Halt |
| 7 | **Budget Exceeded** | `breaker.cost_usd > limits.cost_ceiling_usd` | Halt |
| 8 | **Scope Creep** | `len(changed_files)` exceeds expected or touches forbidden paths | Halt |
| 9 | **Review Cycle Limit** | `breaker.review_cycle_count > limits.max_review_cycles` | Halt |

### Halt Protocol

When any trigger fires:

1. **Detect:** Agent or Watchdog identifies the condition
2. **Update Contract:**
   ```json
   {
     "status": "erik_consultation",
     "status_reason": "Rebuttal limit exceeded (3/2)",
     "breaker": {
       "status": "tripped",
       "triggered_by": "rebuttal_limit",
       "trigger_reason": "Floor Manager and Judge disagree on heading hierarchy"
     }
   }
   ```
3. **Lock Contract:** Rename to `TASK_CONTRACT.json.lock`
4. **Write Halt File:** Create `_handoff/ERIK_HALT.md`:

```markdown
# 🛑 AUTOMATION HALTED

**Task:** DOC-001-AUTH-MERGE  
**Trigger:** Rebuttal Limit Exceeded  
**Time:** 2026-01-16T13:45:00Z

## The Conflict

Floor Manager (Gemini) and Judge (Claude) have disagreed 3 times on this task.

**Gemini's Position:** "H2 headings should be used for major sections"
**Claude's Position:** "H3 headings maintain consistency with other project docs"

## The Two Paths

1. **Accept Gemini's interpretation:** Approve REBUTTAL.md, override Judge
2. **Accept Claude's interpretation:** Reject rebuttal, accept JUDGE_REPORT recommendations

## Current State

- Branch: `task/DOC-001-AUTH-MERGE`
- Files changed: `docs/auth_final.md`
- Diff: +145 lines, -12 lines

## Action Required

Edit this file with your decision, then run:
```bash
./watchdog.py resume DOC-001-AUTH-MERGE --decision [gemini|claude]
```
```

---

## 6. The Judge Output (Structured)

The Judge **must** produce both files:

### `JUDGE_REPORT.md` (Human-Readable)

```markdown
# Judge Report: DOC-001-AUTH-MERGE

**Verdict:** CONDITIONAL  
**Date:** 2026-01-16T13:30:00Z

## Summary

The merged document captures the core authentication logic but has structural issues.

## Blocking Issues

1. **Heading hierarchy violation** (Line 45): H4 used without parent H3
2. **Broken link** (Line 78): `[[login-flow]]` target does not exist

## Non-Blocking Suggestions

- Consider adding a table of contents
- Line 102 could be more concise

## Recommendation

Fix the 2 blocking issues. No full re-review needed; Floor Manager can verify fixes.
```

### `JUDGE_REPORT.json` (Machine-Readable)

```json
{
  "task_id": "DOC-001-AUTH-MERGE",
  "timestamp": "2026-01-16T13:30:00Z",
  "verdict": "CONDITIONAL",
  "blocking_issues": [
    {
      "id": "BI-001",
      "severity": "HIGH",
      "file": "docs/auth_final.md",
      "line": 45,
      "description": "H4 used without parent H3",
      "fix_required": true
    },
    {
      "id": "BI-002", 
      "severity": "MEDIUM",
      "file": "docs/auth_final.md",
      "line": 78,
      "description": "Broken internal link: [[login-flow]]",
      "fix_required": true
    }
  ],
  "suggestions": [
    {
      "id": "SG-001",
      "description": "Add table of contents",
      "fix_required": false
    }
  ],
  "security_flags": [],
  "requires_re_review": false,
  "tokens_used": 2340
}
```

### Verdict Values

| Verdict | Meaning | Floor Manager Action |
|---------|---------|---------------------|
| `PASS` | All requirements met | Merge branch to main |
| `CONDITIONAL` | Minor fixes needed, no re-review | Fix and merge |
| `FAIL` | Blocking issues require re-implementation | Create refinement contract |
| `CRITICAL_HALT` | Security/integrity issue | Trigger circuit breaker |

---

## 7. The Watcher Implementation (Corrected)

### Bash Watcher Loop (Owns the Loop)

```bash
#!/bin/bash
# watcher.sh - Runs in dedicated terminal

HANDOFF_DIR="_handoff"
POLL_INTERVAL=5
MAX_JUDGE_TIME=900  # 15 minutes

while true; do
  # Check for review request (atomic: only process if fully written)
  if [ -f "$HANDOFF_DIR/REVIEW_REQUEST.md" ] && \
     [ ! -f "$HANDOFF_DIR/REVIEW_IN_PROGRESS.md" ]; then
    
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) 🔍 Review request detected"
    
    # Atomically claim the request
    mv "$HANDOFF_DIR/REVIEW_REQUEST.md" "$HANDOFF_DIR/REVIEW_IN_PROGRESS.md"
    
    # Run Claude ONCE (no looping inside Claude)
    timeout $MAX_JUDGE_TIME claude --dangerously-skip-permissions \
      "You are the Judge. Read _handoff/TASK_CONTRACT.json. Review the files in handoff_data.changed_files against the specification.requirements and acceptance_criteria. Write your findings to _handoff/JUDGE_REPORT.md.tmp and _handoff/JUDGE_REPORT.json.tmp. When complete, exit immediately."
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 124 ]; then
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ⏰ Judge timeout"
      # Update contract status to timeout_judge
      python3 watchdog.py timeout-judge
    else
      # Atomically publish results
      mv "$HANDOFF_DIR/JUDGE_REPORT.md.tmp" "$HANDOFF_DIR/JUDGE_REPORT.md" 2>/dev/null
      mv "$HANDOFF_DIR/JUDGE_REPORT.json.tmp" "$HANDOFF_DIR/JUDGE_REPORT.json" 2>/dev/null
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ✅ Judge report written"
    fi
    
    # Cleanup
    rm -f "$HANDOFF_DIR/REVIEW_IN_PROGRESS.md"
  fi
  
  sleep $POLL_INTERVAL
done
```

### Python Watchdog (State Machine Manager)

```python
#!/usr/bin/env python3
"""watchdog.py - Manages state transitions and circuit breakers"""

import json
import os
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path

HANDOFF_DIR = Path("_handoff")
CONTRACT_PATH = HANDOFF_DIR / "TASK_CONTRACT.json"
TRANSITION_LOG = HANDOFF_DIR / "transition.ndjson"

def load_contract() -> dict:
    with open(CONTRACT_PATH) as f:
        return json.load(f)

def save_contract(contract: dict):
    """Atomic write"""
    contract["timestamps"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = CONTRACT_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(contract, f, indent=2)
    tmp.rename(CONTRACT_PATH)

def log_transition(contract: dict, event: str, old_status: str):
    """Append to NDJSON audit log"""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": contract["task_id"],
        "event": event,
        "old_status": old_status,
        "new_status": contract["status"],
        "attempt": contract["attempt"]
    }
    with open(TRANSITION_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def acquire_lock(contract: dict, actor: str) -> bool:
    """Try to acquire lock. Returns False if already held."""
    lock = contract.get("lock", {})
    if lock.get("held_by") and lock.get("expires_at"):
        expires = datetime.fromisoformat(lock["expires_at"])
        if datetime.now(timezone.utc) < expires:
            return False  # Lock still valid
    
    # Acquire lock
    now = datetime.now(timezone.utc)
    contract["lock"] = {
        "held_by": actor,
        "acquired_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=contract["limits"]["timeout_minutes"]["implementer"])).isoformat()
    }
    return True

def check_circuit_breakers(contract: dict) -> tuple[bool, str]:
    """Returns (should_halt, reason)"""
    breaker = contract["breaker"]
    limits = contract["limits"]
    
    if breaker["rebuttal_count"] > limits["max_rebuttals"]:
        return True, f"Rebuttal limit exceeded ({breaker['rebuttal_count']}/{limits['max_rebuttals']})"
    
    if breaker["review_cycle_count"] > limits["max_review_cycles"]:
        return True, f"Review cycle limit exceeded"
    
    if breaker.get("cost_usd", 0) > limits.get("cost_ceiling_usd", float("inf")):
        return True, f"Cost ceiling exceeded (${breaker['cost_usd']:.2f})"
    
    return False, ""

def trigger_halt(contract: dict, reason: str, triggered_by: str):
    """Halt automation and notify Erik"""
    old_status = contract["status"]
    contract["status"] = "erik_consultation"
    contract["status_reason"] = reason
    contract["breaker"]["status"] = "tripped"
    contract["breaker"]["triggered_by"] = triggered_by
    contract["breaker"]["trigger_reason"] = reason
    
    save_contract(contract)
    log_transition(contract, "circuit_breaker_tripped", old_status)
    
    # Rename to .lock
    CONTRACT_PATH.rename(CONTRACT_PATH.with_suffix(".json.lock"))
    
    # Write ERIK_HALT.md
    write_halt_file(contract, reason)

def run_implementer(contract: dict):
    """Dispatch to Ollama for implementation"""
    model = contract["roles"]["implementer"]
    spec = contract["specification"]
    
    prompt = f"""You are the Implementer. Your task:

Task ID: {contract['task_id']}
Target file: {spec['target_file']}

Requirements:
{chr(10).join(f"- {r}" for r in spec['requirements'])}

Source files to merge:
{chr(10).join(f"- {s['path']}" for s in spec['source_files'])}

Constraints:
- Only edit files in: {contract['constraints']['allowed_paths']}
- Do NOT touch: {contract['constraints']['forbidden_paths']}
- Deletions allowed: {contract['constraints']['delete_allowed']}

Write the merged content directly to {spec['target_file']}.
When done, output only: IMPLEMENTATION_COMPLETE
"""
    
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=contract["limits"]["timeout_minutes"]["implementer"] * 60
    )
    
    return "IMPLEMENTATION_COMPLETE" in result.stdout

# ... additional handlers for each state
```

---

## 8. Git Integration (Branch-Per-Task)

Every task runs in isolation:

```bash
# On task creation
git checkout main
git pull origin main
git checkout -b task/DOC-001-AUTH-MERGE

# After each state transition (checkpoint)
git add -A
git commit -m "checkpoint: ${STATUS} - ${STATUS_REASON}"

# On PASS verdict
git checkout main
git merge --no-ff task/DOC-001-AUTH-MERGE -m "Merge: DOC-001-AUTH-MERGE"
git push origin main
git branch -d task/DOC-001-AUTH-MERGE

# On FAIL or halt (rollback available)
git log --oneline task/DOC-001-AUTH-MERGE  # See all checkpoints
git reset --hard <checkpoint-commit>        # Rollback to any state
```

---

## 9. The "Golden Document" Definition

A document is **Golden** when:

1. ✅ **Judge verdict:** `PASS` or `CONDITIONAL` (with fixes applied)
2. ✅ **All internal links resolve** (validated by script)
3. ✅ **No placeholder text:** No `TODO`, `FIXME`, `Lorem Ipsum`, `TBD`
4. ✅ **Heading hierarchy valid:** No skipped levels (H1 → H3 without H2)
5. ✅ **Merged to main:** Exists on the `main` branch
6. ✅ **Indexed:** Listed in project's `00_Index.md` or `README.md`

---

## 10. Observability & Logging

### Transition Log (`_handoff/transition.ndjson`)

Every state change appends a line:

```json
{"timestamp":"2026-01-16T12:00:00Z","task_id":"DOC-001","event":"created","old_status":null,"new_status":"pending_implementer","attempt":1}
{"timestamp":"2026-01-16T12:01:00Z","task_id":"DOC-001","event":"lock_acquired","old_status":"pending_implementer","new_status":"implementation_in_progress","attempt":1}
{"timestamp":"2026-01-16T12:05:00Z","task_id":"DOC-001","event":"code_written","old_status":"implementation_in_progress","new_status":"pending_local_review","attempt":1}
```

### Metrics to Track

| Metric | Purpose |
|--------|---------|
| `time_in_state_seconds` | Detect stuck processes |
| `tokens_per_task` | Cost optimization |
| `attempts_to_pass` | Implementer quality |
| `rebuttal_rate` | Floor Manager/Judge alignment |
| `halt_frequency` | System reliability |

---

## 11. Implementation Checklist

- [ ] Create `_handoff/` directory at project root
- [ ] Add `_handoff/` to `.gitignore`
- [ ] Implement `TASK_CONTRACT.json` schema validation
- [ ] Write `watchdog.py` state machine
- [ ] Write `watcher.sh` for Claude CLI loop
- [ ] Test atomic write protocol
- [ ] Set up branch-per-task git workflow
- [ ] Configure Ollama models (Qwen, DeepSeek)
- [ ] Create Judge prompt template
- [ ] Test circuit breakers with mock failures
- [ ] Set up NDJSON log rotation

---

## 12. Quick Reference: CLI Commands

```bash
# Start the watcher (dedicated terminal)
./watcher.sh

# Create a new task
python watchdog.py create --project Project-A --spec "Merge auth docs"

# Check task status
python watchdog.py status DOC-001-AUTH-MERGE

# Resume from halt
python watchdog.py resume DOC-001-AUTH-MERGE --decision gemini

# Force halt (manual circuit breaker)
python watchdog.py halt DOC-001-AUTH-MERGE --reason "Need to reconsider approach"

# View transition log
tail -f _handoff/transition.ndjson | jq .
```

---

*V2 incorporates feedback from Claude Code Review, GPT-4 Analysis, and Codex Recommendations. Ready for implementation.*
