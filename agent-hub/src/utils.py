import json
import os
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict

# Costs per 1,000,000 tokens (1M)
MODEL_COST_MAP = {
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-code-cli": {"input": 3.00, "output": 15.00}, # Assuming Sonnet usage
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "coding:current": {"input": 0.0, "output": 0.0},     # Local Ollama alias - always free
    "embedding:current": {"input": 0.0, "output": 0.0},  # Local Ollama alias - always free
}

logger = logging.getLogger(__name__)

def atomic_write(path: Path, content: str) -> None:
    """
    Writes content to a file atomically by writing to a temporary file 
    and then renaming it to the target path.
    """
    if os.environ.get("AGENT_HUB_DRY_RUN") == "1":
        logger.info(f"[DRY-RUN] atomic_write to {path}")
        return
        
    temp_path = path.with_suffix(path.suffix + ".tmp")
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
            # Flush to disk if possible
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except (PermissionError, IOError) as e:
        # Handle disk full or permission errors specifically for Prompt 3.2
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {temp_path}: {e}")
        raise e
    except Exception as e:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {temp_path}: {e}")
        raise e

def atomic_write_json(path: Path, data: dict) -> None:
    """
    Writes a dictionary to a JSON file atomically.
    """
    content = json.dumps(data, indent=2)
    atomic_write(path, content)

def safe_read(path: Path, retries: int = 3) -> Optional[str]:
    """
    Reads content from a file safely. Returns None if file doesn't exist.
    Wait briefly if a .tmp version exists to avoid partial reads.
    Retries aggressively for common OS-level issues.
    """
    if path is None:
        return None
    temp_path = path.with_suffix(path.suffix + ".tmp")
    
    for attempt in range(retries):
        # If temp file exists, someone is currently writing. Wait briefly.
        if temp_path.exists():
            time.sleep(0.2 * (attempt + 1))
            continue
            
        if not path.exists():
            return None
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except (FileNotFoundError, PermissionError):
            if attempt == retries - 1:
                return None
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(0.5 * (attempt + 1))
            
    return None

def archive_file(path: Path, archive_dir: Path, suffix: str = "") -> Path:
    """
    Moves a file to the archive directory with an optional suffix.
    """
    if not archive_dir.exists():
        archive_dir.mkdir(parents=True, exist_ok=True)
        
    if os.environ.get("AGENT_HUB_DRY_RUN") == "1":
        logger.info(f"[DRY-RUN] archive_file {path} to {archive_dir}")
        return path

    if suffix:
        new_name = f"{path.stem}_{suffix}{path.suffix}"
    else:
        new_name = path.name
        
    target_path = archive_dir / new_name
    
    # Ensure target path is unique if file already exists in archive
    counter = 1
    original_target_path = target_path
    while target_path.exists():
        target_path = original_target_path.parent / f"{original_target_path.stem}_{counter}{original_target_path.suffix}"
        counter += 1
        
    os.replace(path, target_path)
    return target_path

def count_lines(content: str) -> int:
    """Helper to count lines in string."""
    if not content:
        return 0
    return len(content.splitlines())

def get_sha256(content: str) -> str:
    """Returns SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
