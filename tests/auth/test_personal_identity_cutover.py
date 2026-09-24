"""Exercise the personal Git settings with synthetic credentials only."""

import importlib.util
import json
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
    other_host_helper = '!f() { printf "username=other-host\\npassword=synthetic-other\\n"; }; f'
    subprocess.run(["git", "config", "--global", "--add", "credential.helper",
                    other_host_helper], check=True, timeout=10)
    before = cutover.settings(repo)
    global_before = cutover.scope_settings("--global")
    email = "2491180+eriksjaastad@users.noreply.github.com"
    repo_target = cutover.personal_settings(before, email)
    global_target = cutover.personal_settings(global_before, email)
    cutover.replace_config(repo, repo_target)
    cutover.scope_replace("--global", global_target)
    assert cutover.settings(repo) == repo_target
    assert cutover.scope_settings("--global") == global_target

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
    other = subprocess.run(["git", "credential", "fill"], cwd=repo, env=env,
                           input="protocol=https\nhost=gitlab.com\n\n",
                           capture_output=True, text=True, timeout=10, check=True)
    assert "password=synthetic-other" in other.stdout

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


def test_portfolio_owned_temporary_clone_is_discovered(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    monkeypatch.setattr(cutover, "TEMP_ROOT", tmp_path)
    with tempfile.TemporaryDirectory(prefix="identity-owned-", dir=tmp_path) as location:
        repo = Path(location)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
        subprocess.run(["git", "remote", "add", "origin",
                        "https://github.com/eriksjaastad/tools.git"],
                       cwd=repo, check=True, timeout=10)
        assert str(repo.resolve()) in cutover.repositories(home)


def test_apply_uses_shim_in_interactive_zsh(tmp_path, monkeypatch, capsys):
    if not shutil.which("zsh"):
        pytest.skip("zsh is required to exercise the interactive alias")
    home = tmp_path / "home"
    archive = home / "projects"
    archive.mkdir(parents=True)
    repo = archive / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Synthetic",
                    "-c", "user.email=synthetic@example.invalid", "commit", "--allow-empty",
                    "-qm", "seed"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"],
                   check=True, timeout=10)
    linked = archive / "linked"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb", "linked",
                    str(linked)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(linked), "config", "--worktree", "user.name",
                    "Manager[bot]"], check=True, timeout=10)
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
    subprocess.run(["git", "config", "--global", "user.name", "Manager[bot]"],
                   check=True, timeout=10)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setattr(cutover.Path, "home", lambda: home)
    monkeypatch.setattr(cutover, "repositories", lambda unused_home: [str(repo)])
    monkeypatch.setattr(cutover, "personal_account", lambda: {"login": "eriksjaastad", "id": 2491180})
    monkeypatch.setattr(cutover.sys, "argv", [str(SOURCE), "--apply"])
    assert cutover.main() == 0
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert output[0]["global_bot_author"] is True
    assert output[0]["worktree_bot_authors"] == 1
    assert subprocess.run(["git", "-C", str(linked), "config", "user.name"],
                          capture_output=True, text=True, check=True,
                          timeout=10).stdout.strip() == "eriksjaastad"
    assert "alias gha=" not in (home / ".zshrc").read_text()
    env = os.environ.copy()
    env.update({"ZDOTDIR": str(home), "GH_TOKEN": "synthetic-bot",
                "GITHUB_TOKEN": "synthetic-bot"})
    invocation = subprocess.run(["zsh", "-ic", "gha api user"], env=env,
                                capture_output=True, text=True, timeout=10)
    assert invocation.returncode == 0, invocation.stderr
    assert "personal gh: api user" in invocation.stdout
    monkeypatch.setattr(cutover.sys, "argv", [str(SOURCE), "--restore", output[1]["backup"]])
    assert cutover.main() == 0
    assert cutover.scope_settings("--worktree", linked)["user.name"] == ["Manager[bot]"]
    assert wrapper.read_text() == "#!/bin/sh\nexit 99\n"


def test_worktree_scoped_bot_identity_is_migrated_and_restored(tmp_path):
    repo = tmp_path / "repo"
    linked = tmp_path / "linked"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Synthetic",
                    "-c", "user.email=synthetic@example.invalid", "commit", "--allow-empty",
                    "-qm", "seed"], check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "config", "extensions.worktreeConfig", "true"],
                   check=True, timeout=10)
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-qb", "linked",
                    str(linked)], check=True, timeout=10)
    subprocess.run(["git", "-C", str(linked), "config", "--worktree", "user.name",
                    "Manager[bot]"], check=True, timeout=10)
    rows = cutover.worktree_settings(repo)
    row = next(item for item in rows if item["path"] == str(linked))
    before = row["settings"]
    target = cutover.personal_settings(before, "2491180+eriksjaastad@users.noreply.github.com")
    cutover.scope_replace("--worktree", target, linked)
    effective = subprocess.run(["git", "-C", str(linked), "config", "user.name"],
                               capture_output=True, text=True, check=True, timeout=10)
    assert effective.stdout.strip() == "eriksjaastad"
    cutover.scope_replace("--worktree", before, linked)
    assert cutover.scope_settings("--worktree", linked) == before


def test_restore_skips_disappeared_temporary_clone(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    bin_dir = home / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "gha"
    wrapper.write_text("old wrapper\n")
    monkeypatch.setattr(cutover.Path, "home", lambda: home)
    monkeypatch.setattr(cutover.shutil, "which", lambda name: str(wrapper))
    monkeypatch.setattr(cutover, "repositories", lambda unused_home: [])
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "global-gitconfig"))
    global_before = cutover.scope_settings("--global")
    backup = tmp_path / "backup.json"
    backup.write_text(json.dumps({
        "repos": [{"path": str(tmp_path / "vanished-clone"), "settings": global_before}],
        "global_settings": global_before,
        "wrapper_path": str(wrapper), "wrapper_hex": b"restored wrapper\n".hex(),
        "wrapper_mode": 0o755, "zshrc_changed": False,
    }))
    monkeypatch.setattr(cutover.sys, "argv", [str(SOURCE), "--restore", str(backup)])
    assert cutover.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["restored_repos"] == 0
    assert result["missing_paths"] == [str(tmp_path / "vanished-clone")]
    assert wrapper.read_bytes() == b"restored wrapper\n"
