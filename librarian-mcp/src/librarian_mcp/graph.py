import json
import logging
from typing import List, Dict, Optional, Set
from .config import GRAPH_JSON

logger = logging.getLogger("librarian-mcp")

class KnowledgeGraph:
    def __init__(self, graph_path: str = str(GRAPH_JSON)):
        self.graph_path = graph_path
        self.nodes: Dict[str, Dict] = {}
        self.adjacency: Dict[str, List[Dict]] = {}
        self._load_graph()

    def _load_graph(self):
        try:
            with open(self.graph_path, 'r') as f:
                data = json.load(f)
                
            # data is expected to be { "nodes": [...], "edges": [...] }
            # Optimize nodes lookup
            for node in data.get("nodes", []):
                node_id = node.get("id")
                if node_id:
                    self.nodes[node_id] = node
                
            # Build adjacency list for efficient O(1) neighbor lookup
            for edge in data.get("edges", []):
                source = edge.get("source")
                target = edge.get("target")
                if source and target:
                    if source not in self.adjacency:
                        self.adjacency[source] = []
                    self.adjacency[source].append(edge)
                    
            logger.info(f"Loaded {len(self.nodes)} nodes and {len(data.get('edges', []))} edges")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load graph: {e}")
            self.nodes = {}
            self.adjacency = {}

    def find_node(self, path: str) -> Optional[Dict]:
        """Find node by absolute or relative path."""
        # Simple exact match or suffix match
        for node in self.nodes.values():
            if node.get("path") == path or node.get("id") == path:
                return node
        return None

    def get_neighbors(self, node_id: str) -> List[Dict]:
        """Get outgoing edges from a node."""
        edges = self.adjacency.get(node_id, [])
        return [
            {
                "target": edge["target"],
                "type": edge.get("type", "relates_to"),
                "node": self.nodes.get(edge["target"])
            }
            for edge in edges
            if edge["target"] in self.nodes
        ]

    def find_related(self, path: str, max_depth: int = 2) -> List[Dict]:
        """BFS to find related nodes up to max_depth."""
        start_node = self.find_node(path)
        if not start_node:
            return []
        
        start_id = start_node["id"]
        visited: Set[str] = {start_id}
        queue: List[tuple[str, int]] = [(start_id, 0)]
        results: List[Dict] = []
        
        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue
                
            for neighbor in self.get_neighbors(current_id):
                target_id = neighbor["target"]
                if target_id not in visited:
                    visited.add(target_id)
                    results.append({
                        "id": target_id,
                        "path": neighbor["node"].get("path"),
                        "label": neighbor["node"].get("label"),
                        "relationship": neighbor["type"],
                        "depth": depth + 1
                    })
                    queue.append((target_id, depth + 1))
        
        return results

    def search_nodes(self, query: str) -> List[Dict]:
        """Search node labels and paths."""
        query = query.lower()
        results = []
        for node in self.nodes.values():
            label = node.get("label", "").lower()
            path = node.get("path", "").lower()
            if query in label or query in path:
                results.append(node)
        return results

    def find_path(self, from_path: str, to_path: str) -> Optional[List[Dict]]:
        """BFS to find shortest path between two nodes."""
        start_node = self.find_node(from_path)
        end_node = self.find_node(to_path)
        
        if not start_node or not end_node:
            return None
            
        start_id = start_node["id"]
        end_id = end_node["id"]
        
        queue = [(start_id, [start_node])]
        visited = {start_id}
        
        while queue:
            current_id, path = queue.pop(0)
            if current_id == end_id:
                return path
                
            for neighbor in self.get_neighbors(current_id):
                target_id = neighbor["target"]
                if target_id not in visited:
                    visited.add(target_id)
                    new_path = list(path)
                    node_info = neighbor["node"].copy()
                    node_info["edge_type"] = neighbor["type"]
                    new_path.append(node_info)
                    queue.append((target_id, new_path))
                    
        return None

    def get_project_subgraph(self, project: str, max_nodes: int = 100) -> Dict:
        """Extract subgraph for a single project based on path prefix."""
        project_nodes = []
        project_node_ids = set()
        
        # Identify nodes belonging to project
        # Assuming path starts with project name or is in a directory named after project
        for node_id, node in self.nodes.items():
            path = node.get("path", "")
            if path.startswith(f"{project}/") or f"/{project}/" in path:
                project_nodes.append(node)
                project_node_ids.add(node_id)
                if len(project_nodes) >= max_nodes:
                    break
                    
        # Identify edges between these nodes
        project_edges = []
        for source_id in project_node_ids:
            edges = self.adjacency.get(source_id, [])
            for edge in edges:
                if edge["target"] in project_node_ids:
                    project_edges.append(edge)
                    
        return {
            "nodes": project_nodes,
            "edges": project_edges
        }
