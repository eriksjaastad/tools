"""Exercise the actual wrapper with an isolated PATH and no real credentials."""

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def wrapper(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Only system utilities needed by gh-agent are reachable. In particular the
    # installed uv, gh, git, and Doppler executables cannot be selected by PATH.
    for utility in ("dirname", "sed"):
        (bin_dir / utility).symlink_to(Path("/usr/bin") / utility)
    uv_program = """
import json
import os
import sys
from pathlib import Path
Path(os.environ['UV_CALL_LOG']).write_text(json.dumps(sys.argv[1:]))
sys.stderr.write(os.environ.get('STUB_DIAGNOSTIC', ''))
sys.stdout.write(os.environ.get('STUB_BUNDLE', ''))
sys.exit(int(os.environ.get('STUB_STATUS', '0')))
"""
    gh_program = """
import json
import os
import sys
from pathlib import Path
Path(os.environ['GH_CALL_LOG']).write_text(json.dumps({
    'args': sys.argv[1:], 'token': os.environ.get('GH_TOKEN'),
    'author': os.environ.get('GIT_AUTHOR_NAME'),
    'committer': os.environ.get('GIT_COMMITTER_NAME'),
}))
"""
    for name, program in (("uv", uv_program), ("gh", gh_program), ("git", gh_program)):
        script = tmp_path / f"{name}_stub.py"
        script.write_text(program)
        executable = bin_dir / name
        executable.write_text(
            f"#!/bin/bash\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} \"$@\"\n"
        )
        executable.chmod(0o755)

    # Do not copy the parent environment: it can contain live tokens and keys.
    env = {
        "PATH": str(bin_dir),
        "HOME": str(tmp_path / "isolated-home"),
        "UV_CALL_LOG": str(tmp_path / "uv-call.json"),
        "GH_CALL_LOG": str(tmp_path / "gh-call.json"),
        "GH_TOKEN": "offline-inherited-token-must-not-be-used",
    }

    def invoke(*args, bundle="", status=0, diagnostic="", expected_code=0):
        invocation_env = env | {
            "STUB_BUNDLE": bundle,
            "STUB_STATUS": str(status),
            "STUB_DIAGNOSTIC": diagnostic,
        }
        try:
            result = subprocess.run(
                ["/bin/bash", str(REPO / "gh-agent.sh"), *args],
                cwd=tmp_path, env=invocation_env, text=True, capture_output=True,
                check=True, timeout=10,
            )
        except subprocess.CalledProcessError as error:
            assert error.returncode == expected_code, error.stderr
            return error
        assert expected_code == 0, "Wrapper unexpectedly succeeded"
        return result

    return invoke, tmp_path


@pytest.mark.parametrize(
    "bundle,status,diagnostic",
    [
        ("", 1, "Error: Unknown identity 'claude'. Valid: architect, auxesis-coder, manager\n"),
        ("", 7, "Error: token resolution failed\n"),
        ("manager\nmanager-identity[bot]\noffline-partial-token\n", 1, "Error: partial resolution failed\n"),
        ("manager\nmanager-identity[bot]\n", 0, ""),
        ("\nmanager-identity[bot]\noffline-token\n", 0, ""),
        ("", 0, ""),
    ],
    ids=["unknown-identity", "failed-resolution", "failed-partial-bundle", "empty-token", "empty-identity", "empty-bundle"],
)
@pytest.mark.parametrize("identity", ["manager", "--auto"])
def test_resolution_failure_never_invokes_github(wrapper, bundle, status, diagnostic, identity):
    invoke, tmp_path = wrapper
    result = invoke(identity, "pr", "list", bundle=bundle, status=status, diagnostic=diagnostic, expected_code=1)
    assert "refusing to run" in result.stderr
    assert diagnostic in result.stderr
    assert not (tmp_path / "gh-call.json").exists()
    assert "offline-partial-token" not in result.stderr + result.stdout


@pytest.mark.parametrize("identity", ["manager", "--auto"])
def test_valid_bundle_invokes_github_with_resolved_identity(wrapper, identity):
    invoke, tmp_path = wrapper
    invoke(identity, "pr", "list", bundle="manager\nmanager-identity[bot]\noffline-token\n")
    call = json.loads((tmp_path / "gh-call.json").read_text())
    assert call == {
        "args": ["pr", "list"], "token": "offline-token",
        "author": "manager-identity[bot]", "committer": "manager-identity[bot]",
    }
    uv_args = json.loads((tmp_path / "uv-call.json").read_text())
    assert uv_args[-3:] == [str(REPO / "github-app-token.py"), identity, "--bundle"]


def test_no_arguments_reports_usage_without_resolving_credentials(wrapper):
    invoke, tmp_path = wrapper
    result = invoke(expected_code=1)
    assert "Usage:" in result.stderr
    assert not (tmp_path / "uv-call.json").exists()
    assert not (tmp_path / "gh-call.json").exists()


def test_empty_token_also_blocks_git_execution(wrapper):
    invoke, tmp_path = wrapper
    invoke("manager", "--", "git", "status", bundle="manager\nmanager-identity[bot]\n", expected_code=1)
    assert not (tmp_path / "gh-call.json").exists()
