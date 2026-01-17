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
                    if "error" in event.lower() or "halt" in event.lower() or "fail" in event.lower():
                        color = "\033[91m"  # Red
                    elif "complete" in event.lower() or "pass" in event.lower() or "success" in event.lower() or "merged" in event.lower():
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
