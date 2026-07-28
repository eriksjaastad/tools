"""Load real, project-owned evaluation cases for seats.v1 contracts.

The loader deliberately authorizes sealed access before opening either the
fixture file or an external label file.  Callers should keep using ``dev`` for
prompt development and reserve ``sealed`` for an explicitly unsealed run.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

SplitName = Literal["dev", "sealed"]


class SeatCaseError(ValueError):
    """A seat fixture contract or its data cannot be resolved safely."""


class SealedAccessError(PermissionError):
    """A sealed split was requested without its explicit environment gate."""


@dataclass(frozen=True)
class CaseContext:
    """One resolved context-provider value."""

    id: str
    source: str
    source_ref: str
    value: Any
    path: Path | None = None


@dataclass(frozen=True)
class SeatCase:
    """A model-ready case derived from one immutable source fixture."""

    fixture_id: str
    variant_id: str
    split: SplitName
    input: Any
    expected_output: Any
    contexts: Mapping[str, CaseContext]
    source_row: Mapping[str, Any]
    is_dirty: bool = False


def load_seat_cases(
    project_root: str | Path,
    seat: Mapping[str, Any],
    *,
    split: SplitName = "dev",
    include_dirty: bool = True,
    dirty_variant_limit: int | None = 1,
    max_context_bytes: int = 1_048_576,
    environ: Mapping[str, str] | None = None,
) -> list[SeatCase]:
    """Load one seat's cases, labels, contexts, and deterministic variants.

    ``project_root`` is the directory containing the seat's project-relative
    paths.  ``seat`` is a single mapping from the document's ``seats`` list.
    External labels are joined by ``id_field``.  For the external-label shape
    used by seats.v1 projects, ``expected_output`` is accepted as the label
    payload when the fixture-side ``expected_output_field`` is a join reference
    such as ``label_ref``.
    """

    if split not in ("dev", "sealed"):
        raise SeatCaseError(f"unsupported split {split!r}; expected 'dev' or 'sealed'")
    if dirty_variant_limit is not None and (
        not isinstance(dirty_variant_limit, int)
        or isinstance(dirty_variant_limit, bool)
        or dirty_variant_limit < 0
    ):
        raise SeatCaseError(
            "dirty_variant_limit must be a non-negative integer or None"
        )
    if (
        not isinstance(max_context_bytes, int)
        or isinstance(max_context_bytes, bool)
        or max_context_bytes <= 0
    ):
        raise SeatCaseError("max_context_bytes must be a positive integer")

    fixtures = _require_mapping(seat, "eval_fixtures", "seat")
    split_contract = _require_mapping(fixtures, "split", "eval_fixtures")
    env = os.environ if environ is None else environ
    _authorize_split(split, split_contract, env)

    root = Path(project_root).resolve()
    fixture_path = _project_path(
        root, _require_string(fixtures, "path", "eval_fixtures")
    )
    rows = _load_rows(
        fixture_path, _require_string(fixtures, "format", "eval_fixtures")
    )

    id_field = _require_string(fixtures, "id_field", "eval_fixtures")
    input_field = _require_string(fixtures, "input_field", "eval_fixtures")
    expected_field = _require_string(fixtures, "expected_output_field", "eval_fixtures")
    selected_rows: list[tuple[str, Mapping[str, Any]]] = []
    seen_ids: set[str] = set()

    for index, row in enumerate(rows, start=1):
        raw_id = _field(row, id_field, missing=None)
        if raw_id is None or str(raw_id) == "":
            raise SeatCaseError(f"{fixture_path}: row {index} has no {id_field!r}")
        fixture_id = str(raw_id)
        if fixture_id in seen_ids:
            raise SeatCaseError(f"{fixture_path}: duplicate fixture id {fixture_id!r}")
        seen_ids.add(fixture_id)
        if _fixture_split(row, split_contract) == split:
            selected_rows.append((fixture_id, row))

    # This happens only after the sealed gate above.  In particular, a denied
    # sealed request never opens an external file containing sealed gold.
    external_labels = _load_external_labels(
        root=root,
        fixtures=fixtures,
        id_field=id_field,
        selected_ids={fixture_id for fixture_id, _ in selected_rows},
    )

    cases: list[SeatCase] = []
    dirty = include_dirty and seat.get("input_character") in {"messy", "adversarial"}
    dirty_remaining = dirty_variant_limit
    for fixture_id, source_row in selected_rows:
        try:
            case_input = _field(source_row, input_field)
        except KeyError as exc:
            raise SeatCaseError(
                f"{fixture_path}: fixture {fixture_id!r} has no input field {input_field!r}"
            ) from exc

        expected = _expected_output(
            source_row=source_row,
            external_label=external_labels.get(fixture_id),
            expected_field=expected_field,
            fixture_id=fixture_id,
            external=external_labels is not _NO_EXTERNAL_LABELS,
        )
        base_row = copy.deepcopy(dict(source_row))
        base_input = copy.deepcopy(case_input)
        contexts = _resolve_contexts(root, fixtures, base_row, max_context_bytes)
        cases.append(
            SeatCase(
                fixture_id=fixture_id,
                variant_id=fixture_id,
                split=split,
                input=base_input,
                expected_output=copy.deepcopy(expected),
                contexts=contexts,
                source_row=base_row,
            )
        )

        if dirty and (dirty_remaining is None or dirty_remaining > 0):
            dirty_row = copy.deepcopy(base_row)
            dirty_input = _dirty_input(copy.deepcopy(base_input))
            _set_field(dirty_row, input_field, dirty_input)
            cases.append(
                SeatCase(
                    fixture_id=fixture_id,
                    variant_id=f"{fixture_id}::dirty-v1",
                    split=split,
                    input=dirty_input,
                    expected_output=copy.deepcopy(expected),
                    contexts=_resolve_contexts(
                        root, fixtures, dirty_row, max_context_bytes
                    ),
                    source_row=dirty_row,
                    is_dirty=True,
                )
            )
            if dirty_remaining is not None:
                dirty_remaining -= 1

    return cases


def split_for_fixture(
    row: Mapping[str, Any], split_contract: Mapping[str, Any]
) -> SplitName:
    """Public helper returning the deterministic seats.v1 split for a row."""

    return _fixture_split(row, split_contract)


def _authorize_split(
    split: SplitName, contract: Mapping[str, Any], environ: Mapping[str, str]
) -> None:
    if split != "sealed":
        return
    env_name = _require_string(contract, "sealed_unseal_env", "eval_fixtures.split")
    if environ.get(env_name) != "1":
        raise SealedAccessError(
            f"sealed cases are locked; set {env_name}=1 for this run to unseal them"
        )


def _fixture_split(row: Mapping[str, Any], contract: Mapping[str, Any]) -> SplitName:
    if contract.get("method") != "deterministic_hash_modulo":
        raise SeatCaseError(
            "unsupported eval split method; seats.v1 requires deterministic_hash_modulo"
        )
    hash_field = _require_string(contract, "hash_field", "eval_fixtures.split")
    try:
        value = _field(row, hash_field)
    except KeyError as exc:
        raise SeatCaseError(f"fixture has no split hash field {hash_field!r}") from exc
    modulo = contract.get("modulo")
    if not isinstance(modulo, int) or isinstance(modulo, bool) or modulo <= 0:
        raise SeatCaseError("eval_fixtures.split.modulo must be a positive integer")
    remainder = hashlib.sha256(str(value).encode("utf-8")).digest()[0] % modulo
    dev = _remainder_set(contract, "dev_remainders", modulo)
    sealed = _remainder_set(contract, "sealed_remainders", modulo)
    if dev & sealed or dev | sealed != set(range(modulo)):
        raise SeatCaseError(
            "dev and sealed remainders must be disjoint and cover modulo"
        )
    return "dev" if remainder in dev else "sealed"


def _remainder_set(contract: Mapping[str, Any], field: str, modulo: int) -> set[int]:
    values = contract.get(field)
    if not isinstance(values, list) or not values:
        raise SeatCaseError(f"eval_fixtures.split.{field} must be a non-empty list")
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value >= modulo
        for value in values
    ):
        raise SeatCaseError(
            f"eval_fixtures.split.{field} contains an invalid remainder"
        )
    return set(values)


_NO_EXTERNAL_LABELS: dict[str, Mapping[str, Any]] = {}


def _load_external_labels(
    *,
    root: Path,
    fixtures: Mapping[str, Any],
    id_field: str,
    selected_ids: set[str],
) -> dict[str, Mapping[str, Any]]:
    sealed_labels = fixtures.get("sealed_labels")
    if sealed_labels is None:
        return _NO_EXTERNAL_LABELS
    if not isinstance(sealed_labels, Mapping):
        raise SeatCaseError("eval_fixtures.sealed_labels must be a mapping")
    policy = sealed_labels.get("policy")
    if policy == "co_located":
        return _NO_EXTERNAL_LABELS
    if policy != "external":
        raise SeatCaseError(f"unsupported sealed label policy {policy!r}")

    label_path = _project_path(
        root, _require_string(sealed_labels, "path", "eval_fixtures.sealed_labels")
    )
    # The schema does not declare a separate label format.  Merged contracts
    # use JSONL; matching the fixture extension also supports the other v1
    # serialized row formats without adding a second undeclared field.
    label_format = _format_from_path(label_path, fixtures.get("format"))
    labels: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(_load_rows(label_path, label_format), start=1):
        raw_id = _field(row, id_field, missing=None)
        if raw_id is None:
            raise SeatCaseError(f"{label_path}: label row {index} has no {id_field!r}")
        fixture_id = str(raw_id)
        if fixture_id not in selected_ids:
            continue
        if fixture_id in labels:
            raise SeatCaseError(f"{label_path}: duplicate label id {fixture_id!r}")
        labels[fixture_id] = row
    return labels


def _expected_output(
    *,
    source_row: Mapping[str, Any],
    external_label: Mapping[str, Any] | None,
    expected_field: str,
    fixture_id: str,
    external: bool,
) -> Any:
    if external:
        if external_label is None:
            raise SeatCaseError(f"external label missing for fixture {fixture_id!r}")
        value = _field(external_label, expected_field, missing=_MISSING)
        if value is _MISSING:
            value = _field(external_label, "expected_output", missing=_MISSING)
        if value is _MISSING:
            raise SeatCaseError(
                f"external label for {fixture_id!r} has neither {expected_field!r} "
                "nor 'expected_output'"
            )
        return value
    value = _field(source_row, expected_field, missing=_MISSING)
    if value is _MISSING:
        raise SeatCaseError(
            f"co-located expected output {expected_field!r} missing for fixture {fixture_id!r}"
        )
    return value


def _resolve_contexts(
    root: Path,
    fixtures: Mapping[str, Any],
    row: Mapping[str, Any],
    max_context_bytes: int,
) -> dict[str, CaseContext]:
    providers = fixtures.get("context_providers", [])
    if not isinstance(providers, list):
        raise SeatCaseError("eval_fixtures.context_providers must be a list")
    resolved: dict[str, CaseContext] = {}
    for provider in providers:
        if not isinstance(provider, Mapping):
            raise SeatCaseError("context provider must be a mapping")
        provider_id = _require_string(provider, "id", "context provider")
        source = _require_string(provider, "source", f"context provider {provider_id}")
        source_ref = _require_string(
            provider, "source_ref", f"context provider {provider_id}"
        )
        required = provider.get("required")
        if not isinstance(required, bool):
            raise SeatCaseError(
                f"context provider {provider_id!r} requires a boolean 'required'"
            )
        if source == "fixture_field":
            value = _field(row, source_ref, missing=_MISSING)
            if value is _MISSING or value is None:
                if required:
                    raise SeatCaseError(
                        f"required fixture context {provider_id!r} ({source_ref}) is missing"
                    )
                continue
            context = CaseContext(provider_id, source, source_ref, copy.deepcopy(value))
        elif source == "project_file":
            path = _project_path(root, source_ref)
            if not path.is_file():
                if required:
                    raise SeatCaseError(
                        f"required project context {provider_id!r} does not exist: {source_ref}"
                    )
                continue
            size = path.stat().st_size
            if size > max_context_bytes:
                raise SeatCaseError(
                    f"project context {provider_id!r} is {size} bytes, above the "
                    f"{max_context_bytes}-byte safety limit"
                )
            data = path.read_bytes()
            try:
                value = data.decode("utf-8")
            except UnicodeDecodeError:
                value = data
            context = CaseContext(provider_id, source, source_ref, value, path)
        else:
            raise SeatCaseError(f"unsupported context provider source {source!r}")
        if provider_id in resolved:
            raise SeatCaseError(f"duplicate context provider id {provider_id!r}")
        resolved[provider_id] = context
    return resolved


def _load_rows(path: Path, format_name: str) -> list[Mapping[str, Any]]:
    if not path.is_file():
        raise SeatCaseError(f"fixture data does not exist: {path}")
    if format_name == "jsonl":
        rows: Any = []
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SeatCaseError(
                    f"{path}:{number}: invalid JSON: {exc.msg}"
                ) from exc
    elif format_name == "json":
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SeatCaseError(f"{path}: invalid JSON: {exc.msg}") from exc
    elif format_name == "yaml":
        rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    elif format_name == "csv":
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    else:
        raise SeatCaseError(f"unsupported fixture format {format_name!r}")

    if isinstance(rows, Mapping) and isinstance(rows.get("fixtures"), list):
        rows = rows["fixtures"]
    if not isinstance(rows, list):
        raise SeatCaseError(f"{path}: fixture document must contain a row list")
    if any(not isinstance(row, Mapping) for row in rows):
        raise SeatCaseError(f"{path}: every fixture row must be a mapping")
    return rows


def _format_from_path(path: Path, fixture_format: Any) -> str:
    suffixes = {
        ".jsonl": "jsonl",
        ".ndjson": "jsonl",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".csv": "csv",
    }
    return suffixes.get(path.suffix.lower(), str(fixture_format))


def _project_path(root: Path, reference: str) -> Path:
    ref = Path(reference)
    if ref.is_absolute() or ".." in ref.parts:
        raise SeatCaseError(
            f"project path must be relative and may not contain '..': {reference}"
        )
    candidate = (root / ref).resolve()
    if candidate != root and root not in candidate.parents:
        raise SeatCaseError(f"project path escapes project root: {reference}")
    return candidate


_MISSING = object()
_RAISE = object()


def _field(value: Mapping[str, Any], reference: str, *, missing: Any = _RAISE) -> Any:
    current: Any = value
    for component in reference.split("."):
        if not isinstance(current, Mapping) or component not in current:
            if missing is _RAISE:
                raise KeyError(reference)
            return missing
        current = current[component]
    return current


def _set_field(value: dict[str, Any], reference: str, replacement: Any) -> None:
    components = reference.split(".")
    current = value
    for component in components[:-1]:
        child = current.get(component)
        if not isinstance(child, dict):
            raise SeatCaseError(f"cannot set nested fixture field {reference!r}")
        current = child
    current[components[-1]] = replacement


def _dirty_input(value: Any) -> Any:
    """Apply one stable, semantics-preserving real-world noise transformation."""

    if isinstance(value, str):
        return f" \n[forwarded context; formatting may be inconsistent]\n{value}\n\t"
    if isinstance(value, dict):
        result = copy.deepcopy(value)
        for key in sorted(result):
            if isinstance(result[key], (str, dict, list)):
                result[key] = _dirty_input(result[key])
                return result
        result["_model_bench_noise"] = "forwarded without normalization"
        return result
    if isinstance(value, list):
        result = copy.deepcopy(value)
        if result:
            result[0] = _dirty_input(result[0])
        else:
            result.append("[forwarded empty section]")
        return result
    return {
        "value": copy.deepcopy(value),
        "_model_bench_noise": "forwarded without normalization",
    }


def _require_mapping(
    value: Mapping[str, Any], field: str, location: str
) -> Mapping[str, Any]:
    result = value.get(field)
    if not isinstance(result, Mapping):
        raise SeatCaseError(f"{location}.{field} must be a mapping")
    return result


def _require_string(value: Mapping[str, Any], field: str, location: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise SeatCaseError(f"{location}.{field} must be a non-empty string")
    return result
