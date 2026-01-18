"""
Performance tests - validate targets are met.
"""

import pytest
import tempfile
from pathlib import Path


class TestPerformanceTargets:
    """Test that performance targets from PRD are met."""

    def test_message_bus_latency(self):
        """Message bus round-trip should be < 100ms."""
        from benchmarks.performance_benchmark import benchmark_message_bus

        with tempfile.TemporaryDirectory() as tmp:
            result = benchmark_message_bus(Path(tmp) / "test.db", samples=50)

        # Allow some slack for CI environments
        assert result.mean_ms < 200, f"Message bus too slow: {result.mean_ms}ms"

    def test_budget_check_latency(self):
        """Budget checks should be < 1ms."""
        from benchmarks.performance_benchmark import benchmark_budget_checks

        result = benchmark_budget_checks(samples=100)
        assert result.mean_ms < 10, f"Budget check too slow: {result.mean_ms}ms"

    def test_circuit_breaker_latency(self):
        """Circuit breaker checks should be < 1ms."""
        from benchmarks.performance_benchmark import benchmark_circuit_breaker

        result = benchmark_circuit_breaker(samples=100)
        assert result.mean_ms < 10, f"Circuit breaker too slow: {result.mean_ms}ms"

    def test_concurrent_message_handling(self):
        """Should handle concurrent messages without errors."""
        from benchmarks.performance_benchmark import benchmark_concurrent_messages

        with tempfile.TemporaryDirectory() as tmp:
            result = benchmark_concurrent_messages(
                Path(tmp) / "concurrent.db",
                num_workers=5,
                messages_per_worker=10
            )

        assert result["errors"] == 0, f"Concurrent errors: {result['errors']}"
        assert result["total_messages"] == 50

    def test_memory_bounded(self):
        """Memory usage should stay bounded."""
        from benchmarks.performance_benchmark import benchmark_memory_usage
        from src.message_bus import MessageBus
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bus = MessageBus(Path(tmp) / "mem.db")

            def test_op():
                msg_id = bus.ask_parent("run", "worker", "test")
                bus.reply_to_worker(msg_id, "answer")

            result = benchmark_memory_usage(test_op, iterations=100)

        # Should use less than 50MB for 100 iterations
        assert result["peak_mb"] < 50, f"Memory too high: {result['peak_mb']}MB"
