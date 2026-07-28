from __future__ import annotations

from types import SimpleNamespace

import pytest

from model_bench.judge import judge_seat_responses


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_seat_judge_uses_expected_rubric_and_exact_model_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _completion(
            '{"judgments":[{"model_id":"candidate","score":4,'
            '"reasoning":"Covers the required facts."}]}'
        )

    monkeypatch.setattr("model_bench.judge.litellm.completion", fake_completion)
    seat = {
        "job": "Answer from memory.",
        "output_contract": {
            "validation": "Include every required fact.",
        },
    }
    case = SimpleNamespace(
        expected_output={"required": ["one"], "prohibited": ["invented fact"]}
    )

    result = judge_seat_responses(
        seat=seat,
        case=case,
        prompt="real prompt",
        responses={"candidate": "one"},
    )

    assert result["candidate"]["score"] == 4.0
    assert "invented fact" in captured["messages"][0]["content"]
    assert captured["timeout"] == 60


def test_seat_judge_rejects_omitted_or_binary_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "model_bench.judge.litellm.completion",
        lambda **_: _completion('{"judgments":[]}'),
    )
    seat = {"job": "Judge.", "output_contract": {"validation": "Valid."}}
    case = {"expected_output": {"label": "PASS"}}

    with pytest.raises(ValueError, match="omitted models"):
        judge_seat_responses(
            seat=seat,
            case=case,
            prompt="prompt",
            responses={"candidate": "answer"},
        )
    with pytest.raises(ValueError, match="binary artifacts"):
        judge_seat_responses(
            seat=seat,
            case=case,
            prompt="prompt",
            responses={"candidate": b"image"},
        )
