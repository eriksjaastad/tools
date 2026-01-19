#!/usr/bin/env python3
"""
Phase 1.7: Test Manager → Worker file write delegation.
Verifies that a PROPOSAL_READY message triggers the watchdog pipeline and creates a draft.
"""

import os
import sys
import json
import shutil
import asyncio
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.proposal_converter import convert_proposal
from src.watchdog import load_contract, save_contract, transition, log_transition
from src.git_manager import GitManager

async def test_delegation():
    print("Testing Manager -> Worker delegation...")
    
    # Setup temp directories
    base_dir = Path("temp_test_delegation")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    handoff_dir = base_dir / "_handoff"
    handoff_dir.mkdir()
    drafts_dir = handoff_dir / "drafts"
    drafts_dir.mkdir()
    project_dir = base_dir / "project"
    project_dir.mkdir()
    
    # Create dummy server files to satisfy config validation
    hub_dummy = project_dir / "dummy_hub.js"
    hub_dummy.write_text("// dummy")
    mcp_dummy = project_dir / "dummy_mcp.js"
    mcp_dummy.write_text("// dummy")
    
    # Init git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True, capture_output=True)
    (project_dir / "README.md").write_text("# Test Project")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=project_dir, check=True, capture_output=True)
    
    # 1. Create a proposal file
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    proposal_content = f"""# Proposal: Test Delegation
**Target Project:** DelegationTest
**Complexity:** trivial
## 4. Target Output
- `src/output.txt`
## 5. Requirements
- [ ] Write 'Hello from Worker'
## 7. Constraints
- **Allowed paths:** `src/`
"""
    proposal_path.write_text(proposal_content)
    
    # 2. Mock environment and config
    with patch.dict(os.environ, {
        "HANDOFF_DIR": str(handoff_dir.absolute()),
        "HUB_SERVER_PATH": str(hub_dummy.absolute()),
        "MCP_SERVER_PATH": str(mcp_dummy.absolute()),
        "UAS_SQLITE_BUS": "1"
    }):
        # Force reload config with mocked env
        import src.config
        src.config._config = None
        
        # 3. Convert proposal to contract
        contract_path = convert_proposal(proposal_path, handoff_dir)
        contract = load_contract(contract_path)
        contract["git"]["repo_root"] = str(project_dir.absolute())
        save_contract(contract, contract_path)
        
        # 4. Mock the Worker implementation response
        code_resp = {
            "content": [
                {"type": "text", "text": "Here is code:\n```python\nHello from Worker\n```"}
            ]
        }
        
        mock_mcp_instance = MagicMock()
        mock_mcp_instance.call_tool.return_value = code_resp
        
        mock_mcp_class = MagicMock()
        mock_mcp_class.return_value.__enter__.return_value = mock_mcp_instance
        
        # 5. Run the watchdog run-implementer command
        from src.watchdog import main as watchdog_main
        
        prev_cwd = os.getcwd()
        os.chdir(project_dir.absolute())
        try:
            with patch("src.watchdog.MCPClient", mock_mcp_class), \
                 patch("src.watchdog.check_hub_available", return_value=True):
                
                # Setup task (branching)
                watchdog_main(["watchdog.py", "setup-task"])
                
                # Run implementer
                watchdog_main(["watchdog.py", "run-implementer"])
        finally:
            os.chdir(prev_cwd)
    
    # 6. Verify result
    output_file = project_dir.absolute() / "src" / "output.txt"
    if output_file.exists():
        content = output_file.read_text()
        print(f"File content: {content}")
        if "Hello from Worker" in content:
            print("✓ Manager → Worker file write: PASS")
        else:
            print(f"✗ Manager → Worker file write: FAIL (Wrong content: {content})")
            sys.exit(1)
    else:
        print(f"✗ Manager → Worker file write: FAIL (File not created at {output_file})")
        # List files for debugging
        print(f"Files in project: {list(project_dir.glob('**/*'))}")
        sys.exit(1)
        
    # Cleanup
    shutil.rmtree(base_dir)

if __name__ == "__main__":
    asyncio.run(test_delegation())
