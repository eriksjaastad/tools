import asyncio
import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Set up logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("librarian-mcp")

import hashlib
import time

from .tools import TOOLS
from .db import TrackerDB
from .graph import KnowledgeGraph
from .config import TRACKER_DB, GRAPH_JSON

# Phase 2/3 Components
from .embedding import EmbeddingService
from .memory import MemoryStore
from .memory_db import MemoryDB

# Initialize shared components
db = TrackerDB()
graph = KnowledgeGraph()

# Initialize adaptive memory components
embedding_service = EmbeddingService()
memory_store = MemoryStore()
memory_db = MemoryDB()

# Initialize server
server = Server("librarian")

def get_query_hash(query: str) -> str:
    """Normalize and hash the query."""
    normalized = query.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()

def should_cache(query: str, answer: str, compute_time_ms: float, hit_count: int) -> bool:
    """
    Cache if:
    - Question asked 3+ times (popular)
    - OR compute took >500ms (expensive)
    - OR answer is >1000 chars (substantial)
    """
    if hit_count >= 3:
        return True
    if compute_time_ms > 500:
        return True
    if len(answer) > 1000:
        return True
    return False

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available knowledge tools."""
    return [
        types.Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=tool["inputSchema"]
        ) for tool in TOOLS
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""
    try:
        if name == "search_knowledge":
            query = arguments["query"]
            limit = arguments.get("limit", 10)
            project = arguments.get("project")
            
            # Search TrackerDB
            projects = db.search_projects(query)
            if project:
                projects = [p for p in projects if p["name"] == project]
            
            # Search Graph
            nodes = graph.search_nodes(query)
            if project:
                nodes = [n for n in nodes if project in n.get("path", "")]
                
            # Combine and format
            results = []
            for p in projects:
                results.append(f"Project: {p['name']} - {p.get('description', 'No description')}")
            for n in nodes[:limit]:
                results.append(f"File: {n.get('path')} ({n.get('label')})")
            
            return [types.TextContent(type="text", text="\n".join(results) or "No results found.")]

        elif name == "get_project_info":
            project_name = arguments["project"]
            info = db.get_project(project_name)
            if not info:
                return [types.TextContent(type="text", text=f"Project '{project_name}' not found.")]
            
            deps = db.get_dependencies(project_name)
            agents = db.get_ai_agents(project_name)
            
            res = f"Project: {info['name']}\nDescription: {info.get('description')}\nStatus: {info.get('status')}\n"
            res += f"Upstream Dependencies: {', '.join(deps['upstream']) or 'None'}\n"
            res += f"Downstream Dependencies: {', '.join(deps['downstream']) or 'None'}\n"
            res += f"AI Agents: {', '.join(a['name'] for a in agents) or 'None'}"
            return [types.TextContent(type="text", text=res)]

        elif name == "find_related_docs":
            path = arguments["path"]
            depth = arguments.get("max_depth", 2)
            related = graph.find_related(path, max_depth=depth)
            
            if not related:
                return [types.TextContent(type="text", text=f"No related documents found for '{path}'.")]
                
            res = "\n".join([f"- {r['path']} ({r['relationship']}, depth {r['depth']})" for r in related])
            return [types.TextContent(type="text", text=res)]

        elif name == "list_projects":
            status = arguments.get("status")
            projects = db.list_projects()
            if status:
                projects = [p for p in projects if p.get("status") == status]
            
            res = "\n".join([f"- {p['name']}: {p.get('description', 'No description')} ({p.get('status')})" for p in projects])
            return [types.TextContent(type="text", text=res or "No projects found.")]

        elif name == "get_dependencies":
            project = arguments["project"]
            
            # Fallback/Supplemental from TrackerDB
            db_deps = db.get_dependencies(project)
            
            res = f"Dependencies for {project}:\n"
            res += f"Upstream (from DB): {', '.join(db_deps['upstream'])}\n"
            res += f"Downstream (from DB): {', '.join(db_deps['downstream'])}\n"
            
            return [types.TextContent(type="text", text=res)]

        elif name == "find_connection":
            start = arguments["from"]
            to = arguments["to"]
            path = graph.find_path(start, to)
            
            if not path:
                return [types.TextContent(type="text", text=f"No connection found between {start} and {to}.")]
                
            res = " -> ".join([f"{n.get('path') or n.get('id')}" for n in path])
            return [types.TextContent(type="text", text=f"Path: {res}")]

        elif name == "get_project_graph":
            project = arguments["project"]
            max_nodes = arguments.get("max_nodes", 100)
            subgraph = graph.get_project_subgraph(project, max_nodes)
            
            res = f"Project Graph: {len(subgraph['nodes'])} nodes, {len(subgraph['edges'])} edges.\n"
            res += "Nodes:\n" + "\n".join([f"- {n.get('path')}" for n in subgraph['nodes'][:20]])
            if len(subgraph['nodes']) > 20: res += "\n... (truncated)"
            
            return [types.TextContent(type="text", text=res)]

        elif name == "ask_librarian":
            question = arguments["question"]
            context = arguments.get("context")
            q_hash = get_query_hash(question)

            # L1: Exact Match
            cached = memory_db.lookup_exact(q_hash)
            if cached:
                memory_db.record_hit(q_hash)
                logger.info(f"L1 Cache Hit for query: {question[:50]}")
                return [types.TextContent(type="text", text=cached['answer'])]

            # L2: Semantic Match
            embedding = embedding_service.get_single_embedding(question)
            if embedding:
                similar = memory_store.search_similar(embedding, threshold=0.15)
                if similar:
                    res_hash = get_query_hash(similar['query'])
                    stats = memory_db.get_query_stats(res_hash)
                    if stats and not memory_db.is_stale(stats):
                        memory_db.record_hit(res_hash)
                        logger.info(f"L2 Semantic Hit for query: {question[:50]}")
                        return [types.TextContent(type="text", text=similar['answer'])]
                    else:
                        # Stale semantic hit
                        memory_db.clear_cache(res_hash)
                        memory_store.delete_by_query(similar['query'])

            # L3: Compute
            from .nlq import process_question
            start_time = time.time()
            answer = await process_question(question, context, db, graph)
            compute_ms = (time.time() - start_time) * 1000

            # Caching Decision
            memory_db.record_query(question, q_hash, int(compute_ms))
            hit_count = memory_db.get_hit_count(q_hash)
            
            if should_cache(question, answer, compute_ms, hit_count):
                tier = "warm" if hit_count < 4 else "hot"
                memory_db.update_answer(q_hash, answer, tier)
                if embedding:
                    memory_store.add_search_result(question, answer, embedding, {"tier": tier})
                logger.info(f"Cached new answer for query: {question[:50]}")
                memory_db.evict_if_needed()
            
            return [types.TextContent(type="text", text=answer)]

        elif name == "librarian_remember":
            question = arguments["question"]
            answer = arguments["answer"]
            tier = arguments.get("tier", "warm")
            q_hash = get_query_hash(question)
            
            embedding = embedding_service.get_single_embedding(question)
            memory_db.record_query(question, q_hash)
            memory_db.update_answer(q_hash, answer, tier)
            if embedding:
                memory_store.add_search_result(question, answer, embedding, {"tier": tier, "manual": "true"})
            
            return [types.TextContent(type="text", text=f"I have committed this to my memory tier: {tier}")]

        elif name == "librarian_forget":
            query = arguments.get("query")
            topic = arguments.get("topic")
            
            if query:
                q_hash = get_query_hash(query)
                memory_db.forget_query(q_hash)
                memory_store.delete_by_query(query)
                return [types.TextContent(type="text", text=f"Forgotten memory: {query[:50]}")]
            
            if topic:
                memory_db.forget_topic(topic)
                # ChromaDB topic delete is harder without full search, 
                # but we can at least clear the SQLite side.
                return [types.TextContent(type="text", text=f"Cleared memories related to: {topic}")]
            
            return [types.TextContent(type="text", text="Please provide 'query' or 'topic'.")]

        elif name == "librarian_memory_stats":
            stats = memory_db.get_all_stats()
            res = f"Librarian Memory Stats:\n"
            res += f"Total Memories: {stats['total_memories']}\n"
            res += f"By Tier: {stats['by_tier']}\n"
            res += f"Cache Hit Rate: {stats['cache_hit_rate']:.2%}\n"
            res += f"Avg Compute Time: {stats['avg_compute_time_ms']:.1f}ms"
            return [types.TextContent(type="text", text=res)]

        elif name == "librarian_feedback":
            query = arguments["query"]
            helpful = arguments["helpful"]
            q_hash = get_query_hash(query)

            stats = memory_db.get_query_stats(q_hash)
            if not stats:
                return [types.TextContent(type="text", text="Query not found in memory.")]

            current_conf = stats.get("confidence") or 0.5
            delta = 0.1 if helpful else -0.1
            new_conf = max(0.0, min(1.0, current_conf + delta))

            with memory_db._get_conn() as conn:
                conn.execute("UPDATE query_memory SET confidence = ? WHERE query_hash = ?", (new_conf, q_hash))
                conn.commit()

            return [types.TextContent(type="text", text=f"Feedback recorded. Confidence: {new_conf:.2f}")]

        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()
