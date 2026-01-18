"""
Performance Benchmarks for UAS.

Measures:
- Time to First Token (TTFT) for model calls
- Message bus latency
- Concurrent message handling
- Memory usage
"""

import os
import time
import statistics
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Callable
import tracemalloc

# Targets from PRD
TTFT_TARGET_MS = 500
MESSAGE_LATENCY_TARGET_MS = 100


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    samples: int
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    std_dev_ms: float
    target_ms: float | None
    passed: bool | None

    def __str__(self) -> str:
        status = ""
        if self.target_ms:
            status = " PASS" if self.passed else " FAIL"
        return (
            f"{self.name}:{status}\n"
            f"  Samples: {self.samples}\n"
            f"  Mean: {self.mean_ms:.2f}ms\n"
            f"  Median: {self.median_ms:.2f}ms\n"
            f"  Min: {self.min_ms:.2f}ms\n"
            f"  Max: {self.max_ms:.2f}ms\n"
            f"  StdDev: {self.std_dev_ms:.2f}ms"
            + (f"\n  Target: <{self.target_ms}ms" if self.target_ms else "")
        )


def run_benchmark(
    name: str,
    func: Callable,
    samples: int = 10,
    warmup: int = 2,
    target_ms: float | None = None,
) -> BenchmarkResult:
    """
    Run a benchmark and collect timing statistics.

    Args:
        name: Benchmark name
        func: Function to benchmark (should return quickly)
        samples: Number of samples to collect
        warmup: Warmup iterations (not counted)
        target_ms: Target latency in milliseconds

    Returns:
        BenchmarkResult with statistics
    """
    # Warmup
    for _ in range(warmup):
        func()

    # Collect samples
    timings_ms = []
    for _ in range(samples):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        timings_ms.append((end - start) * 1000)

    mean = statistics.mean(timings_ms)
    passed = mean < target_ms if target_ms else None

    return BenchmarkResult(
        name=name,
        samples=samples,
        mean_ms=mean,
        median_ms=statistics.median(timings_ms),
        min_ms=min(timings_ms),
        max_ms=max(timings_ms),
        std_dev_ms=statistics.stdev(timings_ms) if len(timings_ms) > 1 else 0,
        target_ms=target_ms,
        passed=passed,
    )


def benchmark_message_bus(db_path: Path, samples: int = 100) -> BenchmarkResult:
    """Benchmark message bus write/read latency."""
    from src.message_bus import MessageBus

    bus = MessageBus(db_path)

    def send_receive():
        msg_id = bus.ask_parent("bench-run", "bench-worker", "test?")
        bus.reply_to_worker(msg_id, "answer")
        bus.check_answer(msg_id)

    return run_benchmark(
        name="Message Bus Round-Trip",
        func=send_receive,
        samples=samples,
        target_ms=MESSAGE_LATENCY_TARGET_MS,
    )


def benchmark_concurrent_messages(
    db_path: Path,
    num_workers: int = 10,
    messages_per_worker: int = 10
) -> dict:
    """Benchmark concurrent message handling."""
    from src.message_bus import MessageBus

    bus = MessageBus(db_path)
    results = {"total_messages": 0, "errors": 0, "total_time_ms": 0}
    lock = threading.Lock()

    def worker_task(worker_id: int):
        nonlocal results
        for i in range(messages_per_worker):
            try:
                start = time.perf_counter()
                msg_id = bus.ask_parent("concurrent-run", f"worker-{worker_id}", f"msg-{i}")
                bus.reply_to_worker(msg_id, f"answer-{i}")
                bus.check_answer(msg_id)
                end = time.perf_counter()

                with lock:
                    results["total_messages"] += 1
                    results["total_time_ms"] += (end - start) * 1000
            except Exception:
                with lock:
                    results["errors"] += 1

    # Run concurrent workers
    threads = []
    overall_start = time.perf_counter()

    for i in range(num_workers):
        t = threading.Thread(target=worker_task, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    overall_end = time.perf_counter()

    results["overall_time_ms"] = (overall_end - overall_start) * 1000
    results["avg_latency_ms"] = results["total_time_ms"] / max(results["total_messages"], 1)
    results["throughput_per_sec"] = results["total_messages"] / max((overall_end - overall_start), 0.001)

    return results


def benchmark_memory_usage(func: Callable, iterations: int = 100) -> dict:
    """Measure memory usage during repeated operations."""
    tracemalloc.start()

    for _ in range(iterations):
        func()

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024,
        "iterations": iterations,
    }


def benchmark_budget_checks(samples: int = 1000) -> BenchmarkResult:
    """Benchmark budget check performance."""
    from src.budget_manager import BudgetManager
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        budget = BudgetManager(budget_path=Path(tmp) / "budget.json")

        def check():
            budget.can_afford("cloud-fast", 1000, 500)

        return run_benchmark(
            name="Budget Check",
            func=check,
            samples=samples,
            target_ms=1.0,  # Should be < 1ms
        )


def benchmark_circuit_breaker(samples: int = 1000) -> BenchmarkResult:
    """Benchmark circuit breaker check performance."""
    from src.circuit_breakers import CircuitBreaker
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cb = CircuitBreaker(state_path=Path(tmp) / "cb.json")

        def check():
            cb.should_halt()
            cb.get_status()

        return run_benchmark(
            name="Circuit Breaker Check",
            func=check,
            samples=samples,
            target_ms=1.0,
        )


def run_all_benchmarks(output_path: Path | None = None) -> list[BenchmarkResult]:
    """Run all benchmarks and optionally save results."""
    import tempfile
    import json

    results = []

    print("=" * 60)
    print("UAS Performance Benchmarks")
    print("=" * 60)

    # Message Bus
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "bench.db"

        print("\n[1/5] Message Bus Round-Trip...")
        result = benchmark_message_bus(db_path)
        results.append(result)
        print(result)

        print("\n[2/5] Concurrent Messages (10 workers x 10 messages)...")
        concurrent = benchmark_concurrent_messages(db_path)
        print(f"  Total: {concurrent['total_messages']} messages")
        print(f"  Errors: {concurrent['errors']}")
        print(f"  Avg Latency: {concurrent['avg_latency_ms']:.2f}ms")
        print(f"  Throughput: {concurrent['throughput_per_sec']:.1f} msg/sec")

    # Budget Checks
    print("\n[3/5] Budget Check Performance...")
    result = benchmark_budget_checks()
    results.append(result)
    print(result)

    # Circuit Breaker
    print("\n[4/5] Circuit Breaker Check Performance...")
    result = benchmark_circuit_breaker()
    results.append(result)
    print(result)

    # Memory Usage
    print("\n[5/5] Memory Usage (Message Bus, 100 iterations)...")
    with tempfile.TemporaryDirectory() as tmp:
        from src.message_bus import MessageBus
        db_path = Path(tmp) / "mem.db"
        bus = MessageBus(db_path)

        def mem_test():
            msg_id = bus.ask_parent("mem-run", "worker", "test")
            bus.reply_to_worker(msg_id, "answer")

        mem = benchmark_memory_usage(mem_test)
        print(f"  Current: {mem['current_mb']:.2f} MB")
        print(f"  Peak: {mem['peak_mb']:.2f} MB")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed is True)
    failed = sum(1 for r in results if r.passed is False)
    print(f"Passed: {passed}, Failed: {failed}")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            json.dump([{
                "name": r.name,
                "mean_ms": r.mean_ms,
                "target_ms": r.target_ms,
                "passed": r.passed,
            } for r in results], f, indent=2)
        print(f"\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    run_all_benchmarks()
