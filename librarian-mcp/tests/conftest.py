import pytest
import sqlite3
import json
import os
from pathlib import Path
from librarian_mcp.db import TrackerDB
from librarian_mcp.graph import KnowledgeGraph

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_tracker.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, description TEXT, status TEXT)")
    conn.execute("CREATE TABLE service_dependencies (project_id TEXT, service_name TEXT)")
    conn.execute("CREATE TABLE ai_agents (name TEXT, project TEXT, role TEXT)")
    
    conn.execute("INSERT INTO projects VALUES ('test-id', 'test-proj', 'A test project', 'active')")
    conn.execute("INSERT INTO service_dependencies VALUES ('test-id', 'ext-dep')")
    conn.execute("INSERT INTO service_dependencies VALUES ('other-id', 'test-proj')")
    conn.execute("INSERT INTO ai_agents VALUES ('agent-1', 'test-proj', 'developer')")
    conn.commit()
    conn.close()
    return str(db_path)

@pytest.fixture
def temp_graph(tmp_path):
    graph_path = tmp_path / "test_graph.json"
    data = {
        "nodes": [
            {"id": "test-project/file1.py", "path": "test-project/file1.py", "label": "File 1"},
            {"id": "test-project/file2.py", "path": "test-project/file2.py", "label": "File 2"}
        ],
        "edges": [
            {"source": "test-project/file1.py", "target": "test-project/file2.py", "type": "imports"}
        ]
    }
    with open(graph_path, "w") as f:
        json.dump(data, f)
    return str(graph_path)

@pytest.fixture
def tracker_db(temp_db):
    with TrackerDB(temp_db) as db:
        yield db

@pytest.fixture
def knowledge_graph(temp_graph):
    return KnowledgeGraph(temp_graph)
