import json
from pathlib import Path
import threading
import asyncio
from typing import Any, Dict, Optional, Union

# MCP modules
from MCP_client import MCPClient  # type: ignore
from worker_client import WorkerClient  # type: ignore


def check_for_stop(mcp_path: str) -> bool:
    """
    Checks if the MCP server is stopped.
    
    Args:
        mcp_path (str): Path to MCP server file
    
    Returns:
        bool: True if MCP server is running, False otherwise
    """
    try:
        with open(mcp_path, 'r') as f:
            return json.load(f)['status'] != 'stopped'
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"Error checking MCP status: {e}")
        return False


def run_local_review(contract_path: Path, changed_files: list) -> None:
    """
    Runs the Local Reviewer for a contract.
    
    Args:
        contract_path (Path): Path to contract JSON file
        changed_files (list): List of changed files from handoff data
    """
    check_for_stop(HUB_SERVER_PATH)
    if not contract_path.exists():
        print(f"Error: {contract_path} not found")
        return

    contract = load_contract(contract_path)

    if contract["status"] != "pending_local_review":
        print(f"Error: Status is {contract['status']}, expected pending_local_review")
        return

    repo_root = Path(contract.get("git", {}).get("repo_root", "."))
    gm = GitManager(repo_root)
    
    try:
        with MCPClient(MCP_SERVER_PATH) as mcp:
            worker = WorkerClient(mcp)
            
            if not worker.check_ollama_health():
                trigger_halt(contract, "Ollama connection failed during health check", "ollama_unavailable", contract_path)
                print("Halted: Ollama unavailable")
                return

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
            write_halt_file(contract, reason, contract.parent)
            log_transition(contract, "critical_flaw", old_status, git_manager=gm)
            
            # Rename to lock
            lock_path = contract_path.with_suffix(".json.lock")
            os.replace(contract_path, lock_path)
            print(f"Halted: {reason}")
            return

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


def report_judge(report_path: Path) -> None:
    """
    Processes JUDGE_REPORT.json and updates costs.
    
    Args:
        report_path (Path): Path to judge report file
    """
    check_for_stop(HUB_SERVER_PATH)
    if not contract_path.exists():
        print(f"Error: {contract_path} not found")
        return

    try:
        with open(report_path, 'r') as f:
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
            return
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def status() -> None:
    """
    Prints the current status of contracts in _handoff directory.
    """
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


def transition(old_status: str, new_status: str, contract: dict, git_manager=None) -> tuple[str, str]:
    """
    Transitions the status of a contract.

    Args:
        old_status (str): Current status
        new_status (str): New status to set
        contract (dict): Contract data
        git_manager (GitManager): Git manager instance

    Returns:
        tuple: (new_status, reason)
    """
    check_for_stop(HUB_SERVER_PATH)

    try:
        if new_status == "local_pass":
            update_local_status(contract["handoff_data"], "local_pass")
        elif new_status in ["critical", "local_fail"]:
            pass
    except Exception as e:
        print(f"Error during status transition: {e}")
        return "", ""

    return new_status, ""


def save_contract(contract: dict, path: Path) -> None:
    """
    Saves a contract to the given path.
    
    Args:
        contract (dict): Contract data
        path (Path): Output file path
    """
    with open(path, 'w') as f:
        json.dump(contract, f)


def write_halt_file(contract: dict, reason: str, parent_path: Path) -> None:
    """
    Writes a halt file for the contract.
    
    Args:
        contract (dict): Contract data
        reason (str): Halt reason
        parent_path (Path): Parent directory path
    """
    with open(os.path.join(str(parent_path), 'halts', f'{contract["id"]}_halt'), 'w') as f:
        f.write(reason)


def write_stall_report(contract: dict, issues: list) -> None:
    """
    Writes a stall report for the contract.
    
    Args:
        contract (dict): Contract data
        issues (list): List of stalled issues
    """
    with open(os.path.join(str(contract.parent), 'stalls', f'{contract["id"]}_stall'), 'w') as f:
        json.dump({'issues': issues}, f)


def load_contract(contract_path: Path) -> dict:
    """
    Loads a contract from the given path.
    
    Args:
        contract_path (Path): Path to contract file
    
    Returns:
        dict: Contract data
    """
    with open(contract_path, 'r') as f:
        return json.load(f)


async def run_local_review_async(...) -> None:
    """
    Runs the Local Reviewer for a contract.
    """
    # This would be an async version of run_local_review()
    pass


def _generate_message(...) -> str:
    """
    Generates messages for the MCP client.
    """
    return f"<{__name__} running at {time.time()}>"


async def MessageListener() -> None:
    """
    Listens for messages and processes them.
    """
    while True:
        msg = await _generate_message()
        asyncio.run_coroutine_threadsafe(run_local_review(msg), asyncio.get_event_loop())
        try:
            loop.create_task(run_local_review(msg))
        except BaseException as e:
            pass
