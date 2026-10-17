"""governance-check.sh must not create or sync the committing repo's .venv (#7647).

The hook runs every validator with the real uv from inside whatever repository
is being committed. When uv treated that repository as the project, a validator
without a PEP 723 block made it create a bare .venv, which then shadowed the
real interpreter in fresh worktrees. These tests run the actual master script
with the actual uv against a host repository that has a pyproject.toml.
"""
import os
from pathlib import Path
import random
import shutil
import string
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


SILENT = "def load():\n    try:\n        return fetch()\n    except Exception:\n        return []\n"


def commit_all(host, message):
    root, env = host
    env = dict(env, GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    subprocess.run(["git", "commit", "-qm", message, "--no-verify"], cwd=root, env=env,
                   check=True, timeout=10)


def test_master_blocks_new_silent_failure_but_not_historical(host):
    root, env = host
    (root / "module.py").write_text(SILENT)
    subprocess.run(["git", "add", "module.py"], cwd=root, env=env, check=True, timeout=10)
    blocked = run_master(host)
    assert blocked.returncode == 1
    assert "SF002" in blocked.stdout + blocked.stderr
    commit_all(host, "historical silent handler")
    (root / "module.py").write_text(SILENT + "\nVALUE = 2\n")
    subprocess.run(["git", "add", "module.py"], cwd=root, env=env, check=True, timeout=10)
    result = run_master(host)
    assert result.returncode == 0, result.stdout + result.stderr


def test_staged_ignore_list_is_the_one_judged(host):
    """An unstaged edit to .absolute-path-ignore must not change the verdict (#8356)."""
    root, env = host
    (root / ".absolute-path-ignore").write_text("data/*.json  # cites county URLs\n")
    (root / "data").mkdir()
    (root / "data" / "kb.json").write_text('"' + "/" + 'home/fixture/x"\n')
    subprocess.run(["git", "add", ".absolute-path-ignore", "data/kb.json"], cwd=root, env=env,
                   check=True, timeout=10)
    (root / ".absolute-path-ignore").write_text("")
    result = run_master(host)
    assert result.returncode == 0, result.stdout + result.stderr


def test_symlinked_ignore_list_is_refused_at_commit(host):
    root, env = host
    (root / "list").write_text("data/*.json  # cites county URLs\n")
    (root / ".absolute-path-ignore").symlink_to("list")
    subprocess.run(["git", "add", "list", ".absolute-path-ignore"], cwd=root, env=env,
                   check=True, timeout=10)
    result = run_master(host)
    assert result.returncode == 1
    assert "must be a regular file" in result.stdout + result.stderr



def _token():
    return "ghp_" + "".join(random.Random(8363).choices(string.ascii_letters + string.digits, k=36))


@pytest.mark.parametrize("text, blocked", [
    ('SOURCE = "https://phillipscounty.colorado.gov/sites/g/files/lrnvjt1351/files/Final%20Junk.pdf"\n', False),
    (None, True),
], ids=["county-url", "github-token"])
def test_gitleaks_judges_secrets_by_use(host, text, blocked):
    """#8363: a 40-char URL path is not a secret; a real-looking token is."""
    root, env = host
    (root / "data.py").write_text(text or f'TOKEN = "{_token()}"\n')
    subprocess.run(["git", "add", "data.py"], cwd=root, env=env, check=True, timeout=10)
    result = run_master(host)
    assert (result.returncode == 1) == blocked, result.stdout + result.stderr
    if blocked:
        assert "gitleaks found a likely secret" in result.stdout + result.stderr


def test_missing_gitleaks_fails_closed(host):
    root, env = host
    no_gitleaks = {**env, "PATH": os.pathsep.join(p for p in env["PATH"].split(os.pathsep)
                                                  if not (Path(p) / "gitleaks").exists())}
    result = subprocess.run(["bash", str(MASTER)], cwd=root, env=no_gitleaks,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 1
    assert "brew install gitleaks" in result.stdout + result.stderr



def test_repository_cannot_weaken_gitleaks(host, tmp_path):
    """The shared --config wins over a staged .gitleaks.toml and over GITLEAKS_CONFIG."""
    root, env = host
    allow_all = '[[allowlists]]\npaths = [".*"]\n'
    (tmp_path / "allow.toml").write_text(allow_all)
    (root / ".gitleaks.toml").write_text(allow_all)
    (root / "data.py").write_text(f'TOKEN = "{_token()}"\n')
    subprocess.run(["git", "add", ".gitleaks.toml", "data.py"], cwd=root, env=env, check=True, timeout=10)
    result = subprocess.run(["bash", str(MASTER)], cwd=root,
                            env={**env, "GITLEAKS_CONFIG": str(tmp_path / "allow.toml")},
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "gitleaks found a likely secret" in result.stdout + result.stderr


def test_staged_content_is_judged_not_the_worktree(host):
    """#8363: the commit gate scans staged blobs, as the push gate scans committed ones."""
    root, env = host
    (root / "data.py").write_text(f'TOKEN = "{_token()}"\n')
    subprocess.run(["git", "add", "data.py"], cwd=root, env=env, check=True, timeout=10)
    (root / "data.py").write_text("TOKEN = None\n")
    result = run_master(host)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "gitleaks found a likely secret" in result.stdout + result.stderr


def test_colon_named_staged_secret_is_scanned(host):
    """A leading ':' is pathspec magic unless looked up literally (fail-open in c69bab8)."""
    root, env = host
    (root / ":colon.py").write_text(f'TOKEN = "{_token()}"\n')
    subprocess.run(["git", "--literal-pathspecs", "add", ":colon.py"], cwd=root, env=env,
                   check=True, timeout=10)
    result = run_master(host)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "gitleaks found a likely secret" in result.stdout + result.stderr


def test_unstaged_argument_fails_the_secrets_check(host, tmp_path):
    root, env = host
    outside = tmp_path / "outside.py"
    outside.write_text("VALUE = 1\n")
    result = subprocess.run(["bash", str(MASTER), str(outside)], cwd=root, env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no single staged entry for" in result.stdout + result.stderr
