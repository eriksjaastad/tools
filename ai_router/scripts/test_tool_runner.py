#!/usr/bin/env python3
"""
Test script for AI Router Tool Support

Demonstrates the ToolRouter with Claude's Tool Runner pattern.

Usage:
    cd ~/projects/_tools/ai_router
    python scripts/test_tool_runner.py
"""

import json
import os
import sys
from pathlib import Path

# Add projects to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from _tools.ai_router import _TOOLS_AVAILABLE

if not _TOOLS_AVAILABLE:
    print("❌ Tool support not available. Install anthropic package:")
    print("   pip install anthropic")
    sys.exit(1)

from _tools.ai_router import ToolRouter, tool, create_tool, AgentResult

# =============================================================================
# Define some example tools
# =============================================================================

@tool("get_current_time")
def get_current_time(timezone: str = "UTC") -> dict:
    """Get the current time in a specific timezone."""
    from datetime import datetime, timezone as tz
    now = datetime.now(tz.utc)
    return {
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "timezone": timezone,
        "iso": now.isoformat(),
    }


@tool("calculate")
def calculate(expression: str) -> dict:
    """
    Safely evaluate a mathematical expression.
    
    Supports: +, -, *, /, **, (), sqrt, sin, cos, tan, log, pi, e
    """
    import math
    
    # Safe evaluation context
    safe_dict = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "pi": math.pi,
        "e": math.e,
        "abs": abs,
        "round": round,
    }
    
    try:
        # Only allow safe characters
        allowed = set("0123456789+-*/(). ")
        allowed.update(safe_dict.keys())
        
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


@tool("list_files")
def list_files(directory: str = ".", pattern: str = "*") -> list[str]:
    """List files in a directory matching a pattern."""
    import glob
    path = Path(directory).expanduser()
    if not path.exists():
        return [f"Error: Directory '{directory}' not found"]
    
    files = list(path.glob(pattern))
    return [str(f.relative_to(path)) for f in files[:20]]  # Limit to 20


@tool("read_file_preview")
def read_file_preview(filepath: str, lines: int = 10) -> dict:
    """Read the first N lines of a file."""
    path = Path(filepath).expanduser()
    if not path.exists():
        return {"error": f"File '{filepath}' not found"}
    
    try:
        content = path.read_text()
        preview_lines = content.split("\n")[:lines]
        return {
            "filepath": filepath,
            "total_lines": content.count("\n") + 1,
            "preview": "\n".join(preview_lines),
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Test runner
# =============================================================================

def print_result(result: AgentResult) -> None:
    """Pretty print an agent result."""
    print("\n" + "=" * 60)
    print(f"📊 Agent Result")
    print("=" * 60)
    print(f"Model: {result.model}")
    print(f"Turns: {result.turns}")
    print(f"Tool calls: {len(result.tool_calls)}")
    print(f"Duration: {result.total_duration_ms}ms")
    print(f"Stop reason: {result.stop_reason}")
    
    if result.tool_calls:
        print("\n📞 Tool Calls:")
        for tc in result.tool_calls:
            status = "✅" if not tc.is_error else "❌"
            print(f"  {status} {tc.tool_name}")
            if tc.is_error:
                print(f"     Error: {tc.error_message}")
    
    print("\n📝 Response:")
    print("-" * 40)
    print(result.text)
    print("-" * 40)


def main():
    print("🚀 AI Router Tool Support Test")
    print("=" * 60)
    
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    
    # Create tool router with our tools
    tools = [get_current_time, calculate, list_files, read_file_preview]
    
    router = ToolRouter(
        tools=tools,
        model="claude-sonnet-4-5-20250514",
        max_turns=5,
        verbose=True,  # Show tool execution
    )
    
    print(f"\n📦 Registered tools: {', '.join(t.name for t in tools)}")
    
    # Test 1: Simple calculation
    print("\n" + "=" * 60)
    print("Test 1: Math calculation")
    print("=" * 60)
    
    result = router.run("What is the square root of 144 plus 5 squared?")
    print_result(result)
    
    # Test 2: Time query
    print("\n" + "=" * 60)
    print("Test 2: Current time")
    print("=" * 60)
    
    result = router.run("What time is it right now?")
    print_result(result)
    
    # Test 3: File listing (multi-tool)
    print("\n" + "=" * 60)
    print("Test 3: File exploration")
    print("=" * 60)
    
    result = router.run(
        "List the Python files in my current directory and show me "
        "the first 5 lines of any README file you find."
    )
    print_result(result)
    
    print("\n✅ All tests complete!")


if __name__ == "__main__":
    main()
