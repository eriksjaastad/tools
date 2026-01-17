# Phase 10: End-to-End Real Task Test

**Goal:** Run a real task through the entire pipeline to validate everything works together. No mocks, no simulations - actual code changes reviewed by actual agents.

**Prerequisites:** Phase 9 complete, all systems operational.

---

## The Test

We're going to run a simple but real task through the full pipeline:

```
Erik → Claude (Super Manager) → Proposal
    → Floor Manager (Gemini) → Contract → Implementer (Qwen)
    → Local Review (DeepSeek) → Judge (Claude)
    → Merge or Iterate
```

---

## Prompt 10.1: Test Task Definition

### Context
We need a task that's:
1. **Real** - Actually changes code in a project
2. **Safe** - Low risk if something goes wrong
3. **Verifiable** - Easy to confirm success/failure
4. **Bounded** - Won't trigger cost circuit breakers

### Task
The test task will be: **"Add a `--version` flag to the Floor Manager CLI"**

Create `_handoff/TEST_PROPOSAL.md`:

```markdown
# Proposal: Add Version Flag to Floor Manager CLI

## Summary
Add a `--version` flag to `src/watchdog.py` that prints the version from `skill.json`.

## Specification

### Target File
`src/watchdog.py`

### Requirements
1. Add `--version` or `-v` flag handling in `main()`
2. Read version from `skill.json`
3. Print version and exit (e.g., `floor-manager v1.0.0`)
4. Must work before hub health check (so it works even if hub is down)

### Acceptance Criteria
- [ ] `python -m src.watchdog --version` prints version
- [ ] `python -m src.watchdog -v` prints version
- [ ] Version matches `skill.json` version field
- [ ] No other functionality affected

## Constraints
- Only modify `src/watchdog.py`
- Do not add new dependencies
- Must pass existing tests

## Definition of Done
- [ ] Version flag implemented
- [ ] Version matches skill.json
- [ ] Tests pass
- [ ] Code review PASS from Judge
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/_handoff/TEST_PROPOSAL.md`

---

## Prompt 10.2: Start the Pipeline

### Context
The Floor Manager should be running and listening for messages. We'll trigger the pipeline by sending a `PROPOSAL_READY` message.

### Task
Create a test script `scripts/run_e2e_test.py`:

```python
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
    max_wait = 300  # 5 minutes
    start = time.time()

    while time.time() - start < max_wait:
        if contract_path.exists():
            with open(contract_path) as f:
                contract = json.load(f)
            status = contract.get("status")
            print(f"    Status: {status}")

            if status == "merged":
                print("    Task merged successfully!")
                break
            elif status == "erik_consultation":
                print("    Task halted - needs human intervention")
                return 1

        time.sleep(10)
    else:
        print("    Timeout waiting for completion")
        return 1

    # 3. Verify implementation
    print("[3/5] Verifying implementation...")
    import subprocess
    result = subprocess.run(
        ["python", "-m", "src.watchdog", "--version"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        print(f"    Error: {result.stderr}")
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
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/run_e2e_test.py`

---

## Prompt 10.3: Monitor and Observe

### Context
While the test runs, we need to observe the full flow to verify each agent participates correctly.

### Task
Create a monitoring script `scripts/monitor_pipeline.py`:

```python
#!/usr/bin/env python3
"""
Real-time pipeline monitor.
Tails transition.ndjson and shows status updates.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

def tail_ndjson(path: Path):
    """Tail the ndjson file and print formatted updates."""
    if not path.exists():
        print(f"Waiting for {path}...")
        while not path.exists():
            time.sleep(1)

    with open(path, 'r') as f:
        # Go to end
        f.seek(0, 2)

        while True:
            line = f.readline()
            if line:
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")[:19]
                    event = entry.get("event", entry.get("message_type", "?"))
                    old = entry.get("old_status", "")
                    new = entry.get("new_status", entry.get("from", ""))

                    # Color coding
                    if "error" in event.lower() or "halt" in event.lower():
                        color = "\033[91m"  # Red
                    elif "complete" in event.lower() or "pass" in event.lower():
                        color = "\033[92m"  # Green
                    else:
                        color = "\033[93m"  # Yellow

                    reset = "\033[0m"

                    if old and new:
                        print(f"{color}[{ts}] {event}: {old} → {new}{reset}")
                    else:
                        print(f"{color}[{ts}] {event}{reset}")

                except json.JSONDecodeError:
                    pass
            else:
                time.sleep(0.5)

def main():
    print("=== Pipeline Monitor ===")
    print("Watching _handoff/transition.ndjson")
    print("Press Ctrl+C to stop")
    print()

    try:
        tail_ndjson(Path("_handoff/transition.ndjson"))
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/monitor_pipeline.py`

---

## Prompt 10.4: Cleanup and Archive

### Context
After the test completes (pass or fail), we need to clean up and archive the test artifacts.

### Task
Create cleanup script `scripts/cleanup_e2e_test.sh`:

```bash
#!/bin/bash
# Cleanup after E2E test

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HANDOFF_DIR="$PROJECT_ROOT/_handoff"
ARCHIVE_DIR="$HANDOFF_DIR/archive/e2e_test_$(date +%Y%m%d_%H%M%S)"

echo "=== E2E Test Cleanup ==="

# Create archive directory
mkdir -p "$ARCHIVE_DIR"

# Move test artifacts
for f in TEST_PROPOSAL.md TASK_CONTRACT.json JUDGE_REPORT.md JUDGE_REPORT.json; do
    if [ -f "$HANDOFF_DIR/$f" ]; then
        mv "$HANDOFF_DIR/$f" "$ARCHIVE_DIR/"
        echo "Archived: $f"
    fi
done

# Keep transition.ndjson but copy to archive
if [ -f "$HANDOFF_DIR/transition.ndjson" ]; then
    cp "$HANDOFF_DIR/transition.ndjson" "$ARCHIVE_DIR/"
    echo "Copied: transition.ndjson"
fi

echo ""
echo "Archived to: $ARCHIVE_DIR"
echo "Cleanup complete."
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/scripts/cleanup_e2e_test.sh`

---

## Prompt 10.5: Document Results

### Context
The E2E test results should be documented for future reference.

### Task
After running the test, create `Documents/E2E_TEST_RESULTS.md`:

```markdown
# E2E Test Results

## Test: Version Flag Implementation

**Date:** [DATE]
**Duration:** [DURATION]
**Result:** [PASS/FAIL]

## Pipeline Flow

| Step | Agent | Status | Duration |
|------|-------|--------|----------|
| Proposal Ready | Super Manager | ✅ | 0s |
| Contract Created | Floor Manager | ✅ | Xs |
| Implementation | Implementer (Qwen) | ✅ | Xs |
| Local Review | DeepSeek | ✅ | Xs |
| Judge Review | Claude | ✅ | Xs |
| Merge | Git Manager | ✅ | Xs |

## Observations

### What Worked
- [List positive observations]

### Issues Encountered
- [List any problems]

### Improvements Needed
- [List suggested improvements]

## Artifacts

- Contract: `_handoff/archive/e2e_test_[timestamp]/TASK_CONTRACT.json`
- Judge Report: `_handoff/archive/e2e_test_[timestamp]/JUDGE_REPORT.md`
- Transition Log: `_handoff/archive/e2e_test_[timestamp]/transition.ndjson`
```

### File Location
`/Users/eriksjaastad/projects/_tools/agent-hub/Documents/E2E_TEST_RESULTS.md`

---

## Execution Order

1. **10.1** - Create test proposal (`TEST_PROPOSAL.md`)
2. **10.2** - Create E2E test runner script
3. **10.3** - Create pipeline monitor script
4. **10.4** - Create cleanup script
5. **10.5** - (After test) Document results

### Running the Test

```bash
# Terminal 1: Start Floor Manager
./scripts/start_agent_hub.sh

# Terminal 2: Monitor pipeline
python scripts/monitor_pipeline.py

# Terminal 3: Run E2E test
python scripts/run_e2e_test.py

# After completion:
./scripts/cleanup_e2e_test.sh
```

---

## Success Criteria

Phase 10 is DONE when:
- [ ] Real task flows through entire pipeline
- [ ] Implementer (Qwen) writes actual code
- [ ] Local Reviewer (DeepSeek) runs review
- [ ] Judge (Claude) issues verdict
- [ ] Code is merged to branch
- [ ] `--version` flag works correctly
- [ ] All transitions logged to `transition.ndjson`
- [ ] No manual intervention required (except starting agents)

---

## What This Proves

A successful Phase 10 demonstrates:
1. **MCP messaging works** - Messages flow between all agents
2. **State machine is correct** - Transitions happen as expected
3. **Circuit breakers don't false-positive** - Normal task completes
4. **Git integration works** - Branch created, committed, merged
5. **Audit trail is complete** - Every step is logged
6. **The system is production-ready** - Real work gets done

---

## Fallback: Manual Verification

If automated test fails, verify manually:

```bash
# Check contract status
python -m src.watchdog status

# Check transition log
tail -20 _handoff/transition.ndjson | jq .

# Check if version flag was added
grep -n "version" src/watchdog.py

# Test version flag manually
python -m src.watchdog --version
```

---

*Phase 10 is the graduation ceremony. If this passes, Agent Hub is ready for real work.*
