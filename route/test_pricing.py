from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model-bench"))
sys.path.insert(0, str(ROOT / "route"))

from model_bench.registry import MODELS
from pricing import get_model_pricing, load_registry


def test_cloud_benchmark_models_have_route_pricing():
    load_registry(ROOT / "route" / "model_registry.json")

    missing = [
        model.id
        for model in MODELS
        if model.provider != "ollama" and get_model_pricing(model.id) is None
    ]

    assert missing == []
