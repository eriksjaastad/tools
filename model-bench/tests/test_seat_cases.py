from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from model_bench.seat_cases import (
    SealedAccessError,
    SeatCaseError,
    load_seat_cases,
    split_for_fixture,
)


def _remainder(fixture_id: str) -> int:
    return hashlib.sha256(fixture_id.encode()).digest()[0] % 5


def _id_for(remainders: set[int]) -> str:
    index = 0
    while True:
        fixture_id = f"fixture-{index}"
        if _remainder(fixture_id) in remainders:
            return fixture_id
        index += 1


def _seat(
    path: str, format_name: str = "jsonl", *, external: str | None = None
) -> dict:
    fixtures: dict = {
        "path": path,
        "format": format_name,
        "id_field": "fixture_id",
        "input_field": "input",
        "expected_output_field": "expected_output",
        "split": {
            "method": "deterministic_hash_modulo",
            "hash_field": "fixture_id",
            "modulo": 5,
            "dev_remainders": [1, 2, 3, 4],
            "sealed_remainders": [0],
            "sealed_unseal_env": "TEST_UNSEAL",
        },
    }
    if external:
        fixtures["sealed_labels"] = {"policy": "external", "path": external}
    return {
        "id": "test-seat",
        "input_character": "messy",
        "eval_fixtures": fixtures,
    }


def _write_rows(path: Path, rows: list[dict], format_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if format_name == "jsonl":
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    elif format_name == "json":
        path.write_text(json.dumps({"fixtures": rows}))
    elif format_name == "yaml":
        path.write_text(yaml.safe_dump(rows))
    elif format_name == "csv":
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


@pytest.mark.parametrize(
    ("format_name", "filename"),
    [
        ("jsonl", "cases.jsonl"),
        ("json", "cases.json"),
        ("yaml", "cases.yaml"),
        ("csv", "cases.csv"),
    ],
)
def test_loads_all_declared_fixture_formats(
    tmp_path: Path, format_name: str, filename: str
) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    row = {"fixture_id": fixture_id, "input": "real input", "expected_output": "gold"}
    _write_rows(tmp_path / filename, [row], format_name)

    cases = load_seat_cases(
        tmp_path, _seat(filename, format_name), include_dirty=False, environ={}
    )

    assert [(case.fixture_id, case.input, case.expected_output) for case in cases] == [
        (fixture_id, "real input", "gold")
    ]


def test_external_labels_are_joined_and_dirty_variant_does_not_mutate_source(
    tmp_path: Path,
) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    original = {
        "fixture_id": fixture_id,
        "input": {"claim": "A real claim"},
        "evidence": "Tracked evidence",
    }
    _write_rows(tmp_path / "cases.jsonl", [original], "jsonl")
    _write_rows(
        tmp_path / "labels.jsonl",
        [{"fixture_id": fixture_id, "expected_output": {"verdict": "SUPPORTED"}}],
        "jsonl",
    )
    seat = _seat("cases.jsonl", external="labels.jsonl")
    seat["eval_fixtures"]["context_providers"] = [
        {
            "id": "evidence",
            "source": "fixture_field",
            "source_ref": "evidence",
            "required": True,
        }
    ]
    snapshot = copy.deepcopy(original)

    cases = load_seat_cases(tmp_path, seat, environ={})

    assert len(cases) == 2
    assert cases[0].expected_output == {"verdict": "SUPPORTED"}
    assert cases[0].contexts["evidence"].value == "Tracked evidence"
    assert cases[1].variant_id == f"{fixture_id}::dirty-v1"
    assert cases[1].is_dirty
    assert cases[1].input != cases[0].input
    assert cases[0].source_row == snapshot
    assert original == snapshot


def test_dirty_pressure_adds_only_one_variant_per_seat_by_default(
    tmp_path: Path,
) -> None:
    ids = [_id_for({1, 2, 3, 4})]
    candidate = 1
    while len(ids) < 3:
        fixture_id = f"another-{candidate}"
        if _remainder(fixture_id) and fixture_id not in ids:
            ids.append(fixture_id)
        candidate += 1
    rows = [
        {"fixture_id": fixture_id, "input": f"input {index}", "expected_output": "gold"}
        for index, fixture_id in enumerate(ids)
    ]
    _write_rows(tmp_path / "cases.jsonl", rows, "jsonl")

    cases = load_seat_cases(tmp_path, _seat("cases.jsonl"), environ={})

    assert len(cases) == 4
    assert sum(case.is_dirty for case in cases) == 1
    assert next(case for case in cases if case.is_dirty).fixture_id == ids[0]


def test_external_label_falls_back_from_fixture_join_ref_to_expected_output(
    tmp_path: Path,
) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    _write_rows(
        tmp_path / "cases.jsonl",
        [{"fixture_id": fixture_id, "input": "diff", "label_ref": fixture_id}],
        "jsonl",
    )
    _write_rows(
        tmp_path / "labels.jsonl",
        [{"fixture_id": fixture_id, "expected_output": {"verdict": "PASS"}}],
        "jsonl",
    )
    seat = _seat("cases.jsonl", external="labels.jsonl")
    seat["eval_fixtures"]["expected_output_field"] = "label_ref"

    case = load_seat_cases(tmp_path, seat, include_dirty=False, environ={})[0]

    assert case.expected_output == {"verdict": "PASS"}


def test_sealed_gate_runs_before_any_fixture_or_external_label_read(
    tmp_path: Path,
) -> None:
    seat = _seat("does-not-exist.jsonl", external="also-does-not-exist.jsonl")

    with pytest.raises(SealedAccessError, match="TEST_UNSEAL=1"):
        load_seat_cases(tmp_path, seat, split="sealed", environ={})


def test_sealed_split_loads_only_after_exact_gate(tmp_path: Path) -> None:
    dev_id = _id_for({1, 2, 3, 4})
    sealed_id = _id_for({0})
    rows = [
        {"fixture_id": dev_id, "input": "dev", "expected_output": "dev-label"},
        {"fixture_id": sealed_id, "input": "sealed", "expected_output": "sealed-label"},
    ]
    _write_rows(tmp_path / "cases.jsonl", rows, "jsonl")
    seat = _seat("cases.jsonl")

    with pytest.raises(SealedAccessError):
        load_seat_cases(tmp_path, seat, split="sealed", environ={"TEST_UNSEAL": "true"})
    cases = load_seat_cases(
        tmp_path,
        seat,
        split="sealed",
        include_dirty=False,
        environ={"TEST_UNSEAL": "1"},
    )

    assert [case.fixture_id for case in cases] == [sealed_id]


def test_project_file_and_nested_fixture_contexts_are_resolved(tmp_path: Path) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    (tmp_path / "policy.md").write_text("Repository policy")
    _write_rows(
        tmp_path / "cases.jsonl",
        [
            {
                "fixture_id": fixture_id,
                "input": {"image_refs": ["one.png"]},
                "expected_output": "gold",
            }
        ],
        "jsonl",
    )
    seat = _seat("cases.jsonl")
    seat["eval_fixtures"]["context_providers"] = [
        {
            "id": "images",
            "source": "fixture_field",
            "source_ref": "input.image_refs",
            "required": True,
        },
        {
            "id": "policy",
            "source": "project_file",
            "source_ref": "policy.md",
            "required": True,
        },
    ]

    case = load_seat_cases(tmp_path, seat, include_dirty=False, environ={})[0]

    assert case.contexts["images"].value == ["one.png"]
    assert case.contexts["policy"].value == "Repository policy"
    assert case.contexts["policy"].path == (tmp_path / "policy.md").resolve()


def test_required_missing_context_and_unsafe_paths_fail(tmp_path: Path) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    _write_rows(
        tmp_path / "cases.jsonl",
        [{"fixture_id": fixture_id, "input": "input", "expected_output": "gold"}],
        "jsonl",
    )
    seat = _seat("cases.jsonl")
    seat["eval_fixtures"]["context_providers"] = [
        {
            "id": "policy",
            "source": "project_file",
            "source_ref": "../secret",
            "required": True,
        }
    ]

    with pytest.raises(SeatCaseError, match="may not contain"):
        load_seat_cases(tmp_path, seat, include_dirty=False, environ={})


def test_project_file_context_read_has_explicit_safety_limit(tmp_path: Path) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    (tmp_path / "policy.md").write_text("too much context")
    _write_rows(
        tmp_path / "cases.jsonl",
        [{"fixture_id": fixture_id, "input": "input", "expected_output": "gold"}],
        "jsonl",
    )
    seat = _seat("cases.jsonl")
    seat["eval_fixtures"]["context_providers"] = [
        {
            "id": "policy",
            "source": "project_file",
            "source_ref": "policy.md",
            "required": True,
        }
    ]

    with pytest.raises(SeatCaseError, match="safety limit"):
        load_seat_cases(
            tmp_path,
            seat,
            include_dirty=False,
            max_context_bytes=4,
            environ={},
        )


def test_split_matches_v1_sha256_first_byte_rule() -> None:
    row = {"fixture_id": "known-id"}
    contract = _seat("unused")["eval_fixtures"]["split"]
    expected = "sealed" if _remainder("known-id") == 0 else "dev"

    assert split_for_fixture(row, contract) == expected


def test_missing_external_label_fails_instead_of_silently_scoring_without_gold(
    tmp_path: Path,
) -> None:
    fixture_id = _id_for({1, 2, 3, 4})
    _write_rows(
        tmp_path / "cases.jsonl",
        [{"fixture_id": fixture_id, "input": "input"}],
        "jsonl",
    )
    _write_rows(tmp_path / "labels.jsonl", [], "jsonl")

    with pytest.raises(SeatCaseError, match="external label missing"):
        load_seat_cases(
            tmp_path,
            _seat("cases.jsonl", external="labels.jsonl"),
            include_dirty=False,
            environ={},
        )
