"""
MCP Connection Pool - Persistent server connections.

Keeps MCP servers alive across calls for reduced latency.
Feature flag: UAS_PERSISTENT_MCP
"""

import logging
import threading
import time
from typing import Any
from pathlib import Path

from .mcp_client import MCPClient

logger = logging.getLogger(__name__)

class MCPConnectionPool:
    """
    Pool of persistent MCP connections.

    Usage:
        pool = MCPConnectionPool()
        client = pool.get_client("ollama-mcp", config)
        result = client.call_tool("chat", {...})
        # Client stays alive for next call

        # On shutdown:
        pool.close_all()
    """

    def __init__(self, max_idle_seconds: int = 300):
        self._clients: dict[str, MCPClient] = {}
        self._last_used: dict[str, float] = {}
        self._configs: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._max_idle = max_idle_seconds

    def get_client(self, server_name: str, config: Any | None = None) -> MCPClient:
        """
        Get or create a client for the named server.

        Args:
            server_name: Unique identifier for the server
            config: Server configuration (required on first call, should be a Path or similar)

        Returns:
            Active MCPClient instance
        """
        with self._lock:
            # Check for existing healthy client
            if server_name in self._clients:
                client = self._clients[server_name]
                if self._is_healthy(client):
                    self._last_used[server_name] = time.time()
                    return client
                else:
                    # Client unhealthy, remove it
                    self._remove_client(server_name)

            # Need config to create new client
            if config is None:
                config = self._configs.get(server_name)
            if config is None:
                raise ValueError(f"No config for server: {server_name}")

            # Create new client
            # The original MCPClient takes a Path object
            client = MCPClient(Path(config) if isinstance(config, (str, bytes)) else config)
            client.connect()  # Start the server process

            self._clients[server_name] = client
            self._configs[server_name] = config
            self._last_used[server_name] = time.time()

            logger.info(f"Created new MCP connection: {server_name}")
            return client

    def _is_healthy(self, client: MCPClient) -> bool:
        """Check if client connection is still alive."""
        try:
            # Attempt a lightweight operation to verify connection
            return client.is_connected()
        except Exception:
            return False

    def _remove_client(self, server_name: str) -> None:
        """Remove and close a client (must hold lock)."""
        if server_name in self._clients:
            try:
                self._clients[server_name].close()
            except Exception as e:
                logger.warning(f"Error closing client {server_name}: {e}")
            del self._clients[server_name]
            del self._last_used[server_name]

    def close_idle(self) -> int:
        """Close connections that have been idle too long. Returns count closed."""
        closed = 0
        now = time.time()
        with self._lock:
            to_close = [
                name for name, last in self._last_used.items()
                if now - last > self._max_idle
            ]
            for name in to_close:
                logger.info(f"Closing idle MCP connection: {name}")
                self._remove_client(name)
                closed += 1
        return closed

    def close_all(self) -> None:
        """Close all connections (call on shutdown)."""
        with self._lock:
            for name in list(self._clients.keys()):
                self._remove_client(name)
        logger.info("Closed all MCP connections")

    def stats(self) -> dict:
        """Get pool statistics."""
        with self._lock:
            return {
                "active_connections": len(self._clients),
                "servers": list(self._clients.keys()),
            }


# Global pool instance
_pool: MCPConnectionPool | None = None

def get_pool() -> MCPConnectionPool:
    """Get the global connection pool."""
    global _pool
    if _pool is None:
        _pool = MCPConnectionPool()
    return _pool

def shutdown_pool() -> None:
    """Shutdown the global pool (call on application exit)."""
    global _pool
    if _pool:
        _pool.close_all()
        _pool = None
