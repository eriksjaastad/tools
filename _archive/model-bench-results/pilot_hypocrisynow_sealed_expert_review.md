# Seat Report: `expert_review`

- Run: `20260726T052446Z-hypocrisynow-expert_review`
- Project: `hypocrisynow`
- Pin status: **LIVE**
- Incumbent: `gpt-4o-mini`
- Cases: 3
- Started: `2026-07-26T05:25:49.546826+00:00`
- Finished: `2026-07-26T05:26:30.708420+00:00`

## Per-seat matrix

| Model | Chair | Score | Validity | Latency | Errors | Cost | Δ Score | Δ Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `gpt-4o-mini` | incumbent | 3.333 | 100.0% | 1572ms | 0 | $0.000727 | +0.000 | +0.000000 |
| `gemini/gemini-3.5-flash` | candidate | 3.000 | 100.0% | 3402ms | 0 | $0.019362 | -0.333 | +0.018635 |
| `gpt-4.1-mini` | candidate | 3.000 | 100.0% | 2908ms | 0 | $0.002107 | -0.333 | +0.001380 |

## Recommendation

**keep_current** — No candidate matched or exceeded incumbent validity with a measured quality gain or non-regressive cost saving.

```json
{
  "avg_latency_ms": 1571.6666666666667,
  "avg_score": 3.3333333333333335,
  "case_count": 3,
  "errors": 0,
  "judged_cases": 3,
  "model_id": "gpt-4o-mini",
  "total_cost_usd": 0.0007270499999999999,
  "validity_rate": 1.0
}
```

## Provenance

```json
{
  "cases": {
    "expert-review-010": {
      "fixture_id": "expert-review-010",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "expert-review-010"
    },
    "expert-review-010::dirty-v1": {
      "fixture_id": "expert-review-010",
      "is_dirty": true,
      "split": "sealed",
      "variant_id": "expert-review-010::dirty-v1"
    },
    "expert-review-011": {
      "fixture_id": "expert-review-011",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "expert-review-011"
    }
  },
  "run": {
    "call_parameters": {
      "temperature": 0.3
    },
    "dirty_variants": true,
    "fixture_path": "benchmarks/seats/expert_review.jsonl",
    "fixtures_sha256": "d512b8b724f15fa12f352356d7f29d66a4b5d97cd82c800cd97565d5fee42eb2",
    "project_root": ".",
    "schema_path": "schemas/seat-expert-review-output.schema.json",
    "seats_path": "seats.yaml",
    "seats_sha256": "663820a3f6c0a85277884f60a52558da4609f8e5fe4ce5ab9e9fe09ba900ce48",
    "split": "sealed"
  }
}
```

_Artifact validity is applied before judging; invalid artifacts receive a hard-floor score of 0._
