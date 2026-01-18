import json
import subprocess
import os
import sys
import threading
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class MCPError(Exception):
    """Raised when an MCP protocol error occurs."""
    pass

class MCPTimeoutError(Exception):
    """Raised when an MCP request times out."""
    pass

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, server_path: Path):
        self.server_path = server_path
        self._process = None
        self._lock = threading.Lock()
        self._request_id = 0

    def start(self):
        """Spawns the MCP server subprocess."""
        if self._process is not None:
            return

        try:
            # Spawn Node.js server
            # We use 'node' command, assuming it is in PATH
            self._process = subprocess.Popen(
                ["node", str(self.server_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr, # Forward stderr for debugging
                text=True,
                bufsize=0 # Unbuffered
            )
        except Exception as e:
            raise MCPError(f"Failed to start MCP server: {e}")

    def connect(self):
        """Persistent connection - starts the server without context manager."""
        self.start()

    def stop(self):
        """Terminates the MCP server subprocess."""
        if self._process is not None:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except Exception as e:
                logger.debug(f"MCP process termination failed: {e}")
            finally:
                self._process = None

    def close(self):
        """Persistent connection - stops the server."""
        self.stop()

    def is_connected(self) -> bool:
        """Check if the server process is still running and responsive."""
        return self._process is not None and self._process.poll() is None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def _read_response(self) -> str:
        """Reads a single line from stdout."""
        if self._process is None or self._process.poll() is not None:
            raise MCPError("Server is not running")
            
        line = self._process.stdout.readline()
        if not line:
            raise MCPError("Server closed connection unexpectedly")
        return line.strip()

    def call_tool(self, name: str, arguments: dict, timeout: int = 600) -> Dict[str, Any]:
        """
        Sends a JSON-RPC request to call a tool.
        Format: {"jsonrpc": "2.0", "id": <id>, "method": "tools/call", "params": {"name": <name>, "arguments": <args>}}
        """
        if self._process is None:
            raise MCPError("Client not started")

        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                }
            }
            
            request_str = json.dumps(payload)
            
            try:
                self._process.stdin.write(request_str + "\n")
                self._process.stdin.flush()
            except (BrokenPipeError, IOError) as e:
                raise MCPError(f"Failed to send request: {e}")

            result_container = {}
            
            def read_thread():
                try:
                    line = self._read_response()
                    result_container["line"] = line
                except Exception as e:
                    result_container["error"] = e
                    
            t = threading.Thread(target=read_thread, daemon=True)
            t.start()
            t.join(timeout=timeout)
            
            if t.is_alive():
                self.stop() 
                raise MCPTimeoutError(f"Tool call '{name}' timed out after {timeout}s")
                
            if "error" in result_container:
                raise result_container["error"]
                
            response_str = result_container.get("line")
            
            try:
                response = json.loads(response_str)
            except json.JSONDecodeError:
                raise MCPError(f"Invalid JSON response: {response_str}")
                
            if response.get("id") != request_id:
                raise MCPError(f"Request ID mismatch. Expected {request_id}, got {response.get('id')}")
                
            if "error" in response:
                error = response["error"]
                msg = error.get("message", "Unknown error")
                data = error.get("data")
                raise MCPError(f"MCP Error {error.get('code')}: {msg} - {data}")
                
            if "result" not in response:
                raise MCPError("Response missing 'result' field")
                
            return response["result"]
