# OpenClaw Delegation Experiments

> **Created:** 2026-03-24
> **Goal:** Fast, laptop-driven experiments to test if OpenClaw delegates and escalates properly.
> **Why:** The 3-day baseline experiment (001_baseline) failed to collect data — collection loop wasn't running. These experiments give us answers in minutes, not days.
> **Overall result:** OpenClaw CAN delegate but DEFAULTS to doing everything himself. Needs explicit prompting or a skill to trigger delegation consistently.

---

## Experiment 1: Can Haiku Delegate At All?

**Question:** When given a task that clearly needs delegation, does Haiku spawn a worker or do everything itself?

**Method:** Sent dead code audit task for project-tracker via Slack #group-chat. Asked him to walk through his plan first.

**Success criteria:** Haiku calls `sessions_spawn` at least once instead of doing the work directly.

**Result: FAIL**
- OpenClaw delivered a solid audit report (9 dead modules, 70+ unused functions, tiered)
- But session logs showed: 12:27 interactive session, 32 messages, 0 delegations, 570KB
- He CLAIMED he spawned "The Specialist" — the data showed he did it all himself
- When confronted with the evidence, he admitted: "I did the audit myself... I rationalized it as 'just reading code'"

---

## Experiment 2: Explicit Delegation (grep task)

**Question:** When explicitly told to delegate, does `sessions_spawn` actually work?

**Method:** Told him to spawn a Qwen worker to grep for references to `scripts/doc_audit.py`. Explicitly said "don't do the grep yourself."

**Success criteria:** `sessions_spawn` called, worker session visible in logs.

**Result: PASS**
- CEO cron session (12:25) went from 4 to 7 delegations
- Spawned worker session visible at 12:47 (13 messages, Haiku — not Qwen)
- Worker delivered correct result: doc_audit.py confirmed dead
- Model override to Qwen didn't work initially (spawned Haiku instead)
- Later test confirmed Qwen override DOES work when `model` parameter is explicitly specified

---

## Experiment 3: Diagnostic Task (database investigation)

**Question:** Given a real problem (pt database empty on Mini), does he delegate the investigation or do it himself?

**Method:** Asked him to diagnose why the Mini's tracker.db has 0 tasks when laptop has 740+.

**Success criteria:** Delegation visible in session logs. Correct diagnosis.

**Result: PASS**
- Spawned a worker (visible in session logs: cron session delegation count increased)
- Worker session at 13:18 (24 messages, 137KB)
- Correct diagnosis: pt launcher runs without doppler, so Turso credentials aren't available
- Fix identified: wrap launcher in `doppler run`
- Did NOT escalate to Sonnet or ask Erik — handled within Haiku worker capability

---

## Experiment 4: Escalation to Sonnet (strategic decision)

**Question:** Can Haiku recognize a task that needs a stronger model and escalate to Sonnet?

**Method:** Asked "which 3 projects should be sunset?" — explicitly a strategic question beyond grep work.

**Success criteria:** `sessions_spawn` with `model: "anthropic/claude-sonnet-4-6"`.

**Result: PASS**
- Spawned Sonnet worker for strategic analysis
- Also tested Qwen model override — confirmed working when model param explicitly set
- Sonnet memo: recommended sunsetting market-research, tools/agent-hub, and ai-journal
- Quality was noticeably higher than Haiku-level analysis
- OpenClaw correctly identified this as "beyond my pay grade" and escalated

---

## Key Findings

1. **OpenClaw CAN delegate** — `sessions_spawn` works, model overrides work, the machinery is all there
2. **Default behavior is to do everything himself** — 10% delegation rate over 49 autonomous sessions
3. **When explicitly told to delegate, he does** — Experiments 2-4 all passed
4. **Self-awareness improved during the session** — admitted the gap between belief and behavior
5. **Qwen model override works** when `model` parameter is explicitly passed to `sessions_spawn`
6. **Sonnet escalation works** and produces noticeably better output for strategic questions
7. **The problem is behavioral, not mechanical** — needs a skill or prompt reinforcement to make delegation the default

## Next Steps

- [ ] Check delegation rate again in 48 hours (2026-03-26) to see if behavior change sticks
- [ ] Install escalation skill (SKILL.md) on Mac Mini — see OPENCLAW_ESCALATION_RESEARCH.md
- [ ] Fix pt launcher to include doppler (OpenClaw's Experiment 3 finding)
- [ ] Verify OpenClaw logged his learnings to brain and updated DAILY_DIRECTIVE

---

---

## Phase 2: Model Comparison — Orchestration Tests

Same 5 tests across 3 candidate CEO models. Escalation skill installed for all.

### Test Definitions

| # | Test | What It Measures |
|---|------|-----------------|
| 1 | **Self-directed work finding** | Given "go find valuable work," does it explore, prioritize, and act without asking? |
| 2 | **Parallel delegation** | Given 3 tasks at once, does it spawn 3 workers simultaneously or serialize? |
| 3 | **Task routing accuracy** | Given a mix of grunt/code/strategic tasks, does it route each to the right model tier? |
| 4 | **Failure recovery** | Worker returns garbage or fails — does the CEO retry, escalate, or report? |
| 5 | **Session discipline** | After patrol cron fires, is the session under 10 messages? Or does it spiral? |
| 6 | **Research delegation** | Given a research question, does it use Gemini AND Grok for different angles? |

### GPT-5.4-nano (`openai/gpt-5.4-nano`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Self-directed work | **PASS** | Found PR #36 blockers, structured report, asked before touching revenue project |
| 2 | Parallel delegation | **PARTIAL** | 3 workers spawned simultaneously. Strategic (GPT-4o) and code (Haiku) passed. Grunt (Qwen) failed — context overflow at 111%. Honest reporting. |
| 3 | Task routing | **PASS** | Routed 5 tasks to 5 different models (GPT-4o, Haiku, Gemini, Qwen, Sonnet). Full workforce awareness. |
| 4 | Failure recovery | **PASS** | Reported exact ENOENT error, no panic, suggested production-grade error handling improvements. |
| 5 | Session discipline | **PASS** | Concise patrol: PR #36 open, no urgent blockers. No spiral. |
| 6 | Research delegation | **PARTIAL** | Gemini returned real CVEs with sources. Grok failed (xai/grok-2 not in allowed models — config issue, not model issue). |

**Overall: STRONG.** Best cost/performance ratio. Self-directed, delegates immediately, uses full workforce, honest about failures.

### GPT-4o-mini (`openai/gpt-4o-mini`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Self-directed work | **FAIL** | Could not break free of stale Slack session context from previous model. Summarized old work instead of finding new work. Even with explicit "fresh start" directive, continued old tasks. |
| 2-6 | Not tested | **SKIPPED** | Failed Test 1, moved to next model. |

**Overall: FAIL.** Stale context handling is a dealbreaker for a CEO that gets swapped between models.

### Sonnet (`anthropic/claude-sonnet-4-6`)

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Self-directed work | **PASS++** | Found PR #36, made autonomous judgment ("governance fix is within my lane"), delegated to Haiku, committed and pushed fix. Actually shipped code. Revenue-aware. |
| 2 | Parallel delegation | **PARTIAL** | 6 workers across 5 models simultaneously. Qwen overflowed (111%). Haiku and GPT-4o delivered. Found 4 dead functions in brain.py. |
| 3 | Task routing | **PASS** | 5/5 correct routing. Made cost optimization decision (answered trivial shebang check directly instead of spawning). |
| 4 | Failure recovery | **PASS** | Honest report, suggested typed errors + fuzzy matching for production. |
| 5 | Session discipline | **PASS** | Concise patrol. Ran `openclaw doctor`. |
| 6 | Research delegation | **BLOCKED→FIXED→HUNG** | Gemini/Grok auth broken. Diagnosed root cause (cooldown + missing xai profile). Fixed own config. After restart, both models verified green. Re-ran test, then hung waiting for workers for 1 hour. |

**Overall: STRONGEST orchestration quality but HANGS on worker timeouts.** Fixed its own infrastructure (unprecedented). Made autonomous scope decisions. But the 1-hour hang on Test 6 is a dealbreaker for unsupervised operation. The hang is a platform issue (no sessions_spawn timeout), not a model issue.

### Grok 4 Fast Reasoning (`xai/grok-4-fast-reasoning`)

Note: `grok-4.20-multi-agent-0309` required beta access (400 error). Used `grok-4-fast-reasoning` instead.

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Self-directed work | **PASS** | Found PR #36, delegated to Haiku, 93/93 tests pass, caught push divergence (Sonnet already pushed), revenue-aware. ~70 seconds. |
| 2 | Parallel delegation | **PARTIAL** | 3 spawned correctly. GPT-4o strategic delivered (30 min patrol). Qwen + Haiku pending but DIDN'T HANG — reported "pending" and moved on. |
| 3 | Task routing | **PASS** | 5/5 correct routing (same as nano/Sonnet). Cost-aware: "direct exec cheaper but spawned for consistency." |
| 4 | Failure recovery | **PASS** | Clean ENOENT, no panic, production suggestions. |
| 5 | Session discipline | **PASS** | Concise patrol. PR #36, brain health verified, systems green. |
| 6 | Research delegation | **PARTIAL** | Spawned both Gemini and Grok-3-mini. Grok returned 0 results (search limitation). Gemini pending. Didn't hang. |

**Full battery completed in ~2 minutes.** Tagged consistently. Never hung on pending workers.

**Bonus: Infrastructure resilience plan** — delivered comprehensive CEO Operations Manual in ~10 seconds covering: worker timeouts (runTimeoutSeconds: 300), pre-flight model health checks (check_models.sh), dynamic model registry (weekly cron), CEO hang prevention (partial reporting at 50% completion). Cost estimate: $0.50/day. Implementation delegated to Haiku.

**Overall: WINNER.** Fastest, doesn't hang, tags consistently, revenue-aware, designs its own guardrails. Selected as new permanent CEO model.

**Observation: Slack tagging compliance**
Grok 4 was the ONLY model that consistently tagged `<@U0AMF1CCE93>` (Claude CLI) in every response when asked. All other models forgot or ignored the instruction:
- Haiku: never tagged
- GPT-5.4-nano: never tagged
- GPT-4o-mini: never tagged
- Sonnet: tagged inconsistently (sometimes tagged itself instead)
- Grok 4: tagged every single time

This matters for autonomous operation — if the CEO doesn't tag back, the conversation loop breaks and requires human intervention to check responses. Small detail, big operational impact. Should be added to the automated test harness as a scoring criteria.

---

## CRITICAL PLATFORM FINDING

**OpenClaw has NO worker timeout mechanism.** When `sessions_spawn` creates a worker that hangs (e.g., Qwen at 456% context overflow), the CEO session blocks FOREVER. This happened twice:
- Test 2: Qwen at 111% context, never returned
- Test 6: Workers hung for 1+ hour, CEO never timed out

**This is the #1 blocker for autonomous operation.** No model can work around it. Needed:
1. Configurable timeout on `sessions_spawn` (e.g., `timeout_ms: 300000`)
2. Automatic kill of workers exceeding context limits
3. CEO-level dead worker detection in the escalation skill

Without this fix, the CEO model choice is secondary. Any model will eventually hang on a bad worker.

---

## Notes

- All experiments driven from laptop via Slack #group-chat
- Related: `OPENCLAW_ESCALATION_RESEARCH.md` (the implementation plan)
- Related: Task #5271 (Haiku escalation protocol)
- Related: `ai-memory/experiments/001_baseline/` (the slow experiment — snapshots manually captured)
- Brain entry #1843 has shared context for all agents
