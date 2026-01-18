import pytest
import mcp.types as types
from librarian_mcp.server import handle_call_tool

@pytest.mark.asyncio
async def test_search_knowledge_basic():
    # Test that unknown tools return an error message (not raise)
    # The handle_call_tool catches exceptions and returns error text
    result = await handle_call_tool("non_existent", {})
    assert len(result) == 1
    assert result[0].type == "text"
    assert "Error" in result[0].text or "Unknown tool" in result[0].text

def test_list_projects_filter(tracker_db):
    # Testing the logic directly since handle_call_tool uses global db
    projects = tracker_db.list_projects()
    assert len(projects) == 1
    
def test_get_project_info_logic(tracker_db):
    info = tracker_db.get_project("test-proj")
    assert info["name"] == "test-proj"
