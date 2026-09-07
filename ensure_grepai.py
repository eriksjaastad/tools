#!/usr/bin/env python3
import subprocess
import sys
import time

def is_grepai_running():
    """Return a confirmed status; failed or unfamiliar inspections must raise."""
    result = subprocess.run(
        ["grepai", "watch", "--status"], capture_output=True, text=True,
        check=True, timeout=10,
    )
    statuses = {line.strip() for line in result.stdout.splitlines() if line.strip().startswith("Status:")}
    if statuses == {"Status: running"}:
        return True
    if statuses == {"Status: not running"}:
        return False
    raise RuntimeError("grepai status was not recognized; refusing to start a daemon")

def start_grepai():
    print("Starting grepai watch daemon...")
    subprocess.run(
        ["grepai", "watch", "--background"], check=True,
        capture_output=True, text=True, timeout=15,
    )
    time.sleep(1)
    if not is_grepai_running():
        raise RuntimeError("grepai remained stopped after startup")
    print("✅ grepai watch is now running in the background.")
    return True

def main():
    try:
        if not is_grepai_running():
            start_grepai()
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        print(f"grepai check/start failed: {error}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
