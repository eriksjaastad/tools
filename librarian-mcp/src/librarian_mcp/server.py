import asyncio
import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Set up logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("librarian-mcp")

from .tools import TOOLS
from .db import TrackerDB
from .graph import KnowledgeGraph
from .config import TRACKER_DB, GRAPH_JSON

# Initialize shared components
# Note: Graph is loaded once at startup. DB is connected per request.
db = TrackerDB()
graph = KnowledgeGraph()

# Initialize server
server = Server("librarian")

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
            inc_ext = arguments.get("include_external", False)
            
            # Graph-based dependencies
            # We can use find_related with depth 1 specifically for dependency types
            all_related = graph.get_neighbors(project) # Assuming project is a node in graph
            
            # Fallback/Supplemental from TrackerDB
            db_deps = db.get_dependencies(project)
            
            res = f"Dependencies for {project}:\n"
            res += f"Upstream (from DB): {', '.join(db_deps['upstream'])}\n"
            res += f"Downstream (from DB): {', '.join(db_deps['downstream'])}\n"
            
            if all_related:
                res += "\nGraph Relationships:\n"
                for rel in all_related:
                    res += f"- {rel['target']} ({rel['type']})\n"
            
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
            # This will be implemented in Prompt 4
            from .nlq import process_question
            question = arguments["question"]
            context = arguments.get("context")
            answer = await process_question(question, context, db, graph)
            return [types.TextContent(type="text", text=answer)]

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
