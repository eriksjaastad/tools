"""Exercise the shipped secret-bearing workflow command with an untrusted PR tree."""

import os
import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]


def test_workflow_runs_trusted_scanner_on_every_tracked_name(tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows/content-guard.yml").read_text())
    command = workflow["jobs"]["scan"]["steps"][-1]["run"]

    trusted = tmp_path / "trusted" / "governance" / "validators"
    trusted.mkdir(parents=True)
    shutil.copy2(ROOT / "governance/validators/content-guard.py", trusted / "content-guard.py")

    pr = tmp_path / "pr"
    (pr / "governance" / "validators").mkdir(parents=True)
    (pr / "governance" / "validators" / "content-guard.py").write_text(
        "print('UNTRUSTED SCANNER EXECUTED')\n"
    )
    (pr / "clients.csv").write_bytes(b"\xffname,SYNTHETIC_PRIVATE_CLIENT\n")
    subprocess.run(["git", "init", "-q", str(pr)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(pr), "add", "-A"], check=True, timeout=10)

    env = {**os.environ, "CONTENT_GUARD_PATTERNS": "SYNTHETIC_PRIVATE_CLIENT"}
    result = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        cwd=pr,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,  # A detection is the expected nonzero result.
    )
    assert result.returncode == 1, result.stderr
    assert "clients.csv" in result.stderr
    assert "UNTRUSTED SCANNER EXECUTED" not in result.stdout + result.stderr
    assert "SYNTHETIC_PRIVATE_CLIENT" not in result.stdout + result.stderr
