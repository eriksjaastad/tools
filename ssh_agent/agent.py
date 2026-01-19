# ssh_agent/agent.py
import json
import time
from pathlib import Path
from datetime import datetime, timezone
import os

from src.ssh_mcp.ssh_ops import run_ssh_command

ROOT = Path(__file__).resolve().parent
QUEUE_DIR = ROOT / "queue"
REQUESTS = QUEUE_DIR / "requests.jsonl"
RESULTS = QUEUE_DIR / "results.jsonl"
STATE = QUEUE_DIR / ".agent_state.json"

# Support for backward compatibility
QUEUE_DIR_ENV = os.getenv("SSH_AGENT_QUEUE_DIR")
if QUEUE_DIR_ENV:
    QUEUE_DIR = Path(QUEUE_DIR_ENV)
    REQUESTS = QUEUE_DIR / "requests.jsonl"
    RESULTS = QUEUE_DIR / "results.jsonl"
    STATE = QUEUE_DIR / ".agent_state.json"

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"last_offset": 0}

def save_state(state):
    STATE.write_text(json.dumps(state))

def ensure_files():
    QUEUE_DIR.mkdir(exist_ok=True)
    for p in [REQUESTS, RESULTS]:
        if not p.exists():
            p.write_text("")

def main():
    ensure_files()
    state = load_state()
    last_offset = state.get("last_offset", 0)

    print("SSH Agent (Queue Mode) running. Watching for new requests...")
    while True:
        try:
            with REQUESTS.open("r") as f:
                f.seek(last_offset)
                new_lines = f.readlines()
                last_offset = f.tell()

            if new_lines:
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        req = json.loads(line)
                    except json.JSONDecodeError:
                        print("Skipping invalid JSON:", line)
                        continue

                    req_id = req["id"]
                    host = req["host"]
                    cmd = req["command"]

                    print(f"[{req_id}] {host}$ {cmd}")

                    try:
                        stdout, stderr, exit_status = run_ssh_command(host, cmd)
                    except Exception as e:
                        import traceback
                        tb = traceback.format_exc()
                        print(f"ERROR: {e}")
                        stdout, stderr, exit_status = "", f"AGENT_ERROR: {e}\n{tb}", -1

                    result = {
                        "id": req_id,
                        "host": host,
                        "command": cmd,
                        "stdout": stdout,
                        "stderr": stderr,
                        "exit_status": exit_status,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }

                    with RESULTS.open("a") as rf:
                        rf.write(json.dumps(result) + "\n")

            save_state({"last_offset": last_offset})
        except Exception as e:
            print(f"Error in main loop: {e}")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
