from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from model_bench.seat_cases import CaseContext, SeatCase
from model_bench.seat_prompting import (
    MAX_CONTEXT_CHARS,
    build_seat_prompt,
    image_paths_for_case,
)


def _case(*, context: CaseContext | None = None) -> SeatCase:
    return SeatCase(
        fixture_id="fixture-1",
        variant_id="fixture-1",
        split="dev",
        input={"claim": "real input"},
        expected_output={"verdict": "PASS"},
        contexts={} if context is None else {context.id: context},
        source_row={"fixture_id": "fixture-1"},
    )


def test_prompt_contains_real_input_but_not_gold_label() -> None:
    seat = {
        "job": "Judge a claim.",
        "output_contract": {
            "type": "json",
            "validation": "Validate the verdict schema.",
        },
    }

    prompt = build_seat_prompt(seat=seat, case=_case())

    assert '"claim": "real input"' in prompt
    assert "Validate the verdict schema." in prompt
    assert "PASS" not in prompt
    assert "Return only the JSON artifact" in prompt


def test_prompt_includes_project_json_schema_without_gold(tmp_path: Path) -> None:
    schema = tmp_path / "output.schema.json"
    schema.write_text(
        '{"type":"object","required":["verdict"],'
        '"properties":{"verdict":{"type":"string"}}}'
    )
    seat = SimpleNamespace(
        raw={
            "job": "Judge a claim.",
            "output_contract": {
                "type": "json",
                "validation": "Validate the verdict schema.",
            },
        },
        schema_path=schema,
    )

    prompt = build_seat_prompt(seat=seat, case=_case())

    assert "Required JSON Schema:" in prompt
    assert '"required":["verdict"]' in prompt
    assert "PASS" not in prompt


def test_project_context_is_bounded() -> None:
    context = CaseContext(
        id="policy",
        source="project_file",
        source_ref="policy.md",
        value="x" * (MAX_CONTEXT_CHARS + 10),
    )
    seat = {
        "job": "Answer.",
        "output_contract": {"type": "free_text", "validation": "Non-empty."},
    }

    prompt = build_seat_prompt(seat=seat, case=_case(context=context))

    assert "truncated at" in prompt
    assert len(prompt) < MAX_CONTEXT_CHARS + 1000


def test_vision_paths_are_resolved_and_attached_separately(tmp_path: Path) -> None:
    image = tmp_path / "assets" / "one.png"
    image.parent.mkdir()
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    context = CaseContext(
        id="images",
        source="fixture_field",
        source_ref="input.image_refs",
        value=["assets/one.png"],
    )
    seat = {
        "job": "Review images.",
        "required_capabilities": ["vision", "json_mode"],
        "output_contract": {"type": "json", "validation": "Return scores."},
    }
    case = _case(context=context)

    assert image_paths_for_case(project_root=tmp_path, seat=seat, case=case) == [
        image.resolve()
    ]
    assert "attached separately" in build_seat_prompt(seat=seat, case=case)


def test_vision_path_cannot_escape_project(tmp_path: Path) -> None:
    context = CaseContext(
        id="images",
        source="fixture_field",
        source_ref="input.image_refs",
        value=["../outside.png"],
    )
    seat = {
        "required_capabilities": ["vision"],
        "job": "Review.",
        "output_contract": {"type": "json", "validation": "Return JSON."},
    }

    with pytest.raises(ValueError, match="unsafe fixture image"):
        image_paths_for_case(
            project_root=tmp_path, seat=seat, case=_case(context=context)
        )
