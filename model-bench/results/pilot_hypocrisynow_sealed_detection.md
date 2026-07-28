# Seat Report: `detection`

- Run: `20260726T052446Z-hypocrisynow-detection`
- Project: `hypocrisynow`
- Pin status: **LIVE**
- Incumbent: `gpt-4o-mini`
- Cases: 6
- Started: `2026-07-26T05:24:46.157878+00:00`
- Finished: `2026-07-26T05:25:49.543378+00:00`

## Per-seat matrix

| Model | Chair | Score | Validity | Latency | Errors | Cost | Δ Score | Δ Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `gpt-4o-mini` | incumbent | 3.500 | 100.0% | 1156ms | 0 | $0.000975 | +0.000 | +0.000000 |
| `gpt-4.1-mini` | candidate | 4.333 | 100.0% | 1555ms | 0 | $0.002824 | +0.833 | +0.001849 |
| `gemini/gemini-3.5-flash` | candidate | 0.833 | 16.7% | 3138ms | 0 | $0.033291 | -2.667 | +0.032316 |

## Recommendation

**consider_replacement** — gpt-4.1-mini is the strongest fully evaluated candidate on this run; consider replacement only with the attached seat evidence.

```json
{
  "avg_latency_ms": 1555.0,
  "avg_score": 4.333333333333333,
  "case_count": 6,
  "cost_delta_usd": 0.0018492500000000006,
  "errors": 0,
  "incumbent_cost_usd": 0.0009751499999999998,
  "incumbent_model_id": "gpt-4o-mini",
  "incumbent_score": 3.5,
  "incumbent_validity_rate": 1.0,
  "judged_cases": 6,
  "model_id": "gpt-4.1-mini",
  "score_delta": 0.833333333333333,
  "total_cost_usd": 0.0028244000000000003,
  "validity_rate": 1.0
}
```

## Provenance

```json
{
  "cases": {
    "detection-classify-003": {
      "fixture_id": "detection-classify-003",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "detection-classify-003"
    },
    "detection-classify-007": {
      "fixture_id": "detection-classify-007",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "detection-classify-007"
    },
    "detection-score-003": {
      "fixture_id": "detection-score-003",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "detection-score-003"
    },
    "detection-score-003::dirty-v1": {
      "fixture_id": "detection-score-003",
      "is_dirty": true,
      "split": "sealed",
      "variant_id": "detection-score-003::dirty-v1"
    },
    "detection-score-009": {
      "fixture_id": "detection-score-009",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "detection-score-009"
    },
    "detection-second-opinion-015": {
      "fixture_id": "detection-second-opinion-015",
      "is_dirty": false,
      "split": "sealed",
      "variant_id": "detection-second-opinion-015"
    }
  },
  "run": {
    "call_parameters": {
      "max_tokens": 500,
      "temperature": 0.3
    },
    "dirty_variants": true,
    "fixture_path": "benchmarks/seats/detection.jsonl",
    "fixtures_sha256": "457acb347bd6e296038fddb3089633681b9c130648c4c6c840ddb059c667dd2e",
    "project_root": ".",
    "schema_path": "schemas/seat-detection-output.schema.json",
    "seats_path": "seats.yaml",
    "seats_sha256": "663820a3f6c0a85277884f60a52558da4609f8e5fe4ce5ab9e9fe09ba900ce48",
    "split": "sealed"
  }
}
```

_Artifact validity is applied before judging; invalid artifacts receive a hard-floor score of 0._
