import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.mcp_connection_pool import MCPConnectionPool, get_pool, shutdown_pool

@pytest.fixture
def mock_mcp_client():
    with patch("src.mcp_connection_pool.MCPClient") as mock:
        yield mock

def test_pool_client_creation(mock_mcp_client):
    """Test that the pool creates a client and reuses it."""
    pool = MCPConnectionPool()
    server_name = "test-server"
    config = Path("/tmp/test-server.js")
    
    # First call - creates client
    client1 = pool.get_client(server_name, config)
    assert server_name in pool._clients
    mock_mcp_client.assert_called_once_with(config)
    client1.connect.assert_called_once()
    
    # Second call - reuses client
    client2 = pool.get_client(server_name, config)
    assert client1 is client2
    mock_mcp_client.assert_called_once() # Still only once

def test_pool_unhealthy_client_removal(mock_mcp_client):
    """Test that unhealthy clients are removed and recreated."""
    pool = MCPConnectionPool()
    server_name = "test-server"
    config = Path("/tmp/test-server.js")
    
    # Create healthy client
    mock_mcp_client.return_value = MagicMock()
    client1 = pool.get_client(server_name, config)
    client1.is_connected.return_value = True
    
    # Make it unhealthy
    client1.is_connected.return_value = False
    
    # Set a new mock for the next call
    mock_mcp_client.return_value = MagicMock()
    
    # Get client again - should recreate
    client2 = pool.get_client(server_name, config)
    assert client1 is not client2
    assert mock_mcp_client.call_count == 2
    client1.close.assert_called_once()

def test_pool_close_idle(mock_mcp_client):
    """Test that idle connections are closed."""
    pool = MCPConnectionPool(max_idle_seconds=1)
    server_name = "test-server"
    config = Path("/tmp/test-server.js")
    
    client = pool.get_client(server_name, config)
    
    # Wait for idle timeout
    time.sleep(1.1)
    
    closed_count = pool.close_idle()
    assert closed_count == 1
    assert server_name not in pool._clients
    client.close.assert_called_once()

def test_pool_close_all(mock_mcp_client):
    """Test closing all connections."""
    pool = MCPConnectionPool()
    pool.get_client("server1", Path("s1.js"))
    pool.get_client("server2", Path("s2.js"))
    
    assert len(pool._clients) == 2
    
    pool.close_all()
    assert len(pool._clients) == 0

def test_global_pool():
    """Test global pool access and shutdown."""
    pool1 = get_pool()
    pool2 = get_pool()
    assert pool1 is pool2
    
    with patch.object(pool1, "close_all") as mock_close:
        shutdown_pool()
        mock_close.assert_called_once()
    
    # Should be None after shutdown
    from src import mcp_connection_pool
    assert mcp_connection_pool._pool is None
