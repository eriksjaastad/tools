import asyncio
import logging
import sys
import os
from librarian_mcp.server import handle_call_tool, memory_db, memory_store

# Setup minimal logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

async def run_smoke_test():
    print("--- Phase 2/3 Smoke Test: Adaptive Memory ---")
    
    question = "What is the capital of France?"
    
    # 1. Clean slate for specific test question
    query_text = question
    import hashlib
    q_hash = hashlib.sha256(query_text.lower().strip().encode()).hexdigest()
    memory_db.forget_query(q_hash)
    memory_store.delete_by_query(query_text)
    
    print("\n[Trial 1] First time asking (should compute/miss cache)")
    res1 = await handle_call_tool("ask_librarian", {"question": question})
    print(f"Result: {res1[0].text[:100]}...")
    stats = memory_db.get_query_stats(q_hash)
    print(f"Hit Count: {stats['ask_count']}, Tier: {stats['tier']}, Cached Answer: {bool(stats['answer'])}")
    
    print("\n[Trial 2] Second time asking (still should miss cache unless expensive/long)")
    res2 = await handle_call_tool("ask_librarian", {"question": question})
    stats = memory_db.get_query_stats(q_hash)
    print(f"Hit Count: {stats['ask_count']}, Tier: {stats['tier']}, Cached Answer: {bool(stats['answer'])}")
    
    print("\n[Trial 3] Third time asking (should trigger cache)")
    res3 = await handle_call_tool("ask_librarian", {"question": question})
    stats = memory_db.get_query_stats(q_hash)
    print(f"Hit Count: {stats['ask_count']}, Tier: {stats['tier']}, Cached Answer: {bool(stats['answer'])}")
    
    print("\n[Trial 4] Fourth time (should be L1 Exact HIT)")
    res4 = await handle_call_tool("ask_librarian", {"question": question})
    print(f"Source: {'L1 Hit' if stats['cache_hits'] > 0 else 'Computed'}")
    
    print("\n[Trial 5] Semantic variation (should be L2 Semantic HIT)")
    alt_question = "Tell me the capital of France"
    res5 = await handle_call_tool("ask_librarian", {"question": alt_question})
    print(f"Alt Question: {alt_question}")
    print(f"Result: {res5[0].text[:100]}...")
    
    print("\n[Stats] Memory Distribution:")
    stats_all = memory_db.get_all_stats()
    print(stats_all)

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
