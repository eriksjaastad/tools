import pytest
from librarian_mcp.graph import KnowledgeGraph

def test_find_node_found(knowledge_graph):
    node = knowledge_graph.find_node("test-project/file1.py")
    assert node is not None
    assert node["id"] == "test-project/file1.py"

def test_find_node_not_found(knowledge_graph):
    node = knowledge_graph.find_node("missing.py")
    assert node is None

def test_get_neighbors(knowledge_graph):
    neighbors = knowledge_graph.get_neighbors("test-project/file1.py")
    assert len(neighbors) == 1
    assert neighbors[0]["target"] == "test-project/file2.py"
    assert neighbors[0]["type"] == "imports"

def test_find_related(knowledge_graph):
    related = knowledge_graph.find_related("test-project/file1.py", max_depth=1)
    assert len(related) == 1
    assert related[0]["id"] == "test-project/file2.py"

def test_search_nodes(knowledge_graph):
    results = knowledge_graph.search_nodes("File 2")
    assert len(results) == 1
    assert results[0]["id"] == "test-project/file2.py"
