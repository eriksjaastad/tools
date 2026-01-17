# Code Review Standardization

**Status:** Proven Pattern
**Context:** Standardizing AI-driven code reviews for consistency and tracking.

---

## The Pattern

All code review requests and results must follow a strict format to ensure quality and enable dashboard tracking.

### 1. The Review Request (Input)

Every document or code block submitted for review **MUST** contain a **Definition of Done (DoD)** section.

* **Why:** AI models need clear success criteria to provide meaningful critiques. Without a DoD, reviews become vague and "hallucinatory."
* **Format:** A section titled `## Definition of Done` or `## DoD` with a checklist.

### 2. The Review Result (Output)

Review output files are standardized to enable automated tracking and prevent context clobbering.

* **Naming Convention:** `CODE_REVIEW_{REVIEWER_NAME}_{VERSION}.md` (All Caps).
    *   Example: `CODE_REVIEW_CLAUDE_v1.md`, `CODE_REVIEW_GEMINI_v2.1.md`.
* **Location - The "Now" Rule:** The most recent review **MUST** reside in the **Project Root**.
* **Location - The "Archive" Rule:** All previous versions **MUST** be moved to `Documents/archives/reviews/` before a new review is initiated.
* **Review ID:** Every review should include a `Review ID: [UUID or Timestamp]` in the frontmatter to enable linking to `WARDEN_LOG.yaml`.

### 3. The Review Workflow

1. **Prepare:** Use `templates/CODE_REVIEW.md.template` to create your request.
2. **Define:** Fill out the **Definition of Done** clearly.
3. **Execute:** Run `scaffold review --type code --input path/to/your/request.md`.
4. **Enforce:** The CLI will reject any request missing the DoD.

---

## Dashboard Integration

By using the `CODE_REVIEW_` prefix in all caps, we can easily track review status across multiple projects:

```bash
# Example: Finding all architecture reviews
find . -name "CODE_REVIEW_ARCHITECTURE_REVIEWER.md"
```

---

## When to Use

* For every significant architectural decision.
* For security-critical code paths.
* When "handing off" a task between tiered AI models.

## Scars

* **The "Generic Review" Scar:** Early reviews without a DoD resulted in AI models giving vague advice like "Add more comments" instead of catching architectural flaws.
* **The "Lost Review" Scar:** Inconsistent naming made it impossible to see which projects had been reviewed and which hadn't. Standardizing on `CODE_REVIEW_` fixed this.

## Related Documentation

- [[CODE_REVIEW_ANTI_PATTERNS]] - code review
- [[architecture_patterns]] - architecture
- [[dashboard_architecture]] - dashboard/UI
- [[queue_processing_guide]] - queue/workflow
- [[case_studies]] - examples
- [[security_patterns]] - security
