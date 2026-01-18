#!/usr/bin/env python3
"""
End-to-end test runner.
Sends PROPOSAL_READY and monitors the pipeline.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime, timezone

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
from src.mcp_client import MCPClient
from src.hub_client import HubClient

def main():
    config = get_config()
    proposal_path = Path("_handoff/TEST_PROPOSAL.md")

    if not proposal_path.exists():
        print("Error: TEST_PROPOSAL.md not found. Create it first.")
        return 1

    print("=== E2E Test: Version Flag Implementation ===")
    print(f"Proposal: {proposal_path}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print()

    # 1. Send PROPOSAL_READY
    print("[1/5] Sending PROPOSAL_READY to Floor Manager...")
    try:
        with MCPClient(config.hub_path) as mcp:
            hub = HubClient(mcp)
            hub.connect("e2e_test_runner")
            msg_id = hub.send_message("floor_manager", "PROPOSAL_READY", {
                "proposal_path": str(proposal_path.absolute()),
                "task_id": "e2e_test_version_flag"
            })
            print(f"    Sent: {msg_id}")
    except Exception as e:
        print(f"    Error: {e}")
        return 1

    # 2. Monitor contract status
    print("[2/5] Monitoring contract status...")
    contract_path = Path("_handoff/TASK_CONTRACT.json")
    max_wait = 600  # 10 minutes (increased for real agent work)
    start = time.time()

    last_status = None
    while time.time() - start < max_wait:
        if contract_path.exists():
            try:
                with open(contract_path) as f:
                    contract = json.load(f)
                status = contract.get("status")
                if status != last_status:
                    print(f"    Status: {status}")
                    last_status = status

                if status == "merged":
                    print("    Task merged successfully!")
                    break
                elif status == "erik_consultation":
                    print("    Task halted - needs human intervention")
                    return 1
            except Exception:
                pass # Might be midway through atomic write

        time.sleep(10)
    else:
        print("    Timeout waiting for completion")
        return 1

    # 3. Verify implementation
    print("[3/5] Verifying implementation...")
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.watchdog", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Try -v just in case
        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.watchdog", "-v"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"    Error: {e}")
            return 1

    version_output = result.stdout.strip()
    print(f"    Output: {version_output}")

    # 4. Verify version matches skill.json
    print("[4/5] Verifying version matches skill.json...")
    with open("skill.json") as f:
        skill = json.load(f)
    expected_version = skill["version"]

    if expected_version in version_output:
        print(f"    Version {expected_version} confirmed!")
    else:
        print(f"    Version mismatch! Expected {expected_version}")
        return 1

    # 5. Summary
    print("[5/5] Test Complete!")
    print()
    print("=== E2E Test PASSED ===")
    print(f"Duration: {int(time.time() - start)} seconds")

    return 0

if __name__ == "__main__":
    sys.exit(main())
