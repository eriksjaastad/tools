"""Timing utilities for latency measurement."""

import time
from contextlib import contextmanager
from typing import Generator

@contextmanager
def measure_latency() -> Generator[dict, None, None]:
    """
    Context manager to measure latency in milliseconds.

    Usage:
        with measure_latency() as timing:
            result = do_something()
        print(f"Took {timing['latency_ms']}ms")
    """
    result = {"latency_ms": 0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        end = time.perf_counter()
        result["latency_ms"] = int((end - start) * 1000)
