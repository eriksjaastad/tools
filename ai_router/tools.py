"""
AI Router Tool Support - Claude Tool Runner Integration

Extends the AI Router with tool use capabilities using Claude's Tool Runner pattern.
This enables agentic workflows where Claude can execute tools and iterate.

Specification: https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use

Usage:
    from _tools.ai_router.tools import ToolRouter, Tool
    
    # Define tools
    @tool("get_weather")
    def get_weather(location: str, unit: str = "celsius") -> dict:
        '''Get current weather for a location.'''
        return {"temp": 22, "unit": unit, "location": location}
    
    # Create router with tools
    router = ToolRouter(tools=[get_weather])
    
    # Run agentic task
    result = router.run("What's the weather in San Francisco?")
"""

from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, get_type_hints

import anthropic

from .router import AIRouter, AIResult, TelemetryLogger

# ANSI colors for CLI output
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


@dataclass
class Tool:
    """
    A tool that Claude can call during agentic workflows.
    
    Follows Claude's tool specification:
    - name: Unique identifier (lowercase, hyphens, max 64 chars)
    - description: Detailed explanation of what the tool does
    - input_schema: JSON Schema for parameters
    - function: The actual Python function to execute
    - input_examples: Optional examples for complex tools (beta)
    """
    name: str
    description: str
    input_schema: dict[str, Any]
    function: Callable[..., Any]
    input_examples: list[dict[str, Any]] = field(default_factory=list)
    
    def to_api_format(self, include_examples: bool = False) -> dict[str, Any]:
        """Convert to Claude API tool format."""
        tool_def = {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
        if include_examples and self.input_examples:
            tool_def["input_examples"] = self.input_examples
        return tool_def
    
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given arguments."""
        return self.function(**kwargs)


def tool(
    name: str,
    description: str | None = None,
    examples: list[dict[str, Any]] | None = None,
) -> Callable[[Callable], Tool]:
    """
    Decorator to create a Tool from a function.
    
    Example:
        @tool("get_weather", description="Get weather for a location")
        def get_weather(location: str, unit: str = "celsius") -> dict:
            return {"temp": 22, "unit": unit}
    """
    def decorator(func: Callable) -> Tool:
        # Generate description from docstring if not provided
        tool_description = description or func.__doc__ or f"Execute {name}"
        
        # Build input schema from type hints
        hints = get_type_hints(func)
        sig = inspect.signature(func)
        
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
                
            # Get type from hints
            param_type = hints.get(param_name, str)
            json_type = _python_type_to_json_type(param_type)
            
            # Get description from docstring (simplified)
            param_desc = f"The {param_name} parameter"
            
            properties[param_name] = {
                "type": json_type,
                "description": param_desc,
            }
            
            # Handle enums
            if hasattr(param_type, "__args__") and all(
                isinstance(arg, str) for arg in getattr(param_type, "__args__", [])
            ):
                properties[param_name]["enum"] = list(param_type.__args__)
            
            # Required if no default
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
        
        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        
        return Tool(
            name=name,
            description=tool_description,
            input_schema=input_schema,
            function=func,
            input_examples=examples or [],
        )
    
    return decorator


def _python_type_to_json_type(py_type: type) -> str:
    """Convert Python type to JSON Schema type."""
    if py_type is str:
        return "string"
    elif py_type is int:
        return "integer"
    elif py_type is float:
        return "number"
    elif py_type is bool:
        return "boolean"
    elif py_type is list or (hasattr(py_type, "__origin__") and py_type.__origin__ is list):
        return "array"
    elif py_type is dict or (hasattr(py_type, "__origin__") and py_type.__origin__ is dict):
        return "object"
    else:
        return "string"  # Default fallback


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_name: str
    tool_use_id: str
    result: Any
    is_error: bool = False
    error_message: str | None = None


@dataclass
class AgentResult:
    """Result from an agentic workflow with tool use."""
    text: str
    tool_calls: list[ToolResult] = field(default_factory=list)
    turns: int = 0
    total_duration_ms: int = 0
    model: str = ""
    stop_reason: str = ""


class ToolRouter:
    """
    Agentic router with tool use support.
    
    Combines the AI Router's smart routing with Claude's Tool Runner pattern
    for executing agentic workflows with automatic tool execution.
    
    Features:
    - Automatic tool execution when Claude requests them
    - Multi-turn conversation support
    - Error handling with retry
    - Telemetry logging
    - Optional escalation on tool failures
    
    Usage:
        from _tools.ai_router.tools import ToolRouter, tool
        
        @tool("search_files")
        def search_files(query: str, path: str = ".") -> list[str]:
            '''Search for files matching a pattern.'''
            import glob
            return glob.glob(f"{path}/**/*{query}*", recursive=True)
        
        router = ToolRouter(tools=[search_files])
        result = router.run("Find all Python files in my project")
        print(result.text)
    """
    
    def __init__(
        self,
        tools: list[Tool],
        *,
        model: str = "claude-sonnet-4-5-20250514",
        max_turns: int = 10,
        max_tokens: int = 4096,
        anthropic_api_key: str | None = None,
        include_examples: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize the tool router.
        
        Args:
            tools: List of Tool objects to make available to Claude
            model: Claude model to use (default: claude-sonnet-4-5)
            max_turns: Maximum agentic turns before stopping
            max_tokens: Max tokens per response
            anthropic_api_key: API key (defaults to ANTHROPIC_API_KEY env var)
            include_examples: Include input_examples in tool definitions (beta)
            verbose: Print tool execution details
        """
        self.tools = {t.name: t for t in tools}
        self.model = model
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.include_examples = include_examples
        self.verbose = verbose
        
        import os
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for tool use")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.telemetry = TelemetryLogger(log_dir="data/logs")
    
    def run(
        self,
        prompt: str,
        *,
        system: str | None = None,
        messages: list[dict[str, Any]] | None = None,
    ) -> AgentResult:
        """
        Run an agentic task with tool use.
        
        The router will:
        1. Send the prompt to Claude with available tools
        2. If Claude requests a tool, execute it and continue
        3. Repeat until Claude provides a final response or max_turns reached
        
        Args:
            prompt: The user's request
            system: Optional system prompt
            messages: Optional conversation history to continue
            
        Returns:
            AgentResult with final text, tool calls made, and metadata
        """
        t0 = time.time()
        
        # Build initial messages
        conversation = messages or []
        if prompt:
            conversation.append({"role": "user", "content": prompt})
        
        # Tool definitions for API
        tool_defs = [
            t.to_api_format(include_examples=self.include_examples)
            for t in self.tools.values()
        ]
        
        tool_calls = []
        turns = 0
        final_text = ""
        stop_reason = ""
        
        while turns < self.max_turns:
            turns += 1
            
            # Build request
            request_kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": conversation,
                "tools": tool_defs,
            }
            if system:
                request_kwargs["system"] = system
            
            if self.verbose:
                print(f"{CYAN}[Turn {turns}] Calling Claude...{RESET}")
            
            # Call Claude
            response = self.client.messages.create(**request_kwargs)
            stop_reason = response.stop_reason
            
            # Process response content
            assistant_content = []
            text_parts = []
            tool_use_blocks = []
            
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })
            
            # Add assistant message to conversation
            conversation.append({"role": "assistant", "content": assistant_content})
            
            # If no tool use, we're done
            if stop_reason == "end_turn" or not tool_use_blocks:
                final_text = "\n".join(text_parts)
                break
            
            # Execute tools
            tool_results_content = []
            
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_input = tool_use.input
                tool_id = tool_use.id
                
                if self.verbose:
                    print(f"{YELLOW}  → Executing: {tool_name}({json.dumps(tool_input)}){RESET}")
                
                tool = self.tools.get(tool_name)
                
                if not tool:
                    # Tool not found
                    result = ToolResult(
                        tool_name=tool_name,
                        tool_use_id=tool_id,
                        result=None,
                        is_error=True,
                        error_message=f"Tool '{tool_name}' not found",
                    )
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": f"Error: Tool '{tool_name}' not found",
                        "is_error": True,
                    })
                else:
                    try:
                        # Execute the tool
                        output = tool.execute(**tool_input)
                        
                        # Serialize output
                        if isinstance(output, (dict, list)):
                            output_str = json.dumps(output, indent=2)
                        else:
                            output_str = str(output)
                        
                        result = ToolResult(
                            tool_name=tool_name,
                            tool_use_id=tool_id,
                            result=output,
                        )
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": output_str,
                        })
                        
                        if self.verbose:
                            preview = output_str[:100] + "..." if len(output_str) > 100 else output_str
                            print(f"{GREEN}  ✓ Result: {preview}{RESET}")
                            
                    except Exception as e:
                        result = ToolResult(
                            tool_name=tool_name,
                            tool_use_id=tool_id,
                            result=None,
                            is_error=True,
                            error_message=str(e),
                        )
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Error executing {tool_name}: {e}",
                            "is_error": True,
                        })
                        
                        if self.verbose:
                            print(f"{YELLOW}  ✗ Error: {e}{RESET}")
                
                tool_calls.append(result)
            
            # Add tool results to conversation (all in single user message)
            conversation.append({"role": "user", "content": tool_results_content})
        
        duration_ms = int((time.time() - t0) * 1000)
        
        if self.verbose:
            print(f"{CYAN}[Complete] {turns} turns, {len(tool_calls)} tool calls, {duration_ms}ms{RESET}")
        
        return AgentResult(
            text=final_text,
            tool_calls=tool_calls,
            turns=turns,
            total_duration_ms=duration_ms,
            model=self.model,
            stop_reason=stop_reason,
        )


# Convenience function for quick tool definition
def create_tool(
    name: str,
    func: Callable[..., Any],
    description: str | None = None,
    examples: list[dict[str, Any]] | None = None,
) -> Tool:
    """
    Create a Tool from a function without using the decorator.
    
    Example:
        def my_search(query: str) -> list[str]:
            return ["result1", "result2"]
        
        search_tool = create_tool("search", my_search, "Search for things")
    """
    decorated = tool(name, description, examples)(func)
    return decorated
