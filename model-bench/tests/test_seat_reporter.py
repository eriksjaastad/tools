from __future__ import annotations

import json

from model_bench.seat_reporter import (
    render_seat_markdown,
    save_seat_report,
    save_seat_reports,
    seat_scorecard_to_dict,
)
from model_bench.seat_runner import (
    SeatCaseResult,
    SeatRun,
    SeatRunManifest,
    ValidityResult,
)
from model_bench.seat_scorer import score_seat_run


def _scorecard(status: str = "LIVE"):
    manifest = SeatRunManifest(
        schema_version="seat-run.v1",
        run_id="run/with spaces",
        project_id="example",
        seat_id="expert_review",
        seat_status=status,
        current_pin={
            "provider": "fake",
            "model": "incumbent",
            "status": status,
            "reason": "test",
        },
        incumbent_model_id="incumbent",
        candidate_model_ids=["incumbent"],
        case_ids=["case-1"],
        started_at="2026-07-25T12:00:00+00:00",
        finished_at="2026-07-25T12:01:00+00:00",
        provenance={
            "seats_file": "seats.yaml",
            "seats_sha256": "abc123",
            "fixture_sha256": "def456",
        },
        case_provenance={"case-1": {"source_refs": ["DECISIONS.md"]}},
    )
    result = SeatCaseResult(
        seat_id="expert_review",
        case_id="case-1",
        model_id="incumbent",
        is_incumbent=True,
        prompt="Review this.",
        response='{"verdict":"PASS"}',
        latency_ms=125,
        tokens_in=20,
        tokens_out=10,
        cost_usd=0.002,
        validity=ValidityResult(True),
        judge_score=4.5,
        judge_reasoning="Grounded in the fixture.",
        provenance={"source_refs": ["DECISIONS.md"]},
    )
    return score_seat_run(SeatRun(manifest=manifest, results=[result]))


def test_json_serialization_preserves_manifest_and_case_provenance() -> None:
    data = seat_scorecard_to_dict(_scorecard())

    assert data["schema_version"] == "seat-report.v1"
    assert data["manifest"]["provenance"]["seats_sha256"] == "abc123"
    assert data["manifest"]["case_provenance"]["case-1"] == {
        "source_refs": ["DECISIONS.md"]
    }
    assert data["case_results"][0]["provenance"] == {"source_refs": ["DECISIONS.md"]}
    assert data["candidates"]["incumbent"]["validity_rate"] == 1.0


def test_markdown_contains_per_seat_matrix_and_recommendation_evidence() -> None:
    markdown = render_seat_markdown(_scorecard())

    assert "# Seat Report: `expert_review`" in markdown
    assert "## Per-seat matrix" in markdown
    assert "| Model | Chair | Score | Validity | Latency | Errors | Cost |" in markdown
    assert "| `incumbent` | incumbent | 4.500 | 100.0% | 125ms | 0 |" in markdown
    assert "## Recommendation" in markdown
    assert '"seats_file": "seats.yaml"' in markdown
    assert "validity is applied before judging" in markdown


def test_frozen_markdown_explicitly_disables_replacement_recommendations() -> None:
    scorecard = _scorecard("FROZEN")
    scorecard.manifest.provenance["frozen_reason"] = "Paper comparability."
    markdown = render_seat_markdown(scorecard)

    assert "> FROZEN: report-only incumbent baseline." in markdown
    assert "> Reason: Paper comparability." in markdown
    assert "**frozen**" in markdown


def test_save_writes_json_and_markdown_with_safe_per_seat_names(tmp_path) -> None:
    scorecard = _scorecard()

    json_path, markdown_path = save_seat_report(scorecard, tmp_path)

    assert json_path.name == "seat_expert_review_run-with-spaces.json"
    assert markdown_path.name == "seat_expert_review_run-with-spaces.md"
    assert json.loads(json_path.read_text())["manifest"]["run_id"] == "run/with spaces"
    assert markdown_path.read_text() == render_seat_markdown(scorecard)

    pairs = save_seat_reports([scorecard], tmp_path / "multi")
    assert len(pairs) == 1
    assert pairs[0][0].is_file()
    assert pairs[0][1].is_file()


def test_save_sanitizes_custom_stem_and_leaves_no_atomic_temp_files(
    tmp_path,
) -> None:
    json_path, markdown_path = save_seat_report(
        _scorecard(),
        tmp_path / "reports",
        stem="../../outside report",
    )

    reports_dir = (tmp_path / "reports").resolve()
    assert json_path == reports_dir / "outside-report.json"
    assert markdown_path == reports_dir / "outside-report.md"
    assert list(reports_dir.glob(".*.tmp")) == []
