from __future__ import annotations

from pathlib import Path

from model_bench.seat_bench import plan_seats
from model_bench.seats import ModelPin, PinStatus, SeatDefinition


def _seat(tmp_path: Path, *, status: PinStatus) -> SeatDefinition:
    fixture = tmp_path / "fixtures.jsonl"
    fixture.write_text(
        '{"fixture_id":"case-2","input":"real","expected_output":"gold"}\n'
    )
    seats_path = tmp_path / "seats.yaml"
    seats_path.write_text("schema_version: seats.v1\n")
    raw = {
        "id": "answerer",
        "job": "Answer.",
        "input_character": "messy",
        "required_capabilities": ["long_context"],
        "output_contract": {"type": "free_text", "validation": "Non-empty."},
        "current_pin": {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "status": status.value,
            "reason": "Pinned.",
        },
        "eval_fixtures": {
            "path": "fixtures.jsonl",
            "format": "jsonl",
            "id_field": "fixture_id",
            "input_field": "input",
            "expected_output_field": "expected_output",
            "split": {
                "method": "deterministic_hash_modulo",
                "hash_field": "fixture_id",
                "modulo": 5,
                "dev_remainders": [1, 2, 3, 4],
                "sealed_remainders": [0],
                "sealed_unseal_env": "TEST_UNSEAL",
            },
        },
    }
    return SeatDefinition(
        project_id="project",
        project_root=tmp_path,
        seats_path=seats_path,
        seat_id="answerer",
        job="Answer.",
        pin=ModelPin(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            status=status,
            reason="Pinned.",
            parameters={},
        ),
        fixture_path=fixture,
        schema_path=None,
        context_paths=(),
        labels_path=None,
        raw=raw,
    )


def test_frozen_plan_reports_reason_without_loading_or_sweeping(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures.jsonl"
    seat = _seat(tmp_path, status=PinStatus.FROZEN)
    fixture.unlink()

    plan = plan_seats([seat])

    assert plan[0].status == "FROZEN"
    assert plan[0].cases == 0
    assert plan[0].candidate_model_ids == ("claude-haiku-4-5-20251001",)
    assert plan[0].frozen_reason == "Pinned."
