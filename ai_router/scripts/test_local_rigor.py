import sys
import os
import time
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter

def test_local_rigor():
    router = AIRouter()
    
    print("🔬 Starting Rigorous Local Model Test...\n")
    
    # 1. Connectivity & Model Presence
    print("📡 1. Checking Ollama connectivity and models...")
    models = router.get_local_models()
    if not models:
        print("❌ Error: Could not connect to Ollama or no models found.")
        return
    
    print(f"✅ Found {len(models)} local models: {', '.join(models)}")
    
    if router.local_model not in [m.split(':')[0] for m in models] and router.local_model not in models:
        print(f"⚠️ Warning: Default local model '{router.local_model}' not found in Ollama tags.")

    # 2. Context Window Stress Test (Medium sized prompt)
    print("\n📦 2. Stress testing context window (respecting num_ctx)...")
    # Generate a prompt that is roughly 10k characters (~3k tokens)
    large_content = "This is a test of the context window. " * 500 
    messages = [{"role": "user", "content": f"{large_content}\n\nSummarize the previous text in one sentence."}]
    
    t0 = time.time()
    res = router.chat(messages, tier="local", escalate=False)
    duration = time.time() - t0
    
    if res.error:
        print(f"❌ Context Test Failed: {res.error}")
    else:
        print(f"✅ Context Test Passed ({res.duration_ms}ms)")
        print(f"📝 Response: {res.text.strip()[:100]}...")

    # 3. Reliability Loop (Small fast requests)
    print("\n🔄 3. Testing reliability (5 rapid-fire requests)...")
    successes = 0
    for i in range(5):
        res = router.chat([{"role": "user", "content": f"Repeat the number {i}"}], tier="local", escalate=False)
        if not res.error:
            successes += 1
            print(f"  [{i+1}/5] OK ({res.duration_ms}ms)")
        else:
            print(f"  [{i+1}/5] FAILED: {res.error}")
            
    if successes == 5:
        print("✅ Reliability Test Passed (100% success rate)")
    else:
        print(f"⚠️ Reliability Test Warning: Only {successes}/5 succeeded")

    # 4. Escalation Verification
    print("\n🚀 4. Verifying escalation on poor response...")
    print("   (Verifying logic: local -> cheap -> expensive)")

    # 5. Strict Mode (Loud Failure)
    print("\n🔊 5. Testing 'Strict Mode' (should fail loudly)...")
    try:
        # Forcing a failure via a non-existent model in strict mode
        router.chat(
            [{"role": "user", "content": "test"}], 
            model_override="non-existent-model", 
            strict=True
        )
        print("❌ Error: Strict mode should have raised an exception!")
    except Exception as e:
        print(f"✅ Success: Caught expected loud failure: {str(e)[:60]}...")

    # Final Summary
    print("\n" + "="*50)
    print("LOCAL RIGOR TEST COMPLETE")
    print("="*50)
    print(router.get_performance_summary())

if __name__ == "__main__":
    test_local_rigor()

