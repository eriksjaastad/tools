import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from librarian_mcp.server import handle_call_tool, memory_db

async def test_eviction():
    print("Testing cache eviction...")
    
    # Check current size
    stats = memory_db.get_all_stats()
    print(f"Initial memories: {stats['total_memories']}")
    
    # Set a small MAX_CACHED for testing
    os.environ["LIBRARIAN_MAX_CACHED"] = "10"
    import librarian_mcp.memory_db
    librarian_mcp.memory_db.MAX_CACHED = 10
    
    print("Generating 15 memories...")
    for i in range(15):
        await handle_call_tool("librarian_remember", {
            "question": f"Eviction test query {i}",
            "answer": f"Answer {i}",
            "tier": "cold"
        })
    
    stats = memory_db.get_all_stats()
    print(f"Memories after adding 15: {stats['total_memories']}")
    
    # Trigger eviction manually if needed (it's called in ask_librarian)
    memory_db.evict_if_needed()
    
    # Check size again - it should be capped (MAX_CACHED - 100 + 100... wait, the logic is count - MAX_CACHED + 100)
    # Actually, in memory_db.py:
    # to_evict = count - MAX_CACHED + 100
    # If count is 15 and MAX_CACHED is 10, to_evict = 15 - 10 + 100 = 105? 
    # That would delete EVERYTHING.
    
    with memory_db._get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM query_memory WHERE answer IS NOT NULL").fetchone()[0]
        print(f"Cached answers count: {count}")

if __name__ == "__main__":
    asyncio.run(test_eviction())
