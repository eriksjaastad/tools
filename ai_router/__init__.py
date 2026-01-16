"""
AI Router - Cost-optimized routing between local Ollama and cloud AI models

Automatically routes requests to:
- Local (free): llama3.2 via Ollama
- Cheap cloud: gpt-4o-mini
- Expensive cloud: gpt-4o

With automatic escalation on failures or poor responses.

Tool Support:
- ToolRouter: Agentic workflows with Claude tool use
- Tool: Decorator and class for defining tools
"""

from .router import AIRouter, AIResult, Tier, AIRouterError, AIModelError

# Tool support (optional - requires anthropic package)
try:
    from .tools import ToolRouter, Tool, ToolResult, AgentResult, tool, create_tool
    _TOOLS_AVAILABLE = True
except ImportError:
    _TOOLS_AVAILABLE = False
    ToolRouter = None  # type: ignore
    Tool = None  # type: ignore
    ToolResult = None  # type: ignore
    AgentResult = None  # type: ignore
    tool = None  # type: ignore
    create_tool = None  # type: ignore

__all__ = [
    # Core routing
    "AIRouter", "AIResult", "Tier", "AIRouterError", "AIModelError",
    # Tool support (may be None if anthropic not installed)
    "ToolRouter", "Tool", "ToolResult", "AgentResult", "tool", "create_tool",
    "_TOOLS_AVAILABLE",
]
__version__ = "1.1.0"  # Bumped for tool support
