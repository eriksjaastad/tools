import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from .utils import atomic_write_json, safe_read, get_sha256, count_lines, MODEL_COST_MAP, atomic_write
from .git_manager import GitManager, GitError, GitConflictError
from .mcp_client import MCPClient, MCPError
from .worker_client import WorkerClient
from .hub_client import HubClient
from .config import get_config

_config = get_config()
MCP_SERVER_PATH = _config.mcp_server_path
HUB_SERVER_PATH = _config.hub_path

VALID_STATUSES = [
    "pending_implementer",
    "implementation_in_progress",
    "pending_local_review",
    "pending_judge_review",
    "judge_review_in_progress",
    "review_complete",
    "pending_rebuttal",
    "merged",
    "timeout_implementer",
    "timeout_judge",
    "erik_consultation"
]

class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""
    pass

def load_contract(path: Path) -> Dict[str, Any]:
    """Loads a contract from disk."""
    content = safe_read(path)
    if content is None:
        raise FileNotFoundError(f"Contract not found: {path}")
    return json.loads(content)

def save_contract(contract: Dict[str, Any], path: Path) -> None:
    """Atomic write of the contract with improved error handling and signal dispatch."""
    contract["timestamps"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        atomic_write_json(path, contract)
        
        # Signal Dispatch (Phase 8: Message Only)
        if contract.get("status") == "pending_judge_review":
            try:
                with MCPClient(HUB_SERVER_PATH) as mcp:
                    hub = HubClient(mcp)
                    hub.connect("floor_manager")
                    hub.send_message("judge", "REVIEW_NEEDED", {
                        "task_id": contract["task_id"],
                        "contract_path": str(path)
                    })
            except Exception as e:
                print(f"Warning: Failed to send MCP REVIEW_NEEDED: {e}")
                
    except (PermissionError, IOError) as e:
        raise e

def log_transition(contract: Dict[str, Any], event: str, old_status: str, log_dir: Path = Path("_handoff"), git_manager: Optional[GitManager] = None) -> None:
    """Logs a state transition to transition.ndjson with enriched context and creates a git checkpoint."""
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
        
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": contract["task_id"],
        "event": event,
        "old_status": old_status,
        "new_status": contract["status"],
        "status_reason": contract.get("status_reason", ""),
        "attempt": contract.get("attempt", 1),
        "cumulative_cost_usd": contract.get("breaker", {}).get("cost_usd", 0.0)
    }
    
    log_file = log_dir / "transition.ndjson"
    
    # NDJSON Rotation (Prompt 5.2)
    if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
        rotated = log_file.with_suffix(".ndjson.1")
        if rotated.exists():
            rotated.unlink() # Simple 1-file rotation for now
        os.rename(log_file, rotated)

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    # Git Checkpoint
    if git_manager:
        try:
            # Only commit if we have a task branch active
            # We skip committing if we just transitioned to 'merged' because that's handled by merge_task_branch
            if contract["status"] != "merged":
                allowed_paths = contract.get("constraints", {}).get("allowed_paths", [])
                git_manager.checkpoint_commit(
                    contract["task_id"], 
                    contract["status"], 
                    event,
                    allowed_paths=allowed_paths
                )
        except GitError:
            # In a real scenario, we might want to trigger a halt if git fails
            pass

def transition(state: str, event: str, contract: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (new_status, status_reason). Raises InvalidTransition if not allowed.
    """
    transitions = {
        ("pending_implementer", "lock_acquired"): 
            ("implementation_in_progress", "Implementer working"),
        ("implementation_in_progress", "code_written"): 
            ("pending_local_review", "Awaiting local syntax check"),
        ("implementation_in_progress", "timeout"): 
            ("timeout_implementer", "Implementer exceeded time limit"),
        ("timeout_implementer", "escalate"):
            ("erik_consultation", "Implementer stalled (Strike 2)"),
        ("timeout_implementer", "retry"):
            ("pending_implementer", "Retrying with reworked contract (Strike 1)"),
            
        ("pending_local_review", "local_pass"): 
            ("pending_judge_review", "Local review passed"),
        ("pending_local_review", "critical_flaw"): 
            ("erik_consultation", "Local reviewer found critical security flaw"),
            
        ("pending_judge_review", "review_started"):
            ("judge_review_in_progress", "Judge review in progress"),
            
        ("judge_review_in_progress", "judge_complete"):
            ("review_complete", "Judge review complete"),
        ("judge_review_in_progress", "timeout"):
            ("timeout_judge", "Judge exceeded time limit"),
        ("timeout_judge", "escalate"):
            ("erik_consultation", "Judge timed out"),
            
        ("review_complete", "pass"): 
            ("merged", "Task completed and merged"),
        ("review_complete", "fail_agree"): 
            ("pending_implementer", "Attempt failed, reworking"),
        ("review_complete", "fail_disagree"): 
            ("pending_rebuttal", "Floor Manager disagrees with Judge"),
        ("review_complete", "conditional"): 
            ("pending_implementer", "Minor fixes required"),
            
        ("pending_rebuttal", "rebuttal_limit_exceeded"):
            ("erik_consultation", "Rebuttal limit exceeded"),
        ("pending_rebuttal", "rebuttal_accepted"):
            ("pending_judge_review", "Rebuttal accepted, awaiting re-review"),
    }
    
    # Generic halt transition
    if event == "circuit_breaker_halt":
        return ("erik_consultation", "Circuit breaker triggered halt")

    key = (state, event)
    if key not in transitions:
        raise InvalidTransition(f"Cannot {event} from {state}")
    
    return transitions[key]

def acquire_lock(contract: Dict[str, Any], actor: str) -> bool:
    """
    Try to acquire lock. Returns False if held by another actor.
    """
    lock = contract.get("lock", {})
    now = datetime.now(timezone.utc)
    
    held_by = lock.get("held_by")
    expires_at = lock.get("expires_at")
    
    if held_by and expires_at:
        expires = datetime.fromisoformat(expires_at)
        if now < expires and held_by != actor:
            return False
            
    # Acquire or renew lock
    timeout = contract["limits"]["timeout_minutes"].get("implementer", 15)
    contract["lock"] = {
        "held_by": actor,
        "acquired_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=timeout)).isoformat()
    }
    return True

def release_lock(contract: Dict[str, Any]) -> None:
    """Release the lock."""
    contract["lock"] = {
        "held_by": None,
        "acquired_at": None,
        "expires_at": None
    }

def check_circuit_breakers(contract: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Returns (should_halt, reason). Checks all 9 triggers.
    """
    breaker = contract.get("breaker", {})
    limits = contract.get("limits", {})
    handoff = contract.get("handoff_data", {})
    history = contract.get("history", [])
    
    # 1. Rebuttal Limit Exceeded
    if breaker.get("rebuttal_count", 0) > limits.get("max_rebuttals", 2):
        return True, f"Trigger 1: Rebuttal limit exceeded ({breaker['rebuttal_count']}/{limits['max_rebuttals']})"
        
    # 2. Destructive Diff
    # Logic: if diff_lines_deleted / total_lines > 0.5
    diff_stats = handoff.get("diff_stats", {})
    deleted = diff_stats.get("lines_deleted", 0)
    target_file = contract.get("specification", {}).get("target_file")
    if deleted > 0 and target_file:
        file_path = Path(target_file)
        content = safe_read(file_path)
        if content:
            total_lines = count_lines(content) + deleted # Approx lines before edit
            if total_lines > 0 and (deleted / total_lines) > 0.5:
                return True, f"Trigger 2: Destructive diff detected ({deleted} lines deleted / {total_lines} total)"

    # 3. Logical Paradox
    if handoff.get("local_review_passed") == False and handoff.get("judge_verdict") == "PASS":
        return True, "Trigger 3: Logical Paradox: Local Review failed but Judge passed"
        
    # 4. Hallucination Loop
    # If the current file hash matches a hash that was previously rejected by a Judge verdict of "FAIL"
    current_hash = handoff.get("current_file_hash")
    if current_hash:
        for entry in history:
            if entry.get("file_hash") == current_hash and entry.get("verdict") == "FAIL":
                return True, "Trigger 4: Hallucination Loop - Hash match with previously failed attempt"

    # 5. GPT-Energy Nitpicking
    # If review_cycle_count >= 3 AND only style issues
    if breaker.get("review_cycle_count", 0) >= 3:
        judge_report_path = Path(handoff.get("judge_report_json", "_handoff/JUDGE_REPORT.json"))
        report_content = safe_read(judge_report_path)
        if report_content:
            try:
                report = json.loads(report_content)
                issues = report.get("blocking_issues", [])
                suggestions = report.get("suggestions", [])
                
                # Check if all issues/suggestions are style-related
                all_style = True
                STYLE_KEYWORDS = ["style", "formatting", "indentation", "spacing", "naming", "whitespace"]
                
                if not issues and not suggestions:
                    all_style = False # Should have been a PASS then?
                
                for issue in issues + suggestions:
                    desc = issue.get("description", "").lower()
                    if not any(k in desc for k in STYLE_KEYWORDS):
                        all_style = False
                        break
                
                if all_style:
                    return True, "Trigger 5: GPT-Energy Nitpicking - 3+ cycles of pure style issues"
            except json.JSONDecodeError:
                pass

    # 6. Timeout (Inactivity)
    now = datetime.now(timezone.utc)
    updated_at = datetime.fromisoformat(contract["timestamps"]["updated_at"])
    max_timeout = max(limits.get("timeout_minutes", {"any": 30}).values())
    if now > updated_at + timedelta(minutes=max_timeout * 2):
        return True, "Trigger 6: Task inactivity timeout"

    # 7. Budget Exceeded
    if breaker.get("cost_usd", 0) > limits.get("cost_ceiling_usd", 0.50):
        return True, f"Trigger 7: Cost ceiling exceeded (${breaker['cost_usd']})"
        
    # 8. Scope Creep
    if len(handoff.get("changed_files", [])) > 20:
        return True, "Trigger 8: Too many files changed (Scope Creep)"
        
    # 9. Review Cycle Limit
    if breaker.get("review_cycle_count", 0) > limits.get("max_review_cycles", 5):
        return True, f"Trigger 9: Review cycle limit exceeded ({breaker['review_cycle_count']})"
        
    # 10. Global Timeout (Prompt 3.2)
    created_at = datetime.fromisoformat(contract["timestamps"]["created_at"])
    if now > created_at + timedelta(hours=4):
        return True, "Global Timeout: Task exceeded 4 hour limit"

    return False, ""

def trigger_halt(contract: Dict[str, Any], reason: str, triggered_by: str, contract_path: Path) -> None:
    """Halt automation and notify Erik."""
    old_status = contract["status"]
    contract["status"] = "erik_consultation"
    contract["status_reason"] = reason
    
    if "breaker" not in contract:
        contract["breaker"] = {}
    contract["breaker"]["status"] = "tripped"
    contract["breaker"]["triggered_by"] = triggered_by
    contract["breaker"]["trigger_reason"] = reason
    
    save_contract(contract, contract_path)
    log_transition(contract, "circuit_breaker_tripped", old_status, log_dir=contract_path.parent)
    
    # Rename to .lock to signal halt
    lock_path = contract_path.with_suffix(".json.lock")
    if contract_path.exists():
        os.replace(contract_path, lock_path)
    
    write_halt_file(contract, reason, contract_path.parent)

def write_halt_file(contract: Dict[str, Any], reason: str, handoff_dir: Path) -> None:
    """Writes ERIK_HALT.md."""
    content = f"""# 🛑 AUTOMATION HALTED

**Task:** {contract['task_id']}
**Trigger:** {contract.get('breaker', {}).get('triggered_by', 'Unknown')}
**Time:** {datetime.now(timezone.utc).isoformat()}

## Reason
{reason}

## Action Required
Review the task state and resolve the conflict.
"""
    (handoff_dir / "ERIK_HALT.md").write_text(content, encoding="utf-8")

def write_stall_report(contract: Dict[str, Any], reason: str, handoff_dir: Path) -> None:
    """Writes STALL_REPORT.md for Strike 2 failures."""
    content = f"""# 🛑 STALL REPORT (Strike 2)

**Task:** {contract['task_id']}
**Time:** {datetime.now(timezone.utc).isoformat()}

## Summary
The local model has stalled twice on this task.

## Final Failure Reason
{reason}

## Action Required
Guidance needed from Erik.
"""
    (handoff_dir / "STALL_REPORT.md").write_text(content, encoding="utf-8")

def check_for_stop(hub_server_path: Path) -> None:
    """Check for STOP_TASK messages and exit if found."""
    try:
        with MCPClient(hub_server_path) as mcp:
            hub = HubClient(mcp)
            hub.connect("floor_manager")
            messages = hub.receive_messages()
            for msg in messages:
                if msg["type"] == "STOP_TASK":
                    print(f"Received STOP signal: {msg['payload']}")
                    import sys
                    sys.exit(0)
    except Exception:
        pass # Don't block if hub is down

def start_heartbeat(hub_server_path: Path, task_id: str, stop_event: threading.Event):
    """Background thread to emit heartbeats."""
    try:
        with MCPClient(hub_server_path) as mcp:
            hub = HubClient(mcp)
            hub.connect("floor_manager")
            while not stop_event.is_set():
                hub.emit_heartbeat(f"implementing {task_id}")
                time.sleep(30)
    except Exception:
        pass

def check_hub_available(hub_path: Path) -> bool:
    """Verify MCP hub is running before any operation."""
    try:
        with MCPClient(hub_path) as mcp:
            hub = HubClient(mcp)
            return hub.connect("health_check_watchdog")
    except Exception:
        return False

def update_cost(contract: Dict[str, Any], tokens_in: int, tokens_out: int, model: str) -> None:
    """Calculates and updates cost in the contract."""
    if "breaker" not in contract:
        contract["breaker"] = {}
    
    rates = MODEL_COST_MAP.get(model, {"input": 0.0, "output": 0.0})
    cost = (tokens_in / 1_000_000 * rates["input"]) + (tokens_out / 1_000_000 * rates["output"])
    
    contract["breaker"]["tokens_used"] = contract["breaker"].get("tokens_used", 0) + tokens_in + tokens_out
    contract["breaker"]["cost_usd"] = contract["breaker"].get("cost_usd", 0.0) + cost

def cleanup_task_files(task_id: str, handoff_dir: Path) -> None:
    """Moves task-related files to archive (Prompt 5.2)."""
    archive_dir = handoff_dir / "archive" / task_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Files to keep in _handoff: transition.ndjson
    # Files to archive: TASK_CONTRACT.json, JUDGE_REPORT.*, REVIEW_REQUEST.md, etc.
    patterns = [
        f"TASK_CONTRACT.json*",
        "JUDGE_REPORT.*",
        "REVIEW_REQUEST.md",
        "REVIEW_IN_PROGRESS.md",
        "REBUTTAL.md",
        "PROPOSAL_REJECTED.md"
    ]
    
    for pattern in patterns:
        for f in handoff_dir.glob(pattern):
            if f.is_file():
                os.replace(f, archive_dir / f.name)
    
    # Remove ERIK_HALT.md if it exists (resolved)
    halt_file = handoff_dir / "ERIK_HALT.md"
    if halt_file.exists():
        halt_file.unlink()

def print_status(contract: Dict[str, Any], path: Path) -> None:
    """Beautiful CLI status output (Prompt 5.3)."""
    print("=" * 60)
    print(f"TASK ID:   {contract['task_id']}")
    print(f"STATUS:    {contract['status'].upper()}")
    print(f"REASON:    {contract.get('status_reason', 'N/A')}")
    print("-" * 60)
    print(f"PROJECT:   {contract['project']}")
    print(f"COST:      ${contract.get('breaker', {}).get('cost_usd', 0.0):.4f}")
    print(f"TOKENS:    {contract.get('breaker', {}).get('tokens_used', 0)}")
    print(f"LOCATION:  {path}")
    print("=" * 60)

def main(argv):
    import sys
    
    if "--version" in argv or "-v" in argv:
        try:
            with open("skill.json", "r") as f:
                v = json.load(f).get("version", "unknown")
            print(f"floor-manager v{v}")
            sys.exit(0)
        except Exception as e:
            print(f"Error reading version: {e}")
            sys.exit(1)

    # Phase 8: Hub health check on startup
    config = get_config()
    
    # Phase 9: Config validation
    errors = config.validate()
    if errors:
        for e in errors:
            print(f"Config error: {e}")
        sys.exit(1)

    handoff_dir = config.handoff_dir
    
    if not check_hub_available(config.hub_path):
        print(f"Error: MCP Hub not available at {config.hub_path}. Start claude-mcp first.")
        sys.exit(1)
    
    if len(argv) > 1:
        cmd = argv[1]
        contract_path = handoff_dir / "TASK_CONTRACT.json"
        
        if cmd == "timeout-judge":
            check_for_stop(HUB_SERVER_PATH)
            if not contract_path.exists():
                print(f"Error: {contract_path} not found")
                sys.exit(1)
            
            contract = load_contract(contract_path)
            old_status = contract["status"]
            
            # Initialize GitManager
            repo_root = Path(contract.get("git", {}).get("repo_root", "."))
            gm = GitManager(repo_root)

            try:
                # Map 'timeout-judge' to 'timeout' event in 'judge_review_in_progress' state
                new_status, reason = transition(old_status, "timeout", contract)
                contract["status"] = new_status
                contract["status_reason"] = reason
                save_contract(contract, contract_path)
                log_transition(contract, "timeout", old_status, git_manager=gm)
                print(f"Status updated to: {new_status}")
            except InvalidTransition as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        elif cmd == "setup-task":
            check_for_stop(HUB_SERVER_PATH)
            # New command to initialize the git branch for a task
            if not contract_path.exists():
                print(f"Error: {contract_path} not found")
                sys.exit(1)
            
            contract = load_contract(contract_path)
            repo_root = Path(contract.get("git", {}).get("repo_root", "."))
            gm = GitManager(repo_root)
            
            try:
                branch = gm.create_task_branch(contract["task_id"], contract.get("git", {}).get("base_branch", "main"))
                contract["git"]["task_branch"] = branch
                contract["git"]["base_commit"] = gm.get_current_commit()
                save_contract(contract, contract_path)
                print(f"Task branch created: {branch}")
            except GitError as e:
                trigger_halt(contract, f"Git Setup Failed: {e}", "git_error", contract_path)
                print(f"Halted: {e}")
                sys.exit(1)

        elif cmd == "finalize-task":
            check_for_stop(HUB_SERVER_PATH)
            # Command to merge the task branch
            if not contract_path.exists():
                print(f"Error: {contract_path} not found")
                sys.exit(1)
                
            contract = load_contract(contract_path)
            if contract["status"] != "merged":
                print("Error: Task is not in 'merged' status")
                sys.exit(1)
                
            repo_root = Path(contract.get("git", {}).get("repo_root", "."))
            gm = GitManager(repo_root)
            
            try:
                gm.merge_task_branch(contract["task_id"], contract.get("git", {}).get("base_branch", "main"))
                print("Task merged successfully")
                
                # Cleanup (Prompt 5.2)
                cleanup_task_files(contract["task_id"], contract_path.parent)
                print(f"Archived task files to _handoff/archive/{contract['task_id']}")
                
            except GitConflictError as e:
                trigger_halt(contract, f"Merge Conflict: {e}", "git_conflict", contract_path)
                print(f"Halted: {e}")
                sys.exit(1)
            except GitError as e:
                trigger_halt(contract, f"Git Merge Failed: {e}", "git_error", contract_path)
                print(f"Halted: {e}")
                sys.exit(1)
        
        elif cmd == "run-implementer":
            # Command to invoke the Implementer (Qwen) via MCP
            if not contract_path.exists():
                print(f"Error: {contract_path} not found")
                sys.exit(1)
            
            contract = load_contract(contract_path)
            
            if contract["status"] != "pending_implementer":
                print(f"Error: Status is {contract['status']}, expected pending_implementer")
                sys.exit(1)
                
            # Acquire lock
            if not acquire_lock(contract, "watchdog-implementer"):
                print("Error: Could not acquire lock")
                sys.exit(1)
            save_contract(contract, contract_path)
            
            repo_root = Path(contract.get("git", {}).get("repo_root", "."))
            gm = GitManager(repo_root)

            try:
                # Initialize MCP/Worker
                with MCPClient(MCP_SERVER_PATH) as mcp:
                    worker = WorkerClient(mcp)
                    
                    if not worker.check_ollama_health():
                        trigger_halt(contract, "Ollama connection failed during health check", "ollama_unavailable", contract_path)
                        print("Halted: Ollama unavailable")
                        sys.exit(1)
                    
                    # Phase 8: Heartbeat and STOP check (Always on)
                    check_for_stop(HUB_SERVER_PATH)
                    import threading
                    stop_heartbeat = threading.Event()
                    hb_thread = threading.Thread(
                        target=start_heartbeat, 
                        args=(HUB_SERVER_PATH, contract["task_id"], stop_heartbeat),
                        daemon=True
                    )
                    hb_thread.start()
                    
                    try:
                        # Log transition to working state
                        old_status = contract["status"]
                        new_status, reason = transition(old_status, "lock_acquired", contract)
                        contract["status"] = new_status
                        contract["status_reason"] = reason
                        save_contract(contract, contract_path)
                        log_transition(contract, "lock_acquired", old_status, git_manager=gm)
                    
                        # Run Task
                        print(f"Invoking Implementer agent ({contract['roles']['implementer']})...")
                        result = worker.implement_task(contract)
                        
                        if result["success"]:
                            token_stats = result.get("tokens", {})
                            update_cost(contract, token_stats.get("input", 0), token_stats.get("output", 0), contract["roles"]["implementer"])
                            contract["handoff_data"]["changed_files"] = result["files_changed"]
                            
                            old_status = contract["status"]
                            new_status, reason = transition(old_status, "code_written", contract)
                            contract["status"] = new_status
                            contract["status_reason"] = reason
                            release_lock(contract) # Release lock upon completion
                            save_contract(contract, contract_path)
                            log_transition(contract, "code_written", old_status, git_manager=gm)
                            print(f"Implementation complete. Files changed: {result['files_changed']}")
                            
                            stop_heartbeat.set()
                            
                        else:
                            # STALL LOGIC
                            stall_reason = result.get("stall_reason", "unknown")
                            attempt = contract.get("attempt", 1)
                            print(f"Implementer stalled: {stall_reason} (Attempt {attempt})")
                            
                            release_lock(contract)
                            
                            if attempt < 2:
                                # Strike 1: Retry
                                contract["attempt"] = attempt + 1
                                old_status = contract["status"]
                                # Transition back to pending via 'retry' event from timeout_implementer 
                                # But we are in implementation_in_progress. 
                                # We treat stall as timeout for state machine purposes?
                                # Map stall -> timeout -> retry sequence
                                # 1. To timeout
                                ns, _ = transition(old_status, "timeout", contract)
                                # 2. To pending (retry)
                                ns2, reason = transition(ns, "retry", contract)
                                contract["status"] = ns2
                                contract["status_reason"] = f"Retry after stall: {stall_reason}"
                                save_contract(contract, contract_path)
                                log_transition(contract, "implementer_retry", old_status, git_manager=gm)
                                print("Retrying task (Strike 1)...")
                                
                            else:
                                # Strike 2: Halt
                                old_status = contract["status"]
                                ns, _ = transition(old_status, "timeout", contract)
                                ns2, reason = transition(ns, "escalate", contract)
                                contract["status"] = ns2
                                contract["status_reason"] = f"Stalled twice: {stall_reason}"
                                
                                write_stall_report(contract, stall_reason, contract_path.parent)
                                save_contract(contract, contract_path)
                                log_transition(contract, "implementer_stalled", old_status, git_manager=gm)
                                print("Halted task (Strike 2). Check STALL_REPORT.md")
                                stop_heartbeat.set()
                                sys.exit(1)
                    except Exception as e:
                        # Ensure lock is released if we crash
                        contract = load_contract(contract_path)
                        release_lock(contract)
                        save_contract(contract, contract_path)
                        print(f"Inner error: {e}")
                        sys.exit(1)

            except Exception as e:
                # Ensure lock is released if we crash
                contract = load_contract(contract_path)
                release_lock(contract)
                save_contract(contract, contract_path)
                print(f"Unexpected error: {e}")
                sys.exit(1)

        elif cmd == "run-local-review":
            check_for_stop(HUB_SERVER_PATH)
             # Command to invoke Local Reviewer (DeepSeek) via MCP
            if not contract_path.exists():
                print(f"Error: {contract_path} not found")
                sys.exit(1)
            
            contract = load_contract(contract_path)
            
            if contract["status"] != "pending_local_review":
                print(f"Error: Status is {contract['status']}, expected pending_local_review")
                sys.exit(1)
                
            repo_root = Path(contract.get("git", {}).get("repo_root", "."))
            gm = GitManager(repo_root)
            
            try:
                with MCPClient(MCP_SERVER_PATH) as mcp:
                    worker = WorkerClient(mcp)
                    
                    if not worker.check_ollama_health():
                        trigger_halt(contract, "Ollama connection failed during health check", "ollama_unavailable", contract_path)
                        print("Halted: Ollama unavailable")
                        sys.exit(1)

                    changed_files = contract["handoff_data"].get("changed_files", [])
                    print(f"Invoking Local Reviewer ({contract['roles']['local_reviewer']})...")
                    
                    review = worker.run_local_review(contract, changed_files)
                    
                    # Update (zero cost for local, but call it anyway for tracking if we change models)
                    update_cost(contract, 0, 0, contract["roles"]["local_reviewer"])
                    
                    if review["critical"]:
                         # CRITICAL HALT
                        reason = f"Critical security issues found: {review['issues']}"
                        
                        # Transition to consultation via critical_flaw
                        old_status = contract["status"]
                        new_status, _ = transition(old_status, "critical_flaw", contract)
                        
                        contract["status"] = new_status
                        contract["status_reason"] = reason
                        
                        contract["breaker"]["status"] = "tripped"
                        contract["breaker"]["triggered_by"] = "local_reviewer"
                        contract["breaker"]["trigger_reason"] = reason
                        
                        save_contract(contract, contract_path)
                        write_halt_file(contract, reason, contract_path.parent)
                        log_transition(contract, "critical_flaw", old_status, git_manager=gm)
                        
                        # Rename to lock
                        lock_path = contract_path.with_suffix(".json.lock")
                        os.replace(contract_path, lock_path)
                        print(f"Halted: {reason}")
                        sys.exit(1)
                        
                    elif review["passed"]:
                        # PASS
                        contract["handoff_data"]["local_review_passed"] = True
                        contract["handoff_data"]["local_review_issues"] = []
                        
                        old_status = contract["status"]
                        new_status, reason = transition(old_status, "local_pass", contract)
                        contract["status"] = new_status
                        contract["status_reason"] = reason
                        save_contract(contract, contract_path)
                        log_transition(contract, "local_pass", old_status, git_manager=gm)
                        print("Local review passed. Proceeding to Judge.")
                        
                    else:
                        # FAILED (Non-critical) - treat as pass but with issues
                        contract["handoff_data"]["local_review_passed"] = False 
                        contract["handoff_data"]["local_review_issues"] = review["issues"]
                        
                        old_status = contract["status"]
                        new_status, reason = transition(old_status, "local_pass", contract)
                        contract["status"] = new_status
                        contract["status_reason"] = f"Local review issues: {review['issues']}"
                        save_contract(contract, contract_path)
                        log_transition(contract, "local_warn", old_status, git_manager=gm)
                        print(f"Local review found issues: {review['issues']}. Proceeding to Judge.")

            except Exception as e:
                print(f"Unexpected error: {e}")
                sys.exit(1)

        elif cmd == "report-judge":
            check_for_stop(HUB_SERVER_PATH)
            # Process JUDGE_REPORT.json and update costs
            if not contract_path.exists():
                print(f"Error: {contract_path} not found")
                sys.exit(1)
            
            contract = load_contract(contract_path)
            report_path = Path(contract["handoff_data"].get("judge_report_json", "_handoff/JUDGE_REPORT.json"))
            
            if report_path.exists():
                report_content = safe_read(report_path)
                if report_content:
                    try:
                        report = json.loads(report_content)
                        usage = report.get("usage", {})
                        if usage:
                            # Prompt 5.1: update_cost
                            update_cost(
                                contract, 
                                usage.get("prompt_tokens", 0), 
                                usage.get("completion_tokens", 0), 
                                usage.get("model", "claude-code-cli")
                            )
                            save_contract(contract, contract_path)
                            print("Updated costs from Judge report")
                    except json.JSONDecodeError:
                        print("Error: Invalid JUDGE_REPORT.json")
            
            # Now transition status
            old_status = contract["status"]
            try:
                new_status, reason = transition(old_status, "judge_complete", contract)
                contract["status"] = new_status
                contract["status_reason"] = reason
                save_contract(contract, contract_path)
                log_transition(contract, "judge_complete", old_status)
                print(f"Status updated to: {new_status}")
            except InvalidTransition as e:
                print(f"Error: {e}")
                sys.exit(1)
        
        elif cmd == "status":
            if not contract_path.exists():
                # Check for .lock version
                lock_path = contract_path.with_suffix(".json.lock")
                if lock_path.exists():
                    contract = load_contract(lock_path)
                    print_status(contract, lock_path)
                else:
                    print(f"Error: No active task found at {contract_path}")
            else:
                contract = load_contract(contract_path)
                print_status(contract, contract_path)

if __name__ == "__main__":
    import sys
    main(sys.argv)
