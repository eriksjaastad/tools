import subprocess
import os
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

class GitConflictError(Exception):
    """Raised when a git merge results in conflicts."""
    pass

class GitError(Exception):
    """Generic git operation error."""
    pass

class GitManager:
    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        if not (repo_root / ".git").exists():
            # In a real scenario we might want to check this, 
            # but for tests or initialization we might just assume it's a git repo.
            pass

    def _run_git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        mutating_cmds = ["add", "commit", "merge", "checkout", "branch", "clean", "reset"]
        is_dry_run = self.dry_run or os.environ.get("AGENT_HUB_DRY_RUN") == "1"
        if is_dry_run and args and args[0] in mutating_cmds:
            # Skip branch --list which is not mutating but starts with 'branch'
            if args[0] == "branch" and "--list" in args:
                pass
            else:
                logger.info(f"[DRY-RUN] git {' '.join(args)}")
                return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=check,
                timeout=60
            )
            return result
        except subprocess.CalledProcessError as e:
            raise GitError(f"Git command failed: {' '.join(e.cmd)}\nStdout: {e.stdout}\nStderr: {e.stderr}") from e

    def is_clean(self) -> bool:
        """Returns True if there are no uncommitted changes."""
        result = self._run_git(["status", "--porcelain"])
        return result.stdout.strip() == ""

    def create_task_branch(self, task_id: str, base_branch: str = "main") -> str:
        """
        Creates and switches to task/<task_id>.
        Ensures the repo is clean before starting.
        """
        if not self.is_clean():
            raise GitError("Repository is not clean. Commit or stash changes before creating a task branch.")
        
        branch_name = f"task/{task_id}"
        
        # Ensure we are on base branch first
        self._run_git(["checkout", base_branch])
        
        # Check if branch exists, if so just switch to it, otherwise create
        result = self._run_git(["branch", "--list", branch_name])
        if result.stdout.strip():
            self._run_git(["checkout", branch_name])
        else:
            self._run_git(["checkout", "-b", branch_name])
            
        return branch_name

    def checkpoint_commit(self, task_id: str, status: str, event: str, allowed_paths: Optional[List[str]] = None):
        """
        Adds changed files and commits with a standardized message.
        """
        if allowed_paths:
            for path in allowed_paths:
                # Add specifically allowed paths if they exist
                if (self.repo_root / path).exists():
                    self._run_git(["add", path])
        else:
            # Add all changes except what's ignored
            # We use 'git add -u' to only add tracked files or others? 
            # Requirements say "Adds all changed files (including _handoff/ if not ignored, but usually just target files)."
            # Better to be explicit or use 'git add .'
            self._run_git(["add", "."])
            
        # Check if there's anything to commit
        status_res = self._run_git(["status", "--porcelain"])
        if not status_res.stdout.strip():
            return None # Nothing to commit
            
        msg = f"[TASK: {task_id}] Transition: {status} (Event: {event})"
        self._run_git(["commit", "-m", msg])
        
        # Get commit hash
        rev_parse = self._run_git(["rev-parse", "HEAD"])
        return rev_parse.stdout.strip()

    def merge_task_branch(self, task_id: str, target_branch: str = "main"):
        """
        Switches to target branch and merges the task branch.
        """
        branch_name = f"task/{task_id}"
        
        # Switch to target branch
        self._run_git(["checkout", target_branch])
        
        # Try to merge
        try:
            self._run_git(["merge", branch_name])
        except GitError as e:
            if "conflict" in str(e).lower():
                raise GitConflictError(f"Merge conflict detected in task {task_id}") from e
            raise e

    def rollback_to_base(self, base_branch: str = "main"):
        """
        Aborts ongoing merges/reverts and switches back to base branch.
        """
        try:
            self._run_git(["merge", "--abort"], check=False)
        except Exception as e:
            logger.debug(f"Merge abort failed (likely no merge in progress): {e}")
            
        self._run_git(["checkout", base_branch])
        # Clean up any untracked files that might have been left over if appropriate
        # self._run_git(["clean", "-fd"], check=False)

    def get_current_commit(self) -> str:
        res = self._run_git(["rev-parse", "HEAD"])
        return res.stdout.strip()
