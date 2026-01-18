import json
import re
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from .mcp_client import MCPClient, MCPError, MCPTimeoutError
from .utils import safe_read, atomic_write
from . import ollama_http_client
from .utils import feature_flags, timing
from . import cost_logger
from . import litellm_bridge
from .librarian_client import query_librarian

logger = logging.getLogger(__name__)

MAX_INPUT_TOKENS = 100000  # Adjust based on model limits

def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ~ 4 characters."""
    return len(text) // 4

def prepare_prompt(content: str) -> str:
    """Prepare prompt with token safety check."""
    estimated = estimate_tokens(content)
    if estimated > MAX_INPUT_TOKENS:
        logger.warning(f"Content exceeds token limit ({estimated} > {MAX_INPUT_TOKENS}), truncating")
        # Truncate to approximate limit
        max_chars = MAX_INPUT_TOKENS * 4
        content = content[:max_chars] + "\n\n[TRUNCATED - content exceeded token limit]"
    return content

class WorkerClient:
    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client

    def check_ollama_health(self) -> bool:
        """Verifies Ollama is responsive."""
        if feature_flags.use_ollama_http():
            try:
                models = ollama_http_client.list_models()
                return isinstance(models, list)
            except Exception:
                return False
        
        try:
            # simple list models check
            result = self.mcp.call_tool("ollama_list_models", {}, timeout=5)
            # Just check we got a valid MCP content response
            return "content" in result
        except (MCPError, MCPTimeoutError):
            return False

    def _parse_mcp_response(self, result: Dict[str, Any]) -> str:
        """Extracts the text content from an MCP tool result."""
        if "content" not in result or not isinstance(result["content"], list):
            return ""
        
        full_text = ""
        for item in result["content"]:
            if item.get("type") == "text":
                full_text += item.get("text", "")
        
        # OLLAMA-MCP COMPATIBILITY:
        # The ollama-mcp tool returns a JSON string containing structure { stdout, stderr, exitCode, metadata }.
        # We need to extract 'stdout' from this wrapper if it exists.
        try:
            # Heuristic: does it look like the ollama-mcp object?
            if full_text.strip().startswith("{") and '"stdout":' in full_text:
                wrapped = json.loads(full_text)
                if isinstance(wrapped, dict) and "stdout" in wrapped:
                    # Log metadata for visibility but return just the text
                    if "metadata" in wrapped and wrapped["metadata"].get("timed_out"):
                        print(f"Ollama Timeout: {wrapped['metadata']}")
                        # This might be empty if timed out, but let's return what we have
                    return wrapped["stdout"]
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse ollama-mcp response as JSON: {e}")
            
        return full_text

    def implement_task(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the implementer agent.
        Returns: { success, output, files_changed, tokens, stall_reason }
        """
        spec = contract.get("specification", {})
        requirements = "\n".join(f"- {r}" for r in spec.get("requirements", []))
        source_files_content = ""
        for src in spec.get("source_files", []):
            path = src["path"]
            content = safe_read(Path(path)) or "(File not found or empty)"
            source_files_content += f"\n--- {path} ---\n{content}\n"

        target_file = spec.get("target_file", "output.txt")
        
        prompt = f"""You are an expert software developer. Implement the following task.

TASK: {contract['task_id']}
PROJECT: {contract['project']}

REQUIREMENTS:
{requirements}

SOURCE FILES:
{source_files_content}

TARGET FILE: {target_file}

CONSTRAINTS:
- Write the COMPLETE code for the target file.
- Do not use placeholders.
- Output ONLY the code for the target file, inside a code block.
"""
        prompt = prepare_prompt(prompt)
        model = contract.get("roles", {}).get("implementer", "qwen2.5-coder:14b")
        
        try:
            # Ensure model name doesn't contain disallowed chars if we want to be safe, 
            # but we assume contract is valid.
            
            # Using a custom timeout for implementation
            timeout_min = contract.get("limits", {}).get("timeout_minutes", {}).get("implementer", 10)
            timeout_sec = timeout_min * 60

            if feature_flags.use_litellm_routing():
                # Use LiteLLM bridge
                response = litellm_bridge.route_chat(
                    messages=[{"role": "user", "content": prompt}],
                    task_type="code"
                )
                output_text = response.get("content", "")
            elif feature_flags.use_ollama_http():
                # Use direct HTTP client
                response = ollama_http_client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False
                )
                output_text = response.get("message", {}).get("content", "")
            else:
                # Use legacy MCP path
                with timing.measure_latency() as t:
                    try:
                        result = self.mcp.call_tool("ollama_run", {
                            "model": model,
                            "prompt": prompt,
                            "options": {
                                "timeout": int(timeout_sec * 1000)
                            }
                        }, timeout=timeout_sec + 30)
                        output_text = self._parse_mcp_response(result)
                        
                        # Log legacy call
                        cost_logger.log_model_call(
                            model=model,
                            tokens_in=estimate_tokens(prompt),
                            tokens_out=estimate_tokens(output_text),
                            latency_ms=t["latency_ms"],
                            success=True
                        )
                    except Exception as e:
                        cost_logger.log_model_call(
                            model=model,
                            tokens_in=estimate_tokens(prompt),
                            tokens_out=0,
                            latency_ms=t["latency_ms"],
                            success=False,
                            error=str(e)
                        )
                        raise
            
            # Stall Detection: Empty/Whitespace
            if not output_text or not output_text.strip():
                return {
                    "success": False,
                    "stall_reason": "empty_output",
                    "output": ""
                }

            # Stall Detection: Malformed (No code block)
            # We look for markdown code blocks
            code_match = re.search(r"```(?:\w+)?\s+(.*?)```", output_text, re.DOTALL)
            if not code_match:
                 # Be lenient? Requirements say "stall_reason": "malformed_output" if no markers
                 # DEBUG: Log output
                 with open("_handoff/last_worker_output.txt", "w") as f:
                     f.write(output_text)
                 
                 return {
                    "success": False,
                    "stall_reason": "malformed_output",
                    "output": output_text
                 }
            
            code_content = code_match.group(1)
            
            # Write key file
            atomic_write(Path(target_file), code_content)
            
            # Extract token usage if available (Ollama MCP might provide it in text or separate field?)
            # The current ollama-mcp implementation might wrap usage. 
            # If not provided, we estimate or leave empty.
            # Assuming 'result' might have it if updated, otherwise basic estimation?
            # Prompt 6.3 Note says: "If ollama_run returns token counts..."
            # Let's check current output. The MCP tool returns text. 
            # If the tool is just `ollama run`, it usually streams text.
            # We'll default to 0 for now unless we see it in response.
            
            return {
                "success": True,
                "output": output_text,
                "files_changed": [target_file],
                "tokens": {"input": len(prompt)//4, "output": len(output_text)//4} # Rough est
            }

        except MCPTimeoutError:
            return {"success": False, "stall_reason": "timeout"}
        except Exception as e:
            return {"success": False, "stall_reason": f"error: {str(e)}"}

    def run_local_review(self, contract: Dict[str, Any], changed_files: List[str]) -> Dict[str, Any]:
        """
        Runs the local reviewer agent.
        Returns: { passed, issues, critical }
        """
        file_contents = ""
        for f in changed_files:
            content = safe_read(Path(f)) or "(Empty)"
            file_contents += f"\n--- {f} ---\n{content}\n"
            
        prompt = f"""You are a code reviewer. Review the following files for SECURITY vulnerabilities and SYNTAX errors.

FILES:
{file_contents}

CHECKLIST:
1. Are there any hardcoded secrets? (CRITICAL)
2. Is there dangerous input handling? (CRITICAL)
3. Are there syntax errors? (BLOCKING)
4. Are there style issues? (MINOR)

OUTPUT FORMAT:
Return a JSON object with this structure:
{{
  "verdict": "PASS" | "FAIL",
  "critical": true | false,
  "issues": ["list", "of", "issues"]
}}
Output ONLY the JSON.
"""
        prompt = prepare_prompt(prompt)
        model = contract.get("roles", {}).get("local_reviewer", "deepseek-r1:7b")
        
        try:
            timeout_min = contract.get("limits", {}).get("timeout_minutes", {}).get("local_review", 5)
            timeout_sec = timeout_min * 60
            
            if feature_flags.use_litellm_routing():
                # Use LiteLLM bridge
                response = litellm_bridge.route_chat(
                    messages=[{"role": "user", "content": prompt}],
                    task_type="reasoning"
                )
                output_text = response.get("content", "")
            elif feature_flags.use_ollama_http():
                # Use direct HTTP client
                response = ollama_http_client.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False
                )
                output_text = response.get("message", {}).get("content", "")
            else:
                # Use legacy MCP path
                with timing.measure_latency() as t:
                    try:
                        result = self.mcp.call_tool("ollama_run", {
                            "model": model,
                            "prompt": prompt,
                            "format": "json", # Force JSON mode if supported by Ollama
                            "options": {
                                "timeout": int(timeout_sec * 1000)
                            }
                        }, timeout=timeout_sec + 30)
                        output_text = self._parse_mcp_response(result)
                        
                        # Log legacy call
                        cost_logger.log_model_call(
                            model=model,
                            tokens_in=estimate_tokens(prompt),
                            tokens_out=estimate_tokens(output_text),
                            latency_ms=t["latency_ms"],
                            success=True
                        )
                    except Exception as e:
                        cost_logger.log_model_call(
                            model=model,
                            tokens_in=estimate_tokens(prompt),
                            tokens_out=0,
                            latency_ms=t["latency_ms"],
                            success=False,
                            error=str(e)
                        )
                        raise
            
            # Parse JSON
            # DeepSeek might be chatty even with format instructions, look for { ... }
            json_match = re.search(r"(\{.*\})", output_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                return {
                    "passed": data.get("verdict") == "PASS",
                    "critical": data.get("critical", False),
                    "issues": data.get("issues", [])
                }
            else:
                 # Fallback: analyze text heuristics
                 if "CRITICAL" in output_text.upper():
                     return {"passed": False, "critical": True, "issues": ["Could not parse JSON, found CRITICAL keyword"]}
                 elif "FAIL" in output_text.upper():
                     return {"passed": False, "critical": False, "issues": ["Could not parse JSON, found FAIL keyword"]}
                 
                 return {"passed": True, "issues": [], "critical": False}

        except Exception as e:
             return {"passed": False, "critical": False, "issues": [f"Review error: {str(e)}"]}

    def ask_for_clarification(
        self,
        question: str,
        timeout_seconds: int = 300,
        poll_interval: float = 5.0,
        max_poll_interval: float = 30.0
    ) -> str | None:
        """
        Ask the parent for clarification and wait for response.
        
        Uses adaptive polling: starts at poll_interval, doubles up to max_poll_interval.
        """
        import time
        from .state_adapter import get_state_adapter

        adapter = get_state_adapter()

        # Create a run_id if we don't have one
        run_id = getattr(self, "_current_run_id", None) or "default"
        agent_id = getattr(self, "_agent_id", None) or "worker"

        # Ask the question
        message_id = adapter.ask_parent(run_id, agent_id, question)
        logger.info(f"Asked question (msg_id={message_id}): {question[:50]}...")

        # Poll for answer with adaptive backoff
        start_time = time.time()
        current_interval = poll_interval

        while time.time() - start_time < timeout_seconds:
            answer = adapter.check_answer(message_id)
            if answer is not None:
                logger.info(f"Received answer for {message_id}")
                return answer

            # Wait with adaptive backoff
            time.sleep(current_interval)
            current_interval = min(current_interval * 2, max_poll_interval)

        logger.warning(f"Timeout waiting for answer to {message_id}")
        return None

def find_files_smart(query: str) -> List[str]:
    """Try librarian first, fall back to grep/glob placeholder."""
    librarian_result = query_librarian(f"find files related to: {query}")
    if librarian_result and librarian_result.get("sources"):
        return librarian_result["sources"]
    
    # Fallback simulation
    logging.getLogger("agent-hub").info(f"Librarian unavailable or no results for '{query}', falling back.")
    return []
