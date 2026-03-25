# OpenClaw Model Escalation Research

> **Source:** Claude (web) conversation with Erik, 2026-03-23
> **Status:** Not yet implemented. Task #5271 in project-tracker.
> **Goal:** Haiku CEO auto-escalates to Sonnet for complex tasks instead of failing or asking Erik.

---

## Key Discovery: `sessions_spawn` has a model parameter

This is the core escalation mechanism. From the session tools documentation:

```javascript
sessions_spawn({
  task: "Complex architectural decision about microservices",
  model: "anthropic/claude-sonnet-4-6",  // Override model per spawn
  thinking: "high"
})
```

## Current OpenClaw Routing Mechanisms

### 1. Config-Level Sub-Agent Model Defaults

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-haiku-4-5"
      },
      "subagents": {
        "model": {
          "primary": "anthropic/claude-sonnet-4-6"
        }
      }
    }
  }
}
```

### 2. Per-Spawn Model Override

The `sessions_spawn` tool accepts a `model` parameter that overrides both main and sub-agent defaults.

### 3. Heartbeat Model (used for Ollama)

```json
{
  "heartbeat": {
    "model": "ollama/qwen3-32b"
  }
}
```

## Critical Nuances

### Bug Alert: Model Parameter Not Always Working

Open bug (Issue #7330, #10963) where `sessions_spawn`'s model parameter returns `modelApplied: true` but the sub-agent still runs on the parent's model. Reported Feb 2026, may still be present.

**Workaround:** Set `agents.defaults.subagents.model.primary` as your escalation target, then use cheaper model as main.

### Sub-Agents Can't Spawn Sub-Agents (Depth Limit)

- `maxSpawnDepth` defaults to 1, max is 2
- Sub-agents cannot call `sessions_spawn` (no recursive spawning)
- This means: Haiku CEO -> spawns Sonnet worker OK | Sonnet worker -> spawns another worker NO

### Router Pattern is Proven

Multiple production deployments use this exact pattern:
- Cheap router (Haiku, gpt-4o-mini, Gemini Flash) classifies incoming requests
- Router calls `sessions_spawn` with appropriate model for the task
- 80-90% cost savings reported

## Three Approaches

### Option A: Smart Router Skill (RECOMMENDED)

Build a skill that teaches Haiku CEO when to escalate:

```markdown
# Escalation Protocol Skill

## When to Spawn Sonnet Worker

AUTO-ESCALATE to Sonnet via `sessions_spawn` for:
- Morning report generation (needs full project context)
- Cross-project architectural decisions
- Resolving conflicts between projects
- Any task marked "strategic" in tracker
- Questions about "what should we prioritize"

STAY on Haiku for:
- Single-project status checks
- File operations
- Routine updates
- Heartbeat checks

## How to Escalate

sessions_spawn({
  task: "[specific task description]",
  model: "anthropic/claude-sonnet-4-6",
  label: "strategic-decision"
})
```

Implementation: `~/.openclaw/workspace/skills/escalation-protocol/SKILL.md`

### Option B: Community Skill `openclaw-model-router`

- Classifies tasks into 5 tiers (free -> premium)
- Progressive escalation (try cheap, escalate on failure)
- Install: `npx playbooks add skill openclaw/skills --skill openclaw-model-router`

### Option C: Multi-Agent Setup (Nuclear option)

Two agents: `haiku-ceo` (default, 90% of work) and `sonnet-strategist` (complex decisions).

## Decision

**Option A** is the right call:
- Explicit routing rules (no guessing)
- Haiku stays default (cheap)
- Sonnet only fires when needed (controlled cost)
- No infrastructure changes (just a skill file)
