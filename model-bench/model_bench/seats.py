"""Discover and load portfolio ``seats.yaml`` contracts.

The contract itself belongs to project-scaffolding.  This module intentionally
loads that repository's validator instead of copying schema rules into
model-bench, then adds the cross-project and filesystem checks needed by a
benchmark runner.
"""

from __future__ import annotations

import importlib.util
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any


class SeatDiscoveryError(RuntimeError):
    """Raised when portfolio seat discovery cannot complete safely."""


class SeatDiscoveryWarning(UserWarning):
    """Warns when discovery is valid but produces a suspicious result."""


class PinStatus(str, Enum):
    """Whether a model pin may participate in comparative evaluation."""

    LIVE = "LIVE"
    FROZEN = "FROZEN"


@dataclass(frozen=True)
class ModelPin:
    """The model currently assigned to a seat."""

    provider: str
    model: str
    status: PinStatus
    reason: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True)
class SeatDefinition:
    """A validated, project-owned model job."""

    project_id: str
    project_root: Path
    seats_path: Path
    seat_id: str
    job: str
    pin: ModelPin
    fixture_path: Path
    schema_path: Path | None
    context_paths: tuple[Path, ...]
    labels_path: Path | None
    raw: Mapping[str, Any]

    @property
    def id(self) -> str:
        """Return the seat's unqualified contract identifier."""
        return self.seat_id

    @property
    def qualified_id(self) -> str:
        """Return the stable portfolio identifier for this seat."""
        return f"{self.project_id}/{self.seat_id}"

    @property
    def status(self) -> PinStatus:
        """Expose LIVE versus FROZEN without reaching into the raw contract."""
        return self.pin.status

    @property
    def is_live(self) -> bool:
        return self.status is PinStatus.LIVE

    @property
    def is_frozen(self) -> bool:
        return self.status is PinStatus.FROZEN


@dataclass(frozen=True)
class ProjectSeats:
    """A validated project's seat collection."""

    project_id: str
    name: str
    project_root: Path
    seats_path: Path
    seats: tuple[SeatDefinition, ...]
    raw: Mapping[str, Any]

    @property
    def id(self) -> str:
        return self.project_id


Validator = Callable[[Path], dict[str, Any]]


def discover_project_seats(
    projects_root: Path,
    *,
    validator_repo: Path | None = None,
) -> tuple[ProjectSeats, ...]:
    """Discover and strictly load root-level ``seats.yaml`` files.

    ``projects_root`` is the configurable directory whose immediate child
    directories are portfolio projects.  The project-scaffolding checkout is
    found under that same root unless ``validator_repo`` is explicitly supplied
    (primarily useful for tests and nonstandard layouts).

    Discovery is deterministic by directory name and seat id.  Any validator,
    contract, duplicate-id, or referenced-file problem aborts discovery rather
    than silently omitting a project or seat.
    """
    root = _require_directory(projects_root, "projects root")
    validator = _load_validator(root, validator_repo)
    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise SeatDiscoveryError(f"cannot scan projects root {root}: {exc}") from exc
    seats_paths = sorted(
        (
            child / "seats.yaml"
            for child in children
            if child.is_dir() and (child / "seats.yaml").is_file()
        ),
        key=lambda path: (path.parent.name.casefold(), path.parent.name),
    )
    if not seats_paths:
        warnings.warn(
            f"no seats.yaml files found directly under projects root {root}",
            SeatDiscoveryWarning,
            stacklevel=2,
        )

    projects: list[ProjectSeats] = []
    project_ids: dict[str, Path] = {}

    for seats_path in seats_paths:
        project = _load_project(seats_path, validator)
        previous_project = project_ids.get(project.project_id)
        if previous_project is not None:
            raise SeatDiscoveryError(
                f"duplicate project id {project.project_id!r}: "
                f"{previous_project} and {project.seats_path}"
            )
        project_ids[project.project_id] = project.seats_path
        projects.append(project)

    return tuple(projects)


def discover_seats(
    projects_root: Path,
    *,
    validator_repo: Path | None = None,
) -> tuple[SeatDefinition, ...]:
    """Return all validated seats in deterministic project/seat order."""
    projects = discover_project_seats(projects_root, validator_repo=validator_repo)
    return tuple(seat for project in projects for seat in project.seats)


def _require_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise SeatDiscoveryError(
            f"{description} does not exist or is not a directory: {path}"
        )
    return resolved


def _load_validator(projects_root: Path, validator_repo: Path | None) -> Validator:
    if validator_repo is None:
        repo = projects_root / "project-scaffolding"
    else:
        repo = validator_repo.expanduser().resolve()

    module_path = repo / "scaffold" / "seats.py"
    if not module_path.is_file():
        raise SeatDiscoveryError(
            "project-scaffolding seats.v1 validator not found at "
            f"{module_path}; supply the portfolio projects root or validator_repo"
        )

    module = _import_validator_module(module_path)
    schema_version = getattr(module, "SCHEMA_VERSION", None)
    if schema_version != "seats.v1":
        raise SeatDiscoveryError(
            f"{module_path}: expected seats.v1 validator, found {schema_version!r}"
        )
    validator = getattr(module, "validate_seats_file", None)
    if not callable(validator):
        raise SeatDiscoveryError(f"{module_path}: validate_seats_file is missing")
    return validator


def _import_validator_module(module_path: Path) -> ModuleType:
    module_name = f"_model_bench_seats_validator_{abs(hash(module_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise SeatDiscoveryError(f"cannot load seats validator from {module_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise SeatDiscoveryError(
            f"cannot import seats validator {module_path}: {exc}"
        ) from exc
    return module


def _load_project(seats_path: Path, validator: Validator) -> ProjectSeats:
    try:
        data = validator(seats_path)
    except Exception as exc:
        raise SeatDiscoveryError(
            f"{seats_path}: seats.v1 validation failed: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise SeatDiscoveryError(
            f"{seats_path}: seats.v1 validator returned {type(data).__name__}, expected dict"
        )

    project_data = _mapping(data, "project", seats_path)
    project_id = _string(project_data, "id", seats_path)
    project_name = project_data.get("name", project_id)
    if not isinstance(project_name, str):
        raise SeatDiscoveryError(f"{seats_path}: project.name must be a string")

    raw_seats = data.get("seats")
    if not isinstance(raw_seats, list):
        raise SeatDiscoveryError(f"{seats_path}: seats must be a list")

    project_root = seats_path.parent.resolve()
    seats = tuple(
        sorted(
            (
                _build_seat(project_id, project_root, seats_path, seat_data)
                for seat_data in raw_seats
            ),
            key=lambda seat: seat.seat_id,
        )
    )
    return ProjectSeats(
        project_id=project_id,
        name=project_name,
        project_root=project_root,
        seats_path=seats_path.resolve(),
        seats=seats,
        raw=data,
    )


def _build_seat(
    project_id: str,
    project_root: Path,
    seats_path: Path,
    seat_data: Any,
) -> SeatDefinition:
    if not isinstance(seat_data, dict):
        raise SeatDiscoveryError(f"{seats_path}: validator accepted a non-mapping seat")

    seat_id = _string(seat_data, "id", seats_path)
    job = _string(seat_data, "job", seats_path)
    pin_data = _mapping(seat_data, "current_pin", seats_path)
    try:
        pin_status = PinStatus(_string(pin_data, "status", seats_path))
    except ValueError as exc:
        raise SeatDiscoveryError(
            f"{seats_path}: seat {seat_id!r} has unknown pin status {pin_data.get('status')!r}"
        ) from exc

    parameters = pin_data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise SeatDiscoveryError(
            f"{seats_path}: seat {seat_id!r} pin parameters must be a mapping"
        )
    pin = ModelPin(
        provider=_string(pin_data, "provider", seats_path),
        model=_string(pin_data, "model", seats_path),
        status=pin_status,
        reason=_string(pin_data, "reason", seats_path),
        parameters=parameters,
    )

    fixture_data = _mapping(seat_data, "eval_fixtures", seats_path)
    fixture_path = _require_project_file(
        project_root,
        _string(fixture_data, "path", seats_path),
        seats_path,
        seat_id,
        "fixture",
    )

    output_contract = _mapping(seat_data, "output_contract", seats_path)
    schema_path = None
    schema_ref = output_contract.get("schema_ref")
    if schema_ref is not None:
        if not isinstance(schema_ref, str):
            raise SeatDiscoveryError(
                f"{seats_path}: seat {seat_id!r} output schema reference must be a string"
            )
        schema_path = _require_project_file(
            project_root, schema_ref, seats_path, seat_id, "output schema"
        )

    context_paths: list[Path] = []
    context_providers = fixture_data.get("context_providers", [])
    if not isinstance(context_providers, list):
        raise SeatDiscoveryError(
            f"{seats_path}: seat {seat_id!r} context_providers must be a list"
        )
    for provider in context_providers:
        if not isinstance(provider, dict):
            raise SeatDiscoveryError(
                f"{seats_path}: seat {seat_id!r} has a non-mapping context provider"
            )
        if provider.get("source") == "project_file":
            source_ref = provider.get("source_ref")
            if not isinstance(source_ref, str):
                raise SeatDiscoveryError(
                    f"{seats_path}: seat {seat_id!r} project-file context "
                    "reference must be a string"
                )
            context_paths.append(
                _require_project_file(
                    project_root,
                    source_ref,
                    seats_path,
                    seat_id,
                    "context",
                )
            )

    labels_path = None
    sealed_labels = fixture_data.get("sealed_labels")
    if isinstance(sealed_labels, dict) and sealed_labels.get("policy") == "external":
        label_ref = sealed_labels.get("path")
        if not isinstance(label_ref, str):
            raise SeatDiscoveryError(
                f"{seats_path}: seat {seat_id!r} external label reference must be a string"
            )
        labels_path = _require_project_file(
            project_root, label_ref, seats_path, seat_id, "external labels"
        )

    return SeatDefinition(
        project_id=project_id,
        project_root=project_root,
        seats_path=seats_path.resolve(),
        seat_id=seat_id,
        job=job,
        pin=pin,
        fixture_path=fixture_path,
        schema_path=schema_path,
        context_paths=tuple(context_paths),
        labels_path=labels_path,
        raw=seat_data,
    )


def _mapping(data: Mapping[str, Any], key: str, seats_path: Path) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SeatDiscoveryError(f"{seats_path}: {key} must be a mapping")
    return value


def _string(data: Mapping[str, Any], key: str, seats_path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise SeatDiscoveryError(f"{seats_path}: {key} must be a non-empty string")
    return value


def _require_project_file(
    project_root: Path,
    reference: str,
    seats_path: Path,
    seat_id: str,
    description: str,
) -> Path:
    candidate = (project_root / reference).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise SeatDiscoveryError(
            f"{seats_path}: seat {seat_id!r} {description} reference escapes "
            f"the project root: {reference}"
        ) from exc
    if not candidate.is_file():
        raise SeatDiscoveryError(
            f"{seats_path}: seat {seat_id!r} {description} file does not exist: {reference}"
        )
    return candidate
