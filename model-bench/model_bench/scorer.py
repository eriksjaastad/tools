"""Aggregates scores into comparison matrix. Pure math, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from .judge import JudgeScore
from .caller import CallResult
from .registry import ModelEntry, estimate_cost


@dataclass
class CategoryScore:
    """Aggregated score for one model in one category."""

    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost_usd: float = 0.0
    num_tasks: int = 0
    errors: int = 0


@dataclass
class ModelSummary:
    """Overall summary for one model across all categories."""

    model_id: str
    display_name: str
    tier: str
    overall_score: float = 0.0
    overall_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    categories: dict[str, CategoryScore] = field(default_factory=dict)


@dataclass
class Matrix:
    """Full benchmark matrix."""

    models: dict[str, ModelSummary] = field(default_factory=dict)
    categories: list[str] = field(default_factory=list)


def build_matrix(
    judge_scores: list[JudgeScore],
    call_results: list[CallResult],
    models: list[ModelEntry],
    categories: list[str],
) -> Matrix:
    """Build the comparison matrix from raw results."""
    matrix = Matrix(categories=sorted(set(categories)))

    # Initialize model summaries
    model_map = {m.id: m for m in models}
    for m in models:
        matrix.models[m.id] = ModelSummary(
            model_id=m.id,
            display_name=m.display_name,
            tier=m.tier,
        )

    # Index call results by (model_id, task_id, variant_id)
    call_index: dict[tuple[str, str, str], CallResult] = {}
    for cr in call_results:
        # Extract task_id and variant_id from the key set during runner
        key = getattr(cr, "_key", None)
        if key:
            call_index[key] = cr

    # Group judge scores by category
    # task_id format: "{category_prefix}_{number}" e.g. "code_gen_001"
    # We'll need the category passed in alongside scores
    score_by_model_cat: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    latency_by_model_cat: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    cost_by_model_cat: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    errors_by_model_cat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for js in judge_scores:
        score_by_model_cat[js.model_id][js.category].append(js.overall)

    for cr in call_results:
        key = getattr(cr, "_key", None)
        if not key:
            continue
        model_id, task_id, variant_id, cat = key

        latency_by_model_cat[model_id][cat].append(float(cr.latency_ms))

        model_entry = model_map.get(model_id)
        if model_entry:
            cost = estimate_cost(model_entry, cr.tokens_in, cr.tokens_out)
            cost_by_model_cat[model_id][cat].append(cost)

        if cr.error:
            errors_by_model_cat[model_id][cat] += 1

    # Aggregate into matrix
    for model_id, summary in matrix.models.items():
        all_scores = []
        all_latencies = []
        total_cost = 0.0

        for cat in matrix.categories:
            scores = score_by_model_cat[model_id].get(cat, [])
            latencies = latency_by_model_cat[model_id].get(cat, [])
            costs = cost_by_model_cat[model_id].get(cat, [])
            errs = errors_by_model_cat[model_id].get(cat, 0)

            cat_score = CategoryScore(
                avg_score=_avg(scores),
                avg_latency_ms=_avg(latencies),
                avg_cost_usd=sum(costs),
                num_tasks=len(scores),
                errors=errs,
            )
            summary.categories[cat] = cat_score

            all_scores.extend(scores)
            all_latencies.extend(latencies)
            total_cost += sum(costs)

        summary.overall_score = _avg(all_scores)
        summary.overall_latency_ms = _avg(all_latencies)
        summary.total_cost_usd = total_cost

    return matrix


def _avg(values: list[float]) -> float:
    """Safe average."""
    return sum(values) / len(values) if values else 0.0


