"""
Quick test to verify AI Router setup
"""

import sys
import os

from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from router import AIRouter, AIResult
    print("✅ Import successful!")
    print(f"   AIRouter: {AIRouter}")
    print(f"   AIResult: {AIResult}")
    
    # Try to initialize (won't call any APIs, but needs dummy key)
    os.environ.setdefault("OPENAI_API_KEY", "dummy-key-for-testing")
    router = AIRouter()
    print("✅ Initialization successful!")
    print(f"   Local model: {router.local_model}")
    print(f"   Cheap model: {router.cheap_model}")
    print(f"   Expensive model: {router.expensive_model}")
    
    # Test routing logic
    test_messages = [
        {"role": "user", "content": "Hi"},
        {"role": "user", "content": "Design a microservices architecture with kubernetes"},
    ]
    
    print("\n✅ Routing logic test:")
    for msgs in test_messages:
        tier = router.route([msgs])
        content = msgs["content"][:50]
        print(f"   '{content}...' → {tier}")
    
    print("\n🎉 All tests passed! AI Router is ready to use.")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure you're in the projects directory")
    print("2. Or add to PYTHONPATH:")
    print("   export PYTHONPATH='[USER_HOME]/projects:$PYTHONPATH'")
    sys.exit(1)
except Exception as e:
    print(f"❌ Test failed: {e}")
    sys.exit(1)

