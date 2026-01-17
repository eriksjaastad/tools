# Review System Design & Recommendations

**Status:** ACTIVE
**Goal:** Transition from subjective "Personality-based" reviews to systematic "Process-based" reviews.

---

## The Core Philosophy: Process over Personality

Historically, "be grumpy" or "try harder" were used as review directives. This failed because:
1. **Subjective:** "Grumpy" means different things to different models/people.
2. **Unreliable:** Depends on mood, energy, and context window.
3. **Blind Spots:** Easy to focus on one area (e.g., scripts) while missing others (e.g., templates).

**New Model:** "Execute the Protocol."
- **Checklist-First:** Intelligence belongs in the checklist, not the prompt.
- **Evidence-First:** Every check requires proof (grep output, test result).
- **Blast Radius Prioritization:** Check files in order of their potential to infect the ecosystem.

---

## Recommendation 1: Two-Layer Defense Model

### Layer 1: Automated Pre-Review Scan
Mechanical sweeps for common anti-patterns.
- **Tool:** `scripts/pre_review_scan.sh`
- **Catch:** Hardcoded paths, secrets, silent exceptions, unpinned deps.
- **Rule:** A single "FAIL" blocks the human/AI review.

### Layer 2: Cognitive Audit
Human/AI Architects focus on high-level concerns.
- **Tool:** `templates/CODE_REVIEW.md.template`
- **Focus:** Architectural debt, logic edge cases, Inverse Test Analysis.
- **Deliverable:** A completed evidence trail.

---

## Recommendation 2: "Inverse Test" Analysis

For every passing test, the reviewer must ask:
**"What does this test NOT check?"**

Example:
- **Test:** `test_no_hardcoded_paths()`
- **Checks:** `scripts/` directory only.
- **Inverse Question:** What directories are ignored?
- **Answer:** `templates/`, `patterns/`, `Documents/`.
- **Action:** Manually verify or expand the test.

---

## Recommendation 3: Trickle-Down Analysis

For upstream/infrastructure repos (like project-scaffolding), every change must be evaluated for its multiplication factor.
- **Propagation Sources:** `templates/`, `.cursorrules`, `AGENTS.md`.
- **Multiplier:** A minor bug here becomes 30 bugs downstream.
- **Audit:** Run a "New Machine Test" (grep for username) before every release.

---

## Recommendation 4: Silent Failure Detection

CI pipelines must be "Honest." A pipeline that exits with code 0 while skipping errors is dangerous.
- **Rule:** No bare `except:` or `except: pass`.
- **Rule:** Every CLI tool must exit with non-zero on failure.
- **Verification:** Use AST parsing or aggressive grepping to find swallowing patterns.

---

## Future Enhancements

- **Phase 2: Template Linting:** Dedicated script to lint `.template` files.
- **Phase 3: Dependency Drift Detection:** Automated check for major version boundaries.
- **Phase 4: Review Quality Metrics:** Track scan effectiveness vs. human discovery.
