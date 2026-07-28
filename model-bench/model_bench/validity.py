"""Deterministic artifact-validity gates that run before model judging."""

from __future__ import annotations

import base64
import binascii
import json
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import jsonschema


@dataclass(frozen=True)
class ValidityResult:
    """Validity outcome; invalid artifacts always carry a hard-floor reason."""

    valid: bool
    parsed_output: Any = None
    hard_floor_reason: str | None = None
    mime_type: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    execution_details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.valid and self.hard_floor_reason is not None:
            raise ValueError("a valid result cannot have a hard-floor reason")
        if not self.valid and not self.hard_floor_reason:
            raise ValueError("an invalid result must have a hard-floor reason")

    @property
    def reason(self) -> str:
        """Compatibility with ``SeatRunner``'s validator result protocol."""

        return self.hard_floor_reason or ""

    @property
    def details(self) -> dict[str, Any]:
        """Machine-readable artifact metadata for run provenance."""

        details: dict[str, Any] = {}
        if self.parsed_output is not None:
            details["parsed_output"] = self.parsed_output
        if self.mime_type is not None:
            details["mime_type"] = self.mime_type
        if self.width_px is not None:
            details["width_px"] = self.width_px
        if self.height_px is not None:
            details["height_px"] = self.height_px
        if self.execution_details is not None:
            details["execution"] = dict(self.execution_details)
        return details


class CodeExecutor(Protocol):
    """Execute untrusted code in a caller-owned sandbox."""

    def __call__(
        self,
        code: str,
        *,
        contract: Mapping[str, Any],
        project_root: Path,
    ) -> bool | Mapping[str, Any]: ...


def validate_artifact(
    output: Any,
    output_contract: dict[str, Any],
    *,
    project_root: str | Path,
    code_executor: CodeExecutor | None = None,
) -> ValidityResult:
    """Validate an output artifact according to a merged seats.v1 contract."""

    contract_type = output_contract.get("type")
    root = Path(project_root).resolve()
    if contract_type == "free_text":
        return _validate_text(output, "free_text")
    if contract_type == "code":
        return _validate_code(output, output_contract, root, code_executor)
    if contract_type == "json":
        return _validate_json(output, output_contract, root)
    if contract_type == "image":
        return _validate_image(output, output_contract)
    return _invalid(
        "contract.unsupported_type", f"unsupported output type {contract_type!r}"
    )


def validate_seat_artifact(
    *,
    seat: Mapping[str, Any] | object,
    case: Mapping[str, Any] | object,
    artifact: Any,
    project_root: str | Path | None = None,
    code_executor: CodeExecutor | None = None,
) -> ValidityResult:
    """Adapt :func:`validate_artifact` to ``SeatRunner``'s validator protocol.

    ``case`` is accepted because it is part of that protocol; representation
    validity depends only on the seat contract.  A discovered
    ``SeatDefinition`` supplies both ``raw`` and ``project_root``.  Raw mappings
    require an explicit ``project_root`` for project-relative schema lookup.
    """

    del case
    raw = getattr(seat, "raw", seat)
    if not isinstance(raw, Mapping):
        return _invalid("contract.seat", "seat has no raw contract mapping")
    contract = raw.get("output_contract")
    if not isinstance(contract, dict):
        return _invalid("contract.output", "seat has no output_contract mapping")
    root = (
        project_root
        if project_root is not None
        else getattr(seat, "project_root", None)
    )
    if root is None:
        return _invalid(
            "contract.project_root", "project_root is required for artifact validity"
        )
    return validate_artifact(
        artifact, contract, project_root=root, code_executor=code_executor
    )


def _validate_text(output: Any, contract_type: str) -> ValidityResult:
    if not isinstance(output, str):
        return _invalid(f"{contract_type}.not_text", "artifact is not text")
    if not output.strip():
        return _invalid(f"{contract_type}.empty", "artifact is empty")
    if "\x00" in output:
        return _invalid(f"{contract_type}.nul_byte", "artifact contains a NUL byte")
    return ValidityResult(valid=True, parsed_output=output)


def _validate_code(
    output: Any,
    contract: Mapping[str, Any],
    project_root: Path,
    executor: CodeExecutor | None,
) -> ValidityResult:
    result = _validate_text(output, "code")
    if not result.valid:
        return result
    if executor is None:
        return _invalid(
            "code.execution_unavailable",
            "code artifacts require an explicitly injected sandbox executor",
        )
    try:
        raw = executor(output, contract=contract, project_root=project_root)
    except Exception as exc:  # noqa: BLE001 - sandbox adapter failure is evidence
        return _invalid("code.execution_error", f"sandbox executor failed: {exc}")
    if isinstance(raw, bool):
        passed = raw
        reason = "" if raw else "sandbox execution or project checks failed"
        details: Mapping[str, Any] = {}
    elif isinstance(raw, Mapping):
        passed = bool(raw.get("passed", raw.get("valid", raw.get("success", False))))
        reason = str(raw.get("reason", ""))
        raw_details = raw.get("details", {})
        details = (
            raw_details if isinstance(raw_details, Mapping) else {"result": raw_details}
        )
    else:
        return _invalid(
            "code.execution_result",
            "sandbox executor must return a boolean or result mapping",
        )
    if not passed:
        return ValidityResult(
            valid=False,
            hard_floor_reason=(
                "code.execution_failed: "
                f"{reason or 'sandbox execution or project checks failed'}"
            ),
            execution_details=details,
        )
    return ValidityResult(
        valid=True,
        parsed_output=output,
        execution_details=details,
    )


def _validate_json(
    output: Any, contract: dict[str, Any], project_root: Path
) -> ValidityResult:
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as exc:
            return _invalid(
                "json.parse", f"invalid JSON at line {exc.lineno}, column {exc.colno}"
            )
    elif isinstance(output, (dict, list, int, float, bool)) or output is None:
        parsed = output
    else:
        return _invalid(
            "json.not_json", "artifact is neither JSON text nor a JSON value"
        )

    schema_ref = contract.get("schema_ref")
    if not isinstance(schema_ref, str) or not schema_ref:
        return _invalid("json.schema_ref", "JSON contract has no schema_ref")
    try:
        schema_path = _project_path(project_root, schema_ref)
    except ValueError as exc:
        return _invalid("json.schema_ref", str(exc))
    if not schema_path.is_file():
        return _invalid("json.schema_missing", f"schema does not exist: {schema_ref}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _invalid(
            "json.schema_invalid", f"cannot load schema {schema_ref}: {exc}"
        )
    unsafe_ref = _find_nonlocal_schema_ref(schema)
    if unsafe_ref is not None:
        return _invalid(
            "json.schema_ref_unresolved",
            f"only in-document JSON Schema references are supported: {unsafe_ref}",
        )

    try:
        validator_class = jsonschema.validators.validator_for(schema)
        validator_class.check_schema(schema)
        validator = validator_class(
            schema,
            format_checker=validator_class.FORMAT_CHECKER,
        )
        errors = sorted(
            validator.iter_errors(parsed), key=lambda item: list(item.absolute_path)
        )
    except jsonschema.exceptions.SchemaError as exc:
        return _invalid("json.schema_invalid", exc.message)
    except jsonschema.exceptions.RefResolutionError as exc:
        return _invalid("json.schema_ref_unresolved", str(exc))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        return _invalid("json.schema", f"{location}: {error.message}")
    return ValidityResult(valid=True, parsed_output=parsed)


def _validate_image(output: Any, contract: dict[str, Any]) -> ValidityResult:
    image_contract = contract.get("image")
    if not isinstance(image_contract, dict):
        return _invalid("image.contract", "image contract is missing")
    try:
        data, declared_mime = _image_bytes(output)
    except (OSError, ValueError) as exc:
        return _invalid("image.read", str(exc))

    max_bytes = image_contract.get("max_bytes")
    if isinstance(max_bytes, int) and len(data) > max_bytes:
        return _invalid(
            "image.max_bytes", f"{len(data)} bytes exceeds maximum {max_bytes}"
        )

    try:
        mime_type, width, height = _inspect_image(data)
    except ValueError as exc:
        return _invalid("image.decode", str(exc))
    if declared_mime is not None and declared_mime != mime_type:
        return _invalid(
            "image.mime_mismatch",
            f"declared MIME {declared_mime!r} does not match artifact {mime_type!r}",
        )
    allowed_mimes = image_contract.get("allowed_mime_types")
    if not isinstance(allowed_mimes, list) or mime_type not in allowed_mimes:
        return _invalid("image.mime", f"MIME {mime_type!r} is not allowed")

    min_width = image_contract.get("min_width_px")
    if isinstance(min_width, int) and width < min_width:
        return _invalid("image.min_width", f"width {width}px is below {min_width}px")
    min_height = image_contract.get("min_height_px")
    if isinstance(min_height, int) and height < min_height:
        return _invalid(
            "image.min_height", f"height {height}px is below {min_height}px"
        )

    ratios = image_contract.get("allowed_aspect_ratios")
    if ratios:
        matches = False
        for ratio in ratios:
            try:
                ratio_width, ratio_height = (int(part) for part in ratio.split(":", 1))
            except (AttributeError, TypeError, ValueError):
                return _invalid("image.contract", f"invalid aspect ratio {ratio!r}")
            matches |= width * ratio_height == height * ratio_width
        if not matches:
            return _invalid(
                "image.aspect_ratio", f"{width}:{height} is not an allowed ratio"
            )

    return ValidityResult(
        valid=True,
        parsed_output=data,
        mime_type=mime_type,
        width_px=width,
        height_px=height,
    )


def _image_bytes(output: Any) -> tuple[bytes, str | None]:
    declared_mime: str | None = None
    value = output
    if isinstance(output, dict):
        declared = output.get("mime_type")
        if declared is not None and not isinstance(declared, str):
            raise ValueError("image mime_type must be text")
        declared_mime = declared
        if "data" in output:
            value = output["data"]
        elif "path" in output:
            value = Path(output["path"])
        else:
            raise ValueError("image mapping requires 'data' or 'path'")
    if isinstance(value, str) and value.startswith("data:"):
        header, separator, encoded = value.partition(",")
        if not separator or ";base64" not in header:
            raise ValueError("only base64 image data URLs are supported")
        data_mime = header[5:].split(";", 1)[0]
        if declared_mime is not None and declared_mime != data_mime:
            raise ValueError("mapping MIME and data URL MIME disagree")
        declared_mime = data_mime
        try:
            return base64.b64decode(encoded, validate=True), declared_mime
        except binascii.Error as exc:
            raise ValueError("image data URL has invalid base64") from exc
    if isinstance(value, (str, Path)):
        return Path(value).read_bytes(), declared_mime
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value), declared_mime
    raise ValueError(
        "image artifact must be bytes, a path, a data URL, or an artifact mapping"
    )


def _inspect_image(data: bytes) -> tuple[str, int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = _png_dimensions(data)
        return "image/png", width, height
    if data.startswith((b"GIF87a", b"GIF89a")):
        if len(data) < 14 or data[-1:] != b";":
            raise ValueError("truncated GIF")
        width, height = struct.unpack("<HH", data[6:10])
        if width <= 0 or height <= 0:
            raise ValueError("invalid GIF dimensions")
        return "image/gif", width, height
    if data.startswith(b"\xff\xd8"):
        width, height = _jpeg_dimensions(data)
        return "image/jpeg", width, height
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        width, height = _webp_dimensions(data)
        return "image/webp", width, height
    raise ValueError("unsupported or unrecognized image encoding")


def _png_dimensions(data: bytes) -> tuple[int, int]:
    offset = 8
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    saw_iend = False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise ValueError("truncated PNG chunk")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError(
                f"PNG {chunk_type.decode('ascii', 'replace')} chunk has a bad CRC"
            )
        if offset == 8 and chunk_type != b"IHDR":
            raise ValueError("PNG IHDR is not the first chunk")
        if chunk_type == b"IHDR":
            if length != 13 or width is not None:
                raise ValueError("invalid PNG IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", chunk_data)
            )
            if width <= 0 or height <= 0:
                raise ValueError("invalid PNG dimensions")
            if compression != 0 or filtering != 0 or interlace not in {0, 1}:
                raise ValueError("unsupported PNG encoding")
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0:
                raise ValueError("invalid PNG IEND")
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end
    if (
        None in {width, height, bit_depth, color_type, interlace}
        or not compressed
        or not saw_iend
    ):
        raise ValueError("PNG is missing required chunks")
    if offset != len(data):
        raise ValueError("PNG has trailing data")

    channels_by_color = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    valid_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if color_type not in channels_by_color or bit_depth not in valid_depths[color_type]:
        raise ValueError("invalid PNG color type or bit depth")
    channels = channels_by_color[color_type]
    scanlines = _png_scanline_lengths(width, height, channels, bit_depth, interlace)
    decoded_size = sum(length + 1 for length in scanlines)
    # Validity checking is a trust boundary.  Avoid turning a tiny compressed
    # artifact with hostile dimensions into an unbounded allocation.
    if decoded_size > 512 * 1024 * 1024:
        raise ValueError("decoded PNG exceeds the 512 MiB safety limit")
    try:
        decoded = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise ValueError("PNG pixel stream cannot be decompressed") from exc
    if len(decoded) != decoded_size:
        raise ValueError("PNG pixel stream length does not match its dimensions")
    position = 0
    for scanline_length in scanlines:
        if decoded[position] > 4:
            raise ValueError("PNG contains an invalid scanline filter")
        position += scanline_length + 1
    return width, height


def _png_scanline_lengths(
    width: int, height: int, channels: int, bit_depth: int, interlace: int
) -> list[int]:
    def row_bytes(row_width: int) -> int:
        return (row_width * channels * bit_depth + 7) // 8

    if interlace == 0:
        return [row_bytes(width)] * height
    # Adam7 pass origins and strides.
    passes = (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    )
    lengths: list[int] = []
    for x_start, y_start, x_step, y_step in passes:
        pass_width = max(0, (width - x_start + x_step - 1) // x_step)
        pass_height = max(0, (height - y_start + y_step - 1) // y_step)
        if pass_width:
            lengths.extend([row_bytes(pass_width)] * pass_height)
    return lengths


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or not data.endswith(b"\xff\xd9"):
        raise ValueError("truncated JPEG")
    offset = 2
    sof_markers = set(range(0xC0, 0xD4)) - {0xC4, 0xC8, 0xCC}
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if length < 2 or offset + length > len(data):
            raise ValueError("invalid JPEG segment")
        if marker in sof_markers:
            if length < 7:
                raise ValueError("invalid JPEG size segment")
            height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
            if width <= 0 or height <= 0:
                raise ValueError("invalid JPEG dimensions")
            return width, height
        offset += length
    raise ValueError("JPEG has no size frame")


def _webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30:
        raise ValueError("truncated WebP")
    declared_length = struct.unpack("<I", data[4:8])[0] + 8
    if declared_length > len(data):
        raise ValueError("truncated WebP RIFF payload")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
    elif chunk == b"VP8L":
        if data[20] != 0x2F:
            raise ValueError("invalid lossless WebP signature")
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
    elif chunk == b"VP8 ":
        start = data.find(b"\x9d\x01\x2a", 20)
        if start < 0 or start + 7 > len(data):
            raise ValueError("WebP has no lossy size frame")
        width, height = struct.unpack("<HH", data[start + 3 : start + 7])
        width &= 0x3FFF
        height &= 0x3FFF
    else:
        raise ValueError("unsupported WebP chunk layout")
    if width <= 0 or height <= 0:
        raise ValueError("invalid WebP dimensions")
    return width, height


def _project_path(root: Path, reference: str) -> Path:
    ref = Path(reference)
    if ref.is_absolute() or ".." in ref.parts:
        raise ValueError("schema_ref must be a safe project-relative path")
    path = (root / ref).resolve()
    if path != root and root not in path.parents:
        raise ValueError("schema_ref escapes project root")
    return path


def _find_nonlocal_schema_ref(value: Any) -> str | None:
    if isinstance(value, Mapping):
        ref = value.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            return ref
        for child in value.values():
            found = _find_nonlocal_schema_ref(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_nonlocal_schema_ref(child)
            if found is not None:
                return found
    return None


def _invalid(code: str, detail: str) -> ValidityResult:
    return ValidityResult(valid=False, hard_floor_reason=f"{code}: {detail}")
