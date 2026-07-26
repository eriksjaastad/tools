"""Pure seat-level aggregation and evidence-only recommendation policy."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .seat_runner import SeatCaseResult, SeatRun, SeatRunManifest


@dataclass
class CandidateSeatScore:
    """Aggregate evidence for one candidate in one seat."""

    model_id: str
    is_incumbent: bool
    avg_score: float
    validity_rate: float
    avg_latency_ms: float
    total_cost_usd: float
    errors: int
    case_count: int
    valid_cases: int
    judged_cases: int
    score_delta_vs_incumbent: float | None = None
    cost_delta_vs_incumbent: float | None = None


@dataclass
class SeatRecommendation:
    """A recommendation backed only by evidence in this run."""

    status: str
    candidate_model_id: str | None
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeatScorecard:
    """Per-seat matrix plus manifest and raw case evidence."""

    manifest: SeatRunManifest
    candidates: dict[str, CandidateSeatScore]
    recommendation: SeatRecommendation
    case_results: list[SeatCaseResult]


def score_seat_run(
    run: SeatRun,
    *,
    min_score_gain: float = 0.1,
    max_score_regression_for_savings: float = 0.0,
    min_cost_savings_usd: float = 1e-9,
) -> SeatScorecard:
    """Aggregate one run and derive a policy-safe recommendation."""

    grouped: dict[str, list[SeatCaseResult]] = defaultdict(list)
    for result in run.results:
        if (
            run.manifest.seat_status == "FROZEN"
            and result.model_id != run.manifest.incumbent_model_id
        ):
            continue
        grouped[result.model_id].append(result)

    candidates = {
        model_id: _aggregate(model_id, results) for model_id, results in grouped.items()
    }
    incumbent = candidates.get(run.manifest.incumbent_model_id)
    if incumbent is not None:
        for score in candidates.values():
            score.score_delta_vs_incumbent = score.avg_score - incumbent.avg_score
            score.cost_delta_vs_incumbent = (
                score.total_cost_usd - incumbent.total_cost_usd
            )

    recommendation = _recommend(
        manifest=run.manifest,
        candidates=candidates,
        incumbent=incumbent,
        min_score_gain=min_score_gain,
        max_score_regression_for_savings=max_score_regression_for_savings,
        min_cost_savings_usd=min_cost_savings_usd,
    )
    return SeatScorecard(
        manifest=run.manifest,
        candidates=candidates,
        recommendation=recommendation,
        case_results=list(run.results),
    )


def _aggregate(
    model_id: str,
    results: list[SeatCaseResult],
) -> CandidateSeatScore:
    judged = [
        float(result.judge_score)
        for result in results
        if result.judge_score is not None
    ]
    valid_cases = sum(result.validity.valid for result in results)
    errors = sum(
        bool(result.error or result.judge_error or result.cost_error)
        for result in results
    )
    return CandidateSeatScore(
        model_id=model_id,
        is_incumbent=any(result.is_incumbent for result in results),
        avg_score=_avg(judged),
        validity_rate=valid_cases / len(results) if results else 0.0,
        avg_latency_ms=_avg([float(result.latency_ms) for result in results]),
        total_cost_usd=sum(result.cost_usd for result in results),
        errors=errors,
        case_count=len(results),
        valid_cases=valid_cases,
        judged_cases=len(judged),
    )


def _recommend(
    *,
    manifest: SeatRunManifest,
    candidates: dict[str, CandidateSeatScore],
    incumbent: CandidateSeatScore | None,
    min_score_gain: float,
    max_score_regression_for_savings: float,
    min_cost_savings_usd: float,
) -> SeatRecommendation:
    if manifest.seat_status == "FROZEN":
        return SeatRecommendation(
            status="frozen",
            candidate_model_id=None,
            summary=(
                "FROZEN seat: incumbent results are report-only; replacement "
                "recommendations and candidate sweeps are disabled."
            ),
            evidence={"incumbent_model_id": manifest.incumbent_model_id},
        )

    if incumbent is None:
        return SeatRecommendation(
            status="no_recommendation",
            candidate_model_id=None,
            summary="No incumbent result is available for an evidence-based comparison.",
        )
    if not _complete_evidence(incumbent):
        return SeatRecommendation(
            status="no_recommendation",
            candidate_model_id=None,
            summary="Incumbent evidence is incomplete or contains execution errors.",
            evidence=_evidence(incumbent),
        )

    eligible: list[CandidateSeatScore] = []
    for candidate in candidates.values():
        if candidate.model_id == incumbent.model_id:
            continue
        if not _complete_evidence(candidate):
            continue
        if candidate.case_count != incumbent.case_count:
            continue
        if candidate.validity_rate < incumbent.validity_rate:
            continue
        quality_gain = candidate.avg_score - incumbent.avg_score
        cost_savings = incumbent.total_cost_usd - candidate.total_cost_usd
        quality_win = quality_gain >= min_score_gain
        savings_win = (
            quality_gain >= -max_score_regression_for_savings
            and cost_savings >= min_cost_savings_usd
        )
        if quality_win or savings_win:
            eligible.append(candidate)

    if not eligible:
        return SeatRecommendation(
            status="keep_current",
            candidate_model_id=incumbent.model_id,
            summary=(
                "No candidate matched or exceeded incumbent validity with a "
                "measured quality gain or non-regressive cost saving."
            ),
            evidence=_evidence(incumbent),
        )

    winner = max(
        eligible,
        key=lambda score: (
            score.avg_score,
            score.validity_rate,
            -score.errors,
            -score.total_cost_usd,
        ),
    )
    evidence = _evidence(winner)
    evidence.update(
        {
            "incumbent_model_id": incumbent.model_id,
            "incumbent_score": incumbent.avg_score,
            "incumbent_validity_rate": incumbent.validity_rate,
            "incumbent_cost_usd": incumbent.total_cost_usd,
            "score_delta": winner.avg_score - incumbent.avg_score,
            "cost_delta_usd": winner.total_cost_usd - incumbent.total_cost_usd,
        }
    )
    return SeatRecommendation(
        status="consider_replacement",
        candidate_model_id=winner.model_id,
        summary=(
            f"{winner.model_id} is the strongest fully evaluated candidate on "
            "this run; consider replacement only with the attached seat evidence."
        ),
        evidence=evidence,
    )


def _complete_evidence(score: CandidateSeatScore) -> bool:
    return (
        score.case_count > 0
        and score.judged_cases == score.case_count
        and score.errors == 0
        and score.validity_rate == 1.0
    )


def _evidence(score: CandidateSeatScore) -> dict[str, Any]:
    return {
        "model_id": score.model_id,
        "avg_score": score.avg_score,
        "validity_rate": score.validity_rate,
        "avg_latency_ms": score.avg_latency_ms,
        "total_cost_usd": score.total_cost_usd,
        "errors": score.errors,
        "case_count": score.case_count,
        "judged_cases": score.judged_cases,
    }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
