# Seat Report: `extraction`

- Run: `20260726T052446Z-hypocrisynow-extraction`
- Project: `hypocrisynow`
- Pin status: **LIVE**
- Incumbent: `gpt-4o-mini`
- Cases: 2
- Started: `2026-07-26T05:26:30.718907+00:00`
- Finished: `2026-07-26T05:26:58.937451+00:00`

## Per-seat matrix

| Model | Chair | Score | Validity | Latency | Errors | Cost | Δ Score | Δ Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `gpt-4o-mini` | incumbent | 1.500 | 100.0% | 2020ms | 0 | $0.000549 | +0.000 | +0.000000 |
| `gemini/gemini-3.5-flash` | candidate | 2.000 | 50.0% | 5536ms | 0 | $0.027251 | +0.500 | +0.026702 |
| `gpt-4.1-mini` | candidate | 0.000 | 100.0% | 614ms | 0 | $0.000727 | -1.500 | +0.000178 |

## Recommendation

**keep_current** — No candidate matched or exceeded incumbent validity with a measured quality gain or non-regressive cost saving.

```json
{
  "avg_latency_ms": 2019.5,
  "avg_score": 1.5,
  "case_count": 2,
  "errors": 0,
  "judged_cases": 2,
  "model_id": "gpt-4o-mini",
  "total_cost_usd": 0.0005487000000000001,
  "validity_rate": 1.0
}
```

## Provenance

```json
{
  "cases": {
    "extraction-003": {
      "fixture_id": "extraction-003",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "extraction-003"
    },
    "extraction-003::dirty-v1": {
      "fixture_id": "extraction-003",
      "is_dirty": true,
      "split": "sealed",
      "variant_id": "extraction-003::dirty-v1"
    }
  },
  "run": {
    "call_parameters": {
      "max_tokens": 1500,
      "temperature": 0.3
    },
    "dirty_variants": true,
    "fixture_path": "benchmarks/seats/extraction.jsonl",
    "fixtures_sha256": "5583a1b6df446670dd7c60d913afb809273a188f2161c8edd864e30e36fe9fdb",
    "project_root": ".",
    "schema_path": "schemas/seat-extraction-output.schema.json",
    "seats_path": "seats.yaml",
    "seats_sha256": "663820a3f6c0a85277884f60a52558da4609f8e5fe4ce5ab9e9fe09ba900ce48",
    "split": "sealed"
  }
}
```

_Artifact validity is applied before judging; invalid artifacts receive a hard-floor score of 0._
