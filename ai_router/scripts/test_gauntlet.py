import sys
import os
from pprint import pprint

from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter

def test_routing_gauntlet():
    router = AIRouter()
    
    tasks = [
        {
            "name": "Local Tier (Simple Classification)",
            "messages": [{"role": "user", "content": "Classify this as SPAM or HAM: 'Get a free prize now!'"}]
        },
        {
            "name": "Cheap Tier (Informational Question)",
            "messages": [{"role": "user", "content": "Can you explain the difference between a local model and a cloud model in three sentences?"}]
        },
        {
            "name": "Expensive Tier (Code/Architecture)",
            "messages": [{"role": "user", "content": "Write a Python function that uses the AIRouter to optimize its own cost by switching models dynamically."}]
        }
    ]
    
    print("🚀 Starting AI Router Gauntlet...\n")
    
    for task in tasks:
        print(f"--- Testing: {task['name']} ---")
        result = router.chat(task['messages'])
        
        print(f"📍 Route: {result.tier.upper()} ({result.provider} / {result.model})")
        print(f"⏱️ Time: {result.duration_ms}ms")
        
        if result.error:
            print(f"❌ Error: {result.error}")
        else:
            # Show a snippet of the response
            snippet = result.text.strip().split('\n')[0]
            if len(result.text) > 100:
                snippet = snippet[:100] + "..."
            print(f"📝 Response: {snippet}")
        
        print("\n")

if __name__ == "__main__":
    test_routing_gauntlet()

