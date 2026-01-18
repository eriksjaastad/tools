import pytest
import asyncio
from librarian_mcp.server import server, handle_list_tools, handle_call_tool
import mcp.types as types

@pytest.mark.asyncio
async def test_server_starts():
    # Basic check that server is initialized
    assert server.name == "librarian"

@pytest.mark.asyncio
async def test_tools_list():
    # Call the handler function directly
    tools = await handle_list_tools()
    assert len(tools) > 0
    assert any(t.name == "search_knowledge" for t in tools)

@pytest.mark.asyncio
async def test_ask_librarian_tool():
    # Test that ask_librarian returns a response (even if it's an error about missing data)
    result = await handle_call_tool("ask_librarian", {"question": "test question"})
    assert len(result) == 1
    assert result[0].type == "text"
