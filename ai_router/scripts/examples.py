"""
Basic usage examples for AI Router
"""

import sys
from pathlib import Path

# Add project root to path for local imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from router import AIRouter


def example_basic():
    """Basic auto-routing example"""
    print("=== Basic Auto-routing ===\n")
    
    router = AIRouter()
    
    # Simple question → local
    result = router.chat([
        {"role": "user", "content": "What is 2+2?"}
    ])
    print(f"Q: What is 2+2?")
    print(f"A ({result.model}): {result.text}")
    print(f"Provider: {result.provider}, Duration: {result.duration_ms}ms\n")


def example_spam_filter():
    """Spam filtering example - perfect for local"""
    print("=== Spam Filter (Local) ===\n")
    
    router = AIRouter()
    
    messages = [
        "Buy now! Limited time offer!!!",
        "Meeting scheduled for tomorrow at 3pm",
        "CLICK HERE TO WIN $$$",
        "Your invoice is attached"
    ]
    
    for msg in messages:
        result = router.chat(
            [{"role": "user", "content": f"Is this spam? '{msg}'"}],
            tier="local",  # Force local for speed
            escalate=False  # Don't escalate, good enough
        )
        is_spam = "yes" in result.text.lower()
        print(f"'{msg[:40]}...' → {'SPAM' if is_spam else 'NOT SPAM'}")
    
    print()


def example_force_tiers():
    """Example forcing specific tiers"""
    print("=== Force Specific Tiers ===\n")
    
    router = AIRouter()
    
    prompt = "Explain quantum computing"
    
    # Try all three tiers
    for tier in ["local", "cheap", "expensive"]:
        result = router.chat(
            [{"role": "user", "content": prompt}],
            tier=tier,
            escalate=False
        )
        print(f"{tier.upper()} ({result.model}):")
        print(f"  {result.text[:100]}...")
        print(f"  Duration: {result.duration_ms}ms\n")


def example_escalation():
    """Example showing automatic escalation"""
    print("=== Automatic Escalation ===\n")
    
    router = AIRouter()
    
    # This might cause local to fail or give poor response
    result = router.chat([
        {"role": "user", "content": "Design a distributed system architecture"}
    ])
    
    print(f"Final model used: {result.model}")
    print(f"Provider: {result.provider}")
    print(f"Response: {result.text[:200]}...")
    print()


def example_error_handling():
    """Example handling errors"""
    print("=== Error Handling ===\n")
    
    # Try with bad endpoint to demonstrate error handling
    router = AIRouter(local_base_url="http://localhost:99999/v1")
    
    result = router.chat(
        [{"role": "user", "content": "Test"}],
        tier="local",
        escalate=True  # Will escalate to cloud on error
    )
    
    if result.error:
        print(f"Local failed: {result.error}")
        print(f"Escalated to: {result.model}")
    else:
        print(f"Success with: {result.model}")
    
    print()


if __name__ == "__main__":
    # Run examples
    example_basic()
    example_spam_filter()
    example_force_tiers()
    example_escalation()
    example_error_handling()
    
    print("✅ All examples complete!")

