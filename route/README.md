# route — Token Usage & Shadow Pricing CLI

A shared tool that reads session data from Claude Code, Codex CLI, and Gemini CLI, applies shadow pricing, and shows you what your AI usage actually costs.

## Usage

```bash
route summary --all               # All recorded shadow costs by model
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

Claude totals come from `~/.claude/stats-cache.json`; its `modelUsage` object
is aggregated and may lag recent sessions. Codex totals use the last cumulative
token event in each session, attributed to the explicit top-level `model` in
`~/.codex/config.toml`. That current configuration is an estimation assumption,
not proof of the model used by every historical session.
Native `token_count` updates with explicit `info: null` and nonempty
`rate_limits` metadata carry no new usage; they preserve the last cumulative
count. A session containing only rate-limit updates still lacks usage evidence.

Readers raise on missing, unreadable, malformed, or incomplete evidence. The
CLI prints a diagnostic and exits 2 without a summary total or session list.
An existing empty session directory, or a stats cache with an explicit empty
`modelUsage` object, is valid zero usage. A missing source, absent Codex token
event, invalid timestamp, or missing pricing-model configuration is unavailable
evidence, not zero usage. Repair or finish writing the source before retrying;
concurrently written incomplete JSONL records also fail explicitly.

Session mtimes are required for Claude ordering and date filters. Reader APIs
reject invalid dates; Codex session timestamps must carry a timezone, while a
requested date without one means UTC. The Claude reader keeps its existing
local-time date interpretation. `summary --week` and `summary --month` exit 2
because aggregate Claude statistics cannot establish those ranges. Use
`summary --all`; a filtered label must not conceal all-time totals.

## Session Classification

Sessions are classified by tool call patterns:
- **CODING** — >20% of tool calls are file writes (Edit/Write)
- **RESEARCH** — >50% of tool calls are reads (Read/Glob/Grep)
- **TALKING** — Few or no tool calls, mostly conversation
- **MIXED** — Combination of talking and coding

## Shadow Pricing

For subscription plans (Claude Max, ChatGPT Pro), the tool computes what the usage *would* cost at API rates. This gives visibility into the value you're getting from subscriptions and helps decide when API usage might be more cost-effective.

## Model Registry

`model_registry.json` contains USD per million token estimates, verified on
2026-09-06 against the sources below. Cache reads use the published rate for
each model; there is no universal cache discount.

| Models | Official pricing source |
|--------|-------------------------|
| Opus 4.8, Opus 5, Sonnet 5, Haiku 4.5 | [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) |
| GPT-5.5 | [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.5) |
| GPT-4.1 Mini | [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini) |
| GPT-4o Mini | [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini) |
| Gemini 2.5 Flash, 2.5 Pro, 3.5 Flash | [Google pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| Grok 4.3, Grok Build 0.1, GLM-5.2, DeepSeek V3.2, Qwen3-Coder | [OpenRouter public model catalog](https://openrouter.ai/api/v1/models) |

The OpenRouter catalog reports USD per token; multiply `prompt`, `completion`,
and `input_cache_read` by 1,000,000 for registry rates. These are catalog base
rates, and the selected endpoint/provider can charge differently. Tests use
checked-in expectations and never fetch prices or invoke provider APIs.

### Estimate boundaries

The existing flat-rate API estimates standard paid text usage at the base
context tier. `input_tokens` excludes cache reads and writes; callers must
split those counts before calling `compute_shadow_cost`. Output counts include
billed reasoning/thinking tokens. This is a shadow estimate, not an invoice.

- Anthropic cache writes assume a five-minute TTL (1.25 times ordinary input).
  One-hour writes cost twice ordinary input and cannot be distinguished by the
  current token counters. Fast mode, regional premiums, and tools are excluded.
- GPT-5.5 uses the tier through 272K input tokens. Longer contexts and regional
  processing have additional charges.
- Gemini 2.5 Pro uses prompts through 200K tokens. Gemini Flash uses text input
  rates; audio input and time-based cache storage are excluded.
- Grok 4.3 and Grok Build 0.1 use base rates below the OpenRouter catalog's
  200K prompt-token override. Higher context tiers and priority rates are excluded.
- Batch, flex, priority, cache storage, tool charges, and subscription billing
  are outside the per-token calculation. Non-Anthropic `cache_write_tokens`
  retain the input-rate fallback; that does not estimate cache storage fees.

Sonnet 5's $2 input / $10 output rates are now standard: Anthropic canceled the
previously announced September 1 increase. Subscription entries remain local
comparison assumptions; this refresh verifies token prices, not plan prices.

### Model lifecycle

Keep a retired model's historical pricing row so old sessions remain costed,
clear its `role_fit`, and record its retirement date and official lifecycle
source in that row. An empty `role_fit` excludes it from `route estimate`.
Do not replace an old ID with a newer model's price.

At this verification, none of the registry's exact IDs has a confirmed
retirement: [Anthropic lifecycle](https://platform.claude.com/docs/en/about-claude/model-deprecations)
lists the included Claude IDs as active; [Google lifecycle](https://ai.google.dev/gemini-api/docs/deprecations)
lists no shutdown date for the included Gemini IDs. The OpenAI model pages
and OpenRouter catalog still list their included IDs. Older versions alone do
not establish retirement, so their pricing and recommendation roles remain.

### Tests

```bash
uv run --python 3.12 --with pytest pytest route/test_pricing.py route/test_readers.py -q
```

Only pytest and the standard library are needed. The benchmark coverage test
imports the repository's model catalog without loading provider transports.
Arithmetic tests cover ordinary input/output, model-specific cache reads,
Anthropic five-minute writes, mixed usage, zero usage, and the existing unknown
model behavior (`get_model_pricing` returns `None`; cost returns `0.0`).
