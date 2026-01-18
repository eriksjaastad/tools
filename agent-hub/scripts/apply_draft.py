#!/usr/bin/env python3
"""Apply an accepted draft to its original file."""

import json
import shutil
import sys
import os
from pathlib import Path

def apply_draft(submission_path: str) -> dict:
    """Apply draft changes to original file."""
    try:
        path = Path(submission_path)
        if not path.exists():
            return {"success": False, "error": f"Submission file not found: {submission_path}"}

        submission = json.loads(path.read_text())

        draft_path = Path(submission["draft_path"])
        original_path = Path(submission["original_path"])

        if not draft_path.exists():
            return {"success": False, "error": f"Draft file not found: {draft_path}"}

        # Backup original (just in case)
        backup_path = original_path.with_suffix(original_path.suffix + ".backup")
        shutil.copy2(original_path, backup_path)

        # Apply draft atomically (copy to temp then rename)
        temp_path = original_path.with_suffix(original_path.suffix + ".tmp")
        shutil.copy2(draft_path, temp_path)
        temp_path.replace(original_path)

        # Clean up
        if draft_path.exists():
            draft_path.unlink()
        if backup_path.exists():
            backup_path.unlink()

        return {"success": True, "applied_to": str(original_path)}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_draft.py <submission_path>")
        sys.exit(1)
    
    result = apply_draft(sys.argv[1])
    print(json.dumps(result, indent=2))
    if not result["success"]:
        sys.exit(1)
