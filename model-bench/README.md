# model-bench

Benchmark cheap/free models against worker tasks. Scores with Opus judge.

## Which Computer Are You Running This On?

This tool runs on both Erik's laptop and the Mac Mini, but the experience is very different. Read this before you do anything.

### Laptop (MacBook Pro)

- **RAM is tight.** You cannot run the 32B model here. It will thrash memory and timeout.
- **`reviewing:current` (Qwen2.5-Coder 32B) is commented out in `registry.py`.** Leave it that way.
- **Local models are slow.** Expect 40-90s per call. The laptop runs hot under sustained Ollama load.
- **Model swapping kills you.** Ollama evicts the previous model when loading a new one. Two local models back-to-back means cold loads every time.
- **Best use:** Cloud model benchmarks (Haiku, GPT-4.1 Mini, Gemini Flash). Local models are testable but painful.
- **Available local models:** `coding:current` (14B), `reasoning:current` (11B)

### Mac Mini (M4 Pro, 64GB)

- **This is where local benchmarks belong.** All three models fit comfortably.
- **Uncomment `reviewing:current` in `registry.py`** to enable the 32B model.
- **Ollama can keep multiple models loaded.** Set `OLLAMA_KEEP_ALIVE` in `.env` if you want models to stay warm between calls.
- **Expect 5-15s per call** for local models (vs 40-90s on laptop).
- **Available local models:** `coding:current` (14B), `reviewing:current` (32B), `reasoning:current` (11B)
- **Connection:** `ssh eriksjaastad@eriks-mac-mini.local`

### Registry Changes Between Machines

In `model_bench/registry.py`, the `reviewing:current` entry is commented out by default (laptop-safe). On the Mac Mini, uncomment it:

```python
# Uncomment this on Mac Mini:
ModelEntry(
    id="ollama/reviewing:current",
    display_name="reviewing:current (Qwen2.5-Coder 32B)",
    provider="ollama",
    tier="local",
),
```

### Ollama Aliases

Both machines need these Ollama aliases set up:

```bash
ollama cp qwen2.5-coder:14b coding:current
ollama cp qwen2.5-coder:32b-instruct-q3_K_L reviewing:current   # Mac Mini only
ollama cp llama3.2-vision:11b reasoning:current
```

## Quick Start

```bash
cd _tools/model-bench
cp .env.example .env  # Add your API keys
uv run model_bench models              # List registered models
uv run model_bench run --dry-run       # Preview plan + cost estimate
uv run model_bench run                 # Full sweep
uv run model_bench results             # View latest results
```

## Commands

| Command | Description |
|---------|-------------|
| `run` | Execute benchmark (full or filtered) |
| `run --category code_generation` | One category only |
| `run --models coding:current,reasoning:current` | Subset of models |
| `run --dry-run` | Show plan + cost, no calls |
| `run --no-judge` | Skip Opus scoring, latency only |
| `results` | Show latest run as table |
| `results --format markdown` | Markdown output |
| `models` | List registered models + availability |
| `estimate` | Cost estimate for full run |

## Task Bank

YAML files in `tasks/` — one per category. Each task has prompt variants and a rubric for Opus to score against.

5 categories, 20 tasks, ~39 variants total:
- `code_generation` — fibonacci, REST endpoints, SQL builders, async decorators
- `dialogue_creative` — character voice, group chat, scene writing, conflict
- `review_judgment` — code review, architecture decisions, PR review, error messages
- `diagnosis_debugging` — race conditions, memory leaks, stack traces, N+1 queries
- `summarization` — tech docs, error logs, meeting notes, changelogs

## Adding Models

Edit `model_bench/registry.py` — add to `MODELS` list with provider, tier, and LiteLLM model ID.

## Adding Tasks

Create or edit YAML files in `tasks/`. Follow the existing format (see `tasks/code_generation.yaml`).

## Known Issues

- **Local model compliance:** Models may generate correct code but ignore instructions about target files or output format. The judge catches this in scoring.
- **Cold load latency:** First call to a model after swap includes Ollama load time (10-40s depending on model size and hardware).
- **Rate limiting:** Cloud APIs may rate-limit rapid-fire calls. The runner adds 1s delay between cloud calls.
