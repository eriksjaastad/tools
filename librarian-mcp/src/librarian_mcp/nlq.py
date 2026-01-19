import logging
from typing import Dict, Any, Optional
from .db import TrackerDB
from .graph import KnowledgeGraph

logger = logging.getLogger("librarian-mcp")

async def process_question(question: str, context: Optional[str], db: TrackerDB, graph: KnowledgeGraph) -> str:
    """Parse question intent and route to appropriate internal logic."""
    q = question.lower()
    
    try:
        # Intent: Get project info / "what is X"
        if any(word in q for word in ["what is", "tell me about", "info on"]):
            # Extract potential project name (simplistic)
            for word in q.split():
                try:
                    project = db.get_project(word.strip("?.,"))
                    if project:
                        deps = db.get_dependencies(project["name"])
                        return f"Project: {project['name']}\nDescription: {project['description']}\nStatus: {project['status']}\nDepends on: {', '.join(deps['upstream']) or 'Nothing'}"
                except Exception as e:
                    logger.warning(f"Project lookup failed for {word}: {e}")
                    continue

        # Intent: Get dependencies / "what depends on X"
        if any(word in q for word in ["depends on", "dependency", "upstream", "downstream"]):
            for word in q.split():
                try:
                    deps = db.get_dependencies(word.strip("?.,"))
                    if deps["upstream"] or deps["downstream"]:
                        return f"Dependencies for {word}:\nUpstream: {', '.join(deps['upstream'])}\nDownstream: {', '.join(deps['downstream'])}"
                except Exception as e:
                    logger.warning(f"Dependency lookup failed for {word}: {e}")
                    continue

        # Intent: Find connection / "how does X relate to Y"
        if "relate" in q or "connect" in q or "link" in q:
            # This would require extracting two entities, keeping it simple for now
            pass

        # Default: Search Knowledge
        results = db.search_projects(question)
        nodes = graph.search_nodes(question)
        
        answer = "I searched the knowledge base and found the following:\n"
        if results:
            answer += "Projects:\n" + "\n".join([f"- {p['name']}: {p['description']}" for p in results[:3]]) + "\n"
        if nodes:
            answer += "Relevant Files:\n" + "\n".join([f"- {n.get('path')} ({n.get('label')})" for n in nodes[:5]])
            
        if not results and not nodes:
            answer = f"I couldn't find anything matching '{question}' in the knowledge base."
            
        return answer

    except Exception as e:
        logger.error(f"Error in NLQ processing: {e}")
        return f"Sorry, I encountered an error while searching: {str(e)}"
