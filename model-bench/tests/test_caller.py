from __future__ import annotations

from pathlib import Path

import pytest

from model_bench.caller import _litellm_content, call_model
from model_bench.registry import ModelEntry


def test_litellm_content_embeds_bounded_image(tmp_path: Path) -> None:
    image = tmp_path / "fixture.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    content = _litellm_content("inspect it", [image])

    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "inspect it"}
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_litellm_content_rejects_non_image(tmp_path: Path) -> None:
    text = tmp_path / "not-an-image.txt"
    text.write_text("payload")

    with pytest.raises(ValueError, match="unsupported image MIME"):
        _litellm_content("inspect it", [text])


def test_stability_call_fails_closed_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STABILITY_API_KEY", raising=False)
    model = ModelEntry(
        id="stability-ai/stable-image-core",
        display_name="stable image",
        provider="stability-ai",
        tier="incumbent",
        capabilities=frozenset({"image_generation"}),
    )

    result = call_model(model, "food photo")

    assert result.error == "STABILITY_API_KEY is not configured"
    assert result.artifact is None


def test_litellm_receives_portable_seat_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Message:
        content = "ok"

    class _Choice:
        message = _Message()

    class _Usage:
        prompt_tokens = 2
        completion_tokens = 1

    class _Response:
        def __init__(self) -> None:
            self.choices = [_Choice()]
            self.usage = _Usage()

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr("litellm.completion", fake_completion)
    model = ModelEntry(
        id="gpt-test",
        display_name="test",
        provider="openai",
        tier="cheap",
    )

    result = call_model(
        model,
        "prompt",
        parameters={"temperature": 0.3, "max_tokens": 200},
    )

    assert result.error is None
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 200
