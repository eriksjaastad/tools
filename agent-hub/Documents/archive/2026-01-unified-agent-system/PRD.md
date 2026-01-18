# PRD: Agent Hub - Autonomous Multi-Agent Pipeline

**Version:** 3.0
**Status:** Draft
**Author:** Erik Sjaastad + Claude (Super Manager)
**Created:** 2026-01-16
**Last Updated:** 2026-01-17
**Changelog:**
- V3.0 - Added V4 Sandbox Draft Pattern: local models can now edit files via sandboxed drafts with Floor Manager gating.
- V2.0 - Added V3 Direct Agent Communication (DAC) requirements, constrained messaging, heartbeat monitoring, MCP Hub architecture.

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
- When Erik says **"Write PROPOSAL_FINAL"** (formalized trigger phrase), Super Manager commits the proposal
- Super Manager writes `PROPOSAL_FINAL.md` to `_handoff/`
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
| FR-00a | Floor Manager MUST write `PROPOSAL_REJECTED.md` if proposal is malformed/vague (with specific issues) |
| FR-01 | Super Manager (Claude CLI) MUST write `PROPOSAL_FINAL.md` when Erik says "Write PROPOSAL_FINAL" |
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
| FR-13 | System SHOULD support complexity-based rebuttal limits AND cost ceilings ($0.25-$5.00) |
| FR-14 | System SHOULD send notifications on halt (email/webhook) |
| FR-15 | System SHOULD provide a `status` command showing all active tasks |

### MAY Have (V2)

| ID | Requirement |
|----|-------------|
| FR-16 | System MAY support filesystem watchers instead of polling |
| FR-17 | System MAY provide a web dashboard for task monitoring |
| FR-18 | System MAY support custom Judge prompts per project |
| FR-19 | System MAY auto-learn from rebuttal patterns |

### V3 Direct Agent Communication (DAC) Requirements

These requirements define the MCP-based messaging layer that replaces file polling.

#### Messaging Infrastructure

| ID | Requirement |
|----|-------------|
| FR-20 | System MUST provide an MCP Hub (`claude-mcp`) as the central message bus |
| FR-21 | Agents MUST use `send_message(recipient, payload)` for inter-agent communication |
| FR-22 | Agents MUST use `receive_message()` to check for incoming signals |
| FR-23 | System MUST support `open_negotiation_channel(task_id)` for multi-turn planning |
| FR-24 | Message delivery latency MUST be < 100ms (direct invocation, not polling) |

#### Constrained Message Types

| ID | Requirement |
|----|-------------|
| FR-25 | System MUST enforce a fixed menu of message types (no freeform agent-to-agent prompts) |
| FR-26 | Valid message types: `PROPOSAL_READY`, `REVIEW_NEEDED`, `STOP_TASK`, `QUESTION`, `ANSWER`, `VERDICT_SIGNAL`, `HEARTBEAT`, `DRAFT_READY`, `DRAFT_ACCEPTED`, `DRAFT_REJECTED`, `DRAFT_ESCALATED` |
| FR-27 | `QUESTION` messages MUST include 2-4 predefined options (agent cannot ask open-ended questions) |
| FR-28 | `ANSWER` messages MUST reference the original question and selected option |
| FR-29 | Floor Manager MUST NOT send arbitrary prompts to Super Manager/Judge |

#### Heartbeat Monitoring (Replaces Hard Time Limits)

| ID | Requirement |
|----|-------------|
| FR-30 | All agents in `active` state MUST emit `HEARTBEAT` signals at configurable intervals |
| FR-31 | MCP Hub MUST detect agent stalls (no heartbeat for X minutes) |
| FR-32 | On stall detection, Hub MUST notify Erik via CLI alert or system notification |
| FR-33 | Heartbeat SHOULD include progress indicator (e.g., "reviewing file 3/7") |
| FR-34 | Stall detection replaces hard timeouts as primary liveness check |

#### Negotiation Protocol

| ID | Requirement |
|----|-------------|
| FR-35 | Super Manager and Floor Manager MUST negotiate before finalizing contracts |
| FR-36 | Negotiation channel preserves context for multi-turn clarification |
| FR-37 | Contract creation happens ONLY after negotiation concludes |
| FR-38 | Either party MAY request clarification via `QUESTION` message |

#### Migration Path (Backward Compatibility)

| ID | Requirement |
|----|-------------|
| FR-39 | Phase 7.1 (Mailbox): File polling remains active alongside MCP messages |
| FR-40 | Phase 7.2 (Hotline): File signals deprecated, all transitions via MCP |
| FR-41 | `watchdog.py` transitions from driver to observer of MCP Hub |

### V4 Sandbox Draft Pattern Requirements

These requirements define controlled file editing for local models via sandboxed drafts.

#### Problem Solved

In Phase 10 testing, local models (DeepSeek) would overwrite entire files with hallucinated stubs instead of making targeted edits. The Sandbox Draft Pattern gives local models "hands" while keeping the Floor Manager as gatekeeper.

#### Draft Tools (Ollama MCP)

| ID | Requirement |
|----|-------------|
| FR-42 | System MUST provide `ollama_request_draft` to copy a file to sandbox |
| FR-43 | System MUST provide `ollama_write_draft` to edit draft content (sandbox only) |
| FR-44 | System MUST provide `ollama_read_draft` to read current draft |
| FR-45 | System MUST provide `ollama_submit_draft` to submit for Floor Manager review |
| FR-46 | Draft tools MUST validate all paths are within `_handoff/drafts/` |
| FR-47 | Draft tools MUST block path traversal attempts (`..`) |
| FR-48 | Draft tools MUST use atomic writes (tmp + rename) |

#### Draft Gate (Floor Manager)

| ID | Requirement |
|----|-------------|
| FR-49 | Floor Manager MUST handle `DRAFT_READY` messages from workers |
| FR-50 | Draft Gate MUST generate unified diff between original and draft |
| FR-51 | Draft Gate MUST detect secrets (API keys, passwords) and REJECT |
| FR-52 | Draft Gate MUST detect hardcoded user paths (`/Users/`, `/home/`) and REJECT |
| FR-53 | Draft Gate MUST escalate destructive diffs (>50% deletion) |
| FR-54 | Draft Gate MUST detect conflicts (original hash changed) and ESCALATE |
| FR-55 | Draft Gate MUST log all decisions to `transition.ndjson` |
| FR-56 | On ACCEPT: Floor Manager copies draft over original, cleans up sandbox |
| FR-57 | On REJECT: Floor Manager deletes draft, notifies worker with reason |
| FR-58 | On ESCALATE: Floor Manager notifies Super Manager/Erik for human review |

#### Sandbox Security Model

| ID | Requirement |
|----|-------------|
| FR-59 | Workers can ONLY write to `_handoff/drafts/` directory |
| FR-60 | Workers CANNOT delete files |
| FR-61 | Workers CANNOT execute shell commands |
| FR-62 | Sensitive files (`.env`, `credentials`, etc.) CANNOT be drafted |
| FR-63 | All draft operations MUST be logged with `SECURITY:` prefix on violations |

---

## 5. Non-Functional Requirements

### Performance

| ID | Requirement |
|----|-------------|
| NFR-01 | Watchdog polling interval ≤ 5 seconds (Phase 7.1 only) |
| NFR-01a | MCP message delivery latency < 100ms (Phase 7.2) |
| NFR-02 | State transitions complete in < 1 second |
| NFR-03 | Heartbeat interval: 30 seconds for active agents |
| NFR-03a | Stall detection threshold: 3 missed heartbeats (90 seconds) |
| NFR-04 | Hard timeout (fallback): 15 minutes if heartbeat system fails |

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

## 6. Out of Scope (V1/V2)

The following are **explicitly NOT** part of this project:

| Item | Reason | Status |
|------|--------|--------|
| Web UI / Dashboard | CLI-first | Future consideration |
| Multi-user support | Erik-only system | Not planned |
| Cloud deployment | Runs on Erik's Mac | Not planned |
| ~~Real-time notifications~~ | ~~Polling-based is fine for V1~~ | **IN SCOPE (V3)** - Heartbeat + stall alerts |
| Natural language task creation | Structured CLI input for now | Future consideration |
| Cross-repo tasks | One repo per task | Future consideration |
| Automatic retry on transient failures | Manual resume via CLI | Partial - negotiation handles some |
| Freeform agent-to-agent prompts | Security risk, unpredictable | **EXPLICITLY FORBIDDEN** |

---

## 7. Dependencies & Risks

### Dependencies

| Dependency | Risk Level | Mitigation |
|------------|------------|------------|
| Ollama running locally | Medium | Health check on watchdog start |
| Claude Code CLI | Medium | Check version on startup |
| Python 3.11+ | Low | Specified in requirements.txt |
| Swarm/LiteLLM | Medium | Already integrated in hub.py |
| Git | Low | Required for branch isolation |
| **claude-mcp server** | **High** | **Required for V3 messaging; fallback to file polling (V2 mode)** |
| Node.js 18+ | Low | Required for claude-mcp MCP server |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Local model quality too low | Medium | High | Use Local Reviewer as safety net; escalate to cloud if needed |
| Claude Code API changes | Low | High | Pin version; wrap in abstraction |
| Infinite loops not caught | Low | High | Heartbeat monitoring + hard timeout fallback |
| File corruption from race condition | Medium | High | Atomic writes; lock mechanism |
| Context window overflow | Medium | Medium | Summarize history; limit contract size |
| **MCP Hub crashes** | Low | **Critical** | **Auto-restart; fallback to V2 file polling** |
| **Heartbeat false positives** | Medium | Medium | **Tunable thresholds; require 3 missed beats** |
| **Agent sends malformed message** | Low | Medium | **Schema validation at Hub; reject invalid messages** |
| **Antigravity IDE limitations** | **High** | **High** | **Single Floor Manager only; no parallel agents in same IDE** |

---

## 8. Architecture Overview

### V3 Architecture (Direct Agent Communication)

```
┌─────────────────────────────────────────────────────────────────┐
│                         ERIK (Architect)                        │
│                    Vision, approval, resolves halts             │
└─────────────────────────────────────────────────────────────────┘
          │
          │ Collaborates (Claude Code CLI)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SUPER MANAGER (Claude Code)                   │
│         Strategic partner, drafts proposals WITH Erik           │
│         Negotiates with Floor Manager via MCP Hub               │
│                                                                 │
│         Output: PROPOSAL_FINAL.md + PROPOSAL_READY message      │
└─────────────────────────────────────────────────────────────────┘
          │                                               ▲
          │ MCP Message                                   │ MCP Message
          ▼                                               │
┌─────────────────────────────────────────────────────────────────┐
│                     ╔═══════════════════╗                       │
│                     ║   CLAUDE MCP HUB  ║                       │
│                     ║  (Message Bus)    ║                       │
│                     ║                   ║                       │
│                     ║  • send_message   ║                       │
│                     ║  • receive_message║                       │
│                     ║  • heartbeat      ║                       │
│                     ║  • negotiate      ║                       │
│                     ╚═══════════════════╝                       │
│                          THE CONTROL PLANE                      │
└─────────────────────────────────────────────────────────────────┘
          │                       │                       │
          │ MCP                   │ MCP                   │ MCP
          ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLOOR MANAGER (Gemini/Antigravity)           │
│     Receives PROPOSAL_READY → Negotiates if unclear             │
│     Decomposes into right-sized chunks for local models         │
│     Emits HEARTBEAT every 30s while active                      │
│     Sends REVIEW_NEEDED → Receives VERDICT_SIGNAL               │
│              Orchestrates, routes, decides merge/loop           │
└─────────────────────────────────────────────────────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────┐
│   IMPLEMENTER   │   │ LOCAL REVIEWER  │   │       JUDGE         │
│  (Ollama/Qwen)  │   │(Ollama/DeepSeek)│   │   (Claude Code)     │
│                 │   │                 │   │                     │
│  Writes code    │   │ Syntax/security │   │ Deep architectural  │
│  to target files│   │ first-pass      │   │ review              │
└─────────────────┘   └─────────────────┘   └─────────────────────┘
```

### Message Types (Constrained Protocol)

| Message | Sender | Receiver | Purpose |
|---------|--------|----------|---------|
| `PROPOSAL_READY` | Super Manager | Floor Manager | Proposal file ready for pickup |
| `QUESTION` | Any | Any | Request clarification (2-4 options required) |
| `ANSWER` | Any | Any | Response to question (must reference original) |
| `REVIEW_NEEDED` | Floor Manager | Judge | Implementation ready for review |
| `VERDICT_SIGNAL` | Judge | Floor Manager | Review complete (PASS/FAIL/CONDITIONAL) |
| `STOP_TASK` | Any | Floor Manager | Halt current task immediately |
| `HEARTBEAT` | Active Agent | Hub | "I'm alive and working on X" |
| `DRAFT_READY` | Worker | Floor Manager | Draft submitted for gate review (V4) |
| `DRAFT_ACCEPTED` | Floor Manager | Worker | Draft approved and applied (V4) |
| `DRAFT_REJECTED` | Floor Manager | Worker | Draft rejected with reason (V4) |
| `DRAFT_ESCALATED` | Floor Manager | Super Manager | Draft needs human review (V4) |

**Key Constraint:** Agents cannot send arbitrary prompts to each other. Communication is structured, predictable, and auditable.

**Note:** Claude Code serves TWO roles:
- **Super Manager mode:** Strategic planning with Erik (proposal phase)
- **Judge mode:** Architectural review of completed work (review phase)

### V4 Simplified Pipeline

The V4 architecture clarifies roles: **Floor Manager is a dispatcher, not a reviewer.**

```
┌─────────────────────────────────────────────────────────────┐
│                    V4 PIPELINE (SIMPLIFIED)                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Super Manager              Floor Manager        Workers    │
│  (Plans tasks)              (Dispatches)         (Ollama)   │
│       │                          │                  │       │
│       │  Task spec               │                  │       │
│       ├─────────────────────────▶│                  │       │
│       │                          │  ollama_agent_run│       │
│       │                          ├─────────────────▶│       │
│       │                          │                  │       │
│       │                          │◀─────────────────┤       │
│       │                          │  Draft in sandbox│       │
│       │                          │                  │       │
│       │                          │                  │       │
│  Claude (Judge)◀─────────────────┤                  │       │
│       │         Submission       │                  │       │
│       │                          │                  │       │
│       ├─────────────────────────▶│                  │       │
│       │  ACCEPT/REJECT           │                  │       │
│       │                          │                  │       │
│       │                          │  Apply changes   │       │
│       │                          ├─────────────────▶│       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Role Definitions (V4):**

| Role | Responsibility | Does NOT Do |
|------|----------------|-------------|
| **Super Manager** | Plans tasks, creates specs, works with Erik | Execute tasks |
| **Floor Manager** | Dispatches to Workers, collects drafts, routes to Claude | Review code, make judgments |
| **Workers (Ollama)** | Execute tasks, create drafts in sandbox | Write outside sandbox |
| **Claude (Judge)** | Reviews ALL submissions, ACCEPT/REJECT | Execute code |

**Key Principle:** Floor Manager is a relay. All review decisions flow through Claude.

---

## 9. Related Documents

| Document | Purpose |
|----------|---------|
| [Agentic Blueprint.md](Documents/Agentic%20Blueprint.md) | High-level vision and 4-phase pipeline |
| [Agentic Blueprint Setup V2.md](Documents/Agentic%20Blueprint%20Setup%20V2.md) | V2 design: file-based polling, schema, circuit breakers |
| [Agentic Blueprint Setup V3.md](Documents/Agentic%20Blueprint%20Setup%20V3.md) | V3 design: MCP Hub, direct messaging, heartbeats |
| [Agentic Blueprint Setup V4.md](Documents/Agentic%20Blueprint%20Setup%20V4.md) | **V4 design: Sandbox Draft Pattern, local model file editing** |
| [Direct_Communication_Protocol.md](Documents/Direct_Communication_Protocol.md) | Research doc: MCP as message bus |
| [TODO.md](TODO.md) | Implementation checklist |
| [hub.py](hub.py) | Existing foundation (Swarm + LiteLLM) |

### V4 Implementation Files

| File | Purpose |
|------|---------|
| `src/sandbox.py` | Path validation, security gatekeeper |
| `src/draft_gate.py` | Draft review logic (accept/reject/escalate) |
| `ollama-mcp/src/draft-tools.ts` | Ollama MCP draft tools |
| `ollama-mcp/src/sandbox-utils.ts` | TypeScript path validation |

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

*This PRD defines WHAT we're building and WHY. For HOW, see the [Agentic Blueprint Setup V4](Documents/Agentic%20Blueprint%20Setup%20V4.md) (current) or earlier versions for historical context.*
