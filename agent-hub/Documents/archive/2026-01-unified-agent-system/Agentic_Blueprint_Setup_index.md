# 🗂️ Index: Agentic Blueprint & Multi-Agent Pipeline

This index serves as the central hub for the **Agentic Blueprint** development, including the core architecture, implementation setup, and all expert peer reviews.

## 🏗️ Core Architecture & Setup

| Version | Document | Status | Description |
|---------|----------|--------|-------------|
| V1 | [Agentic Blueprint Setup.md](Agentic%20Blueprint%20Setup.md) | Archive | Original "Factory Line" implementation |
| V2 | [Agentic Blueprint Setup V2.md](Agentic%20Blueprint%20Setup%20V2.md) | Archive | Asynchronous file polling with peer review fixes |
| V3 | [Agentic Blueprint Setup V3.md](Agentic%20Blueprint%20Setup%20V3.md) | **CURRENT** | Direct Agent Communication (DAC) via MCP Hub |
| V4 | [Agentic Blueprint Setup V4.md](Agentic%20Blueprint%20Setup%20V4.md) | Planning | Sandbox Draft Pattern - local model file writes |

### Supporting Documents
- **[Agentic Blueprint.md](Agentic%20Blueprint.md)**: The high-level objective and 4-phase "Implementation Factory" pipeline.
- **[PRD integration.md](PRD%20integration.md)**: Strategy for "As-Built" retroactive PRDs to anchor existing projects.

## 📋 Version Summary

- **V1 → V2**: Added circuit breakers, atomic file writes, peer review feedback
- **V2 → V3**: Replaced file polling with MCP Hub messaging (<100ms latency)
- **V3 → V4**: Gives local models controlled file writing via sandboxed drafts

## 🔍 Peer Reviews (The Audit Pile)
- **[Agentic Blueprint Setup Claude code review.md](Reviews/Agentic%20Blueprint%20Setup%20Claude%20code%20review.md)**: Deep dive into race conditions, Claude CLI flags, and atomicity.
- **[Agentic Blueprint Setup gpt review.md](Reviews/Agentic%20Blueprint%20Setup%20gpt%20review.md)**: Analysis of the contract-driven assembly line and potential failure modes.
- **[Agentic Blueprint Setup gpt codex review.md](Reviews/Agentic%20Blueprint%20Setup%20gpt%20codex%20review.md)**: Recommendations for schema versioning, checksums, and idempotent transitions.

---
*Last Updated: 2026-01-17 by Claude Opus 4.5 (Super Manager)*
