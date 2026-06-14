# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.40"]
# ///
"""
Mercury Coder smoke test + throughput benchmark.

Runs against Inception's OpenAI-compatible API. Reports per-machine latency and
tokens/sec — the only thing that actually differs between the laptop and the Mini,
since Mercury is cloud-only.

Run:  doppler run -- uv run bench.py
Env:  any INCEPTIONLABS_*_API_KEY (injected by Doppler), MERCURY_MODEL (optional override)
"""
import os
import socket
import time

from openai import OpenAI

BASE_URL = "https://api.inceptionlabs.ai/v1"


def find_api_key() -> str | None:
    """Each machine has its own key (e.g. INCEPTIONLABS_LAPTOP_API_KEY,
    INCEPTIONLABS_MINI_API_KEY). Grab whichever one Doppler injected."""
    for name, value in os.environ.items():
        if name.startswith("INCEPTIONLABS_") and name.endswith("_API_KEY") and value:
            return value
    return os.environ.get("INCEPTION_API_KEY")
PROMPT = (
    "Write a Python function `merge_intervals(intervals)` that merges overlapping "
    "intervals given as a list of [start, end] pairs. Include a docstring and 3 "
    "assert-based tests. Return only the code."
)


def main() -> None:
    api_key = find_api_key()
    if not api_key:
        raise SystemExit("No INCEPTIONLABS_*_API_KEY set — run via `doppler run -- uv run bench.py`")

    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    host = socket.gethostname()

    # 1) Discover the exact model id rather than guessing.
    available = [m.id for m in client.models.list().data]
    print(f"[{host}] models available: {available}")
    model = os.environ.get("MERCURY_MODEL")
    if not model:
        model = next((m for m in available if "coder" in m.lower()), None) or (
            available[0] if available else "mercury-coder"
        )
    print(f"[{host}] using model: {model}\n")

    # 2) Timed completion.
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT}],
        max_tokens=1024,
        temperature=0.0,
    )
    elapsed = time.perf_counter() - t0

    out = resp.choices[0].message.content
    usage = resp.usage
    out_tokens = getattr(usage, "completion_tokens", 0)
    tps = out_tokens / elapsed if elapsed else 0.0

    print(f"[{host}] latency: {elapsed:.2f}s")
    print(f"[{host}] output tokens: {out_tokens}  ->  {tps:.0f} tok/s")
    print(f"[{host}] prompt tokens: {getattr(usage, 'prompt_tokens', 0)}")
    print("\n----- generated code -----\n")
    print(out)


if __name__ == "__main__":
    main()
