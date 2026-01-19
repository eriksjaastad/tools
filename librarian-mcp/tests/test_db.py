import pytest
from librarian_mcp.db import TrackerDB

def test_get_project_found(tracker_db):
    project = tracker_db.get_project("test-proj")
    assert project is not None
    assert project["name"] == "test-proj"

def test_get_project_not_found(tracker_db):
    project = tracker_db.get_project("ghost")
    assert project is None

def test_list_projects(tracker_db):
    projects = tracker_db.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "test-proj"

def test_search_projects(tracker_db):
    results = tracker_db.search_projects("test")
    assert len(results) == 1
    assert results[0]["name"] == "test-proj"

def test_get_dependencies(tracker_db):
    # Data is now in fixtures in conftest.py
    deps = tracker_db.get_dependencies("test-proj")
    assert "ext-dep" in deps["upstream"]

def test_get_ai_agents(tracker_db):
    agents = tracker_db.get_ai_agents("test-proj")
    assert len(agents) == 1
    assert agents[0]["name"] == "agent-1"
