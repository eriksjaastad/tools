"""Portfolio orchestration for project-owned seat-fit evaluations."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .judge import judge_seat_responses
from .registry import (
    ModelEntry,
    get_models_for_capabilities,
    model_from_pin,
    resolve_models,
)
from .seat_cases import SeatCase, load_seat_cases
from .seat_prompting import build_seat_prompt, image_paths_for_case
from .seat_reporter import save_seat_report
from .seat_runner import RenderedCase, SeatRun, SeatRunManifest, SeatRunner
from .seat_scorer import SeatScorecard, score_seat_run
from .seats import SeatDefinition, discover_seats
from .validity import validate_seat_artifact


@dataclass(frozen=True)
class SeatPlan:
    qualified_id: str
    status: str
    split: str
    cases: int
    dirty_cases: int
    candidate_model_ids: tuple[str, ...]
    current_pin: str
    frozen_reason: str | None = None


def select_seats(
    projects_root: Path,
    *,
    project_ids: set[str] | None = None,
    seat_ids: set[str] | None = None,
    validator_repo: Path | None = None,
) -> list[SeatDefinition]:
    """Strictly discover then filter seats without weakening validation."""
    seats = list(discover_seats(projects_root, validator_repo=validator_repo))
    if project_ids:
        seats = [seat for seat in seats if seat.project_id in project_ids]
    if seat_ids:
        seats = [
            seat
            for seat in seats
            if seat.seat_id in seat_ids or seat.qualified_id in seat_ids
        ]
    if not seats:
        raise ValueError("no seats matched the requested filters")
    return seats


def plan_seats(
    seats: Sequence[SeatDefinition],
    *,
    split: str = "dev",
    model_ids: Sequence[str] | None = None,
    include_dirty: bool = True,
    max_cases: int | None = None,
) -> list[SeatPlan]:
    """Resolve fixture counts and policy-safe candidate lists without calls."""
    plans: list[SeatPlan] = []
    for seat in seats:
        incumbent = _incumbent(seat)
        if seat.is_frozen:
            plans.append(
                SeatPlan(
                    qualified_id=seat.qualified_id,
                    status=seat.status.value,
                    split=split,
                    cases=0,
                    dirty_cases=0,
                    candidate_model_ids=(incumbent.id,),
                    current_pin=incumbent.id,
                    frozen_reason=seat.pin.reason,
                )
            )
            continue
        cases = _cases(
            seat,
            split=split,
            include_dirty=include_dirty,
            max_cases=max_cases,
        )
        candidates = _candidates(seat, incumbent, model_ids)
        plans.append(
            SeatPlan(
                qualified_id=seat.qualified_id,
                status=seat.status.value,
                split=split,
                cases=len(cases),
                dirty_cases=sum(case.is_dirty for case in cases),
                candidate_model_ids=tuple(model.id for model in candidates),
                current_pin=incumbent.id,
            )
        )
    return plans


def run_seats(
    seats: Sequence[SeatDefinition],
    *,
    results_dir: Path,
    split: str = "dev",
    model_ids: Sequence[str] | None = None,
    include_dirty: bool = True,
    max_cases: int | None = None,
    no_judge: bool = False,
) -> list[tuple[SeatScorecard, tuple[Path, Path]]]:
    """Execute selected seats and atomically save per-seat evidence reports."""
    completed: list[tuple[SeatScorecard, tuple[Path, Path]]] = []
    run_group = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for seat in seats:
        incumbent = _incumbent(seat)
        if seat.is_frozen:
            scorecard = score_seat_run(_frozen_run(seat, incumbent, run_group))
        else:
            cases = _cases(
                seat,
                split=split,
                include_dirty=include_dirty,
                max_cases=max_cases,
            )
            candidates = _candidates(seat, incumbent, model_ids)
            timeout_seconds = int(seat.pin.parameters.get("timeout_seconds", 120))
            runner = SeatRunner(
                validator=validate_seat_artifact,
                judge=None if no_judge else judge_seat_responses,
                prompt_builder=lambda *, seat, case: RenderedCase(
                    prompt=build_seat_prompt(seat=seat, case=case),
                    image_paths=tuple(
                        image_paths_for_case(
                            project_root=seat.project_root,
                            seat=seat,
                            case=case,
                        )
                    ),
                ),
            )
            run = runner.run(
                seat=seat,
                cases=cases,
                candidates=candidates,
                incumbent=incumbent,
                timeout_seconds=timeout_seconds,
                call_parameters=_call_parameters(seat),
                run_id=f"{run_group}-{seat.project_id}-{seat.seat_id}",
                provenance={
                    "split": split,
                    "dirty_variants": include_dirty,
                    "call_parameters": _call_parameters(seat),
                    "seats_sha256": _sha256(seat.seats_path),
                    "fixtures_sha256": _sha256(seat.fixture_path),
                },
            )
            scorecard = score_seat_run(run)
        paths = save_seat_report(scorecard, results_dir)
        completed.append((scorecard, paths))
    return completed


def _cases(
    seat: SeatDefinition,
    *,
    split: str,
    include_dirty: bool,
    max_cases: int | None,
) -> list[SeatCase]:
    cases = load_seat_cases(
        seat.project_root,
        seat.raw,
        split=split,
        include_dirty=include_dirty,
    )
    if not cases:
        raise ValueError(f"{seat.qualified_id}: split {split!r} has no cases")
    if max_cases is not None:
        if max_cases <= 0:
            raise ValueError("max_cases must be positive")
        cases = cases[:max_cases]
    return cases


def _candidates(
    seat: SeatDefinition,
    incumbent: ModelEntry,
    model_ids: Sequence[str] | None,
) -> list[ModelEntry]:
    required = set(seat.raw["required_capabilities"])
    if model_ids:
        try:
            candidates = resolve_models(list(model_ids))
        except ValueError as exc:
            raise ValueError(f"{seat.qualified_id}: {exc}") from exc
        incompatible = [
            model.id for model in candidates if not required <= model.capabilities
        ]
        if incompatible:
            raise ValueError(
                f"{seat.qualified_id}: candidates lack {sorted(required)}: "
                f"{incompatible}"
            )
    else:
        candidates = get_models_for_capabilities(required)
    by_id = {model.id: model for model in candidates}
    by_id.setdefault(incumbent.id, incumbent)
    return list(by_id.values())


def _incumbent(seat: SeatDefinition) -> ModelEntry:
    return model_from_pin(
        {
            "provider": seat.pin.provider,
            "model": seat.pin.model,
        },
        required_capabilities=seat.raw["required_capabilities"],
    )


def _call_parameters(seat: SeatDefinition) -> dict[str, object]:
    """Select provider-portable generation controls from the project pin."""
    parameters = seat.pin.parameters
    selected: dict[str, object] = {}
    temperature = parameters.get("temperature")
    if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
        selected["temperature"] = float(temperature)
    max_tokens = parameters.get("max_tokens")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool):
        operation_limits = [
            value
            for key, value in parameters.items()
            if key.endswith("_max_tokens")
            and isinstance(value, int)
            and not isinstance(value, bool)
        ]
        max_tokens = max(operation_limits, default=None)
    if isinstance(max_tokens, int) and not isinstance(max_tokens, bool):
        selected["max_tokens"] = max_tokens
    return selected


def _frozen_run(
    seat: SeatDefinition,
    incumbent: ModelEntry,
    run_group: str,
) -> SeatRun:
    now = datetime.now(UTC).isoformat()
    return SeatRun(
        manifest=SeatRunManifest(
            schema_version="seat-run.v1",
            run_id=f"{run_group}-{seat.project_id}-{seat.seat_id}",
            project_id=seat.project_id,
            seat_id=seat.seat_id,
            seat_status="FROZEN",
            current_pin=dict(seat.raw["current_pin"]),
            incumbent_model_id=incumbent.id,
            candidate_model_ids=[incumbent.id],
            case_ids=[],
            started_at=now,
            finished_at=now,
            provenance={
                "policy": "reported_without_execution_or_optimization",
                "frozen_reason": seat.pin.reason,
                "seats_sha256": _sha256(seat.seats_path),
            },
        ),
        results=[],
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
