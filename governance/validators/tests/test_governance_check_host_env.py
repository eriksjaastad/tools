"""governance-check.sh must not create or sync the committing repo's .venv (#7647).

The hook runs every validator with the real uv from inside whatever repository
is being committed. When uv treated that repository as the project, a validator
without a PEP 723 block made it create a bare .venv, which then shadowed the
real interpreter in fresh worktrees. These tests run the actual master script
with the actual uv against a host repository that has a pyproject.toml.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


MASTER = Path(__file__).resolve().parents[2] / "governance-check.sh"
REAL_UV = shutil.which("uv") or str(Path.home() / ".local/bin/uv")

pytestmark = pytest.mark.skipif(not os.access(REAL_UV, os.X_OK), reason="uv is not installed")


@pytest.fixture
def host(tmp_path):
    root = tmp_path / "host"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "host"\nversion = "0"\nrequires-python = ">=3.11"\n'
        'dependencies = ["host-only-dependency-that-must-never-resolve"]\n'
    )
    (root / "module.py").write_text("VALUE = 1\n")
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/uv").symlink_to(REAL_UV)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "UV_", "VIRTUAL_ENV"))}
    env.update(HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               UV_PYTHON=sys.executable, UV_CACHE_DIR=str(tmp_path / "uv-cache"),
               UV_OFFLINE="1")
    subprocess.run(["git", "init", "-q", str(root)], env=env, check=True, timeout=10)
    subprocess.run(["git", "add", "pyproject.toml", "module.py"], cwd=root, env=env,
                   check=True, timeout=10)
    return root, env


def run_master(host):
    root, env = host
    return subprocess.run(["bash", str(MASTER)], cwd=root, env=env,
                          capture_output=True, text=True, timeout=120)


def snapshot(directory):
    return sorted((str(p.relative_to(directory)), p.stat().st_mtime_ns)
                  for p in directory.rglob("*"))


def test_commit_does_not_create_host_venv(host):
    result = run_master(host)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All governance checks passed" in result.stdout
    assert not (host[0] / ".venv").exists()


def test_commit_leaves_existing_host_venv_untouched(host):
    venv = host[0] / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /nonexistent\n")
    (venv / "bin/marker").write_text("owned by the host project\n")
    before = snapshot(venv)
    result = run_master(host)
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot(venv) == before
