"""Seat-level execution with validity-first judging and run provenance."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .caller import CallResult, call_model
from .registry import ModelEntry, estimate_cost

SeatLike = Mapping[str, Any] | object
CaseLike = Mapping[str, Any] | object


class ArtifactValidator(Protocol):
    """Validate one model artifact before it can reach a quality judge."""

    def __call__(
        self,
        *,
        seat: SeatLike,
        case: CaseLike,
        artifact: Any,
    ) -> ValidityResult | bool | Mapping[str, Any]: ...


class SeatJudge(Protocol):
    """Judge only the valid responses for one seat case."""

    def __call__(
        self,
        *,
        seat: SeatLike,
        case: CaseLike,
        prompt: str,
        responses: Mapping[str, Any],
    ) -> Mapping[str, Any] | Sequence[Any]: ...


class PromptBuilder(Protocol):
    """Render a project-owned fixture into the exact model prompt."""

    def __call__(self, *, seat: SeatLike, case: CaseLike) -> str | RenderedCase: ...


@dataclass(frozen=True)
class RenderedCase:
    """Project-owned prompt plus optional multimodal input paths."""

    prompt: str
    image_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class ValidityResult:
    """Machine-checkable validity result for one artifact."""

    valid: bool
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Judgment:
    """Normalized quality judgment for one valid artifact."""

    score: float
    reasoning: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeatCaseResult:
    """Complete evidence for one candidate on one seat case."""

    seat_id: str
    case_id: str
    model_id: str
    is_incumbent: bool
    prompt: str
    response: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    validity: ValidityResult
    artifact_size_bytes: int = 0
    artifact_mime_type: str | None = None
    judge_score: float | None = None
    judge_reasoning: str = ""
    judge_details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    judge_error: str | None = None
    cost_error: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeatRunManifest:
    """Reproducibility metadata for one seat run."""

    schema_version: str
    run_id: str
    project_id: str
    seat_id: str
    seat_status: str
    current_pin: dict[str, Any]
    incumbent_model_id: str
    candidate_model_ids: list[str]
    case_ids: list[str]
    started_at: str
    finished_at: str
    provenance: dict[str, Any] = field(default_factory=dict)
    case_provenance: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class SeatRun:
    """Raw seat execution ready for aggregation and reporting."""

    manifest: SeatRunManifest
    results: list[SeatCaseResult]


class FrozenSeatError(ValueError):
    """Raised when a FROZEN seat cannot be run on its incumbent only."""


class SeatRunner:
    """Execute candidate models while enforcing seat policy."""

    def __init__(
        self,
        *,
        validator: ArtifactValidator,
        judge: SeatJudge | None,
        caller: Callable[..., CallResult] = call_model,
        cost_estimator: Callable[[ModelEntry, int, int], float] = estimate_cost,
        prompt_builder: PromptBuilder | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._validator = validator
        self._judge = judge
        self._caller = caller
        self._cost_estimator = cost_estimator
        self._prompt_builder = prompt_builder
        self._now = now or (lambda: datetime.now(UTC))

    def run(
        self,
        *,
        seat: SeatLike,
        cases: Sequence[CaseLike],
        candidates: Sequence[ModelEntry],
        incumbent: ModelEntry | None = None,
        project_id: str = "",
        timeout_seconds: int = 30,
        call_parameters: Mapping[str, Any] | None = None,
        run_id: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> SeatRun:
        """Run one seat across cases and policy-filtered candidates."""

        contract = _seat_contract(seat)
        seat_id = str(_field(seat, "id", _field(contract, "id")))
        seat_status = str(_nested(contract, "current_pin", "status")).upper()
        if seat_status not in {"LIVE", "FROZEN"}:
            raise ValueError(f"{seat_id}: unsupported pin status {seat_status!r}")

        pin = dict(_mapping(_field(contract, "current_pin")))
        selected, incumbent_model = _select_candidates(
            seat_status=seat_status,
            pin=pin,
            candidates=candidates,
            incumbent=incumbent,
        )
        case_ids = [
            str(
                _field(
                    case,
                    "variant_id",
                    _field(case, "id", _field(case, "fixture_id", "")),
                )
            )
            for case in cases
        ]
        if any(not case_id for case_id in case_ids):
            raise ValueError(f"{seat_id}: every case needs id or fixture_id")

        started_at = _iso(self._now())
        resolved_run_id = run_id or uuid.uuid4().hex
        results: list[SeatCaseResult] = []
        case_provenance: dict[str, dict[str, Any]] = {}

        for case, case_id in zip(cases, case_ids, strict=True):
            rendered = self._build_prompt(seat, case)
            prompt = rendered.prompt
            case_provenance[case_id] = _extract_case_provenance(case)
            case_results: list[SeatCaseResult] = []
            valid_artifacts: dict[str, Any] = {}

            for model in selected:
                call_result = self._call_model(
                    model=model,
                    rendered=rendered,
                    timeout_seconds=timeout_seconds,
                    parameters=call_parameters,
                )
                artifact = _call_artifact(call_result)
                validity = self._validate_call(seat, case, call_result, artifact)
                cost, cost_error = self._estimate_cost(model, call_result)
                artifact_bytes = getattr(call_result, "artifact", None)
                result = SeatCaseResult(
                    seat_id=seat_id,
                    case_id=case_id,
                    model_id=model.id,
                    is_incumbent=model.id == incumbent_model.id,
                    prompt=prompt,
                    response=call_result.response,
                    latency_ms=call_result.latency_ms,
                    tokens_in=call_result.tokens_in,
                    tokens_out=call_result.tokens_out,
                    cost_usd=cost,
                    validity=validity,
                    artifact_size_bytes=(
                        len(artifact_bytes)
                        if isinstance(artifact_bytes, (bytes, bytearray, memoryview))
                        else 0
                    ),
                    artifact_mime_type=getattr(call_result, "artifact_mime_type", None),
                    error=call_result.error,
                    cost_error=cost_error,
                    provenance=case_provenance[case_id],
                )
                if not validity.valid:
                    result.judge_score = 0.0
                    result.judge_reasoning = (
                        f"Artifact validity hard floor: {validity.reason}"
                    )
                elif call_result.error is None:
                    valid_artifacts[model.id] = artifact
                case_results.append(result)

            self._judge_valid_responses(
                seat=seat,
                case=case,
                prompt=prompt,
                responses=valid_artifacts,
                case_results=case_results,
            )
            results.extend(case_results)

        manifest = SeatRunManifest(
            schema_version="seat-run.v1",
            run_id=resolved_run_id,
            project_id=project_id or str(_field(seat, "project_id", "")),
            seat_id=seat_id,
            seat_status=seat_status,
            current_pin=pin,
            incumbent_model_id=incumbent_model.id,
            candidate_model_ids=[model.id for model in selected],
            case_ids=case_ids,
            started_at=started_at,
            finished_at=_iso(self._now()),
            provenance={
                **_extract_seat_provenance(seat),
                **dict(provenance or {}),
            },
            case_provenance=case_provenance,
        )
        return SeatRun(manifest=manifest, results=results)

    def _build_prompt(self, seat: SeatLike, case: CaseLike) -> RenderedCase:
        if self._prompt_builder is not None:
            rendered = self._prompt_builder(seat=seat, case=case)
        else:
            prompt = _field(case, "prompt", None)
            if prompt is None:
                input_value = _field(case, "input", None)
                if isinstance(input_value, str):
                    prompt = input_value
            rendered = prompt
        if isinstance(rendered, RenderedCase):
            prompt = rendered.prompt
        else:
            prompt = rendered
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(
                "case has no prompt string; provide a project-owned prompt_builder"
            )
        if isinstance(rendered, RenderedCase):
            return rendered
        return RenderedCase(prompt=prompt)

    def _call_model(
        self,
        *,
        model: ModelEntry,
        rendered: RenderedCase,
        timeout_seconds: int,
        parameters: Mapping[str, Any] | None,
    ) -> CallResult:
        kwargs: dict[str, Any] = {}
        if rendered.image_paths:
            kwargs["image_paths"] = list(rendered.image_paths)
        if parameters:
            kwargs["parameters"] = dict(parameters)
        return self._caller(model, rendered.prompt, timeout_seconds, **kwargs)

    def _validate_call(
        self,
        seat: SeatLike,
        case: CaseLike,
        call_result: CallResult,
        artifact: Any,
    ) -> ValidityResult:
        if call_result.error:
            return ValidityResult(False, f"model call failed: {call_result.error}")
        try:
            raw = self._validator(
                seat=seat,
                case=case,
                artifact=artifact,
            )
        except Exception as exc:  # noqa: BLE001 - validator is a project adapter
            return ValidityResult(False, f"validator error: {exc}")
        return _normalize_validity(raw)

    def _estimate_cost(
        self,
        model: ModelEntry,
        call_result: CallResult,
    ) -> tuple[float, str | None]:
        try:
            return (
                float(
                    self._cost_estimator(
                        model,
                        call_result.tokens_in,
                        call_result.tokens_out,
                    )
                ),
                None,
            )
        except Exception as exc:  # noqa: BLE001 - pricing adapter must not abort runs
            return 0.0, str(exc)

    def _judge_valid_responses(
        self,
        *,
        seat: SeatLike,
        case: CaseLike,
        prompt: str,
        responses: Mapping[str, Any],
        case_results: list[SeatCaseResult],
    ) -> None:
        if self._judge is None or not responses:
            return
        try:
            raw = self._judge(
                seat=seat,
                case=case,
                prompt=prompt,
                responses=responses,
            )
            judgments = _normalize_judgments(raw)
        except Exception as exc:  # noqa: BLE001 - judge failures are run evidence
            for result in case_results:
                if result.model_id in responses:
                    result.judge_error = str(exc)
            return

        for result in case_results:
            if result.model_id not in responses:
                continue
            judgment = judgments.get(result.model_id)
            if judgment is None:
                result.judge_error = "judge returned no score for valid artifact"
                continue
            result.judge_score = judgment.score
            result.judge_reasoning = judgment.reasoning
            result.judge_details = judgment.details


def run_seat(
    *,
    seat: SeatLike,
    cases: Sequence[CaseLike],
    candidates: Sequence[ModelEntry],
    validator: ArtifactValidator,
    judge: SeatJudge | None,
    incumbent: ModelEntry | None = None,
    caller: Callable[..., CallResult] = call_model,
    cost_estimator: Callable[[ModelEntry, int, int], float] = estimate_cost,
    prompt_builder: PromptBuilder | None = None,
    project_id: str = "",
    timeout_seconds: int = 30,
    call_parameters: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> SeatRun:
    """Functional entry point for one seat run."""

    runner = SeatRunner(
        validator=validator,
        judge=judge,
        caller=caller,
        cost_estimator=cost_estimator,
        prompt_builder=prompt_builder,
    )
    return runner.run(
        seat=seat,
        cases=cases,
        candidates=candidates,
        incumbent=incumbent,
        project_id=project_id,
        timeout_seconds=timeout_seconds,
        call_parameters=call_parameters,
        run_id=run_id,
        provenance=provenance,
    )


def _select_candidates(
    *,
    seat_status: str,
    pin: Mapping[str, Any],
    candidates: Sequence[ModelEntry],
    incumbent: ModelEntry | None,
) -> tuple[list[ModelEntry], ModelEntry]:
    unique = {model.id: model for model in candidates}
    if incumbent is not None:
        unique.setdefault(incumbent.id, incumbent)
    incumbent_model = incumbent or next(
        (model for model in unique.values() if _matches_pin(model, pin)),
        None,
    )
    if incumbent_model is None:
        message = "current pin must resolve to an incumbent ModelEntry"
        if seat_status == "FROZEN":
            raise FrozenSeatError(message)
        raise ValueError(message)
    if seat_status == "FROZEN":
        return [incumbent_model], incumbent_model
    return list(unique.values()), incumbent_model


def _matches_pin(model: ModelEntry, pin: Mapping[str, Any]) -> bool:
    pinned = str(pin.get("model", ""))
    provider = str(pin.get("provider", ""))
    return (
        model.id in {pinned, f"{provider}/{pinned}"}
        or model.id.removeprefix(f"{provider}/") == pinned
    )


def _normalize_validity(
    raw: ValidityResult | bool | Mapping[str, Any],
) -> ValidityResult:
    if isinstance(raw, ValidityResult):
        return raw
    if isinstance(raw, bool):
        return ValidityResult(raw, "" if raw else "validator rejected artifact")
    if isinstance(raw, Mapping):
        return ValidityResult(
            bool(raw.get("valid")),
            str(raw.get("reason", "")),
            dict(raw.get("details", {})),
        )
    valid = getattr(raw, "valid", None)
    if isinstance(valid, bool):
        reason = getattr(raw, "reason", None)
        if reason is None:
            reason = getattr(raw, "hard_floor_reason", "")
        details = {
            key: value
            for key in ("mime_type", "width_px", "height_px")
            if (value := getattr(raw, key, None)) is not None
        }
        parsed_output = getattr(raw, "parsed_output", None)
        if parsed_output is not None:
            details["parsed_output_type"] = type(parsed_output).__name__
        return ValidityResult(
            valid,
            str(reason or ""),
            details,
        )
    raise TypeError("validator must return ValidityResult, bool, or mapping")


def _normalize_judgments(raw: Mapping[str, Any] | Sequence[Any]) -> dict[str, Judgment]:
    if isinstance(raw, Mapping):
        items = raw.items()
    else:
        items = ((str(_field(item, "model_id")), item) for item in raw)
    return {model_id: _normalize_judgment(value) for model_id, value in items}


def _normalize_judgment(raw: Any) -> Judgment:
    if isinstance(raw, Judgment):
        return raw
    if isinstance(raw, (int, float)):
        return Judgment(float(raw))
    if isinstance(raw, Mapping):
        score = raw.get("score", raw.get("overall"))
        if score is None:
            raise ValueError("judgment mapping needs score or overall")
        details = dict(raw.get("details", raw.get("scores", {})))
        return Judgment(
            float(score),
            str(raw.get("reasoning", "")),
            details,
        )
    score = getattr(raw, "overall", getattr(raw, "score", None))
    if score is None:
        raise TypeError("judge result needs model_id and overall/score")
    return Judgment(
        float(score),
        str(getattr(raw, "reasoning", "")),
        dict(getattr(raw, "scores", {})),
    )


def _extract_case_provenance(case: CaseLike) -> dict[str, Any]:
    explicit = _field(case, "provenance", None)
    if isinstance(explicit, Mapping):
        return dict(explicit)
    keys = (
        "fixture_id",
        "variant_id",
        "split",
        "is_dirty",
        "source_ref",
        "source_refs",
        "source_commit",
        "source_paths",
    )
    provenance = {
        key: value for key in keys if (value := _field(case, key, None)) is not None
    }
    source_row = _field(case, "source_row", None)
    if isinstance(source_row, Mapping):
        for key in ("source_ref", "source_refs", "source_commit", "source_paths"):
            if key in source_row:
                provenance[key] = source_row[key]
    return provenance


def _extract_seat_provenance(seat: SeatLike) -> dict[str, Any]:
    root_value = _field(seat, "project_root", None)
    if root_value is None:
        return {}
    root = Path(root_value).resolve()
    provenance = {"project_root": "."}
    for key in ("seats_path", "fixture_path", "schema_path", "labels_path"):
        value = _field(seat, key, None)
        if value is None:
            continue
        path = Path(value).resolve()
        try:
            provenance[key] = str(path.relative_to(root))
        except ValueError as exc:
            raise ValueError(f"{key} escapes project root: {path}") from exc
    return provenance


def _seat_contract(seat: SeatLike) -> SeatLike:
    raw = _field(seat, "raw", None)
    if isinstance(raw, Mapping) and "current_pin" in raw:
        return raw
    return seat


def _call_artifact(call_result: CallResult) -> Any:
    artifact = getattr(call_result, "artifact", None)
    if artifact is None:
        return call_result.response
    mime_type = getattr(call_result, "artifact_mime_type", None)
    return {"data": artifact, "mime_type": mime_type}


def validate_with_seat_contract(
    *,
    seat: SeatLike,
    case: CaseLike,
    artifact: Any,
) -> Any:
    """Adapter from loaded seats to the deterministic validity module."""

    del case
    from .validity import validate_artifact

    contract = _seat_contract(seat)
    output_contract = _field(contract, "output_contract")
    project_root = _field(seat, "project_root", None)
    if project_root is None:
        raise ValueError("seat contract validation requires project_root")
    return validate_artifact(
        artifact,
        dict(_mapping(output_contract)),
        project_root=project_root,
    )


def _field(value: Any, name: str, default: Any = ...) -> Any:
    if isinstance(value, Mapping) and name in value:
        return value[name]
    if hasattr(value, name):
        return getattr(value, name)
    if default is not ...:
        return default
    raise KeyError(name)


def _nested(value: Any, parent: str, child: str) -> Any:
    return _field(_field(value, parent), child)


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("expected mapping")
    return value


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def fixture_prompt_builder(*, seat: SeatLike, case: CaseLike) -> str:
    """Deterministic fallback for callers whose fixture input is already text."""

    del seat
    input_value = _field(case, "input")
    if isinstance(input_value, str):
        return input_value
    raise ValueError(
        "structured fixture inputs require a project-owned prompt builder; "
        f"received {json.dumps(input_value, sort_keys=True, default=str)[:120]}"
    )
