"""JSON and Markdown reporting for per-seat score matrices."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .seat_scorer import SeatScorecard


def seat_scorecard_to_dict(scorecard: SeatScorecard) -> dict[str, Any]:
    """Serialize a scorecard without dropping manifest or case provenance."""

    return _json_ready(
        {
            "schema_version": "seat-report.v1",
            "manifest": asdict(scorecard.manifest),
            "candidates": {
                model_id: asdict(candidate)
                for model_id, candidate in scorecard.candidates.items()
            },
            "recommendation": asdict(scorecard.recommendation),
            "case_results": [asdict(result) for result in scorecard.case_results],
        }
    )


def render_seat_markdown(scorecard: SeatScorecard) -> str:
    """Render one seat's score, validity, latency, error, and cost matrix."""

    manifest = scorecard.manifest
    lines = [
        f"# Seat Report: `{_escape(manifest.seat_id)}`",
        "",
        f"- Run: `{_escape(manifest.run_id)}`",
        f"- Project: `{_escape(manifest.project_id or 'unknown')}`",
        f"- Pin status: **{_escape(manifest.seat_status)}**",
        f"- Incumbent: `{_escape(manifest.incumbent_model_id)}`",
        f"- Cases: {len(manifest.case_ids)}",
        f"- Started: `{_escape(manifest.started_at)}`",
        f"- Finished: `{_escape(manifest.finished_at)}`",
        "",
    ]
    if manifest.seat_status == "FROZEN":
        reason = manifest.provenance.get("frozen_reason", "No reason supplied.")
        lines.extend(
            [
                (
                    "> FROZEN: report-only incumbent baseline. No replacement "
                    "recommendation or candidate sweep is permitted."
                ),
                f"> Reason: {_escape(reason)}",
                "",
            ]
        )

    lines.extend(
        [
            "## Per-seat matrix",
            "",
            "| Model | Chair | Score | Validity | Latency | Errors | Cost | Δ Score | Δ Cost |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for candidate in sorted(
        scorecard.candidates.values(),
        key=lambda item: (not item.is_incumbent, -item.avg_score, item.model_id),
    ):
        score_delta = _format_delta(candidate.score_delta_vs_incumbent)
        cost_delta = _format_money_delta(candidate.cost_delta_vs_incumbent)
        lines.append(
            f"| `{_escape(candidate.model_id)}` "
            f"| {'incumbent' if candidate.is_incumbent else 'candidate'} "
            f"| {candidate.avg_score:.3f} "
            f"| {candidate.validity_rate:.1%} "
            f"| {candidate.avg_latency_ms:.0f}ms "
            f"| {candidate.errors} "
            f"| ${candidate.total_cost_usd:.6f} "
            f"| {score_delta} "
            f"| {cost_delta} |"
        )

    recommendation = scorecard.recommendation
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            (
                f"**{_escape(recommendation.status)}** — "
                f"{_escape(recommendation.summary)}"
            ),
            "",
            "```json",
            json.dumps(_json_ready(recommendation.evidence), indent=2, sort_keys=True),
            "```",
            "",
            "## Provenance",
            "",
            "```json",
            json.dumps(
                _json_ready(
                    {
                        "run": manifest.provenance,
                        "cases": manifest.case_provenance,
                    }
                ),
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            (
                "_Artifact validity is applied before judging; invalid artifacts "
                "receive a hard-floor score of 0._"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def save_seat_report(
    scorecard: SeatScorecard,
    results_dir: Path,
    *,
    stem: str | None = None,
) -> tuple[Path, Path]:
    """Write one JSON and Markdown per-seat matrix."""

    results_dir = results_dir.expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = (
        _safe(stem)
        if stem is not None
        else (
            f"seat_{_safe(scorecard.manifest.seat_id)}_{_safe(scorecard.manifest.run_id)}"
        )
    )
    json_path = results_dir / f"{safe_stem}.json"
    markdown_path = results_dir / f"{safe_stem}.md"
    _atomic_write(
        json_path,
        json.dumps(seat_scorecard_to_dict(scorecard), indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(markdown_path, render_seat_markdown(scorecard))
    return json_path, markdown_path


def save_seat_reports(
    scorecards: list[SeatScorecard],
    results_dir: Path,
) -> list[tuple[Path, Path]]:
    """Write independent report pairs for a multi-seat run."""

    return [save_seat_report(scorecard, results_dir) for scorecard in scorecards]


def _format_delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.3f}"


def _format_money_delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.6f}"


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.") or "unknown"


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "size": len(value)}
    return value


def _atomic_write(path: Path, content: str) -> None:
    if path.parent.resolve() != path.parent:
        raise ValueError(f"report parent must be resolved: {path.parent}")
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
