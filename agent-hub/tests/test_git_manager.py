import pytest
import subprocess
import os
from pathlib import Path
from src.git_manager import GitManager, GitError, GitConflictError

@pytest.fixture
def temp_repo(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Initialize git
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    
    # Create initial commit
    (repo_dir / "README.md").write_text("initial")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_dir, check=True)
    
    return repo_dir

def test_create_task_branch(temp_repo):
    gm = GitManager(temp_repo)
    task_id = "TASK-123"
    branch_name = gm.create_task_branch(task_id)
    
    assert branch_name == "task/TASK-123"
    
    # Verify current branch
    res = subprocess.run(["git", "branch", "--show-current"], cwd=temp_repo, capture_output=True, text=True)
    assert res.stdout.strip() == branch_name

def test_checkpoint_commit(temp_repo):
    gm = GitManager(temp_repo)
    task_id = "TASK-123"
    gm.create_task_branch(task_id)
    
    (temp_repo / "new_file.py").write_text("print('test')")
    commit_hash = gm.checkpoint_commit(task_id, "in_progress", "code_written")
    
    assert commit_hash is not None
    
    # Verify commit message
    res = subprocess.run(["git", "log", "-1", "--pretty=%s"], cwd=temp_repo, capture_output=True, text=True)
    assert "[TASK: TASK-123] Transition: in_progress (Event: code_written)" in res.stdout

def test_merge_success(temp_repo):
    gm = GitManager(temp_repo)
    task_id = "TASK-SUCCESS"
    gm.create_task_branch(task_id)
    
    (temp_repo / "feature.txt").write_text("new feature")
    gm.checkpoint_commit(task_id, "done", "merge_ready")
    
    gm.merge_task_branch(task_id, "main")
    
    # Switch to main and verify file exists
    subprocess.run(["git", "checkout", "main"], cwd=temp_repo, check=True)
    assert (temp_repo / "feature.txt").exists()

def test_merge_conflict(temp_repo):
    gm = GitManager(temp_repo)
    task_id = "TASK-CONFLICT"
    
    # Create a conflict source in main
    (temp_repo / "common.txt").write_text("main version")
    subprocess.run(["git", "add", "common.txt"], cwd=temp_repo, check=True)
    subprocess.run(["git", "commit", "-m", "add common"], cwd=temp_repo, check=True)
    
    gm.create_task_branch(task_id)
    (temp_repo / "common.txt").write_text("task version")
    gm.checkpoint_commit(task_id, "done", "ready")
    
    # Mutate main to cause conflict
    subprocess.run(["git", "checkout", "main"], cwd=temp_repo, check=True)
    (temp_repo / "common.txt").write_text("main version changed")
    subprocess.run(["git", "add", "common.txt"], cwd=temp_repo, check=True)
    subprocess.run(["git", "commit", "-m", "mutate common"], cwd=temp_repo, check=True)
    
    with pytest.raises(GitConflictError):
        gm.merge_task_branch(task_id, "main")
