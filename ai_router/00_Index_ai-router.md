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
---

# AI Router

Smart routing between local and cloud AI models based on complexity heuristics, context window size, and cost optimization. It automatically escalates from free local models (Ollama) to cheap cloud models (gpt-4o-mini) and finally to expensive models (gpt-4o) when needed.

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
**Status:** #status/active  
**Last Major Update:** January 2026  
**Priority:** #mission-critical
**Infrastructure:** #api/openai #local-first

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
