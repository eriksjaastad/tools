# ssh_agent/agent.py
import json
import re
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timezone

import paramiko
import pexpect
import yaml

ROOT = Path(__file__).resolve().parent  # directory containing this file
QUEUE_DIR = ROOT / "queue"
REQUESTS = QUEUE_DIR / "requests.jsonl"
RESULTS = QUEUE_DIR / "results.jsonl"
STATE = QUEUE_DIR / ".agent_state.json"

# Support for backward compatibility with 3d-pose-factory or other projects
# If a project-specific queue is needed, it can be passed via environment variable
import os
QUEUE_DIR_ENV = os.getenv("SSH_AGENT_QUEUE_DIR")
if QUEUE_DIR_ENV:
    QUEUE_DIR = Path(QUEUE_DIR_ENV)
    REQUESTS = QUEUE_DIR / "requests.jsonl"
    RESULTS = QUEUE_DIR / "results.jsonl"
    STATE = QUEUE_DIR / ".agent_state.json"

HOSTS_CONFIG = Path(__file__).resolve().parent / "ssh_hosts.yaml"


def load_hosts():
    with open(HOSTS_CONFIG, "r") as f:
        return yaml.safe_load(f)["hosts"]


HOSTS = load_hosts()

# Cache for persistent SSH shells
PERSISTENT_SHELLS = {}


class PersistentShell:
    """
    Keep one interactive ssh session open and send commands into it with a sentinel.
    Designed for truly interactive-only SSH like RunPod's.
    """

    def __init__(self, host_alias: str, cfg: dict, username: str, timeout: int = 60):
        self.host_alias = host_alias
        self.cfg = cfg
        self.username = username
        self.timeout = timeout
        self.child = None
        self.lock = threading.Lock()
        self._start_shell()

    def _start_shell(self):
        hostname = self.cfg["hostname"]
        port = self.cfg.get("port", 22)
        key_path = Path(self.cfg["key_path"]).expanduser()

        ssh_target = f"{self.username}@{hostname}"
        ssh_cmd = [
            "ssh",
            "-i", str(key_path),
            "-p", str(port),
            "-o", "StrictHostKeyChecking=no",
            ssh_target,
        ]

        # Start interactive SSH session
        self.child = pexpect.spawn(
            ssh_cmd[0],
            ssh_cmd[1:],
            encoding="utf-8",
            timeout=self.timeout,
        )

        # Give it a moment to finish banners / MOTD / prompt
        try:
            # Just read until we see something or timeout
            self.child.expect("\n", timeout=5)
        except Exception:
            pass  # ignore, shell is probably still ready

    def _clean_output(self, raw_output: str, command: str) -> str:
        """Remove ANSI codes, echoed command, and other shell artifacts."""
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', raw_output)
        
        # Remove carriage returns (Windows-style line endings)
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove the echoed command line (usually at the start)
        lines = cleaned.split('\n')
        # Skip banner, echoed command, and empty lines at the start
        output_lines = []
        skip_until_output = True
        for line in lines:
            # Skip RunPod banner and echoed command
            if skip_until_output:
                if line.strip() and not any(x in line for x in ['RUNPOD.IO', 'Enjoy your Pod', command, 'printf']):
                    skip_until_output = False
                    output_lines.append(line)
            else:
                output_lines.append(line)
        
        return '\n'.join(output_lines).strip()
    
    def run_command(self, command: str):
        SENTINEL = "__AGENT_DONE__"

        with self.lock:
            if self.child is None or not self.child.isalive():
                print(f"  Starting fresh SSH session for {self.host_alias}...")
                self._start_shell()

            # Clear any pending output before sending a new command
            try:
                pending = self.child.read_nonblocking(size=8192, timeout=0.1)
                if pending:
                    print(f"  Cleared {len(pending)} bytes of pending output")
            except Exception:
                pass

            # Send command wrapped with sentinel
            # Use double quotes so $? expands to the actual exit code
            wrapped = f'{command}; printf "\\n{SENTINEL}$?__\\n"\n'
            print(f"  Sending to shell: {command}")
            self.child.sendline(wrapped)

            try:
                print(f"  Waiting for sentinel (timeout={self.timeout}s)...")
                idx = self.child.expect(
                    [r"__AGENT_DONE__([0-9]+)__", pexpect.EOF, pexpect.TIMEOUT],
                    timeout=self.timeout,
                )
            except pexpect.TIMEOUT:
                print("  ERROR: Timeout waiting for sentinel!")
                print(f"  Buffer contents: {self.child.before[:200] if self.child.before else '(empty)'}")
                return "", "AGENT_ERROR: command timed out in persistent shell", -1

            if idx == 1:  # EOF
                print("  ERROR: EOF (idx==1)")
                # Check if sentinel is in the buffer anyway
                buffer = self.child.before or ""
                if "__AGENT_DONE__" in buffer:
                    print("  But sentinel found in buffer! Parsing...")
                    # Extract output and exit code manually
                    parts = buffer.split("__AGENT_DONE__")
                    raw_output = parts[0]
                    exit_code = 0
                    if len(parts) > 1:
                        match = re.search(r'^(\d+)__', parts[1])
                        if match:
                            exit_code = int(match.group(1))
                    # Clean the output
                    output = self._clean_output(raw_output, command)
                    print(f"  ✅ Recovered from EOF ({len(output)} bytes, exit={exit_code})")
                    return output, "", exit_code
                print(f"  Buffer: {buffer[:200] if buffer else '(empty)'}")
                return "", "AGENT_ERROR: SSH session closed unexpectedly", -1
                
            if idx == 2:  # TIMEOUT
                print("  ERROR: Timeout (idx==2)")
                buffer = self.child.before or ""
                print(f"  Buffer: {buffer[:200] if buffer else '(empty)'}")
                return "", "AGENT_ERROR: command timed out waiting for sentinel", -1

            # child.before contains everything printed before the sentinel line
            raw_output = self.child.before or ""
            
            # Clean up output: remove ANSI codes and echoed command
            output = self._clean_output(raw_output, command)
            print(f"  ✅ Got output ({len(output)} bytes)")

            # Grab exit status from capturing group
            try:
                exit_status_str = self.child.match.group(1)
                exit_status = int(exit_status_str)
                print(f"  Exit status: {exit_status}")
            except Exception as e:
                print(f"  ERROR parsing exit status: {e}")
                exit_status = -1

            # NOTE: stdout+stderr are merged in interactive shell
            return output, "", exit_status


def _run_ssh_cli_persistent(host_alias: str, cfg: dict, username: str, command: str, timeout: int = 60):
    """Use a persistent interactive SSH shell (for RunPod)"""
    global PERSISTENT_SHELLS
    shell = PERSISTENT_SHELLS.get(host_alias)
    if shell is None:
        shell = PersistentShell(host_alias, cfg, username, timeout=timeout)
        PERSISTENT_SHELLS[host_alias] = shell
    return shell.run_command(command)


def _run_ssh_cli(host_alias: str, cfg: dict, username: str, command: str, timeout: int = 60):
    """
    Use the system ssh client with -tt so it behaves exactly
    like manual SSH sessions. This works around RunPod's broken SSH.
    """
    hostname = cfg["hostname"]
    port = cfg.get("port", 22)
    key_path = Path(cfg["key_path"]).expanduser()

    # Build ssh command
    ssh_target = f"{username}@{hostname}"
    
    ssh_cmd = [
        "ssh",
        "-i", str(key_path),
        "-p", str(port),
        "-tt",  # Force pseudo-terminal allocation (RunPod requires this)
        "-o", "StrictHostKeyChecking=no",  # Auto-accept host keys
        ssh_target,
        "--",
        command,
    ]

    # Run the SSH command
    proc = subprocess.run(
        ssh_cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return proc.stdout, proc.stderr, proc.returncode


def _run_ssh_paramiko(host_alias: str, cfg: dict, username: str, key: paramiko.PKey, command: str, timeout: int = 60):
    """
    Use paramiko for normal servers that support proper SSH protocol.
    """
    hostname = cfg["hostname"]
    port = cfg.get("port", 22)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            pkey=key,
            timeout=10,
        )
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        exit_status = stdout.channel.recv_exit_status()
    finally:
        client.close()

    return out, err, exit_status


def run_ssh_command(host_alias: str, command: str, timeout: int = 60):
    if host_alias not in HOSTS:
        raise ValueError(f"Unknown host alias: {host_alias}")
    
    cfg = HOSTS[host_alias].copy()
    username = cfg["username"]
    key_path = Path(cfg["key_path"]).expanduser()
    method = cfg.get("method", "paramiko")  # Default to paramiko for normal servers

    # Special handling for RunPod: read POD_ID from .pod_id file
    if host_alias == "runpod" and username is None:
        pod_id_file = ROOT / ".pod_id"
        if not pod_id_file.exists():
            raise FileNotFoundError(f"RunPod POD_ID not found at {pod_id_file}")
        username = pod_id_file.read_text().strip()

    # Route to appropriate SSH method
    if method == "cli_persistent":
        # Use persistent interactive SSH shell (for RunPod)
        return _run_ssh_cli_persistent(host_alias, cfg, username, command, timeout)
    elif method == "cli":
        # Use system ssh command (one-shot, for other restricted SSH)
        return _run_ssh_cli(host_alias, cfg, username, command, timeout)
    else:
        # Use paramiko (for normal servers)
        # Try to load key - support both RSA and ED25519
        key = None
        for key_class in [paramiko.Ed25519Key, paramiko.RSAKey]:
            try:
                key = key_class.from_private_key_file(str(key_path))
                break
            except paramiko.SSHException:
                continue
        
        if key is None:
            raise ValueError(f"Could not load SSH key from {key_path}")
        
        return _run_ssh_paramiko(host_alias, cfg, username, key, command, timeout)


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

    print("SSH Agent running. Watching for new requests...")
    while True:
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
                    print(tb)
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
        time.sleep(1)  # simple polling; can tune as needed


if __name__ == "__main__":
    main()
