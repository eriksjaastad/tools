from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_bench.caller import CallResult
from model_bench.registry import ModelEntry
from model_bench.seat_runner import (
    FrozenSeatError,
    RenderedCase,
    SeatRunner,
    ValidityResult,
)


def _model(model_id: str) -> ModelEntry:
    return ModelEntry(
        id=model_id,
        display_name=model_id,
        provider="fake",
        tier="test",
    )


def _seat(status: str = "LIVE") -> dict:
    return {
        "id": "claim_extraction",
        "current_pin": {
            "provider": "fake",
            "model": "incumbent",
            "status": status,
            "reason": "test pin",
        },
    }


class FakeCaller:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, int]] = []

    def __call__(
        self,
        model: ModelEntry,
        prompt: str,
        timeout_seconds: int,
    ) -> CallResult:
        self.calls.append((model.id, prompt, timeout_seconds))
        response = self.responses[model.id]
        return CallResult(
            model_id=model.id,
            response=response,
            latency_ms=100 + len(self.calls),
            tokens_in=10,
            tokens_out=20,
        )


class FakeJudge:
    def __init__(self) -> None:
        self.response_batches: list[dict[str, str]] = []

    def __call__(self, **kwargs):
        responses = dict(kwargs["responses"])
        self.response_batches.append(responses)
        return {
            model_id: {
                "overall": 4.5 if "good" in response else 3.0,
                "reasoning": "fixture evidence",
                "scores": {"quality": 4},
            }
            for model_id, response in responses.items()
        }


def _validator(**kwargs) -> ValidityResult:
    artifact = kwargs["artifact"]
    if artifact.startswith("INVALID"):
        return ValidityResult(False, "schema mismatch", {"path": "$.verdict"})
    return ValidityResult(True)


def test_validity_precedes_judging_and_invalid_artifacts_get_hard_floor() -> None:
    caller = FakeCaller(
        {
            "incumbent": "acceptable",
            "candidate-good": "good response",
            "candidate-invalid": "INVALID json",
        }
    )
    judge = FakeJudge()
    runner = SeatRunner(
        caller=caller,
        validator=_validator,
        judge=judge,
        cost_estimator=lambda model, tokens_in, tokens_out: tokens_out / 1000,
    )

    run = runner.run(
        seat=_seat(),
        cases=[
            {
                "fixture_id": "case-1",
                "prompt": "Extract the claim.",
                "source_refs": ["tests/source.md"],
            }
        ],
        candidates=[
            _model("incumbent"),
            _model("candidate-good"),
            _model("candidate-invalid"),
        ],
        project_id="example",
        timeout_seconds=17,
        run_id="run-1",
        provenance={"seats_file": "seats.yaml", "fixture_sha256": "abc"},
    )

    assert [call[0] for call in caller.calls] == [
        "incumbent",
        "candidate-good",
        "candidate-invalid",
    ]
    assert all(call[2] == 17 for call in caller.calls)
    assert judge.response_batches == [
        {
            "incumbent": "acceptable",
            "candidate-good": "good response",
        }
    ]

    invalid = next(
        result for result in run.results if result.model_id == "candidate-invalid"
    )
    assert invalid.validity.valid is False
    assert invalid.judge_score == 0.0
    assert "hard floor" in invalid.judge_reasoning
    assert invalid.cost_usd == pytest.approx(0.02)

    assert run.manifest.schema_version == "seat-run.v1"
    assert run.manifest.run_id == "run-1"
    assert run.manifest.candidate_model_ids == [
        "incumbent",
        "candidate-good",
        "candidate-invalid",
    ]
    assert run.manifest.provenance["seats_file"] == "seats.yaml"
    assert run.manifest.case_provenance["case-1"] == {
        "fixture_id": "case-1",
        "source_refs": ["tests/source.md"],
    }


def test_frozen_seat_calls_only_incumbent_and_never_sweeps_candidates() -> None:
    caller = FakeCaller(
        {
            "incumbent": "acceptable",
            "challenger": "good response",
        }
    )
    judge = FakeJudge()
    runner = SeatRunner(
        caller=caller,
        validator=_validator,
        judge=judge,
        cost_estimator=lambda model, tokens_in, tokens_out: 0.0,
    )

    run = runner.run(
        seat=_seat("FROZEN"),
        cases=[{"id": "case-1", "prompt": "Grade this."}],
        candidates=[_model("incumbent"), _model("challenger")],
        project_id="example",
    )

    assert [call[0] for call in caller.calls] == ["incumbent"]
    assert run.manifest.candidate_model_ids == ["incumbent"]
    assert len(run.results) == 1
    assert run.results[0].is_incumbent is True


def test_frozen_seat_requires_resolvable_incumbent() -> None:
    runner = SeatRunner(
        caller=FakeCaller({"challenger": "response"}),
        validator=_validator,
        judge=None,
    )

    with pytest.raises(FrozenSeatError):
        runner.run(
            seat=_seat("FROZEN"),
            cases=[{"id": "case-1", "prompt": "Grade this."}],
            candidates=[_model("challenger")],
        )


def test_structured_case_requires_project_owned_prompt_builder() -> None:
    runner = SeatRunner(
        caller=FakeCaller({"incumbent": "response"}),
        validator=_validator,
        judge=None,
    )

    with pytest.raises(ValueError, match="project-owned prompt_builder"):
        runner.run(
            seat=_seat(),
            cases=[{"id": "case-1", "input": {"article": "tracked text"}}],
            candidates=[_model("incumbent")],
        )


def test_manifest_timestamps_can_be_injected_for_reproducible_tests() -> None:
    moments = iter(
        [
            datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
            datetime(2026, 7, 25, 12, 1, tzinfo=UTC),
        ]
    )
    runner = SeatRunner(
        caller=FakeCaller({"incumbent": "response"}),
        validator=_validator,
        judge=None,
        now=lambda: next(moments),
    )

    run = runner.run(
        seat=_seat(),
        cases=[{"id": "case-1", "prompt": "Prompt"}],
        candidates=[_model("incumbent")],
        run_id="stable",
    )

    assert run.manifest.started_at == "2026-07-25T12:00:00+00:00"
    assert run.manifest.finished_at == "2026-07-25T12:01:00+00:00"


def test_loaded_seat_case_and_image_artifact_flow_through_adapters(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "input.png"
    seat = SimpleNamespace(
        id="poster_generation",
        project_id="creative",
        project_root=tmp_path,
        seats_path=tmp_path / "seats.yaml",
        fixture_path=tmp_path / "fixtures.jsonl",
        schema_path=None,
        labels_path=None,
        raw={
            "id": "poster_generation",
            "current_pin": {
                "provider": "fake",
                "model": "incumbent",
                "status": "LIVE",
                "reason": "production pin",
            },
        },
    )
    case = SimpleNamespace(
        fixture_id="poster-1",
        variant_id="poster-1::dirty-v1",
        input={"brief": "Draw a lighthouse"},
        source_row={"source_refs": ["briefs/poster-1.md"]},
        split="dev",
        is_dirty=True,
    )
    call_inputs: list[tuple[str, str, int, list[Path]]] = []
    validated_artifacts: list[object] = []
    judged_artifacts: list[dict[str, object]] = []

    def image_caller(
        model: ModelEntry,
        prompt: str,
        timeout_seconds: int,
        *,
        image_paths: list[Path],
    ) -> CallResult:
        call_inputs.append((model.id, prompt, timeout_seconds, image_paths))
        return CallResult(
            model_id=model.id,
            response="generated poster",
            latency_ms=250,
            tokens_in=15,
            tokens_out=5,
            artifact=b"\x89PNG\r\n",
            artifact_mime_type="image/png",
        )

    def image_validator(**kwargs):
        validated_artifacts.append(kwargs["artifact"])
        return SimpleNamespace(
            valid=True,
            parsed_output=b"\x89PNG\r\n",
            hard_floor_reason=None,
            mime_type="image/png",
            width_px=1024,
            height_px=768,
        )

    def image_judge(**kwargs):
        judged_artifacts.append(dict(kwargs["responses"]))
        return {"incumbent": {"overall": 4.75, "reasoning": "usable image"}}

    runner = SeatRunner(
        caller=image_caller,
        validator=image_validator,
        judge=image_judge,
        prompt_builder=lambda **kwargs: RenderedCase(
            prompt=f"Create: {kwargs['case'].input['brief']}",
            image_paths=(image_path,),
        ),
        cost_estimator=lambda model, tokens_in, tokens_out: 0.03,
    )

    run = runner.run(
        seat=seat,
        cases=[case],
        candidates=[_model("incumbent")],
        timeout_seconds=19,
    )

    artifact = {"data": b"\x89PNG\r\n", "mime_type": "image/png"}
    assert call_inputs == [
        (
            "incumbent",
            "Create: Draw a lighthouse",
            19,
            [image_path],
        )
    ]
    assert validated_artifacts == [artifact]
    assert judged_artifacts == [{"incumbent": artifact}]
    assert run.manifest.project_id == "creative"
    assert run.manifest.case_ids == ["poster-1::dirty-v1"]
    assert run.manifest.provenance["project_root"] == "."
    assert run.manifest.provenance["seats_path"] == "seats.yaml"
    assert run.manifest.provenance["fixture_path"] == "fixtures.jsonl"
    assert run.manifest.case_provenance["poster-1::dirty-v1"] == {
        "fixture_id": "poster-1",
        "variant_id": "poster-1::dirty-v1",
        "split": "dev",
        "is_dirty": True,
        "source_refs": ["briefs/poster-1.md"],
    }
    result = run.results[0]
    assert result.artifact_size_bytes == len(b"\x89PNG\r\n")
    assert result.artifact_mime_type == "image/png"
    assert result.validity.details == {
        "mime_type": "image/png",
        "width_px": 1024,
        "height_px": 768,
        "parsed_output_type": "bytes",
    }
    assert result.judge_score == pytest.approx(4.75)
