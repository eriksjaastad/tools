from __future__ import annotations

import pytest

from model_bench.seat_runner import (
    SeatCaseResult,
    SeatRun,
    SeatRunManifest,
    ValidityResult,
)
from model_bench.seat_scorer import score_seat_run


def _manifest(status: str = "LIVE") -> SeatRunManifest:
    candidates = ["incumbent"] if status == "FROZEN" else ["incumbent", "candidate"]
    return SeatRunManifest(
        schema_version="seat-run.v1",
        run_id="run-1",
        project_id="example",
        seat_id="extraction",
        seat_status=status,
        current_pin={
            "provider": "fake",
            "model": "incumbent",
            "status": status,
            "reason": "test",
        },
        incumbent_model_id="incumbent",
        candidate_model_ids=candidates,
        case_ids=["one", "two"],
        started_at="2026-07-25T12:00:00+00:00",
        finished_at="2026-07-25T12:01:00+00:00",
        provenance={"seats_file": "seats.yaml"},
        case_provenance={
            "one": {"source_ref": "fixture.jsonl:1"},
            "two": {"source_ref": "fixture.jsonl:2"},
        },
    )


def _result(
    model_id: str,
    case_id: str,
    *,
    score: float,
    valid: bool = True,
    latency: int = 100,
    cost: float = 0.1,
    error: str | None = None,
    judge_error: str | None = None,
) -> SeatCaseResult:
    return SeatCaseResult(
        seat_id="extraction",
        case_id=case_id,
        model_id=model_id,
        is_incumbent=model_id == "incumbent",
        prompt="prompt",
        response="response",
        latency_ms=latency,
        tokens_in=10,
        tokens_out=20,
        cost_usd=cost,
        validity=ValidityResult(valid, "" if valid else "invalid"),
        judge_score=score,
        error=error,
        judge_error=judge_error,
        provenance={"source_ref": f"fixture.jsonl:{case_id}"},
    )


def test_aggregates_score_validity_latency_errors_and_cost() -> None:
    run = SeatRun(
        manifest=_manifest(),
        results=[
            _result("incumbent", "one", score=4.0, latency=100, cost=0.2),
            _result(
                "incumbent",
                "two",
                score=0.0,
                valid=False,
                latency=300,
                cost=0.3,
            ),
            _result("candidate", "one", score=4.5, latency=80, cost=0.05),
            _result(
                "candidate",
                "two",
                score=4.0,
                latency=120,
                cost=0.05,
            ),
        ],
    )

    scorecard = score_seat_run(run)
    incumbent = scorecard.candidates["incumbent"]
    candidate = scorecard.candidates["candidate"]

    assert incumbent.avg_score == pytest.approx(2.0)
    assert incumbent.validity_rate == pytest.approx(0.5)
    assert incumbent.avg_latency_ms == pytest.approx(200)
    assert incumbent.total_cost_usd == pytest.approx(0.5)
    assert incumbent.errors == 0
    assert candidate.avg_score == pytest.approx(4.25)
    assert candidate.score_delta_vs_incumbent == pytest.approx(2.25)
    assert candidate.cost_delta_vs_incumbent == pytest.approx(-0.4)
    assert scorecard.recommendation.status == "no_recommendation"
    assert scorecard.recommendation.candidate_model_id is None


def test_recommendation_requires_complete_comparable_evidence() -> None:
    run = SeatRun(
        manifest=_manifest(),
        results=[
            _result("incumbent", "one", score=4.0),
            _result("incumbent", "two", score=4.0),
            _result("candidate", "one", score=5.0, judge_error="judge timeout"),
            _result("candidate", "two", score=5.0),
        ],
    )

    scorecard = score_seat_run(run)

    assert scorecard.recommendation.status == "keep_current"
    assert scorecard.recommendation.candidate_model_id == "incumbent"
    assert scorecard.candidates["candidate"].errors == 1


def test_invalid_scored_artifacts_cannot_produce_recommendation() -> None:
    run = SeatRun(
        manifest=_manifest(),
        results=[
            _result("incumbent", "one", score=1.0, valid=False),
            _result("incumbent", "two", score=1.0, valid=False),
            _result("candidate", "one", score=5.0, valid=False),
            _result("candidate", "two", score=5.0, valid=False),
        ],
    )

    scorecard = score_seat_run(run)

    assert scorecard.candidates["candidate"].validity_rate == 0.0
    assert scorecard.recommendation.status == "no_recommendation"
    assert scorecard.recommendation.candidate_model_id is None


def test_non_regressive_cost_saving_can_support_live_recommendation() -> None:
    run = SeatRun(
        manifest=_manifest(),
        results=[
            _result("incumbent", "one", score=4.0, cost=0.4),
            _result("incumbent", "two", score=4.0, cost=0.4),
            _result("candidate", "one", score=4.0, cost=0.1),
            _result("candidate", "two", score=4.0, cost=0.1),
        ],
    )

    scorecard = score_seat_run(run)

    assert scorecard.recommendation.status == "consider_replacement"
    assert scorecard.recommendation.evidence["cost_delta_usd"] == pytest.approx(-0.6)


def test_frozen_seat_is_report_only_even_if_extra_results_are_supplied() -> None:
    run = SeatRun(
        manifest=_manifest("FROZEN"),
        results=[
            _result("incumbent", "one", score=3.0),
            _result("incumbent", "two", score=3.5),
            _result("candidate", "one", score=5.0),
            _result("candidate", "two", score=5.0),
        ],
    )

    scorecard = score_seat_run(run)

    assert scorecard.recommendation.status == "frozen"
    assert scorecard.recommendation.candidate_model_id is None
    assert "replacement recommendations" in scorecard.recommendation.summary
    assert set(scorecard.candidates) == {"incumbent"}
