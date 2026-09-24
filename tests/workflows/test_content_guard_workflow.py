"""Exercise the shipped secret-bearing workflow command with an untrusted PR tree."""

import os
import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]


def test_workflow_runs_trusted_scanner_on_every_tracked_name(tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows/content-guard.yml").read_text())
    job = workflow["jobs"]["scan"]
    assert job["if"] == "github.event.pull_request.base.ref == github.event.repository.default_branch"
    assert job["steps"][0]["with"]["ref"] == "${{ github.event.repository.default_branch }}"
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

    # A gitlink is tracked, but checkout does not populate its file content.
    (pr / "clients.csv").write_text("name,public\n")
    subprocess.run(["git", "-C", str(pr), "add", "clients.csv"], check=True, timeout=10)
    subprocess.run(
        ["git", "-C", str(pr), "update-index", "--add", "--cacheinfo",
         "160000," + "a" * 40 + ",submodule"],
        check=True, timeout=10,
    )
    clean = subprocess.run(
        command, shell=True, executable="/bin/bash", cwd=pr, env=env,
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert clean.returncode == 0, clean.stderr

    # Git enumeration failure cannot become a successful empty scan.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\nexit 42\n")
    fake_git.chmod(0o755)
    broken = subprocess.run(
        command, shell=True, executable="/bin/bash", cwd=pr,
        env={**env, "PATH": str(fake_bin) + os.pathsep + env["PATH"]},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert broken.returncode == 2
    assert "cannot enumerate tracked files" in broken.stderr
