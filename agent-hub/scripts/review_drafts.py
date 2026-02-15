#!/usr/bin/env python3
"""
Review and apply drafts created by workers.

This script:
1. Scans _handoff/drafts/ for .draft files
2. For each draft, creates a simple contract
3. Calls claude_judge_review via MCP to get a verdict
4. If ACCEPT: applies the draft to the target location
5. If REJECT: logs the reason and deletes the draft
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def parse_draft_filename(draft_file: Path) -> dict:
    """
    Parse draft filename to extract original path and task ID.
    
    Format: {sanitized_path}.{task_id}.draft
    Example: __Users__eriksjaastad__projects__smart-invoice-workflow__AGENT_HUB_TEST.txt.task_simple_test.draft
    """
    name = draft_file.stem  # Remove .draft
    parts = name.rsplit('.', 1)
    
    if len(parts) != 2:
        return None
    
    sanitized_path, task_id = parts
    
    # Convert sanitized path back to real path
    # __Users__eriksjaastad__projects__... -> /Users/eriksjaastad/projects/...
    original_path = sanitized_path.replace('__', '/')
    
    return {
        "draft_path": str(draft_file),
        "original_path": original_path,
        "task_id": task_id
    }

def create_simple_contract(draft_info: dict, task_file: Path) -> dict:
    """Create a minimal contract for Claude review."""
    
    # Read task file if it exists
    objective = "Review draft file"
    if task_file.exists():
        content = task_file.read_text()
        # Extract objective from task file
        for line in content.split('\n'):
            if line.startswith('**Objective:**') or line.startswith('## Objective'):
                objective = line.split(':', 1)[1].strip() if ':' in line else objective
                break
    
    return {
        "task_id": draft_info["task_id"],
        "objective": objective,
        "target_files": [draft_info["original_path"]],
        "acceptance_criteria": [
            "File exists and is syntactically valid",
            "Content addresses the task objective"
        ],
        "draft_files": [draft_info["draft_path"]]
    }

def review_draft_with_claude(contract_path: Path) -> dict:
    """Call claude_judge_review via claude-mcp-go MCP server."""
    
    # Start the MCP server
    mcp_server = Path(__file__).parent.parent.parent / "claude-mcp-go" / "bin" / "claude-mcp-go"
    
    if not mcp_server.exists():
        return {"success": False, "error": "claude-mcp-go binary not found"}
    
    # Prepare JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "claude_judge_review",
            "arguments": {
                "contract_path": str(contract_path),
                "report_dir": "_handoff",
                "timeout_seconds": 300
            }
        }
    }
    
    try:
        # Call MCP server
        proc = subprocess.Popen(
            [str(mcp_server)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send initialize handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "draft-reviewer", "version": "1.0.0"}
            }
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()  # Read init response
        
        # Send initialized notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()
        
        # Send actual request
        proc.stdin.write(json.dumps(request) + "\n")
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        response = json.loads(response_line)
        
        proc.terminate()
        proc.wait()
        
        if "result" in response:
            return response["result"]
        else:
            return {"success": False, "error": response.get("error", "Unknown error")}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def apply_draft(draft_path: Path, original_path: Path) -> bool:
    """Apply draft to original location."""
    try:
        # Create parent directory if needed
        original_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy draft to original location
        import shutil
        shutil.copy2(draft_path, original_path)
        
        # Delete draft
        draft_path.unlink()
        
        return True
    except Exception as e:
        print(f"Error applying draft: {e}")
        return False

def main():
    handoff_dir = Path("_handoff")
    drafts_dir = handoff_dir / "drafts"
    
    if not drafts_dir.exists():
        print("No drafts directory found")
        return
    
    # Find all .draft files
    draft_files = list(drafts_dir.glob("*.draft"))
    
    if not draft_files:
        print("No draft files found")
        return
    
    print(f"Found {len(draft_files)} draft file(s) to review\n")
    
    for draft_file in draft_files:
        print(f"Reviewing: {draft_file.name}")
        
        # Parse filename
        draft_info = parse_draft_filename(draft_file)
        if not draft_info:
            print(f"  ❌ Could not parse filename, skipping\n")
            continue
        
        # Find corresponding task file
        task_file = handoff_dir / f"{draft_info['task_id']}.md"
        
        # Create contract
        contract = create_simple_contract(draft_info, task_file)
        contract_path = handoff_dir / f"contract_{draft_info['task_id']}.json"
        contract_path.write_text(json.dumps(contract, indent=2))
        
        # Review with Claude
        print(f"  📋 Calling Claude for review...")
        result = review_draft_with_claude(contract_path)
        
        if not result.get("success"):
            print(f"  ❌ Review failed: {result.get('error')}")
            contract_path.unlink()
            continue
        
        # Read verdict from report
        report_path = handoff_dir / "JUDGE_REPORT.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            verdict = report.get("verdict", "UNKNOWN")
            
            print(f"  🔍 Verdict: {verdict}")
            
            if verdict == "ACCEPT":
                # Apply draft
                original_path = Path(draft_info["original_path"])
                if apply_draft(draft_file, original_path):
                    print(f"  ✅ Applied to: {original_path}\n")
                else:
                    print(f"  ❌ Failed to apply draft\n")
            else:
                # Reject - just log it
                print(f"  ❌ Rejected - see {report_path} for details\n")
                # Optionally delete the draft
                # draft_file.unlink()
        else:
            print(f"  ⚠️  No report generated\n")
        
        # Cleanup
        contract_path.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
