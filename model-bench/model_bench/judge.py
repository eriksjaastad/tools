"""Sends model responses to the configured judge for rubric-based scoring."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import litellm

from .registry import JUDGE_MODEL


@dataclass
class JudgeScore:
    """Score for one model's response to one task variant."""

    model_id: str
    task_id: str
    variant_id: str
    category: str
    scores: dict[str, int]  # rubric_name → 1-5 score
    overall: float  # weighted average
    reasoning: str


def judge_responses(
    task_id: str,
    variant_id: str,
    category: str,
    prompt: str,
    rubric: list[dict],
    max_score: int,
    responses: dict[str, str],  # model_id → response text
) -> list[JudgeScore]:
    """Score all model responses for one task+variant using the configured judge.

    Sends a single batch prompt to minimize judge calls.
    """
    if not responses:
        return []

    # Build rubric text
    rubric_text = "\n".join(
        f"- **{r['name']}** (weight {r['weight']}): {r['description']}" for r in rubric
    )

    # Build responses section
    responses_text = ""
    for model_id, response in responses.items():
        # Truncate very long responses to keep judge prompt reasonable
        truncated = response[:4000] + "..." if len(response) > 4000 else response
        responses_text += f"\n### Model: {model_id}\n```\n{truncated}\n```\n"

    rubric_format = "\n".join(f"{r['name']}: <score>" for r in rubric)
    judge_prompt = f"""You are a code/content quality judge. Score each model's response on a 1-5 scale for each rubric criterion.

## Task
The models were given this prompt:
```
{prompt}
```

## Rubric (score each 1-5)
{rubric_text}

## Model Responses
{responses_text}

## Instructions
For each model, provide scores for each rubric criterion (1-5 integer) and a brief reasoning.

Respond in this exact format for EACH model (one block per model):

MODEL: <model_id>
{rubric_format}
REASONING: <one sentence>

Be strict but fair. A 3 is "acceptable", 4 is "good", 5 is "excellent". Reserve 1 for broken/wrong, 2 for poor quality.
"""

    try:
        response = litellm.completion(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            timeout=60,
        )
        judge_text = response.choices[0].message.content or ""
    except Exception as e:  # noqa: BLE001 - provider failure becomes score evidence
        # Return zero scores on judge failure
        return [
            JudgeScore(
                model_id=mid,
                task_id=task_id,
                variant_id=variant_id,
                category=category,
                scores={r["name"]: 0 for r in rubric},
                overall=0.0,
                reasoning=f"Judge error: {e}",
            )
            for mid in responses
        ]

    return _parse_judge_output(
        judge_text, task_id, variant_id, category, rubric, responses.keys()
    )


def _parse_judge_output(
    text: str,
    task_id: str,
    variant_id: str,
    category: str,
    rubric: list[dict],
    model_ids: list[str] | set[str],
) -> list[JudgeScore]:
    """Parse structured judge output into JudgeScores."""
    results = []
    blocks = text.split("MODEL:")

    for block in blocks[1:]:  # Skip text before first MODEL:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if not lines:
            continue

        raw_model_id = lines[0].strip()
        # Match parsed model ID against known IDs (fuzzy — judge may reformat)
        model_id = _match_model_id(raw_model_id, model_ids)
        scores: dict[str, int] = {}
        reasoning = ""

        for line in lines[1:]:
            if line.startswith("REASONING:"):
                reasoning = line.removeprefix("REASONING:").strip()
                continue

            for r in rubric:
                if line.lower().startswith(r["name"].lower() + ":"):
                    try:
                        val = int(line.split(":")[1].strip().split()[0])
                        scores[r["name"]] = max(1, min(5, val))
                    except (ValueError, IndexError):
                        scores[r["name"]] = 0

        # Calculate weighted average
        total_weight = sum(r["weight"] for r in rubric)
        if total_weight > 0 and scores:
            weighted_sum = sum(scores.get(r["name"], 0) * r["weight"] for r in rubric)
            overall = weighted_sum / total_weight
        else:
            overall = 0.0

        results.append(
            JudgeScore(
                model_id=model_id,
                task_id=task_id,
                variant_id=variant_id,
                category=category,
                scores=scores,
                overall=overall,
                reasoning=reasoning,
            )
        )

    # Fill in any models that weren't parsed
    parsed_ids = {r.model_id for r in results}
    for mid in model_ids:
        if mid not in parsed_ids:
            results.append(
                JudgeScore(
                    model_id=mid,
                    task_id=task_id,
                    variant_id=variant_id,
                    category=category,
                    scores={r["name"]: 0 for r in rubric},
                    overall=0.0,
                    reasoning="Not found in judge output",
                )
            )

    return results


def _match_model_id(raw: str, known_ids: list[str] | set[str]) -> str:
    """Match a parsed model ID from judge output against known model IDs.

    Handles cases where the judge reformats the ID (e.g. adds backticks,
    changes separators, or uses a display name).
    """
    # Exact match
    if raw in known_ids:
        return raw

    # Strip common formatting artifacts
    cleaned = raw.strip("`\"' ")
    if cleaned in known_ids:
        return cleaned

    # Substring match — if the parsed ID contains or is contained by a known ID
    for kid in known_ids:
        if kid in cleaned or cleaned in kid:
            return kid

    # Lowercase comparison
    for kid in known_ids:
        if kid.lower() == cleaned.lower():
            return kid

    # Give up — return raw (will end up in "not found" bucket)
    return raw


def judge_seat_responses(
    *,
    seat: Mapping[str, Any] | object,
    case: Mapping[str, Any] | object,
    prompt: str,
    responses: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Judge valid seat artifacts against the project-owned expected output."""
    if not responses:
        return {}
    if any(
        not isinstance(response, (str, Mapping, list))
        for response in responses.values()
    ):
        raise ValueError(
            "binary artifacts require a project-declared vision review gate"
        )

    raw_seat = _raw_mapping(seat)
    expected = _value(case, "expected_output")
    response_payload = [
        {
            "model_id": model_id,
            "artifact": response,
        }
        for model_id, response in responses.items()
    ]
    judge_prompt = f"""You are evaluating candidate models for one real project-owned model seat.

Score each already machine-valid artifact from 0 to 5:
- 5: fully satisfies the expected-output rubric/gold and the seat's job
- 4: correct with a minor omission
- 3: acceptable but materially incomplete
- 2: major errors
- 1: mostly wrong
- 0: unusable

Do not reward prose style over correctness. Treat the expected output as a
rubric when it describes required/prohibited qualities rather than one exact
wording.

SEAT JOB:
{raw_seat["job"]}

OUTPUT VALIDATION:
{raw_seat["output_contract"]["validation"]}

MODEL PROMPT:
{prompt}

EXPECTED OUTPUT / RUBRIC:
{json.dumps(expected, ensure_ascii=False, default=str)}

VALID ARTIFACTS:
{json.dumps(response_payload, ensure_ascii=False, default=str)}

Return JSON only:
{{"judgments":[{{"model_id":"exact id","score":0,"reasoning":"one concise sentence"}}]}}
"""
    response = litellm.completion(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": judge_prompt}],
        timeout=60,
        max_tokens=1000,
        reasoning_effort="low",
    )
    content = response.choices[0].message.content or ""
    parsed = _parse_json_object(content)
    judgments = parsed.get("judgments")
    if not isinstance(judgments, list):
        raise TypeError("seat judge response has no judgments list")

    result: dict[str, dict[str, Any]] = {}
    for item in judgments:
        if not isinstance(item, Mapping):
            continue
        model_id = item.get("model_id")
        score = item.get("score")
        if (
            model_id not in responses
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
        ):
            continue
        result[str(model_id)] = {
            "score": max(0.0, min(5.0, float(score))),
            "reasoning": str(item.get("reasoning", "")),
        }
    missing = set(responses) - set(result)
    if missing:
        raise ValueError(f"seat judge omitted models: {sorted(missing)}")
    return result


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"seat judge returned invalid JSON: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise TypeError("seat judge response must be a JSON object")
    return parsed


def _raw_mapping(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raw = getattr(value, "raw", None)
    if isinstance(raw, Mapping):
        return raw
    raise TypeError("seat must be a mapping or expose a raw mapping")


def _value(value: Mapping[str, Any] | object, name: str) -> Any:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)
