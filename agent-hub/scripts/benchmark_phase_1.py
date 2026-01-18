import os
import time
from src import ollama_http_client
from src.utils import timing
from src.utils import feature_flags

# Force HTTP path
os.environ["UAS_OLLAMA_HTTP"] = "1"

print(f"UAS_OLLAMA_HTTP enabled: {feature_flags.use_ollama_http()}")

def benchmark():
    # Warm up
    ollama_http_client.chat("llama3.2:3b", [{"role": "user", "content": "hi"}])
    
    print("\nStarting benchmark...")
    with timing.measure_latency() as t:
        ollama_http_client.chat("llama3.2:3b", [{"role": "user", "content": "Tell me a short joke."}])
    print(f"Total Response Time (warm): {t['latency_ms']}ms")

if __name__ == "__main__":
    try:
        benchmark()
    except Exception as e:
        print(f"Benchmark failed: {e}")
