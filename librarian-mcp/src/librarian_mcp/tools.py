from typing import List, Dict

TOOLS: List[Dict] = [
    {
        "name": "search_knowledge",
        "description": "Search across all project knowledge - files, projects, and documentation. Returns ranked results with file paths and descriptions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (keywords or phrases)"},
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                "project": {"type": "string", "description": "Limit to specific project (optional)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_project_info",
        "description": "Get detailed information about a project including status, dependencies, and AI agents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name (e.g., 'agent-hub', 'project-tracker')"}
            },
            "required": ["project"]
        }
    },
    {
        "name": "find_related_docs",
        "description": "Find documents related to a given file path using the knowledge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (relative to projects root)"},
                "max_depth": {"type": "integer", "description": "Max graph traversal depth (default 2)", "default": 2}
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_projects",
        "description": "List all tracked projects with their status and brief descriptions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status (active, archived, etc.)"}
            }
        }
    },
    {
        "name": "get_dependencies",
        "description": "Get upstream and downstream dependencies for a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "include_external": {"type": "boolean", "description": "Include external dependencies (via TrackerDB)", "default": False}
            },
            "required": ["project"]
        }
    },
    {
        "name": "find_connection",
        "description": "Find how two files or projects are connected in the knowledge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from": {"type": "string", "description": "Source file path or project name"},
                "to": {"type": "string", "description": "Target file path or project name"}
            },
            "required": ["from", "to"]
        }
    },
    {
        "name": "get_project_graph",
        "description": "Get the knowledge subgraph for a project - all files and their relationships.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "max_nodes": {"type": "integer", "description": "Max nodes to return (default 100)", "default": 100}
            },
            "required": ["project"]
        }
    },
    {
        "name": "ask_librarian",
        "description": "Ask a natural language question about the codebase. The librarian will search knowledge, analyze graph relationships, and provide a structured answer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Your question in plain English"},
                "context": {"type": "string", "description": "Optional context (current file, project, etc.)"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "librarian_remember",
        "description": "Force the librarian to memorize a specific question-answer pair.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to remember"},
                "answer": {"type": "string", "description": "The answer to cache"},
                "tier": {"type": "string", "enum": ["cold", "warm", "hot"], "default": "warm"}
            },
            "required": ["question", "answer"]
        }
    },
    {
        "name": "librarian_forget",
        "description": "Clear the librarian's memory for a specific query or topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Exact query to forget"},
                "topic": {"type": "string", "description": "Topic keyword - forgets all related memories"}
            }
        }
    },
    {
        "name": "librarian_memory_stats",
        "description": "Get statistics about the librarian's memory usage.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "librarian_feedback",
        "description": "Provide feedback on answer quality to adjust confidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The question that was answered"},
                "helpful": {"type": "boolean", "description": "Was the answer helpful?"}
            },
            "required": ["query", "helpful"]
        }
    }
]
