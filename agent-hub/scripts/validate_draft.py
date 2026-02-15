#!/usr/bin/env python3
"""
Simple draft validator - checks if worker actually did something.

This is NOT a code review. It just checks:
1. Did the worker create any draft files?
2. Are the drafts non-empty?
3. Do they contain actual content (not just error messages)?

This runs automatically after worker completes.
"""

import json
from pathlib import Path
from datetime import datetime

def validate_drafts(task_id: str, handoff_dir: Path = None) -> dict:
    """
    Quick sanity check on drafts created by a worker.
    
    Returns:
        {
            "valid": bool,
            "draft_count": int,
            "total_bytes": int,
            "issues": [str],
            "drafts": [str]
        }
    """
    if handoff_dir is None:
        handoff_dir = Path("_handoff")
    
    drafts_dir = handoff_dir / "drafts"
    
    if not drafts_dir.exists():
        return {
            "valid": False,
            "draft_count": 0,
            "total_bytes": 0,
            "issues": ["Drafts directory does not exist"],
            "drafts": []
        }
    
    # Find drafts for this task
    draft_files = list(drafts_dir.glob(f"*.{task_id}.draft"))
    
    if not draft_files:
        return {
            "valid": False,
            "draft_count": 0,
            "total_bytes": 0,
            "issues": [f"No draft files found for task {task_id}"],
            "drafts": []
        }
    
    issues = []
    total_bytes = 0
    draft_paths = []
    
    for draft_file in draft_files:
        draft_paths.append(str(draft_file))
        
        # Check if file is empty
        size = draft_file.stat().st_size
        total_bytes += size
        
        if size == 0:
            issues.append(f"{draft_file.name} is empty")
            continue
        
        # Check if it's just an error message or placeholder
        content = draft_file.read_text()
        
        # Common error patterns
        error_patterns = [
            "error:",
            "failed:",
            "exception:",
            "traceback",
            "no such file",
            "permission denied"
        ]
        
        # Hallucination/placeholder patterns
        placeholder_patterns = [
            "<paste",
            "<the ",  # "<the updated content>"
            "paste the",
            "insert code here",
            "add code here",
            "your code here",
            "code goes here",
            "implementation here",
            "todo:",
            "fixme:",
            "placeholder",
            "# ...",
            "// ...",
        ]
        
        content_lower = content.lower()
        
        # Check for error messages
        if any(pattern in content_lower for pattern in error_patterns):
            # Check if it's ONLY errors (no actual content)
            if len(content.strip()) < 100:
                issues.append(f"{draft_file.name} appears to contain only error messages")
        
        # Check for placeholders/hallucinations
        if any(pattern in content_lower for pattern in placeholder_patterns):
            issues.append(f"{draft_file.name} contains placeholder text instead of actual code")
        
        # Check if file is suspiciously small for code
        if size < 50 and draft_file.suffix in ['.py', '.js', '.ts', '.go']:
            issues.append(f"{draft_file.name} is suspiciously small ({size} bytes) for a code file")
    
    # Determine if valid
    valid = len(draft_files) > 0 and total_bytes > 0 and len(issues) == 0
    
    return {
        "valid": valid,
        "draft_count": len(draft_files),
        "total_bytes": total_bytes,
        "issues": issues,
        "drafts": draft_paths
    }

def write_notification(task_id: str, validation_result: dict, handoff_dir: Path = None):
    """Write a notification file for Floor Manager."""
    if handoff_dir is None:
        handoff_dir = Path("_handoff")
    
    notification = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "status": "ready_for_review" if validation_result["valid"] else "needs_attention",
        "validation": validation_result
    }
    
    notification_file = handoff_dir / f"notification_{task_id}.json"
    notification_file.write_text(json.dumps(notification, indent=2))
    
    return notification_file

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python validate_draft.py <task_id>")
        sys.exit(1)
    
    task_id = sys.argv[1]
    result = validate_drafts(task_id)
    
    print(json.dumps(result, indent=2))
    
    if result["valid"]:
        print(f"\n✅ Validation passed: {result['draft_count']} draft(s), {result['total_bytes']} bytes")
        notification_file = write_notification(task_id, result)
        print(f"📬 Notification written: {notification_file}")
    else:
        print(f"\n❌ Validation failed:")
        for issue in result["issues"]:
            print(f"  - {issue}")
        notification_file = write_notification(task_id, result)
        print(f"📬 Notification written: {notification_file}")
        sys.exit(1)
