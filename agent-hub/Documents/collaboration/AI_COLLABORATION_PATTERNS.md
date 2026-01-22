# AI Collaboration Workspace

This folder enables collaboration between different AI assistants (Claude, GPT4All, etc.) through file-based handoffs.

## Folder Structure

### 📥 `inbox/`
**For GPT4All → Claude handoffs**
- Place files here when GPT4All has work for Claude to implement
- Include specifications, requirements, analysis, or code reviews
- Claude monitors this for new tasks

### 📤 `outbox/`
**For Claude → GPT4All handoffs**
- Claude places completed work, questions, or analysis here
- Code implementations, documentation, or requests for review
- GPT4All can pick up and continue the work

### 🤝 `shared/`
**Collaborative documents**
- Working documents both AIs contribute to
- Project planning files
- Shared knowledge bases
- Ongoing discussions

### 📦 `archive/`
**Completed collaborations**
- Move finished handoffs here to keep workspace clean
- Historical record of successful collaborations

## Collaboration Patterns

### Pattern 1: Spec → Implementation
1. GPT4All writes specification in `inbox/`
2. Claude implements and puts result in `outbox/`
3. GPT4All reviews and provides feedback

### Pattern 2: Code Review
1. Claude writes code and puts in `outbox/` with review request
2. GPT4All analyzes and puts feedback in `inbox/`
3. Claude iterates based on feedback

### Pattern 3: Research & Build
1. GPT4All researches topic and creates analysis in `inbox/`
2. Claude builds implementation based on research
3. Both contribute to `shared/` documentation

## File Naming Convention
Use format: `YYYY-MM-DD_[AI]_[project]_[description].md`

Examples:
- `2025-01-27_gpt4all_flo-fi_user-auth-spec.md`
- `2025-01-27_claude_flo-fi_auth-implementation.md`
- `2025-01-27_shared_flo-fi_architecture-decisions.md`

## Templates
Check the `_templates/` folder for standard formats for different types of handoffs.

## Related Documentation

- [[CODE_REVIEW_ANTI_PATTERNS]] - code review
- [[ai_model_comparison]] - AI models
- [[case_studies]] - examples
- [[research_methodology]] - research
- [[security_patterns]] - security
- [[session_documentation]] - session notes

