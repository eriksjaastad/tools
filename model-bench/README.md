# model-bench

`model-bench` is a seat-fit bench for MacBook projects. Projects own their
model job definitions and real evaluation fixtures in `seats.yaml`;
model-bench discovers those files, validates them strictly, and compares
candidate models on the work each project actually performs.

It is not a central seat registry and it does not change production model pins.
Its output is evidence: per-seat quality, artifact validity, latency, errors,
and measured model cost.

## Quick start

```bash
cd _tools/model-bench

# Strictly validate and list every discovered seat.
uv run model_bench seats

# Plan a development sweep. This makes no API calls.
uv run model_bench run

# Plan one project's seats with two candidates.
uv run model_bench run \
  --project hypocrisynow \
  --models gpt-4.1-mini,gemini-3.5-flash

# Execute only after reviewing the plan and available credentials.
uv run model_bench run \
  --project hypocrisynow \
  --models gpt-4.1-mini,gemini-3.5-flash \
  --execute

# Show the latest report.
uv run model_bench results
```

The portfolio root defaults to `~/projects`. Set `PROJECTS_ROOT` or pass
`--projects-root` for a different immediate-child repository root.

## Contract and discovery

The current `seats.v1` contract and validator live in the sibling
`project-scaffolding` repository. Discovery:

1. checks only immediate child repositories under the portfolio root;
2. finds root-level `seats.yaml` files deterministically;
3. imports the canonical `project-scaffolding/scaffold/seats.py` validator;
4. rejects malformed YAML, unknown fields, duplicate project IDs, path
   traversal, and missing fixture/schema/context/label files as hard errors.

There are no silent skips. A valid scan that finds zero contracts emits an
explicit warning.

## Evaluation discipline

### Real fixtures and sealed results

Each seat points to project-owned JSONL, JSON, YAML, or CSV fixtures.
Development runs select only the deterministic `dev` remainders. A sealed run
requires the exact environment gate declared by that seat:

```bash
MODEL_BENCH_UNSEAL=1 uv run model_bench run \
  --project hypocrisynow \
  --split sealed \
  --models gpt-4.1-mini,gemini-3.5-flash \
  --execute
```

Use development fixtures for prompt and runner work. Publication numbers should
come from one deliberate sealed run, not repeated tuning against the holdout.

### FROZEN seats

`FROZEN` is policy, not a label. Frozen seats are reported with the incumbent
and reason, but their fixtures are not loaded, they are not swept against
alternatives, and no replacement recommendation is produced.

This protects ai-memory's paper-comparable LongMemEval judge and its
deployment-honest answerer.

### Dirty-input pressure

Every `messy` or `adversarial` seat receives one deterministic, semantics-
preserving dirty variant by default. This adds formatting and forwarding noise
without mutating the source fixture. Use `--no-dirty` only for a targeted
diagnostic, not publication evidence.

### Validity before judgment

The project contract gates the returned artifact before the quality judge sees
it:

- `json`: parse and validate against the project JSON Schema;
- `image`: inspect actual encoded bytes, MIME, dimensions, size, and ratio;
- `free_text`: require non-empty text without invalid NUL content;
- `code`: require an explicitly injected sandbox executor. Untrusted code is
  never executed directly by the default CLI.

Invalid artifacts receive a hard-floor score of zero. A fluent judge cannot
rescue malformed JSON or a broken artifact.

Project-file contexts are size-bounded. Vision fixture paths are resolved
inside the owning project and attached as actual multimodal inputs. Stability
image generation fails closed when `STABILITY_API_KEY` is unavailable.

## Commands

| Command | Description |
|---|---|
| `seats` | Strictly validate and list discovered seats |
| `run` | Produce a dry seat plan by default |
| `run --execute` | Execute candidate and judge calls |
| `run --project ID` | Restrict to one or more comma-separated projects |
| `run --seat ID` | Restrict by seat ID or `project/seat` |
| `run --split sealed` | Use the explicitly unsealed holdout |
| `run --no-judge` | Capture validity, latency, errors, and cost only |
| `estimate` | Show candidate and judge call counts without calls |
| `models` | List candidate capabilities and availability |
| `results` | Show the latest per-seat report |

The retired fixed-category task bank remains available temporarily through the
hidden `legacy-run` command. It is not the source of truth for seat-fit work.

## Reports and recommendations

Each run writes an atomic JSON/Markdown pair under `results/`. Reports include:

- seat and project identity;
- exact incumbent and candidates;
- fixture split, dirty variants, and source hashes;
- quality score, artifact-validity rate, latency, errors, and cost;
- deltas against the incumbent;
- case and run provenance.

A LIVE replacement is suggested only when both incumbent and candidate have
complete, fully valid, error-free evidence on the same case count. The report
is advisory; changing a production pin requires a separate project decision.

## Credentials

Cloud calls use the provider environment variables expected by LiteLLM.
`STABILITY_API_KEY` is required for the Stability image incumbent. Ollama uses
`OLLAMA_HOST` when configured. Keep credentials in `.env` or the project secret
manager; never commit them. The quality judge defaults to `gpt-5.5`; override
it with `MODEL_BENCH_JUDGE_MODEL` when a deliberate, available judge is needed.
