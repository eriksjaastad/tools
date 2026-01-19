"""
Model Shootout - Benchmark local models for Floor Manager capability.

Usage:
    python -m benchmarks.model_shootout --models llama3.2:1b,qwen2.5-coder:14b
"""

import argparse
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Any

# Import our HTTP client
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.ollama_http_client import chat, list_models

@dataclass
class BenchmarkResult:
    model: str
    task: str
    success: bool
    latency_ms: int
    tokens_in: int
    tokens_out: int
    error: str | None = None

# Test cases for Floor Manager capabilities
FLOOR_MANAGER_TESTS = [
    {
        "name": "task_parsing",
        "prompt": """Parse this task specification and extract the key fields as JSON:

Task: Implement user authentication
Project: web-app
Priority: high
Requirements:
- Add login endpoint
- Add logout endpoint
- Use JWT tokens

Output only valid JSON with fields: task, project, priority, requirements (array)""",
        "validator": lambda r: "task" in r.lower() and "requirements" in r.lower() and "[" in r,
    },
    {
        "name": "routing_decision",
        "prompt": """You are a Floor Manager. Given this task, decide which worker should handle it.

Available workers:
- implementer (qwen2.5-coder:14b): Code generation
- reviewer (deepseek-r1:7b): Code review
- triage (llama3.2:1b): Simple classification

Task: "Write a Python function to calculate fibonacci numbers"

Respond with ONLY the worker name, nothing else.""",
        "validator": lambda r: "implementer" in r.lower(),
    },
    {
        "name": "judgment_call",
        "prompt": """Review these two code review verdicts and make a final decision:

Reviewer 1: PASS - Code looks good, follows conventions
Reviewer 2: FAIL - Missing error handling for edge case

Should this code be approved? Respond with only PASS or FAIL and a one-sentence reason.""",
        "validator": lambda r: "pass" in r.lower() or "fail" in r.lower(),
    },
    {
        "name": "synthesis",
        "prompt": """Summarize these worker outputs into a single status update:

Worker 1 (implementer): Completed auth.py with login/logout endpoints
Worker 2 (reviewer): Found 2 minor style issues, no security concerns
Worker 3 (tester): All 5 tests passing

Provide a 2-sentence summary suitable for a progress report.""",
        "validator": lambda r: len(r) > 50 and len(r) < 500,
    },
]

def run_benchmark(model: str, test: dict) -> BenchmarkResult:
    """Run a single benchmark test."""
    start = time.perf_counter()
    try:
        response = chat(
            model=model,
            messages=[{"role": "user", "content": test["prompt"]}],
            stream=False
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = response.get("message", {}).get("content", "")
        success = test["validator"](content)

        return BenchmarkResult(
            model=model,
            task=test["name"],
            success=success,
            latency_ms=latency_ms,
            tokens_in=response.get("prompt_eval_count", 0),
            tokens_out=response.get("eval_count", 0),
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return BenchmarkResult(
            model=model,
            task=test["name"],
            success=False,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            error=str(e),
        )

def run_shootout(models: list[str]) -> list[BenchmarkResult]:
    """Run all benchmarks for all models."""
    results = []
    for model in models:
        print(f"\n=== Testing {model} ===")
        for test in FLOOR_MANAGER_TESTS:
            print(f"  {test['name']}...", end=" ", flush=True)
            result = run_benchmark(model, test)
            print("✓" if result.success else "✗", f"({result.latency_ms}ms)")
            results.append(result)
    return results

def generate_report(results: list[BenchmarkResult]) -> dict:
    """Generate summary report."""
    by_model = {}
    for r in results:
        if r.model not in by_model:
            by_model[r.model] = {"passed": 0, "failed": 0, "total_latency": 0, "tests": []}
        by_model[r.model]["tests"].append(asdict(r))
        by_model[r.model]["total_latency"] += r.latency_ms
        if r.success:
            by_model[r.model]["passed"] += 1
        else:
            by_model[r.model]["failed"] += 1

    # Calculate scores
    for model, data in by_model.items():
        total = data["passed"] + data["failed"]
        data["success_rate"] = data["passed"] / total if total > 0 else 0
        data["avg_latency_ms"] = data["total_latency"] / total if total > 0 else 0

    return by_model

def main():
    parser = argparse.ArgumentParser(description="Model Shootout Benchmark")
    parser.add_argument("--models", default="llama3.2:1b,qwen2.5-coder:14b,deepseek-r1-distill-qwen:32b",
                        help="Comma-separated list of models to test")
    parser.add_argument("--output", default="benchmarks/shootout_results.json",
                        help="Output file for results")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",")]

    # Check which models are available
    try:
        available = {m["name"] for m in list_models()}
    except Exception as e:
        print(f"Error listing models from Ollama: {e}")
        return

    models = [m for m in models if m in available]

    if not models:
        print("No specified models are available in Ollama")
        return

    print(f"Testing models: {models}")
    results = run_shootout(models)
    report = generate_report(results)

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n=== RESULTS ===")
    for model, data in sorted(report.items(), key=lambda x: -x[1]["success_rate"]):
        print(f"{model}: {data['success_rate']*100:.0f}% success, {data['avg_latency_ms']:.0f}ms avg")

    # Recommendation
    if report:
        best = max(report.items(), key=lambda x: (x[1]["success_rate"], -x[1]["avg_latency_ms"]))
        print(f"\nRecommendation: {best[0]} (best success rate with acceptable latency)")

if __name__ == "__main__":
    main()
