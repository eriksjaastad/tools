import re
import subprocess
import threading
from pathlib import Path
import paramiko
import pexpect
import yaml
import os

# Root of the ssh_agent tool
ROOT = Path(__file__).resolve().parent.parent.parent
HOSTS_CONFIG = ROOT / "ssh_hosts.yaml"

def load_hosts():
    if not HOSTS_CONFIG.exists():
        return {}
    with open(HOSTS_CONFIG, "r") as f:
        return yaml.safe_load(f).get("hosts", {})

# Cache for persistent SSH shells
PERSISTENT_SHELLS = {}

class PersistentShell:
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

        self.child = pexpect.spawn(
            ssh_cmd[0],
            ssh_cmd[1:],
            encoding="utf-8",
            timeout=self.timeout,
        )

        try:
            self.child.expect("\n", timeout=5)
        except Exception:
            pass

    def _clean_output(self, raw_output: str, command: str) -> str:
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', raw_output)
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        lines = cleaned.split('\n')
        output_lines = []
        skip_until_output = True
        for line in lines:
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
                self._start_shell()

            try:
                self.child.read_nonblocking(size=8192, timeout=0.1)
            except Exception:
                pass

            wrapped = f'{command}; printf "\\n{SENTINEL}$?__\\n"\n'
            self.child.sendline(wrapped)

            try:
                idx = self.child.expect(
                    [r"__AGENT_DONE__([0-9]+)__", pexpect.EOF, pexpect.TIMEOUT],
                    timeout=self.timeout,
                )
            except pexpect.TIMEOUT:
                return "", "AGENT_ERROR: command timed out in persistent shell", -1

            if idx == 1:  # EOF
                buffer = self.child.before or ""
                if "__AGENT_DONE__" in buffer:
                    parts = buffer.split("__AGENT_DONE__")
                    raw_output = parts[0]
                    exit_code = 0
                    if len(parts) > 1:
                        match = re.search(r'^(\d+)__', parts[1])
                        if match:
                            exit_code = int(match.group(1))
                    output = self._clean_output(raw_output, command)
                    return output, "", exit_code
                return "", "AGENT_ERROR: SSH session closed unexpectedly", -1
                
            if idx == 2:  # TIMEOUT
                return "", "AGENT_ERROR: command timed out waiting for sentinel", -1

            raw_output = self.child.before or ""
            output = self._clean_output(raw_output, command)
            try:
                exit_status_str = self.child.match.group(1)
                exit_status = int(exit_status_str)
            except Exception:
                exit_status = -1
            return output, "", exit_status

def _run_ssh_cli_persistent(host_alias: str, cfg: dict, username: str, command: str, timeout: int = 60):
    global PERSISTENT_SHELLS
    shell = PERSISTENT_SHELLS.get(host_alias)
    if shell is None:
        shell = PersistentShell(host_alias, cfg, username, timeout=timeout)
        PERSISTENT_SHELLS[host_alias] = shell
    return shell.run_command(command)

def _run_ssh_cli(host_alias: str, cfg: dict, username: str, command: str, timeout: int = 60):
    hostname = cfg["hostname"]
    port = cfg.get("port", 22)
    key_path = Path(cfg["key_path"]).expanduser()
    ssh_target = f"{username}@{hostname}"
    
    ssh_cmd = [
        "ssh",
        "-i", str(key_path),
        "-p", str(port),
        "-tt",
        "-o", "StrictHostKeyChecking=no",
        ssh_target,
        "--",
        command,
    ]

    proc = subprocess.run(
        ssh_cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.stdout, proc.stderr, proc.returncode

def _run_ssh_paramiko(host_alias: str, cfg: dict, username: str, key_path: Path, command: str, timeout: int = 60):
    hostname = cfg["hostname"]
    port = cfg.get("port", 22)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Try to load key
    key = None
    for key_class in [paramiko.Ed25519Key, paramiko.RSAKey]:
        try:
            key = key_class.from_private_key_file(str(key_path))
            break
        except Exception:
            continue
    
    if key is None:
        return "", f"Could not load SSH key from {key_path}", -1

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
    except Exception as e:
        return "", str(e), -1
    finally:
        client.close()

    return out, err, exit_status

def run_ssh_command(host_alias: str, command: str, timeout: int = 60):
    hosts = load_hosts()
    if host_alias not in hosts:
        raise ValueError(f"Unknown host alias: {host_alias}")
    
    cfg = hosts[host_alias].copy()
    username = cfg["username"]
    key_path = Path(cfg["key_path"]).expanduser()
    method = cfg.get("method", "paramiko")

    if host_alias == "runpod" and username is None:
        pod_id_file = ROOT / ".pod_id"
        if not pod_id_file.exists():
            raise FileNotFoundError(f"RunPod POD_ID not found at {pod_id_file}")
        username = pod_id_file.read_text().strip()

    if method == "cli_persistent":
        return _run_ssh_cli_persistent(host_alias, cfg, username, command, timeout)
    elif method == "cli":
        return _run_ssh_cli(host_alias, cfg, username, command, timeout)
    else:
        return _run_ssh_paramiko(host_alias, cfg, username, key_path, command, timeout)
