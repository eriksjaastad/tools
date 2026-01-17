import json
import os
import subprocess
from pathlib import Path
import pytest
from src.proposal_converter import convert_proposal
from src.watchdog import (
    load_contract, save_contract, transition, 
    check_circuit_breakers, trigger_halt, write_stall_report,
    log_transition
)
from src.git_manager import GitManager

def test_full_pipeline_flow(handoff_dir, project_dir):
    # 0. Initialize project_dir as a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "e2e@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "E2E User"], cwd=project_dir, check=True)
    
    # Add .gitignore for _handoff
    (project_dir / ".gitignore").write_text("_handoff/\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=project_dir, check=True)
    
    (project_dir / "init.txt").write_text("start")
    subprocess.run(["git", "add", "init.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True)
    
    gm = GitManager(project_dir)

    # 1. Start with a proposal
    proposal_content = f"""# Proposal: Git Test Task
**Target Project:** E2E-Git
**Complexity:** trivial
## 3. Source Files
- `src/old.py`
## 4. Target Output
- `src/new.py`
## 5. Requirements
- [ ] Requirement 1
## 6. Acceptance Criteria
- [ ] Criterion 1
## 7. Constraints
- **Allowed paths:** `src/`
- **Forbidden paths:** `.env`
- **Deletions allowed:** No
- **Max diff size:** 100 lines
"""
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    proposal_path.write_text(proposal_content)
    
    # 2. Convert to contract
    contract_path = convert_proposal(proposal_path, handoff_dir)
    assert contract_path.exists()
    contract = load_contract(contract_path)
    # Update repo_root in contract to match project_dir
    contract["git"]["repo_root"] = str(project_dir)
    save_contract(contract, contract_path)
    
    # 3. Setup Git Branch (Simulating CLI call)
    branch = gm.create_task_branch(contract["task_id"], "main")
    contract["git"]["task_branch"] = branch
    contract["git"]["base_commit"] = gm.get_current_commit()
    save_contract(contract, contract_path)
    
    assert branch == f"task/{contract['task_id']}"
    
    # 4. Simulate Implementer
    old_status = contract["status"]
    new_status, reason = transition(old_status, "lock_acquired", contract)
    contract["status"] = new_status
    save_contract(contract, contract_path)
    log_transition(contract, "lock_acquired", old_status, git_manager=gm)
    
    # Write mock output
    (project_dir / "src").mkdir(exist_ok=True)
    target_file = project_dir / "src/new.py"
    target_file.write_text("print('hello git')")
    
    # Transition to local review and checkpoint
    old_status = contract["status"]
    new_status, reason = transition(old_status, "code_written", contract)
    contract["status"] = new_status
    save_contract(contract, contract_path)
    log_transition(contract, "code_written", old_status, git_manager=gm)
    
    # Verify commit exists for code_written
    res = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=project_dir, capture_output=True, text=True)
    assert "code_written" in res.stdout
    
    # 5. Simulate Local Review (Pass)
    contract["handoff_data"]["local_review_passed"] = True
    old_status = contract["status"]
    new_status, reason = transition(old_status, "local_pass", contract)
    contract["status"] = new_status
    save_contract(contract, contract_path)
    log_transition(contract, "local_pass", old_status, git_manager=gm)
    
    # 6. Simulate Judge (Pass)
    old_status = contract["status"]
    new_status, reason = transition(old_status, "review_started", contract)
    contract["status"] = new_status
    log_transition(contract, "review_started", old_status, git_manager=gm)
    
    # Judge complete
    old_status = contract["status"]
    new_status, reason = transition(old_status, "judge_complete", contract)
    contract["status"] = new_status
    log_transition(contract, "judge_complete", old_status, git_manager=gm)
    
    # Audit verdict and transition to merged
    contract["handoff_data"]["judge_verdict"] = "PASS"
    old_status = contract["status"]
    new_status, reason = transition(old_status, "pass", contract)
    contract["status"] = new_status
    save_contract(contract, contract_path)
    # Don't call log_transition for merged here yet, because we do the merge next
    
    # 7. Finalize (Merge)
    gm.merge_task_branch(contract["task_id"], "main")
    
    # Verify we are on main and file exists
    res = subprocess.run(["git", "branch", "--show-current"], cwd=project_dir, capture_output=True, text=True)
    assert res.stdout.strip() == "main"
    assert (project_dir / "src/new.py").exists()

def test_git_merge_conflict_halt(handoff_dir, project_dir):
    # Initialize repo
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "conflict@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Conflict User"], cwd=project_dir, check=True)
    
    common_file = project_dir / "common.txt"
    common_file.write_text("base")
    subprocess.run(["git", "add", "common.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=project_dir, check=True)
    
    gm = GitManager(project_dir)
    task_id = "CONFLICT-TASK"
    
    # Create task branch
    gm.create_task_branch(task_id)
    common_file.write_text("task change")
    gm.checkpoint_commit(task_id, "done", "ready")
    
    # Change main
    subprocess.run(["git", "checkout", "main"], cwd=project_dir, check=True)
    common_file.write_text("main change")
    subprocess.run(["git", "add", "common.txt"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "main change"], cwd=project_dir, check=True)
    
    # Try to merge and catch conflict
    contract_data = {
        "task_id": task_id,
        "status": "merged",
        "timestamps": {"updated_at": "2026-01-17T00:00:00Z", "created_at": "2026-01-17T00:00:00Z"},
        "git": {"repo_root": str(project_dir), "base_branch": "main"},
        "limits": {"timeout_minutes": {"any": 10}},
        "breaker": {}
    }
    contract_path = handoff_dir / "TASK_CONTRACT.json"
    with open(contract_path, "w") as f:
        json.dump(contract_data, f)
        
    contract = load_contract(contract_path)
    
    try:
        gm.merge_task_branch(task_id, "main")
    except Exception as e:
        trigger_halt(contract, f"Merge error: {e}", "git_conflict", contract_path)
        
    assert (handoff_dir / "TASK_CONTRACT.json.lock").exists()
    assert (handoff_dir / "ERIK_HALT.md").exists()
    halt_content = (handoff_dir / "ERIK_HALT.md").read_text()
    assert "CONFLICT-TASK" in halt_content
    assert "git_conflict" in halt_content

from unittest.mock import MagicMock, patch

def test_pipeline_with_mocked_mcp(handoff_dir, project_dir, monkeypatch):
    monkeypatch.setenv("HANDOFF_DIR", str(handoff_dir))
    
    # Initialize Repo
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "mcp@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "MCP User"], cwd=project_dir, check=True)
    (project_dir / ".gitignore").write_text("_handoff/\n__pycache__/\n.pytest_cache/\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True)
    
    # 1. Create Proposal
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    proposal_path.write_text("""# Proposal: MCP Task
**Target Project:** MCP-Proj
**Complexity:** trivial
## 3. Source Files
## 4. Target Output
- `src/generated.py`
## 5. Requirements
- [ ] Do work
## 6. Acceptance Criteria
- [ ] Works
## 7. Constraints
- **Allowed paths:** `src/`
""")
    
    # 2. Convert and Setup
    contract_path = convert_proposal(proposal_path, handoff_dir)
    contract = load_contract(contract_path)
    contract["git"]["repo_root"] = str(project_dir)
    save_contract(contract, contract_path)
    
    gm = GitManager(project_dir)
    branch = gm.create_task_branch(contract["task_id"], "main")
    contract["git"]["task_branch"] = branch
    save_contract(contract, contract_path)
    
    # Mock MCP Client Context Manager
    mock_mcp_instance = MagicMock()
    mock_mcp_class = MagicMock()
    mock_mcp_class.return_value.__enter__.return_value = mock_mcp_instance
    
    # Mock Responses
    # Health Check
    # Implementer
    code_resp = '{"content": [{"type": "text", "text": "Here is code:\\n```python\\nprint(\'AI generated\')\\n```"}]}'
    # Local Review
    review_resp = '{"content": [{"type": "text", "text": "{\\"verdict\\": \\"PASS\\", \\"issues\\": []}"}]}'
    
    mock_mcp_instance.call_tool.side_effect = [
        {"content": []}, # Health check (Implementer)
        json.loads(code_resp), # Implementer result
        {"content": []}, # Health check (Reviewer)
        json.loads(review_resp) # Reviewer result
    ]
    
    prev_cwd = os.getcwd()
    os.chdir(project_dir)
    try:
        with patch("src.watchdog.MCPClient", mock_mcp_class):
            from src.watchdog import main
    
            def run_wd(cmd):
                main(["watchdog.py", cmd])
    
            # 3. Run Implementer
            run_wd("run-implementer")
            
            contract = load_contract(contract_path)
            assert contract["status"] == "pending_local_review"
            assert contract["handoff_data"]["changed_files"] == ["src/generated.py"]
            assert (project_dir / "src/generated.py").read_text() == "print('AI generated')\n"
            
            # 4. Run Local Review
            run_wd("run-local-review")
            
            contract = load_contract(contract_path)
            assert contract["status"] == "pending_judge_review"
            assert contract["handoff_data"]["local_review_passed"] is True
            assert (handoff_dir / "REVIEW_REQUEST.md").exists()
            
    finally:
        os.chdir(prev_cwd)

def test_stall_recovery(handoff_dir, project_dir, monkeypatch):
    monkeypatch.setenv("HANDOFF_DIR", str(handoff_dir))
    
    # Setup
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "mcp@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "MCP User"], cwd=project_dir, check=True)
    (project_dir / ".gitignore").write_text("_handoff/\n__pycache__/\n.pytest_cache/\n")
    (project_dir / "init.txt").write_text("root")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True)
    
    # Proposal & Contract
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    proposal_content = """# Proposal: Stall Test
**Target Project:** Stall-Proj
## 4. Target Output
- `output.txt`
## 5. Requirements
- [ ] Recover from stall
"""
    proposal_path.write_text(proposal_content)
    contract_path = convert_proposal(proposal_path, handoff_dir)
    assert contract_path is not None, "Contract conversion failed"
    contract = load_contract(contract_path)
    contract["git"]["repo_root"] = str(project_dir)
    save_contract(contract, contract_path)
    
    gm = GitManager(project_dir)
    gm.create_task_branch(contract["task_id"])
    
    mock_mcp_instance = MagicMock()
    mock_mcp_class = MagicMock()
    mock_mcp_class.return_value.__enter__.return_value = mock_mcp_instance
    
    # Mock Response: Stall 1 (Empty), Stall 2 (Success)
    # 1. Health check (Attempt 1)
    # 2. Implementer (Attempt 1) -> Empty -> Stall -> Strike 1 -> Retry -> pending_implementer
    # 3. Health check (Attempt 2)
    # 4. Implementer (Attempt 2) -> Success
    
    mock_mcp_instance.call_tool.side_effect = [
        {"content": []}, 
        {"content": [{"type": "text", "text": ""}]}, # Empty
        {"content": []},
        {"content": [{"type": "text", "text": "code:\n```python\nprint(1)\n```"}]}
    ]
    
    prev_cwd = os.getcwd()
    os.chdir(project_dir)
    try:
        with patch("src.watchdog.MCPClient", mock_mcp_class):
             from src.watchdog import main
             
             # Attempt 1
             main(["watchdog.py", "run-implementer"])
             
             contract = load_contract(contract_path)
             assert contract["status"] == "pending_implementer"
             assert contract["attempt"] == 2
             assert "Retry after stall" in contract["status_reason"]
             
             # Attempt 2
             main(["watchdog.py", "run-implementer"])
             
             contract = load_contract(contract_path)
             assert contract["status"] == "pending_local_review"
             assert contract["attempt"] == 2  # Still 2, succeeded
    finally:
        os.chdir(prev_cwd)

def test_critical_flaw_detection(handoff_dir, project_dir, monkeypatch):
    monkeypatch.setenv("HANDOFF_DIR", str(handoff_dir))
    
    # Setup
    subprocess.run(["git", "init", "-b", "main"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "mcp@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "MCP User"], cwd=project_dir, check=True)
    (project_dir / ".gitignore").write_text("_handoff/\n__pycache__/\n.pytest_cache/\n")
    (project_dir / "init.txt").write_text("root")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True)
    
    proposal_path = handoff_dir / "PROPOSAL_FINAL.md"
    proposal_content = """# Proposal: Critical
**Target Project:** Crit-Proj
## 4. Target Output
- `gen.py`
## 5. Requirements
- [ ] No bugs
"""
    proposal_path.write_text(proposal_content)
    contract_path = convert_proposal(proposal_path, handoff_dir)
    assert contract_path is not None
    contract = load_contract(contract_path)
    contract["git"]["repo_root"] = str(project_dir)
    contract["status"] = "pending_local_review"
    # Create changed files to review
    contract["handoff_data"]["changed_files"] = ["gen.py"]
    save_contract(contract, contract_path)
    
    gm = GitManager(project_dir)
    gm.create_task_branch(contract["task_id"])
    (project_dir / "gen.py").write_text("API_KEY = '123'")
    
    mock_mcp_instance = MagicMock()
    mock_mcp_class = MagicMock()
    mock_mcp_class.return_value.__enter__.return_value = mock_mcp_instance
    
    # Mock Critical Flaw
    crit_resp = '{"verdict": "FAIL", "critical": true, "issues": ["Found API_KEY"]}'
    mock_mcp_instance.call_tool.return_value = {"content": [{"type": "text", "text": crit_resp}]}
    
    prev_cwd = os.getcwd()
    os.chdir(project_dir)
    try:
        with patch("src.watchdog.MCPClient", mock_mcp_class):
             from src.watchdog import main
             
             # Expect SystemExit due to halt
             with pytest.raises(SystemExit):
                 main(["watchdog.py", "run-local-review"])
    finally:
        os.chdir(prev_cwd)
             
    # Check artifacts
    assert (handoff_dir / "TASK_CONTRACT.json.lock").exists()
    assert (handoff_dir / "ERIK_HALT.md").exists()
    assert "Found API_KEY" in (handoff_dir / "ERIK_HALT.md").read_text()

