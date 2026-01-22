import time
import sys
import os
import asyncio

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from librarian_mcp.server import handle_call_tool

async def benchmark_cached_vs_computed():
    print("Starting benchmark...")
    
    # First run (cold)
    print("Running cold query...")
    start = time.time()
    # We call handle_call_tool directly to simulate an MCP tool call
    # This will trigger the L3 compute logic
    result1 = await handle_call_tool("ask_librarian", {"question": "How does the agent hub work?"})
    cold_time = time.time() - start
    
    # Second run (warm - should hit L1 cache)
    print("Running warm query (exact match)...")
    start = time.time()
    result2 = await handle_call_tool("ask_librarian", {"question": "How does the agent hub work?"})
    warm_time = time.time() - start
    
    print(f"\nResults:")
    print(f"Cold query: {cold_time:.3f}s")
    print(f"Warm query: {warm_time:.3f}s")
    if warm_time > 0:
        print(f"Speedup: {cold_time / warm_time:.1f}x")
    else:
        print("Warm query was too fast to measure speedup accurately.")
    
    # Test similar query (should hit L2 semantic cache)
    print("\nRunning similar query...")
    start = time.time()
    result3 = await handle_call_tool("ask_librarian", {"question": "Explain agent hub functionality"})
    similar_time = time.time() - start
    print(f"Similar query: {similar_time:.3f}s")
    if similar_time > 0:
        print(f"Similar query speedup: {cold_time / similar_time:.1f}x")

if __name__ == "__main__":
    asyncio.run(benchmark_cached_vs_computed())
