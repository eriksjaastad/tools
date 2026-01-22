import asyncio
import json
import os
import sys
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from librarian_mcp.server import handle_call_tool, memory_store, get_query_hash, memory_db

async def tune_threshold():
    test_queries = [
        {"query": "How does agent hub work?", "similar": ["Explain agent hub", "What is agent hub"]},
        {"query": "Where is authentication handled?", "similar": ["Auth logic location", "Find auth code"]},
        {"query": "MCP server setup", "similar": ["Configure MCP", "MCP installation"]}
    ]
    
    # Ensure queries are in cache first
    print("Seeding cache...")
    for item in test_queries:
        # Clear existing entries for these queries to ensure fresh seeding
        q_hash = get_query_hash(item["query"])
        memory_db.forget_query(q_hash)
        memory_store.delete_by_query(item["query"])
        
        # We need to force it to cache by making it "expensive" or "popular"
        # or just use librarian_remember
        await handle_call_tool("librarian_remember", {
            "question": item["query"], 
            "answer": f"Answer to {item['query']}",
            "tier": "hot"
        })
    
    thresholds = [0.15, 0.25, 0.35, 0.45]
    results = {}
    
    for threshold in thresholds:
        print(f"\nTesting threshold: {threshold}")
        hits = 0
        total = 0
        
        for item in test_queries:
            # Get base embedding
            from librarian_mcp.server import embedding_service
            base_emb = embedding_service.get_single_embedding(item["query"])
            
            for sim_query in item["similar"]:
                total += 1
                sim_hash = get_query_hash(sim_query)
                memory_db.forget_query(sim_hash)
                
                sim_emb = embedding_service.get_single_embedding(sim_query)
                
                # Compute actual distance for debugging
                import numpy as np
                a = np.array(base_emb)
                b = np.array(sim_emb)
                cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
                dist = 1.0 - cos_sim
                print(f"  DEBUG: '{sim_query}' vs '{item['query']}' distance: {dist:.4f}")
                
                match = memory_store.search_similar(sim_emb, threshold=threshold)
                
                if match and match["query"] == item["query"]:
                    print(f"  MATCH: '{sim_query}' -> '{item['query']}' (dist: {match['distance']:.3f})")
                    hits += 1
                elif match:
                    print(f"  MISMATCH: '{sim_query}' matched '{match['query']}' (dist: {match['distance']:.3f})")
                else:
                    print(f"  MISS: '{sim_query}'")
        
        results[threshold] = {"hit_rate": hits / total, "hits": hits, "total": total}
        print(f"Threshold {threshold} result: {hits}/{total} ({hits/total:.1%})")

    # Test for false positives (unrelated queries)
    unrelated = ["How do I cook pasta?", "What is the weather in Oslo?", "Who won the world cup?"]
    print("\nTesting false positives...")
    for threshold in thresholds:
        fp = 0
        for q in unrelated:
            from librarian_mcp.server import embedding_service
            emb = embedding_service.get_single_embedding(q)
            match = memory_store.search_similar(emb, threshold=threshold)
            if match:
                print(f"  FP (T={threshold}): '{q}' matched '{match['query']}' (dist: {match['distance']:.3f})")
                fp += 1
        print(f"Threshold {threshold} false positives: {fp}/{len(unrelated)}")

if __name__ == "__main__":
    asyncio.run(tune_threshold())
