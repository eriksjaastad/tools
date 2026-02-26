# route — Token Usage & Shadow Pricing CLI

A shared tool that reads session data from Claude Code, Codex CLI, and Gemini CLI, applies shadow pricing, and shows you what your AI usage actually costs.

## Usage

```bash
route summary                    # This month's shadow costs by model
route summary --week             # Last 7 days
route sessions                   # List recent sessions with classification
route sessions --type coding     # Filter by type (coding/talking/research/mixed)
route estimate --role coder      # What would a coding task cost on each model?
```

## What it reads

| CLI | Data Location | Format |
|-----|--------------|--------|
| Claude Code | `~/.claude/projects/*/*.jsonl` | Session transcripts with tool calls |
| Codex CLI | `~/.codex/sessions/**/*.jsonl` | Session logs with token_count events |
| Gemini/Antigravity | `~/.gemini/antigravity/` | Protobuf (TBD) |

## Session Classification

Sessions are classified by tool call patterns:
- **CODING** — >20% of tool calls are file writes (Edit/Write)
- **RESEARCH** — >50% of tool calls are reads (Read/Glob/Grep)
- **TALKING** — Few or no tool calls, mostly conversation
- **MIXED** — Combination of talking and coding

## Shadow Pricing

For subscription plans (Claude Max, ChatGPT Pro), the tool computes what the usage *would* cost at API rates. This gives visibility into the value you're getting from subscriptions and helps decide when API usage might be more cost-effective.

## Model Registry

`model_registry.json` contains official pricing per model. Update from provider docs periodically.
