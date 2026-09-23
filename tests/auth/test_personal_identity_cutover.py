"""Exercise the personal Git settings with synthetic credentials only."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


SOURCE = Path(__file__).resolve().parents[2] / "github-identity-cutover.py"
SPEC = importlib.util.spec_from_file_location("identity_cutover", SOURCE)
cutover = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cutover)


def test_repo_global_helper_and_rollback(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "global-gitconfig"))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
    subprocess.run(["git", "config", "--local", "user.name", "Manager[bot]"],
                   cwd=repo, check=True, timeout=10)
    subprocess.run(["git", "config", "--local", "user.email", "bot@example.invalid"],
                   cwd=repo, check=True, timeout=10)
    before = cutover.settings(repo)
    global_before = cutover.scope_settings("--global")
    target = {"user.name": ["eriksjaastad"],
              "user.email": ["2491180+eriksjaastad@users.noreply.github.com"],
              "credential.helper": ["", cutover.PERSONAL_HELPER]}
    cutover.replace_config(repo, target)
    cutover.scope_replace("--global", target)
    assert cutover.settings(repo) == target
    assert cutover.scope_settings("--global") == target

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text("#!/bin/sh\n[ -z \"${GH_TOKEN:-}\" ] || exit 19\n"
                       "[ -z \"${GITHUB_TOKEN:-}\" ] || exit 20\n"
                       "printf 'username=eriksjaastad\\npassword=synthetic-personal\\n'\n")
    fake_gh.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
    env["GH_TOKEN"] = "synthetic-bot"
    env["GITHUB_TOKEN"] = "synthetic-bot"
    filled = subprocess.run(["git", "credential", "fill"], cwd=repo, env=env,
                            input="protocol=https\nhost=github.com\n\n",
                            capture_output=True, text=True, timeout=10, check=True)
    assert "password=synthetic-personal" in filled.stdout

    cutover.replace_config(repo, before)
    cutover.scope_replace("--global", global_before)
    assert cutover.settings(repo) == before
    assert cutover.scope_settings("--global") == global_before


def test_legacy_bot_installer_cannot_reinstall_bot_author(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
    result = subprocess.run([str(SOURCE.parent / "set-repo-bot-identity.sh"), "manager"],
                            cwd=repo, capture_output=True, text=True, timeout=10)
    assert result.returncode == 78
    assert "retired" in result.stderr
    assert cutover.settings(repo)["user.name"] == []


def test_portfolio_owned_temporary_clone_is_discovered(tmp_path):
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="identity-owned-", dir="/private/tmp") as location:
        repo = Path(location)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
        subprocess.run(["git", "remote", "add", "origin",
                        "https://github.com/eriksjaastad/tools.git"],
                       cwd=repo, check=True, timeout=10)
        assert str(repo.resolve()) in cutover.repositories(home)


def test_apply_uses_shim_in_interactive_zsh(tmp_path, monkeypatch):
    if not shutil.which("zsh"):
        pytest.skip("zsh is required to exercise the interactive alias")
    home = tmp_path / "home"
    archive = home / "projects"
    archive.mkdir(parents=True)
    repo = archive / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
    (home / ".zshrc").write_text('alias gha="gh"\n')
    bin_dir = home / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "gha"
    wrapper.write_text("#!/bin/sh\nexit 99\n")
    wrapper.chmod(0o755)
    fake_gh = bin_dir / "gh"
    fake_gh.write_text("#!/bin/sh\n[ -z \"${GH_TOKEN:-}\" ] || exit 19\n"
                       "[ -z \"${GITHUB_TOKEN:-}\" ] || exit 20\n"
                       "printf 'personal gh: %s\\n' \"$*\"\n")
    fake_gh.chmod(0o755)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "global-gitconfig"))
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(cutover.Path, "home", lambda: home)
    monkeypatch.setattr(cutover, "repositories", lambda unused_home: [str(repo)])
    monkeypatch.setattr(cutover, "personal_account", lambda: {"login": "eriksjaastad", "id": 2491180})
    monkeypatch.setattr(cutover.sys, "argv", [str(SOURCE), "--apply"])
    assert cutover.main() == 0
    assert "alias gha=" not in (home / ".zshrc").read_text()
    env = os.environ.copy()
    env.update({"ZDOTDIR": str(home), "GH_TOKEN": "synthetic-bot",
                "GITHUB_TOKEN": "synthetic-bot"})
    invocation = subprocess.run(["zsh", "-ic", "gha api user"], env=env,
                                capture_output=True, text=True, timeout=10)
    assert invocation.returncode == 0, invocation.stderr
    assert "personal gh: api user" in invocation.stdout
