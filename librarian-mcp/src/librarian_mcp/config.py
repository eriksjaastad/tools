import os
from pathlib import Path
import logging

logger = logging.getLogger("librarian-mcp")

# Base paths
HOME = Path.home()
PROJECTS_ROOT = Path(os.environ.get("LIBRARIAN_PROJECTS_ROOT", HOME / "projects"))

# Knowledge paths
TRACKER_DB = Path(os.environ.get("LIBRARIAN_TRACKER_DB", PROJECTS_ROOT / "project-tracker/data/tracker.db"))
# Note: Prompt said data/knowledge/graph.json but discovery showed data/graph.json
GRAPH_JSON = Path(os.environ.get("LIBRARIAN_GRAPH_JSON", PROJECTS_ROOT / "project-tracker/data/graph.json"))

def validate_paths():
    """Validate that configured paths exist."""
    if not PROJECTS_ROOT.exists():
        logger.warning(f"PROJECTS_ROOT does not exist: {PROJECTS_ROOT}")
    
    if not TRACKER_DB.exists():
        logger.warning(f"TRACKER_DB does not exist: {TRACKER_DB}")
        
    if not GRAPH_JSON.exists():
        logger.warning(f"GRAPH_JSON does not exist: {GRAPH_JSON}")

# Run validation on import
validate_paths()
