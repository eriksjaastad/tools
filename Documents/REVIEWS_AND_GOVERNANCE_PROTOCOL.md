# Ecosystem Governance & Review Protocol (v1.2)

**Date:** 2026-01-07
**Status:** ACTIVE
**Goal:** Transition from "Rapid Experimentation" to "Industrial-Grade Hardening."

---

## Part 1: The Core Architecture (Checklist-First)
*Intelligence belongs in the checklist, not the prompt.*

### 1. The Fundamental Pivot
Prompts are subjective and mood-dependent; checklists are versioned, auditable specifications of what "reviewed" means.
*   **Evidence-First Rule:** Every check requires an evidence field (e.g., a `grep` output). Empty evidence = Incomplete Review.
*   **The Artifact:** The review deliverable is a completed evidence trail, not an unstructured prose opinion.

### 2. The Blast Radius Prioritization
Audit files in order of their potential to infect the ecosystem:
1.  **Tier 1: Propagation Sources (Highest Impact):** `templates/`, `.cursorrules`, `AGENTS.md`. If these fail, every downstream project inherits the defect.
2.  **Tier 2: Execution Critical:** `scripts/`, `scaffold/`. These run the automation but don't propagate DNA.
3.  **Tier 3: Documentation:** `Documents/`, `patterns/`. Important for humans, zero impact on code execution.

---

## Part 2: The Two-Layer Defense Model

### Layer 1: Robotic Scan (Gatekeeper)
A mechanical script (`pre_review_scan.sh`) that catches hardcoded paths, secrets, and silent errors. A single "FAIL" blocks the AI/Human review.

### Layer 2: Cognitive Audit (Architect Work)
AI Architects focus on judgment-heavy tasks that automation misses:
*   **Inverse Test Analysis:** For every passing test, document what is **NOT** being checked. Identify the "Dark Territory."
*   **Temporal Risk Analysis:** Identify what breaks in 1, 6, or 12 months (e.g., unpinned dependencies, API deprecations).
*   **Propagation Impact:** Verify that Tier 1 files contain no machine-specific assumptions.

---

## Part 3: The Industrial Hardening Audit
*Mandatory checks for projects transitioning from Prototype to Production.*

### 1. The "Data Clobber" Guard
Reviewers must verify that any script writing to global or external paths (e.g., `agent-skills-library`) includes:
*   **Path Validation:** Explicit check that the destination directory exists and is valid.
*   **Dry-Run Mandate:** A `--dry-run` flag that parses all logic but performs zero disk writes.
*   **Safety Gate:** Refuse to write if the `target_path` is not explicitly validated against a whitelist of project roots.

### 2. Subprocess Integrity
Every `subprocess.run` call must follow the **Production Standard**:
*   `check=True`: Fail loudly on non-zero exit codes.
*   `timeout=X`: Never allow a subprocess to hang indefinitely (e.g., `yt-dlp` or `ollama` hangs).
*   `capture_output=True`: Ensure stdout/stderr are captured for telemetry if a failure occurs.

### 3. Frontmatter & Schema Validation
For projects that generate files:
*   **Schema Enforcement:** Generated markdown must be validated against the project's frontmatter taxonomy.
*   **Escape Verbatim:** Verbatim text (like transcripts) must be escaped or truncated to prevent breaking YAML parser logic.

---

## Part 4: Scalability Analysis
*Reviewers must document the "Ceiling" of the current architecture.*

### 1. The Context Window Limit
Any logic that aggregates multiple files (e.g., `synthesize.py` reading an entire library) must be flagged for:
*   **The Truncation Risk:** When does the library size exceed the LLM's context window?
*   **Strategy:** Is there a Map-Reduce, RAG, or Tiered Synthesis plan for scale?

### 2. Repository Bloat
Audit for logic that dumps massive verbatim data (e.g., 2-hour video transcripts) into the main repository. Recommend strategies for externalizing large assets if they don't serve the core LLM reasoning.

---

## Part 5: Continual Learning (The Control Loop)
*How we turn "Scars" into "Standards."*

### 1. The "Scar Tissue" SLA
Any new defect type found must be added to the **Robotic Scan** and the **Checklist** within **24 hours**.

### 2. Regression Harnessing
Every bug found must result in a **Reproducer Test** in CI. These tests are the "immune system" of the repo.

### 3. Context-Aware "Mission Orders" (RISEN)
Use the **RISEN Framework** (Role, Instructions, Steps, Expectations, Narrowing) to create a behavioral contract for the auditor.

---

## Part 6: The Master Review Checklist (Template)

| ID | Category | Check Item | Evidence Requirement |
|----|----------|------------|----------------------|
| **M1** | **Robot** | No hardcoded `/Users/` or `/home/` paths | Paste `grep` output (all files) |
| **M2** | **Robot** | No silent `except: pass` patterns | Paste `grep` output (Python files) |
| **M3** | **Robot** | No API keys (`sk-...`) in code/templates | Paste `grep` output |
| **P1** | **DNA** | Templates contain no machine-specific data | List files checked in `templates/` |
| **P2** | **DNA** | `.cursorrules` is portable | Verify path placeholders used |
| **T1** | **Tests** | Inverse Audit: What do tests MISS? | Map "Dark Territory" |
| **E1** | **Errors** | Exit codes are accurate (non-zero on fail) | Document manual test of failure path |
| **D1** | **Deps** | Dependency versions are pinned/bounded | Paste `requirements.txt` snapshot |
| **H1** | **Hardening**| Subprocess `check=True` and `timeout` used | List files/lines checked |
| **H2** | **Hardening**| Dry-run flag implemented for global writes | Verify `--dry-run` logic exists |
| **H3** | **Hardening**| Atomic writes used for critical file updates | Verify temp-and-rename pattern |
| **H4** | **Hardening**| Path Safety (safe_slug + traversal check) | Verify all user-input paths are sanitized |
| **R1** | **Reviews** | **Active Review Location** | Must be in project root: `CODE_REVIEW_{MODEL}_{VERSION}.md` |
| **R2** | **Reviews** | **Review Archival** | Previous versions MUST be moved to `Documents/archives/reviews/` |
| **S1** | **Scaling** | Context ceiling strategy (Map-Reduce/RAG) | Document the architectural ceiling |
| **S2** | **Scaling** | Memory/OOM guards for unbounded processing | Verify size-aware batching logic |

---

## Related Documentation

- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[architecture_patterns]] - architecture
- [[automation_patterns]] - automation
- [[prompt_engineering_guide]] - prompt engineering
- [[ai_model_comparison]] - AI models
- [[security_patterns]] - security
- [[agent-skills-library/README]] - Agent Skills
