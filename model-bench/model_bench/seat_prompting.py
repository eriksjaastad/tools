"""Deterministic prompt and multimodal-input assembly for seat fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .seat_cases import SeatCase

MAX_CONTEXT_CHARS = 20_000
MAX_CONTEXT_FILES = 8
MAX_SCHEMA_CHARS = 100_000


def build_seat_prompt(
    *,
    seat: Mapping[str, Any] | object,
    case: SeatCase,
) -> str:
    """Build a model prompt from the project-owned job, input, and context.

    Gold labels are intentionally absent. Project-file contexts are bounded so
    a newly added source file cannot silently create an unbounded prompt.
    """
    raw = _seat_mapping(seat)
    output_contract = _mapping(raw, "output_contract")
    output_type = output_contract.get("type")

    if output_type == "image":
        image_prompt = _image_prompt(case.input)
        contexts = _render_contexts(case)
        return image_prompt if not contexts else f"{image_prompt}\n\n{contexts}"

    instructions = [
        f"Job: {raw['job']}",
        f"Output type: {output_type}",
        f"Validity requirements: {output_contract['validation']}",
    ]
    if output_type == "json":
        instructions.append(
            "Return only the JSON artifact; do not wrap it in Markdown."
        )
        schema = _render_schema(seat)
        if schema:
            instructions.append(f"Required JSON Schema:\n{schema}")
    elif output_type == "free_text":
        instructions.append("Return only the requested answer.")
    elif output_type == "code":
        instructions.append("Return only the code artifact.")

    prompt = "\n".join(instructions)
    contexts = _render_contexts(case)
    if contexts:
        prompt += f"\n\nProject-provided context:\n{contexts}"
    prompt += "\n\nReal fixture input:\n" + _render_value(case.input)
    return prompt


def image_paths_for_case(
    *,
    project_root: Path,
    seat: Mapping[str, Any] | object,
    case: SeatCase,
) -> list[Path]:
    """Resolve declared fixture image references without allowing traversal."""
    raw = _seat_mapping(seat)
    if "vision" not in raw.get("required_capabilities", []):
        return []

    references: list[str] = []
    for context in case.contexts.values():
        if context.source != "fixture_field":
            continue
        value = context.value
        if isinstance(value, str):
            references.append(value)
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            references.extend(value)

    if len(references) > MAX_CONTEXT_FILES:
        raise ValueError(
            f"{case.variant_id}: {len(references)} image contexts exceed "
            f"the limit of {MAX_CONTEXT_FILES}"
        )

    root = project_root.resolve()
    paths: list[Path] = []
    for reference in references:
        ref = Path(reference)
        if ref.is_absolute() or ".." in ref.parts:
            raise ValueError(f"unsafe fixture image reference: {reference}")
        path = (root / ref).resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"fixture image escapes project root: {reference}")
        if not path.is_file():
            raise ValueError(f"fixture image does not exist: {reference}")
        paths.append(path)
    return paths


def _render_contexts(case: SeatCase) -> str:
    rendered: list[str] = []
    for context_id in sorted(case.contexts):
        context = case.contexts[context_id]
        if context.source == "fixture_field" and _looks_like_image_refs(context.value):
            rendered.append(f"[{context_id}] image artifacts attached separately")
            continue
        text = _render_value(context.value)
        if len(text) > MAX_CONTEXT_CHARS:
            text = (
                text[:MAX_CONTEXT_CHARS]
                + f"\n[truncated at {MAX_CONTEXT_CHARS} characters by model-bench]"
            )
        rendered.append(f"[{context_id}]\n{text}")
    return "\n\n".join(rendered)


def _render_value(value: Any) -> str:
    if isinstance(value, bytes):
        return f"[binary context: {len(value)} bytes]"
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def _image_prompt(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, Mapping):
        prompt = value.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt
    raise ValueError("image-generation fixture input requires a non-empty prompt")


def _render_schema(seat: Mapping[str, Any] | object) -> str:
    schema_path = getattr(seat, "schema_path", None)
    if schema_path is None:
        return ""
    path = Path(schema_path)
    try:
        schema = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read project JSON Schema {path}: {exc}") from exc
    if len(schema) > MAX_SCHEMA_CHARS:
        raise ValueError(
            f"project JSON Schema exceeds {MAX_SCHEMA_CHARS} character prompt limit"
        )
    return schema


def _seat_mapping(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raw = getattr(value, "raw", None)
    if isinstance(raw, Mapping):
        return raw
    raise TypeError("seat must be a mapping or expose a raw mapping")


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    result = value.get(key)
    if not isinstance(result, Mapping):
        raise TypeError(f"seat.{key} must be a mapping")
    return result


def _looks_like_image_refs(value: Any) -> bool:
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not values:
        return False
    return all(
        isinstance(item, str)
        and Path(item).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        for item in values
    )
