from __future__ import annotations

from pathlib import Path

import pytest

from model_bench.seats import (
    PinStatus,
    SeatDiscoveryError,
    SeatDiscoveryWarning,
    discover_project_seats,
    discover_seats,
)

VALIDATOR_SOURCE = """
from pathlib import Path
import yaml

SCHEMA_VERSION = "seats.v1"

def validate_seats_file(path: Path):
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top level must be a mapping")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("wrong schema version")
    if not isinstance(data.get("project"), dict) or not data["project"].get("id"):
        raise ValueError("missing project id")
    if not isinstance(data.get("seats"), list) or not data["seats"]:
        raise ValueError("missing seats")
    for seat in data["seats"]:
        required = ("id", "job", "output_contract", "current_pin", "eval_fixtures")
        if not isinstance(seat, dict) or any(key not in seat for key in required):
            raise ValueError("malformed seat")
    return data
"""


def _install_validator(projects_root: Path, source: str = VALIDATOR_SOURCE) -> Path:
    repo = projects_root / "project-scaffolding"
    module = repo / "scaffold" / "seats.py"
    module.parent.mkdir(parents=True)
    module.write_text(source)
    return repo


def _seat_yaml(
    project_id: str,
    *,
    seat_id: str = "answerer",
    status: str = "LIVE",
    fixture_ref: str = "benchmarks/answerer.jsonl",
    schema_ref: str | None = None,
    context_ref: str | None = None,
    labels_ref: str | None = None,
) -> str:
    schema_line = f"      schema_ref: {schema_ref}\n" if schema_ref else ""
    context = (
        "      context_providers:\n"
        "        - id: policy\n"
        "          source: project_file\n"
        f"          source_ref: {context_ref}\n"
        "          required: true\n"
        if context_ref
        else ""
    )
    labels = (
        f"      sealed_labels:\n        policy: external\n        path: {labels_ref}\n"
        if labels_ref
        else ""
    )
    return (
        "schema_version: seats.v1\n"
        "project:\n"
        f"  id: {project_id}\n"
        f"  name: {project_id.title()}\n"
        "seats:\n"
        f"  - id: {seat_id}\n"
        "    job: Answer a grounded question.\n"
        "    output_contract:\n"
        "      type: json\n"
        f"{schema_line}"
        "      validation: Validate output.\n"
        "    current_pin:\n"
        "      provider: example\n"
        "      model: tiny-model\n"
        f"      status: {status}\n"
        "      reason: Current assignment.\n"
        "      parameters:\n"
        "        temperature: 0\n"
        "    eval_fixtures:\n"
        f"      path: {fixture_ref}\n"
        f"{context}"
        f"{labels}"
    )


def _make_project(
    projects_root: Path,
    directory: str,
    *,
    project_id: str | None = None,
    seat_id: str = "answerer",
    status: str = "LIVE",
    schema: bool = False,
    context: bool = False,
    labels: bool = False,
) -> Path:
    project = projects_root / directory
    fixture = project / "benchmarks" / "answerer.jsonl"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"fixture_id": "one"}\n')
    schema_ref = "schemas/output.json" if schema else None
    context_ref = "prompts/policy.md" if context else None
    labels_ref = "benchmarks/labels.jsonl" if labels else None
    if schema_ref:
        path = project / schema_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")
    if context_ref:
        path = project / context_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("policy\n")
    if labels_ref:
        path = project / labels_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"fixture_id": "one", "label": "pass"}\n')
    (project / "seats.yaml").write_text(
        _seat_yaml(
            project_id or directory,
            seat_id=seat_id,
            status=status,
            schema_ref=schema_ref,
            context_ref=context_ref,
            labels_ref=labels_ref,
        )
    )
    return project


def test_discovers_typed_seats_deterministically(tmp_path: Path) -> None:
    _install_validator(tmp_path)
    frozen_root = _make_project(
        tmp_path,
        "z-project",
        seat_id="judge",
        status="FROZEN",
        schema=True,
        context=True,
        labels=True,
    )
    _make_project(tmp_path, "A-project", seat_id="answerer")
    nested = tmp_path / "container" / "nested"
    nested.mkdir(parents=True)
    (nested / "seats.yaml").write_text("not: discovered\n")

    projects = discover_project_seats(tmp_path)
    seats = discover_seats(tmp_path)

    assert [project.id for project in projects] == ["A-project", "z-project"]
    assert [seat.qualified_id for seat in seats] == [
        "A-project/answerer",
        "z-project/judge",
    ]
    frozen = seats[1]
    assert frozen.status is PinStatus.FROZEN
    assert frozen.is_frozen is True
    assert frozen.is_live is False
    assert frozen.pin.model == "tiny-model"
    assert frozen.fixture_path == frozen_root / "benchmarks" / "answerer.jsonl"
    assert frozen.schema_path == frozen_root / "schemas" / "output.json"
    assert frozen.context_paths == (frozen_root / "prompts" / "policy.md",)
    assert frozen.labels_path == frozen_root / "benchmarks" / "labels.jsonl"


def test_explicit_validator_repo_supports_nonstandard_layout(tmp_path: Path) -> None:
    projects_root = tmp_path / "portfolio"
    projects_root.mkdir()
    validator_repo = _install_validator(tmp_path / "contracts")
    _make_project(projects_root, "project-a")

    seats = discover_seats(projects_root, validator_repo=validator_repo)

    assert [seat.qualified_id for seat in seats] == ["project-a/answerer"]


@pytest.mark.parametrize(
    ("validator_source", "message"),
    [
        ("SCHEMA_VERSION = 'seats.v1'\n", "validate_seats_file is missing"),
        (
            "SCHEMA_VERSION = 'seats.v0'\ndef validate_seats_file(path): return {}\n",
            "expected seats.v1 validator",
        ),
        ("this is not python", "cannot import seats validator"),
    ],
)
def test_rejects_unusable_validator(
    tmp_path: Path, validator_source: str, message: str
) -> None:
    _install_validator(tmp_path, validator_source)

    with pytest.raises(SeatDiscoveryError, match=message):
        discover_seats(tmp_path)


def test_missing_validator_is_a_hard_error(tmp_path: Path) -> None:
    with pytest.raises(SeatDiscoveryError, match="validator not found"):
        discover_seats(tmp_path)


@pytest.mark.parametrize(
    "document",
    [
        "schema_version: [",
        "schema_version: seats.v0\nproject: {id: p}\nseats: []\n",
        "schema_version: seats.v1\nproject: {}\nseats: []\n",
    ],
)
def test_contract_or_yaml_errors_are_hard_errors(tmp_path: Path, document: str) -> None:
    _install_validator(tmp_path)
    project = tmp_path / "bad-project"
    project.mkdir()
    (project / "seats.yaml").write_text(document)

    with pytest.raises(SeatDiscoveryError, match="seats.v1 validation failed"):
        discover_seats(tmp_path)


def test_duplicate_project_ids_are_rejected(tmp_path: Path) -> None:
    _install_validator(tmp_path)
    _make_project(tmp_path, "one", project_id="duplicate", seat_id="first")
    _make_project(tmp_path, "two", project_id="duplicate", seat_id="second")

    with pytest.raises(SeatDiscoveryError, match="duplicate project id 'duplicate'"):
        discover_seats(tmp_path)


def test_same_seat_id_in_different_projects_uses_qualified_identity(
    tmp_path: Path,
) -> None:
    _install_validator(tmp_path)
    _make_project(tmp_path, "one", seat_id="same")
    _make_project(tmp_path, "two", seat_id="same")

    seats = discover_seats(tmp_path)

    assert [seat.qualified_id for seat in seats] == ["one/same", "two/same"]


def test_empty_discovery_emits_sanity_warning(tmp_path: Path) -> None:
    _install_validator(tmp_path)

    with pytest.warns(SeatDiscoveryWarning, match="no seats.yaml files found"):
        projects = discover_project_seats(tmp_path)

    assert projects == ()


def test_project_scan_failure_is_a_hard_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_validator(tmp_path)

    def fail_scan(_path: Path):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "iterdir", fail_scan)

    with pytest.raises(SeatDiscoveryError, match="cannot scan projects root.*denied"):
        discover_project_seats(tmp_path)


@pytest.mark.parametrize(
    ("missing_kind", "expected_message"),
    [
        ("fixture", "fixture file does not exist"),
        ("schema", "output schema file does not exist"),
        ("context", "context file does not exist"),
        ("labels", "external labels file does not exist"),
    ],
)
def test_missing_referenced_files_are_hard_errors(
    tmp_path: Path, missing_kind: str, expected_message: str
) -> None:
    _install_validator(tmp_path)
    project = _make_project(
        tmp_path,
        "project-a",
        schema=True,
        context=True,
        labels=True,
    )
    targets = {
        "fixture": project / "benchmarks" / "answerer.jsonl",
        "schema": project / "schemas" / "output.json",
        "context": project / "prompts" / "policy.md",
        "labels": project / "benchmarks" / "labels.jsonl",
    }
    targets[missing_kind].unlink()

    with pytest.raises(SeatDiscoveryError, match=expected_message):
        discover_seats(tmp_path)


def test_reference_cannot_escape_project_via_symlink(tmp_path: Path) -> None:
    _install_validator(tmp_path)
    project = _make_project(tmp_path, "project-a")
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n")
    fixture = project / "benchmarks" / "answerer.jsonl"
    fixture.unlink()
    fixture.symlink_to(outside)

    with pytest.raises(SeatDiscoveryError, match="escapes the project root"):
        discover_seats(tmp_path)


def test_unknown_pin_status_is_not_silently_coerced(tmp_path: Path) -> None:
    _install_validator(tmp_path)
    _make_project(tmp_path, "project-a", status="CURRENT")

    with pytest.raises(SeatDiscoveryError, match="unknown pin status 'CURRENT'"):
        discover_seats(tmp_path)
