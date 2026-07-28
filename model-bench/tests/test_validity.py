from __future__ import annotations

import base64
import binascii
import json
import struct
import zlib
from pathlib import Path

import pytest

from model_bench.validity import (
    ValidityResult,
    validate_artifact,
    validate_seat_artifact,
)


def _png(width: int, height: int) -> bytes:
    def chunk(kind: bytes, content: bytes) -> bytes:
        crc = binascii.crc32(kind)
        crc = binascii.crc32(content, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = b"".join(b"\x00" + (b"\x00" * width * 3) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _assert_hard_floor(result: ValidityResult, code: str) -> None:
    assert not result.valid
    assert result.hard_floor_reason
    assert result.hard_floor_reason.startswith(f"{code}:")


@pytest.mark.parametrize("output", ["", " \n\t", None, b"text", "bad\x00text"])
def test_free_text_invalidity_is_a_hard_floor(output: object, tmp_path: Path) -> None:
    result = validate_artifact(output, {"type": "free_text"}, project_root=tmp_path)

    assert not result.valid
    assert result.hard_floor_reason


def test_valid_free_text_passes_without_a_floor(tmp_path: Path) -> None:
    result = validate_artifact(
        "A grounded answer", {"type": "free_text"}, project_root=tmp_path
    )

    assert result.valid
    assert result.parsed_output == "A grounded answer"
    assert result.hard_floor_reason is None


def test_json_is_parsed_and_validated_against_project_schema(tmp_path: Path) -> None:
    (tmp_path / "schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["verdict"],
                "properties": {"verdict": {"enum": ["PASS", "FAIL"]}},
                "additionalProperties": False,
            }
        )
    )
    contract = {"type": "json", "schema_ref": "schema.json"}

    valid = validate_artifact('{"verdict":"PASS"}', contract, project_root=tmp_path)
    invalid = validate_artifact('{"verdict":"MAYBE"}', contract, project_root=tmp_path)

    assert valid.valid
    assert valid.parsed_output == {"verdict": "PASS"}
    _assert_hard_floor(invalid, "json.schema")


def test_malformed_json_and_unsafe_or_missing_schema_are_hard_floors(
    tmp_path: Path,
) -> None:
    malformed = validate_artifact(
        "{", {"type": "json", "schema_ref": "schema.json"}, project_root=tmp_path
    )
    escaped = validate_artifact(
        "{}", {"type": "json", "schema_ref": "../schema.json"}, project_root=tmp_path
    )
    missing = validate_artifact(
        "{}", {"type": "json", "schema_ref": "missing.json"}, project_root=tmp_path
    )

    _assert_hard_floor(malformed, "json.parse")
    _assert_hard_floor(escaped, "json.schema_ref")
    _assert_hard_floor(missing, "json.schema_missing")


def test_json_schema_cannot_trigger_remote_reference_fetch(tmp_path: Path) -> None:
    (tmp_path / "schema.json").write_text(
        json.dumps({"$ref": "https://attacker.invalid/schema.json"})
    )

    result = validate_artifact(
        "{}", {"type": "json", "schema_ref": "schema.json"}, project_root=tmp_path
    )

    _assert_hard_floor(result, "json.schema_ref_unresolved")


def test_png_gates_mime_dimensions_size_and_ratio(tmp_path: Path) -> None:
    artifact = _png(1024, 1024)
    contract = {
        "type": "image",
        "image": {
            "allowed_mime_types": ["image/png"],
            "min_width_px": 1024,
            "min_height_px": 1024,
            "max_bytes": len(artifact),
            "allowed_aspect_ratios": ["1:1"],
        },
    }

    result = validate_artifact(artifact, contract, project_root=tmp_path)

    assert result.valid
    assert result.mime_type == "image/png"
    assert (result.width_px, result.height_px) == (1024, 1024)


def test_image_claims_do_not_override_real_artifact_properties(tmp_path: Path) -> None:
    contract = {
        "type": "image",
        "image": {
            "allowed_mime_types": ["image/webp"],
            "min_width_px": 2048,
            "allowed_aspect_ratios": ["16:9"],
        },
    }

    result = validate_artifact(
        {"data": _png(32, 32), "mime_type": "image/webp"},
        contract,
        project_root=tmp_path,
    )

    _assert_hard_floor(result, "image.mime_mismatch")


def test_image_data_url_is_decoded_before_validation(tmp_path: Path) -> None:
    artifact = _png(4, 4)
    output = "data:image/png;base64," + base64.b64encode(artifact).decode()
    contract = {
        "type": "image",
        "image": {
            "allowed_mime_types": ["image/png"],
            "allowed_aspect_ratios": ["1:1"],
        },
    }

    assert validate_artifact(output, contract, project_root=tmp_path).valid


def test_png_with_corrupt_pixel_stream_is_not_treated_as_decoded(
    tmp_path: Path,
) -> None:
    artifact = bytearray(_png(4, 4))
    artifact[-20] ^= 0x01
    contract = {"type": "image", "image": {"allowed_mime_types": ["image/png"]}}

    _assert_hard_floor(
        validate_artifact(bytes(artifact), contract, project_root=tmp_path),
        "image.decode",
    )


@pytest.mark.parametrize(
    ("artifact", "code"),
    [
        (b"not an image", "image.decode"),
        (_png(10, 5), "image.aspect_ratio"),
        (_png(2, 2), "image.min_width"),
    ],
)
def test_bad_image_artifacts_are_hard_floors(
    artifact: bytes, code: str, tmp_path: Path
) -> None:
    contract = {
        "type": "image",
        "image": {
            "allowed_mime_types": ["image/png"],
            "min_width_px": 4,
            "allowed_aspect_ratios": ["1:1"],
        },
    }

    _assert_hard_floor(
        validate_artifact(artifact, contract, project_root=tmp_path), code
    )


def test_code_gate_rejects_non_text_empty_nul_and_missing_sandbox(
    tmp_path: Path,
) -> None:
    for output in (b"code", "", "x = 1\x00"):
        result = validate_artifact(output, {"type": "code"}, project_root=tmp_path)
        assert not result.valid
        assert result.hard_floor_reason

    unavailable = validate_artifact(
        'fn main() { println!("ok"); }', {"type": "code"}, project_root=tmp_path
    )
    _assert_hard_floor(unavailable, "code.execution_unavailable")


def test_code_execution_failure_is_a_hard_floor_before_judging(tmp_path: Path) -> None:
    calls: list[str] = []

    def executor(code: str, **kwargs):
        calls.append(code)
        assert kwargs["project_root"] == tmp_path
        return {"passed": False, "reason": "tests failed", "details": {"exit_code": 1}}

    result = validate_artifact(
        "print('wrong')",
        {"type": "code"},
        project_root=tmp_path,
        code_executor=executor,
    )

    assert calls == ["print('wrong')"]
    _assert_hard_floor(result, "code.execution_failed")
    assert "tests failed" in result.hard_floor_reason
    assert result.details["execution"]["exit_code"] == 1


def test_code_passes_only_after_sandbox_execution_succeeds(tmp_path: Path) -> None:
    result = validate_artifact(
        "print('ok')",
        {"type": "code"},
        project_root=tmp_path,
        code_executor=lambda code, **kwargs: {
            "passed": True,
            "details": {"exit_code": 0, "sandbox": "test"},
        },
    )

    assert result.valid
    assert result.details["execution"]["exit_code"] == 0


def test_unknown_contract_type_is_a_hard_floor(tmp_path: Path) -> None:
    _assert_hard_floor(
        validate_artifact("value", {"type": "audio"}, project_root=tmp_path),
        "contract.unsupported_type",
    )


def test_validity_result_enforces_hard_floor_invariant() -> None:
    with pytest.raises(ValueError, match="must have"):
        ValidityResult(valid=False)
    with pytest.raises(ValueError, match="cannot have"):
        ValidityResult(valid=True, hard_floor_reason="should not exist")


def test_seat_runner_adapter_exposes_reason_and_details(tmp_path: Path) -> None:
    class DiscoveredSeat:
        def __init__(self) -> None:
            self.raw = {"output_contract": {"type": "free_text"}}
            self.project_root = tmp_path

    result = validate_seat_artifact(
        seat=DiscoveredSeat(),
        case={"fixture_id": "one"},
        artifact="grounded response",
    )

    assert result.valid
    assert result.reason == ""
    assert result.details["parsed_output"] == "grounded response"
