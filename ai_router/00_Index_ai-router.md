---
tags:
  - map/project
  - p/ai-router
  - type/infrastructure
  - domain/ai-orchestration
  - status/active
  - tech/python
  - api/openai
  - arch/pipeline
created: 2026-01-05
updated: 2026-01-19
---

# AI Router

Smart routing between local and cloud AI models based on task type classification, token budget estimation, and cost optimization. Features a budget protector, hard ceiling on expensive models, judge model for quality evaluation, and multi-provider support (OpenAI, Anthropic, Google).

## Key Components

### Core Logic
- `router.py` - Primary logic for routing, escalation, and model configuration (1 file)
- `__init__.py` - Package entry point

### Executable Scripts
- `scripts/` - Test gauntlets, examples, and audit tools (7 files)
  - `cli.py` - Command-line interface for the AI Router
  - `test_gauntlet.py` - Comprehensive routing test
  - `examples.py` - Usage patterns
  - `agent_skills_audit.py` - Real-world use case for strategic routing

### Telemetry & Data
- `data/logs/` - Persistent telemetry and logs
  - `telemetry.jsonl` - Model performance and usage data

### Documentation
- `Documents/` - Centralized documentation
- `README.md` - High-level overview
- `CLAUDE.md` - AI collaboration instructions

## Status

**Tags:** #map/project #p/ai-router
**Type:** #type/infrastructure
**Status:** ✅ Core Complete (Critical/High items done)
**Last Major Update:** January 19, 2026
**Priority:** #mission-critical
**Infrastructure:** #api/openai #api/anthropic #api/google #local-first

### Recent Completions (Jan 19, 2026)
- ✅ Budget Protector (daily limits, spend tracking)
- ✅ Hard Ceiling on expensive models (requires `unlocked=True`)
- ✅ Task Classification (extractive vs generative routing)
- ✅ Judge Model (local quality evaluation before escalation)
- ✅ Multi-Provider Support (Anthropic, Google Gemini)
- ✅ Dashboard Methods (escalation rate, project usage, performance alerts)

---

**Template Version:** 1.0  
**Created:** 2026-01-05  
**Location:** `_tools/ai_router/00_Index_ai-router.md`

## Related Documentation

- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[cost_management]] - cost management
- [[dashboard_architecture]] - dashboard/UI
- [[ai_model_comparison]] - AI models
- [[case_studies]] - examples
- [[performance_optimization]] - performance
