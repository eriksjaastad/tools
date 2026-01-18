import pytest

def test_find_path_exists(knowledge_graph):
    # test-project/file1.py -> test-project/file2.py
    path = knowledge_graph.find_path("test-project/file1.py", "test-project/file2.py")
    assert path is not None
    assert len(path) == 2
    assert path[0]["id"] == "test-project/file1.py"
    assert path[1]["id"] == "test-project/file2.py"
    assert path[1]["edge_type"] == "imports"

def test_find_path_not_exists(knowledge_graph):
    path = knowledge_graph.find_path("test-project/file2.py", "test-project/file1.py")  # No reverse edge
    assert path is None

def test_get_project_subgraph(knowledge_graph):
    # Nodes have paths like "test-project/file1.py"
    subgraph = knowledge_graph.get_project_subgraph("test-project")
    assert len(subgraph["nodes"]) == 2
    assert len(subgraph["edges"]) == 1

def test_performance_large_graph(knowledge_graph):
    # Basic check - ensure it doesn't crash on empty/small graph
    subgraph = knowledge_graph.get_project_subgraph("any", max_nodes=10)
    assert "nodes" in subgraph
