# PRD: Agent Hub - Autonomous Multi-Agent Pipeline

**Version:** 1.0  
**Status:** Draft  
**Author:** Erik Sjaastad + Claude (Super Manager)  
**Created:** 2026-01-16  
**Last Updated:** 2026-01-16

---

## 1. Problem Statement

### The Pain

Erik manages 30+ projects across a complex ecosystem. Documentation is fragmented, duplicated, and inconsistent. AI assistants can help, but the current workflow is:

1. **Manual copy-paste orchestration** - Erik is the message bus between AI tools
2. **No memory between sessions** - Each AI starts fresh, losing context
3. **Expensive cloud overuse** - Every task goes to expensive models, even trivial file operations
4. **No quality gates** - AI outputs go straight to production with no review
5. **Infinite loops possible** - AI can argue with itself forever, or silently regress

### The Cost of Doing Nothing

- **Time:** 2-4 hours/day spent babysitting AI handoffs
- **Money:** Unnecessary cloud API costs for tasks local models could handle
- **Quality:** Inconsistent documentation, broken links, orphaned files
- **Sanity:** Context-switching between tools destroys flow state

### Why Now?

Local models (Qwen 2.5, DeepSeek) are now good enough for implementation grunt work. The missing piece is **orchestration** - a system that coordinates cheap local execution with expensive cloud intelligence.

---

## 2. Goals & Success Metrics

### Primary Goal

Build an autonomous pipeline where Erik collaborates with a **Super Manager** (Claude CLI) to draft proposals, and the system produces a reviewed, merged deliverable with **zero copy-paste between tools**.

### Success Metrics

| Metric | Baseline (Current) | Target (V1) | Stretch (V2) |
|--------|-------------------|-------------|--------------|
| Manual handoffs per task | 5-10 | 0 | 0 |
| Time to merge a doc task | 45 min | 15 min | 5 min |
| Cost per task (tokens) | $0.50+ | $0.10 | $0.05 |
| Tasks requiring Erik intervention | 100% | <20% | <5% |
| Automation halt rate (circuit breakers) | N/A | <10% | <5% |

### Definition of Done (V1)

- [ ] A task can be created via CLI (`python watchdog.py create --spec "..."`)
- [ ] Implementer (local model) writes code without Erik pasting prompts
- [ ] Local Reviewer catches obvious bugs before cloud review
- [ ] Judge (Claude CLI) produces structured verdict
- [ ] Floor Manager merges or loops based on verdict
- [ ] Circuit breakers halt on edge cases and notify Erik
- [ ] Full audit trail exists in `transition.ndjson`

---

## 3. User Stories

### Epic: Task Lifecycle

> **As Erik, I want to** collaborate with an AI partner to define tasks  
> **So that** the pipeline produces reviewed, merged deliverables without me babysitting handoffs.

#### Story 0: Proposal Drafting (NEW)
> **As Erik**, I want to work with a Super Manager (Claude CLI) to draft proposals  
> **So that** I have a strategic partner who understands my ecosystem and helps me think through tasks.

**Acceptance Criteria:**
- Claude CLI acts as Super Manager when invoked for planning
- We collaborate to refine scope, requirements, and acceptance criteria
- When I approve, Super Manager writes `PROPOSAL_FINAL.md` to `_handoff/`
- This file triggers the Floor Manager (Cursor) to take over

#### Story 1: Proposal → Contract Conversion
> **As the Floor Manager**, I want to detect `PROPOSAL_FINAL.md` and convert it to a contract  
> **So that** the pipeline starts automatically without Erik pasting anything.

**Acceptance Criteria:**
- Floor Manager reads and understands the proposal requirements
- Decomposes large tasks into right-sized chunks for local models
- Knows when to use Qwen (fast coding) vs DeepSeek (reasoning)
- Creates one or more `TASK_CONTRACT.json` based on complexity
- Sets appropriate `timeout_minutes` based on model capabilities
- On local model stall: diagnoses cause, reworks contract, retries (Strike 1)
- On second stall: stops work, writes `STALL_REPORT.md`, escalates to Erik (Strike 2)

**Acceptance Criteria:**
- CLI accepts `--project`, `--spec`, and optional `--complexity`
- Contract is created with unique `task_id` and `pending_implementer` status
- Task branch is created in git (`task/<task_id>`)

#### Story 2: Autonomous Implementation
> **As the system**, I want the Implementer to work without human prompting  
> **So that** Erik doesn't have to copy-paste between tools.

**Acceptance Criteria:**
- Watchdog detects `pending_implementer` status
- Ollama is invoked with contract specification
- Output is written directly to target files (not `WORK_OUTPUT.md`)
- Status transitions to `pending_local_review`

#### Story 3: Two-Tier Review
> **As Erik**, I want cheap local review before expensive cloud review  
> **So that** obvious errors are caught without burning Claude tokens.

**Acceptance Criteria:**
- Local Reviewer (DeepSeek) runs syntax/security checks
- Critical flaws trigger immediate halt (no cloud review)
- Minor issues are passed to contract for Judge context

#### Story 4: Structured Verdicts
> **As the Floor Manager**, I want machine-readable Judge output  
> **So that** I can route tasks without parsing prose.

**Acceptance Criteria:**
- Judge produces both `JUDGE_REPORT.md` (human) and `JUDGE_REPORT.json` (machine)
- Verdict is one of: `PASS`, `CONDITIONAL`, `FAIL`, `CRITICAL_HALT`
- Blocking issues have `id`, `severity`, `file`, `line`, `description`

#### Story 5: Circuit Breakers
> **As Erik**, I want automation to halt on edge cases  
> **So that** I don't come back to a disaster.

**Acceptance Criteria:**
- Rebuttal limit exceeded → halt
- Destructive diff (>5% deletion) → halt
- Timeout (>10 min in any phase) → halt
- Logical paradox (Judge PASS + Local CRITICAL) → halt
- `ERIK_HALT.md` is created with context and resolution options

#### Story 6: Audit Trail
> **As Erik**, I want to see exactly what happened on any task  
> **So that** I can debug failures and learn from patterns.

**Acceptance Criteria:**
- Every state transition logged to `transition.ndjson`
- Each entry includes `timestamp`, `task_id`, `event`, `old_status`, `new_status`
- Contract `history` array preserves full evolution

---

## 4. Functional Requirements

### MUST Have (V1 MVP)

| ID | Requirement |
|----|-------------|
| FR-00 | Floor Manager MUST detect `PROPOSAL_FINAL.md` in `_handoff/` and convert to contract |
| FR-01 | Super Manager (Claude CLI) MUST be able to write `PROPOSAL_FINAL.md` to trigger pipeline |
| FR-02 | System MUST invoke local Ollama models for implementation |
| FR-03 | System MUST invoke Claude CLI for architectural review |
| FR-04 | System MUST produce structured JSON verdict from Judge |
| FR-05 | System MUST halt on circuit breaker conditions |
| FR-05a | Floor Manager MUST diagnose and rework contracts on first local model stall (Strike 1) |
| FR-05b | Floor Manager MUST escalate to Erik with `STALL_REPORT.md` on second stall (Strike 2) |
| FR-06 | System MUST create `ERIK_HALT.md` when halted |
| FR-07 | System MUST log all state transitions to NDJSON |
| FR-08 | System MUST use atomic file writes (temp → rename) |
| FR-09 | System MUST isolate tasks to git branches |
| FR-10 | System MUST merge to main only on PASS verdict |

### SHOULD Have (V1.1)

| ID | Requirement |
|----|-------------|
| FR-11 | System SHOULD support parallel tasks across different projects |
| FR-12 | System SHOULD track token usage per task |
| FR-13 | System SHOULD support complexity-based rebuttal limits |
| FR-14 | System SHOULD send notifications on halt (email/webhook) |
| FR-15 | System SHOULD provide a `status` command showing all active tasks |

### MAY Have (V2)

| ID | Requirement |
|----|-------------|
| FR-16 | System MAY support filesystem watchers instead of polling |
| FR-17 | System MAY provide a web dashboard for task monitoring |
| FR-18 | System MAY support custom Judge prompts per project |
| FR-19 | System MAY auto-learn from rebuttal patterns |

---

## 5. Non-Functional Requirements

### Performance

| ID | Requirement |
|----|-------------|
| NFR-01 | Watchdog polling interval ≤ 5 seconds |
| NFR-02 | State transitions complete in < 1 second |
| NFR-03 | Local model invocation timeout ≤ 10 minutes |
| NFR-04 | Cloud model (Judge) timeout ≤ 15 minutes |

### Reliability

| ID | Requirement |
|----|-------------|
| NFR-05 | System MUST survive watchdog restart without data loss |
| NFR-06 | System MUST detect and recover from partial file writes |
| NFR-07 | System MUST prevent concurrent modifications via locks |
| NFR-08 | System MUST log all failures with stack traces |

### Security

| ID | Requirement |
|----|-------------|
| NFR-09 | Local Reviewer MUST flag hardcoded secrets |
| NFR-10 | Implementer MUST NOT touch `forbidden_paths` |
| NFR-11 | Contract MUST specify `allowed_paths` explicitly |
| NFR-12 | No API keys in source code (use `.env`) |

### Observability

| ID | Requirement |
|----|-------------|
| NFR-13 | All state transitions logged with timestamps |
| NFR-14 | Token/cost tracking per task |
| NFR-15 | Circuit breaker triggers logged with reason |
| NFR-16 | Transition log rotated daily |

---

## 6. Out of Scope (V1)

The following are **explicitly NOT** part of this project:

| Item | Reason |
|------|--------|
| Web UI / Dashboard | CLI-first; UI is V2 |
| Multi-user support | Erik-only system |
| Cloud deployment | Runs on Erik's Mac |
| Real-time notifications | Polling-based is fine for V1 |
| Natural language task creation | Structured CLI input for now |
| Cross-repo tasks | One repo per task in V1 |
| Automatic retry on transient failures | Manual resume via CLI |

---

## 7. Dependencies & Risks

### Dependencies

| Dependency | Risk Level | Mitigation |
|------------|------------|------------|
| Ollama running locally | Medium | Health check on watchdog start |
| Claude CLI installed | Medium | Check version on startup |
| Python 3.11+ | Low | Specified in requirements.txt |
| Swarm/LiteLLM | Medium | Already integrated in hub.py |
| Git | Low | Required for branch isolation |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Local model quality too low | Medium | High | Use Local Reviewer as safety net; escalate to cloud if needed |
| Claude CLI API changes | Low | High | Pin version; wrap in abstraction |
| Infinite loops not caught | Low | High | Multiple circuit breakers; hard timeout |
| File corruption from race condition | Medium | High | Atomic writes; lock mechanism |
| Context window overflow | Medium | Medium | Summarize history; limit contract size |

---

## 8. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         ERIK (Architect)                        │
│                    Vision, approval, resolves halts             │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Collaborates
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SUPER MANAGER (Claude CLI)                    │
│         Strategic partner, drafts proposals WITH Erik           │
│                                                                 │
│         Output: PROPOSAL_FINAL.md → _handoff/                   │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  │ File trigger
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLOOR MANAGER (Gemini/Cursor)                │
│     Detects PROPOSAL_FINAL.md → Understands task requirements   │
│     Decomposes into right-sized chunks for local models         │
│     Knows Qwen (fast coder) vs DeepSeek (strong reasoner)       │
│              Orchestrates, routes, decides merge/loop           │
└─────────────────────────────────────────────────────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────┐
│   IMPLEMENTER   │   │ LOCAL REVIEWER  │   │       JUDGE         │
│  (Ollama/Qwen)  │   │(Ollama/DeepSeek)│   │   (Claude CLI)      │
│                 │   │                 │   │                     │
│  Writes code    │   │ Syntax/security │   │ Deep architectural  │
│  to target files│   │ first-pass      │   │ review              │
└─────────────────┘   └─────────────────┘   └─────────────────────┘
          │                       │                       │
          └───────────────────────┴───────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TASK_CONTRACT.json                         │
│                    (Single Source of Truth)                     │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         WATCHDOG.py                             │
│              State machine, transitions, circuit breakers       │
└─────────────────────────────────────────────────────────────────┘
```

**Note:** Claude CLI serves TWO roles:
- **Super Manager mode:** Strategic planning with Erik (proposal phase)
- **Judge mode:** Architectural review of completed work (review phase)

---

## 9. Related Documents

| Document | Purpose |
|----------|---------|
| [Agentic Blueprint.md](Documents/Agentic%20Blueprint.md) | High-level vision and 4-phase pipeline |
| [Agentic Blueprint Setup V2.md](Documents/Agentic%20Blueprint%20Setup%20V2.md) | Detailed design: schema, state machine, circuit breakers |
| [TODO.md](TODO.md) | Implementation checklist |
| [hub.py](hub.py) | Existing foundation (Swarm + LiteLLM) |

### Required Skill (Agent Skills Library)

The Floor Manager's knowledge should be captured as a reusable skill:

| Component | Location |
|-----------|----------|
| **Skill** | `agent-skills-library/claude-skills/floor-manager-orchestration/SKILL.md` |
| **Playbook** | `agent-skills-library/playbooks/floor-manager-orchestration/README.md` |
| **Cursor Rules** | `agent-skills-library/cursor-rules/floor-manager-orchestration/rules.md` |

**Why:** The Floor Manager's knowledge (local model capabilities, task decomposition, stall recovery) is project-agnostic and benefits from accumulated learning. This skill gets loaded whenever Cursor acts as Floor Manager.

---

## 10. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Architect (Approval) | Erik Sjaastad | | |
| Super Manager (Author) | Claude | 2026-01-16 | ✓ |

---

*This PRD defines WHAT we're building and WHY. For HOW, see the [Agentic Blueprint Setup V2](Documents/Agentic%20Blueprint%20Setup%20V2.md).*
