"""Source-deletion checks through the actual shared pre-commit entrypoint."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


MASTER = Path(__file__).resolve().parents[2] / "governance-check.sh"
CHECK = MASTER.parent / "validators/source-deletion-check.py"


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    home = tmp_path / "home"
    uv = home / ".local/bin/uv"
    uv.parent.mkdir(parents=True)
    uv.write_text('#!/bin/sh\nshift\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
    uv.chmod(0o700)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
    subprocess.run(["git", "init", "-q", str(root)], env=env, check=True, timeout=10)
    return root, env


def git(repo, *args):
    root, env = repo
    return subprocess.run(["git", *args], cwd=root, env=env, check=True,
                          capture_output=True, text=True, timeout=10).stdout


def stage(repo, source, name="module.py"):
    root, _ = repo
    (root / name).write_text(source)
    git(repo, "add", name)


def check(repo, *args, master=False):
    root, env = repo
    command = ["bash", str(MASTER)] if master else [sys.executable, str(CHECK)]
    return subprocess.run(command + list(args), cwd=root, env=env,
                          capture_output=True, text=True, timeout=20)


def test_actual_master_blocks_staged_deletion_despite_safe_worktree(repository):
    stage(repository, 'from pathlib import Path\nPath("valuable").unlink()\n')
    (repository[0] / "module.py").write_text("# unstaged safe replacement\n")
    result = check(repository, master=True)
    assert result.returncode != 0
    assert "DS001" in result.stdout + result.stderr


@pytest.mark.parametrize("source", [
    'from os import remove as erase\nerase("valuable")\n',
    'import shutil as files\nfiles.rmtree("valuable")\n',
    'from pathlib import Path\nPath("valuable").rmdir()\n',
    'p.unlink(missing_ok=True)\n',
])
def test_unsafe_sites_block(repository, source):
    stage(repository, source)
    result = check(repository)
    assert result.returncode == 1
    assert "DS001" in result.stdout


@pytest.mark.parametrize("source", [
    'import tempfile, os\nfd, name = tempfile.mkstemp()\ntry:\n    write(name)\nfinally:\n    os.unlink(name)\n',
    'import tempfile\nfrom pathlib import Path\nwith tempfile.NamedTemporaryFile(delete=False) as f:\n    name = Path(f.name)\nname.unlink()\n',
    'from tempfile import TemporaryDirectory\nfrom pathlib import Path\nwith TemporaryDirectory() as root:\n    p = Path(root) / "residue"\n    p.unlink()\n',
    'from send2trash import send2trash\nsend2trash("valuable")\n',
    'p.unlink()  # governance: allow-delete DS001: disposable integration fixture owned by this test\n',
])
def test_recovery_and_verified_temporary_cleanup_pass(repository, source):
    stage(repository, source)
    assert check(repository).returncode == 0


def test_rebound_temporary_path_blocks(repository):
    stage(repository, 'import tempfile, os\nfd, name = tempfile.mkstemp()\nname = user_path\nos.unlink(name)\n')
    assert check(repository).returncode == 1


def test_unchanged_historical_site_does_not_block_unrelated_edit(repository):
    original = 'p.unlink()\nvalue = 1\n'
    stage(repository, original)
    git(repository, "commit", "-qm", "fixture baseline")
    stage(repository, original.replace("value = 1", "value = 2"))
    assert check(repository).returncode == 0
    stage(repository, original + 'q.unlink()\n')
    assert check(repository).returncode == 1


def test_safe_site_becoming_unsafe_blocks_without_changing_call(repository):
    original = 'import tempfile, os\nname = tempfile.mkdtemp()\nos.rmdir(name)\n'
    stage(repository, original)
    git(repository, "commit", "-qm", "safe baseline")
    stage(repository, original.replace("tempfile.mkdtemp()", "user_path"))
    assert check(repository).returncode == 1


def test_staged_parse_failure_visible_without_source_leak(repository):
    stage(repository, 'private_value = (\n')
    result = check(repository)
    assert result.returncode == 2
    assert "parse" in result.stdout.lower() + result.stderr.lower()
    assert "private_value" not in result.stdout + result.stderr


def test_base_commit_checks_committed_changes(repository):
    stage(repository, "value = 1\n")
    git(repository, "commit", "-qm", "baseline")
    base = git(repository, "rev-parse", "HEAD").strip()
    stage(repository, 'p.unlink()\n')
    git(repository, "commit", "-qm", "changed")
    assert check(repository, "--base", base).returncode == 1


def test_string_cannot_authorize_deletion(repository):
    stage(repository, 'note = "# governance: allow-delete DS001: not an actual comment"; p.unlink()\n')
    assert check(repository).returncode == 1


def test_paths_with_spaces_and_deleted_files(repository):
    stage(repository, 'p.unlink()\n', "a space.py")
    assert check(repository).returncode == 1
    git(repository, "commit", "-qm", "historical baseline")
    git(repository, "rm", "a space.py")
    assert check(repository).returncode == 0


@pytest.mark.parametrize("body", [
    'for name in user_paths:\n    os.unlink(name)\n',
    '[os.unlink(name) for name in user_paths]\n',
    'for item in items:\n    os.unlink(name)\n    name = user_path\n',
    'while more:\n    os.unlink(name)\n    name = user_path\n',
    'match user_path:\n    case name:\n        os.unlink(name)\n',
    'name += user_path\nos.unlink(name)\n',
    'name = Path(name).parent\nname.unlink()\n',
    'os.unlink(fd)\n',
    'def later():\n    os.unlink(name)\nname = user_path\nlater()\n',
    'pending = (os.unlink(name) for _ in [1])\nname = user_path\nlist(pending)\n',
    'try:\n    name = user_path\n    might_raise()\n    fd, name = tempfile.mkstemp()\nexcept Exception:\n    os.unlink(name)\n',
])
def test_temporary_proof_cannot_survive_escape_or_rebinding(repository, body):
    stage(repository, 'import tempfile, os\nfrom pathlib import Path\nfd, name = tempfile.mkstemp()\n' + body)
    assert check(repository).returncode == 1


def test_future_shadow_of_import_invalidates_inherited_temporary_origin(repository):
    stage(repository, 'import tempfile, os\ndef cleanup():\n    fd, name = tempfile.mkstemp()\n    os.unlink(name)\ntempfile = user_factory\ncleanup()\n')
    assert check(repository).returncode == 1


def test_optional_temporary_created_inside_try_passes(repository):
    stage(repository, 'import tempfile, os\nname = None\ntry:\n    fd, name = tempfile.mkstemp()\n    write(name)\nfinally:\n    if name is not None:\n        os.unlink(name)\n')
    assert check(repository).returncode == 0


@pytest.mark.parametrize("source", [
    'import tempfile, os\nfd, name = tempfile.mkstemp()\nos.unlink(name); p.unlink()  # governance: allow-delete DS001: fixture cleanup\n',
    'p.unlink(); q.unlink()  # governance: allow-delete DS001: fixture cleanup\n',
    'p.unlink()  # governance: allow-delete DS001:   \n',
])
def test_exception_is_one_call_with_nonempty_rationale(repository, source):
    stage(repository, source)
    assert check(repository).returncode == 1


def test_rename_compares_original_baseline(repository):
    original = 'p.unlink()\n' + '\n'.join(f'x{i} = {i}' for i in range(30)) + '\n'
    stage(repository, original, 'old name.py')
    git(repository, 'commit', '-qm', 'baseline')
    git(repository, 'mv', 'old name.py', 'new name.py')
    assert check(repository).returncode == 0
    stage(repository, original + 'q.unlink()\n', 'new name.py')
    assert check(repository).returncode == 1


def test_git_discovery_failure_is_visible(repository):
    root, env = repository
    result = subprocess.run(['bash', str(MASTER)], cwd=root.parent, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert 'could not discover staged files' in result.stderr
    assert 'No files to check' not in result.stdout


def test_changed_python_symlink_fails_visibly(repository):
    (repository[0] / 'link.py').symlink_to('elsewhere')
    git(repository, 'add', 'link.py')
    assert check(repository).returncode == 2


@pytest.mark.parametrize("body", [
    'os.removedirs(root)\n',
    '(Path(root) / "link" / "valuable").unlink()\n',
    'Path(root).joinpath("link", "valuable").unlink()\n',
    'os.unlink(os.path.join(root, "link", "valuable"))\n',
    '(Path(root) / "../valuable").unlink()\n',
])
def test_temporary_directory_cannot_prove_ancestor_or_symlink_traversal(repository, body):
    stage(repository, 'import tempfile, os\nfrom pathlib import Path\nroot = tempfile.mkdtemp()\n' + body)
    assert check(repository).returncode == 1


@pytest.mark.parametrize("source", [
    'from os import remove\ndef unrelated():\n    remove = 123\ndef cleanup(path):\n    remove(path)\n',
    'import os\nos = os\ndef cleanup(path):\n    os.remove(path)\n',
    'import os\nos.remove((os := user_path))\n',
    'import os, tempfile\nfd, p = tempfile.mkstemp()\n[(os.unlink(p), (p := user_path)) for _ in range(2)]\n',
    'import os, tempfile\nfd,p=tempfile.mkstemp()\n(p := user_path) if condition else (p := tempfile.mkdtemp())\nos.unlink(p)\n',
    'import os, tempfile\np = user_path\ncondition and (p := tempfile.mkdtemp())\nos.unlink(p)\n',
    'try:\n    work()\nexcept choose(p.unlink()):\n    pass\n',
    'def f(x: p.unlink()):\n    pass\n',
    'def f() -> p.unlink():\n    pass\n',
    'x: p.unlink()\n',
    'import tempfile\np.unlink((p := tempfile.mkdtemp()))\n',
    'import tempfile, os\np = user_path\nos.unlink(p, dir_fd=(p := tempfile.mkdtemp()))\n',
    'import tempfile, os\np = user_path\n0 > 1 > (p := tempfile.mkdtemp())\nos.unlink(p)\n',
    'slots[p.unlink()] = result\n',
    'import tempfile, os\nmaker = user_factory\np = maker((maker := tempfile.mkdtemp))\nos.unlink(p)\n',
    'import tempfile, os\nmaker = user_factory\nos.unlink(maker((maker := tempfile.mkdtemp)))\n',
    'import tempfile, os\ndef cleanup():\n    fd, p = tempfile.mkstemp()\n    os.unlink(p)\nfrom user_factory import tempfile\ncleanup()\n',
    'from .tempfile import mkstemp\nimport os\nfd, p = mkstemp()\nos.unlink(p)\n',
    'import tempfile, os\nfrom user_factory import *\nfd, p = tempfile.mkstemp()\nos.unlink(p)\n',
    'import tempfile, os\ndef cleanup():\n    fd, p = tempfile.mkstemp()\n    os.unlink(p)\nfrom user_factory import *\ncleanup()\n',
    'import tempfile as factory, os\nfor item in items:\n    fd, p = factory.mkstemp()\n    os.unlink(p)\n    import foreign as factory\n',
    'import tempfile, os\nf = tempfile.NamedTemporaryFile()\ng = f\ng.name = user_path\nos.unlink(f.name)\n',
    'from os import remove\nif condition:\n    remove = custom\nremove(path)\n',
    'import os, shutil\nif condition:\n    erase = os.remove\nelse:\n    erase = shutil.rmtree\nerase(path)\n',
    'import tempfile\np: (p := user_path) = tempfile.mkdtemp()\np.unlink()\n',
    'import tempfile, os\ndef cleanup():\n    fd,p=tempfile.mkstemp()\n    os.unlink(p)\ndef g(x: (tempfile := user_factory)):\n    pass\ncleanup()\n',
    'with context() as slots[p.unlink()]:\n    pass\n',
    'for slots[p.unlink()] in values:\n    pass\n',
    '[None for slots[p.unlink()] in values]\n',
    'f = lambda p=user_path.unlink(): None\n',
    'import os\nfor item in items:\n    os.remove(user_path)\n    import custom as os\n',
    'import tempfile, os\nfor item in items:\n    fd,p=tempfile.mkstemp()\n    os.unlink(p)\n    from foreign import *\n',
])
def test_review_found_syntax_and_evaluation_order_gaps(repository, source):
    stage(repository, source)
    assert check(repository).returncode == 1


def test_unrelated_local_shadow_preserves_legitimate_atomic_cleanup(repository):
    stage(repository, 'import tempfile, os\ndef unrelated():\n    tempfile = 1\ndef cleanup():\n    name = None\n    try:\n        fd, name = tempfile.mkstemp()\n        os.replace(name, destination)\n    finally:\n        if name is not None:\n            os.unlink(name)\n')
    assert check(repository).returncode == 0
