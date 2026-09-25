"""Tests for governance/sync-gh-workflows.sh.

The suite runs the real script against a fake `gha` executable. The fake reads
a scenario file (list of prefix-match rules), logs every invocation, and exits
with the rule's status. No network access and no real GitHub writes happen.

Scenarios cover the required contract: dry-run, branch/PR creation, an
existing PR, a missing file, archived repos, and API failures.
"""

import base64
import json
import os
from pathlib import Path
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "governance" / "sync-gh-workflows.sh"
DEAD_WRAPPER_PATH = ".github/workflows/claude-review.yml"
DEAD_WRAPPER_REF = (
    "eriksjaastad/tools/.github/workflows/claude-review-reusable.yml@main"
)
SYNC_BRANCH = "tools-sync/delete-dead-claude-review"
REPO = "testrepo"
SLUG = f"eriksjaastad/{REPO}"

CANONICAL_REPOS = [
    "ai-journal",
    "ai-memory",
    "ai-memory-replay",
    "analyze-youtube-videos",
    "cortana-personal-ai",
    "Flo-Fi",
    "holoscape",
    "hypocrisynow",
    "market-research",
    "model-updater",
    "muffinpanrecipes",
    "Portfolio-ai",
    "project-scaffolding",
    "project-tracker",
    "tax-organizer",
    "trading-copilot",
]

WRAPPER_TEXT = (
    "name: Claude Review\n"
    "on: pull_request\n"
    f"uses: {DEAD_WRAPPER_REF}\n"
)

FAKE_GHA = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["FAKE_GHA_SCENARIO"]) as f:
    scenario = json.load(f)
with open(os.environ["FAKE_GHA_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
for rule in scenario:
    match = rule["match"]
    if len(args) >= len(match) and all(
        a.startswith(m) for a, m in zip(args, match)
    ):
        sys.stdout.write(rule.get("stdout", ""))
        sys.stderr.write(rule.get("stderr", ""))
        sys.exit(rule.get("status", 0))
sys.stderr.write("FAKE_GHA_NO_MATCH: " + json.dumps(args) + "\\n")
sys.exit(99)
"""


def make_gha(tmp_path, rules):
    gha = tmp_path / "gha"
    gha.write_text(FAKE_GHA)
    gha.chmod(0o755)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps(rules))
    log = tmp_path / "gha.log"
    log.write_text("")
    return gha, scenario, log


def run_sync(tmp_path, gha, scenario, log, *args):
    env = os.environ.copy()
    env["GHA_BIN"] = str(gha)
    env["FAKE_GHA_SCENARIO"] = str(scenario)
    env["FAKE_GHA_LOG"] = str(log)
    return subprocess.run(
        [str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def read_calls(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line]


def repo_list_rule(entries):
    return {
        "match": ["repo", "list", "eriksjaastad", "--limit", "500",
                  "--json", "name,isArchived"],
        "stdout": json.dumps(
            [{"name": name, "isArchived": archived} for name, archived in entries]
        ),
        "status": 0,
    }


def repo_info_rule(repo=REPO, default_branch="main", archived=False, status=0):
    slug = f"eriksjaastad/{repo}"
    return {
        "match": ["api", f"repos/{slug}"],
        "stdout": json.dumps(
            {
                "full_name": slug,
                "default_branch": default_branch,
                "archived": archived,
            }
        ),
        "status": status,
    }


def contents_rule(text=WRAPPER_TEXT, status=0):
    return {
        "match": ["api",
                  f"repos/{SLUG}/contents/{DEAD_WRAPPER_PATH}"],
        "stdout": json.dumps(
            {
                "name": "claude-review.yml",
                "sha": "deadbeef",
                "content": base64.b64encode(text.encode()).decode(),
            }
        ),
        "status": status,
    }


def pr_list_rule(pulls=None):
    return {
        "match": ["pr", "list", "--repo", SLUG, "--head", SYNC_BRANCH,
                  "--state", "open", "--json", "number,url"],
        "stdout": json.dumps(pulls or []),
        "status": 0,
    }


def sync_branch_ref_rule(status):
    return {
        "match": ["api",
                  f"repos/{SLUG}/git/ref/heads/{SYNC_BRANCH}"],
        "stdout": "",
        "status": status,
    }


def default_branch_ref_rule():
    return {
        "match": ["api", f"repos/{SLUG}/git/ref/heads/main"],
        "stdout": json.dumps(
            {"ref": "refs/heads/main", "object": {"sha": "abc123"}}
        ),
        "status": 0,
    }


def create_ref_rule(status=0):
    return {
        "match": ["api", "-X", "POST", f"repos/{SLUG}/git/refs"],
        "stdout": "",
        "status": status,
    }


def delete_on_branch_rule(status=0):
    return {
        "match": ["api", "-X", "DELETE",
                  f"repos/{SLUG}/contents/{DEAD_WRAPPER_PATH}"],
        "stdout": "",
        "status": status,
    }


def pr_create_rule(status=0):
    return {
        "match": ["pr", "create", "--repo", SLUG, "--head",
                  f"eriksjaastad:{SYNC_BRANCH}", "--base", "main",
                  "--title", "Remove dead claude-review workflow"],
        "stdout": f"https://github.com/{SLUG}/pull/1",
        "status": status,
    }


def test_dry_run_reports_branch_and_pr_without_writes(tmp_path):
    rules = [
        contents_rule(),
        repo_info_rule(),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--dry-run",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 0, result.stderr
    assert "would create branch" in result.stdout
    assert "would delete wrapper via contents API" in result.stdout
    assert "would open PR" in result.stdout
    calls = read_calls(log)
    # Dry-run must only read: no POST refs, no DELETE, no pr create.
    assert not any("pr create" in call[1:3] for call in calls)
    assert not any("-X" in call and "DELETE" in call for call in calls)
    assert not any("git/refs" in " ".join(call) for call in calls)


def test_apply_creates_branch_deletes_file_and_opens_pr(tmp_path):
    rules = [
        contents_rule(),
        pr_list_rule(),
        sync_branch_ref_rule(status=1),
        default_branch_ref_rule(),
        create_ref_rule(),
        delete_on_branch_rule(),
        pr_create_rule(),
        repo_info_rule(),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--apply",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 0, result.stderr
    assert "✓ created branch" in result.stdout
    assert "✓ wrapper deleted on branch" in result.stdout
    assert "✓ PR opened: https://github.com/eriksjaastad/testrepo/pull/1" in result.stdout
    calls = read_calls(log)
    expected_delete = [
        "api", "-X", "DELETE",
        f"repos/{SLUG}/contents/{DEAD_WRAPPER_PATH}",
        "-f", "message=Delete dead claude-review wrapper",
        "-f", "sha=deadbeef",
        "-f", f"branch={SYNC_BRANCH}",
    ]
    assert ["api", "-X", "POST", f"repos/{SLUG}/git/refs",
            "-f", f"ref=refs/heads/{SYNC_BRANCH}",
            "-f", "sha=abc123"] in calls
    assert expected_delete in calls, json.dumps(calls)


def test_apply_skips_when_pr_already_open(tmp_path):
    rules = [
        contents_rule(),
        pr_list_rule([{"number": 7,
                       "url": "https://github.com/eriksjaastad/testrepo/pull/7"}]),
        repo_info_rule(),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--apply",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 0, result.stderr
    assert "PR already open: #7" in result.stdout
    calls = read_calls(log)
    assert not any("-X" in call and "POST" in call for call in calls)
    assert not any("pr create" in call[1:3] for call in calls)


def test_missing_file_is_reported_already_absent(tmp_path):
    rules = [
        contents_rule(status=1),
        repo_info_rule(),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--apply",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 0, result.stderr
    assert "already absent on main" in result.stdout


def test_archived_repo_is_skipped_explicit_target(tmp_path):
    rules = [
        repo_info_rule(archived=True),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--apply",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 0, result.stderr
    assert "skip: archived, no write attempted" in result.stdout
    calls = read_calls(log)
    # Only the repo read happened; no file, branch, or PR calls followed.
    assert all(call[:2] == ["api", f"repos/{SLUG}"] for call in calls)


def test_archived_repo_is_filtered_from_canonical_list(tmp_path):
    entries = [(name, name == "ai-journal") for name in CANONICAL_REPOS]
    rules = [repo_list_rule(entries)]
    for name in CANONICAL_REPOS:
        if name == "ai-journal":
            continue
        # Specific rule first: the dead wrapper is absent on every live repo,
        # so each surviving target reports "already absent" and exits cleanly.
        rules.append({
            "match": ["api",
                      f"repos/eriksjaastad/{name}/contents/{DEAD_WRAPPER_PATH}"],
            "stdout": "",
            "status": 1,
        })
    for name in CANONICAL_REPOS:
        if name == "ai-journal":
            continue
        rules.append(repo_info_rule(repo=name))
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--dry-run",
                      "delete-dead-claude-review")

    assert result.returncode == 0, result.stderr
    assert "skip: archived, no write attempted" in result.stderr
    assert "Repos:  15" in result.stdout
    # The archived repo never gets a per-repo api call.
    calls = read_calls(log)
    assert not any("ai-journal" in " ".join(call) and call[0] == "api"
                   for call in calls)


def test_api_failure_fetching_repo_exits_nonzero(tmp_path):
    rules = [
        repo_info_rule(status=1),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--apply",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 1
    assert "ERROR: cannot fetch repo" in result.stdout
    assert "Done with 1 failure(s)." in result.stdout


def test_api_failure_creating_pr_exits_nonzero(tmp_path):
    rules = [
        contents_rule(),
        pr_list_rule(),
        sync_branch_ref_rule(status=1),
        default_branch_ref_rule(),
        create_ref_rule(),
        delete_on_branch_rule(),
        pr_create_rule(status=1),
        repo_info_rule(),
    ]
    gha, scenario, log = make_gha(tmp_path, rules)
    result = run_sync(tmp_path, gha, scenario, log, "--apply",
                      "delete-dead-claude-review", REPO)

    assert result.returncode == 1
    assert "branch updated but failed to open PR" in result.stdout
    assert "Done with 1 failure(s)." in result.stdout


def test_missing_gha_shim_fails_visibly(tmp_path):
    missing = tmp_path / "missing-gha"
    scenario = tmp_path / "scenario.json"
    scenario.write_text("[]")
    log = tmp_path / "gha.log"
    log.write_text("")
    env = os.environ.copy()
    env["GHA_BIN"] = str(missing)
    env["FAKE_GHA_SCENARIO"] = str(scenario)
    env["FAKE_GHA_LOG"] = str(log)
    result = subprocess.run(
        [str(SCRIPT), "--dry-run", "delete-dead-claude-review"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert "not executable" in result.stderr
    assert "managed identity" in result.stderr
