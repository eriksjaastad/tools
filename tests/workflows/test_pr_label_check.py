"""Regression tests for the PR type-label derivation workflow.

The logic under test is the `run:` block of `.github/workflows/pr-label-check.yml`.
That file is propagated byte-identical to 31 repositories and its `check-label`
job is a required status check in six of them, so a silent break in the title
parser is expensive and invisible.

These tests extract the shipped `run:` block from the YAML and execute it for
real against a stubbed `gh` on PATH. They deliberately do NOT re-implement the
parser: a copy would be a second source of truth and could agree with itself
while disagreeing with what actually runs in CI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-label-check.yml"

# Mirrors the canonical allowlist. Asserted against the workflow below so the
# two cannot drift silently.
CANONICAL_LABELS = {
    "feature",
    "enhancement",
    "bug",
    "chore",
    "refactor",
    "docs",
    "test",
    "hotfix",
    "security",
    "perf",
}

GH_STUB = """#!/usr/bin/env bash
# Stand-in for `gh`. Serves the label list from PR_LABELS_FIXTURE and records
# every `pr edit` invocation to GH_EDIT_LOG so the test can assert on it.
set -euo pipefail

if [ "${1:-}" = "pr" ] && [ "${2:-}" = "view" ]; then
  if [ "${GH_VIEW_FAILS:-0}" = "1" ]; then
    echo "gh: simulated API failure" >&2
    exit 1
  fi
  printf '%s' "${PR_LABELS_FIXTURE:-}"
  exit 0
fi

if [ "${1:-}" = "pr" ] && [ "${2:-}" = "edit" ]; then
  shift 2
  # Failure is selectable per call, not global. A global switch made the
  # "add succeeded, remove failed" branch unreachable, so it went untested.
  case " $* " in
    *" --add-label "*) kind=add ;;
    *)                 kind=remove ;;
  esac
  if [ "${GH_EDIT_FAILS:-0}" = "1" ] || [ "${GH_EDIT_FAILS:-}" = "$kind" ]; then
    echo "gh: simulated failure on $kind" >&2
    exit 1
  fi
  echo "$*" >> "$GH_EDIT_LOG"
  exit 0
fi

echo "gh stub: unexpected invocation: $*" >&2
exit 99
"""


def _run_block() -> str:
    """Pull the shipped shell out of the workflow's single step."""
    doc = yaml.safe_load(WORKFLOW.read_text())
    steps = doc["jobs"]["check-label"]["steps"]
    assert len(steps) == 1, "workflow gained a step; update this test"
    return steps[0]["run"]


@pytest.fixture
def harness(tmp_path):
    """Execute the real run-block with a stubbed `gh` and given inputs."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "gh"
    stub.write_text(GH_STUB)
    stub.chmod(0o755)

    script = tmp_path / "step.sh"
    script.write_text(_run_block())

    edit_log = tmp_path / "edits.log"
    edit_log.touch()

    def run(title: str, labels: tuple[str, ...] = (), **overrides):
        env = dict(os.environ)
        env.update(
            PATH=f"{bindir}:{env['PATH']}",
            GH_TOKEN="stub",
            PR_NUMBER="1",
            PR_TITLE=title,
            REPO="eriksjaastad/tools",
            PR_LABELS_FIXTURE="\n".join(labels),
            GH_EDIT_LOG=str(edit_log),
        )
        env.update({k: str(v) for k, v in overrides.items()})
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )
        return proc, edit_log.read_text().strip()

    return run


# --- the allowlist itself -------------------------------------------------


def test_workflow_job_id_is_check_label():
    """Six repos require the status-check context named `check-label`.

    Renaming the job leaves those required checks permanently pending and makes
    every PR in those repos unmergeable. This test is the tripwire.
    """
    doc = yaml.safe_load(WORKFLOW.read_text())
    assert list(doc["jobs"]) == ["check-label"]


def test_workflow_requests_write_permission():
    doc = yaml.safe_load(WORKFLOW.read_text())
    assert doc["permissions"]["pull-requests"] == "write"


def test_allowlist_has_not_drifted():
    run = _run_block()
    declared = next(
        line.split("=", 1)[1].strip().strip('"')
        for line in run.splitlines()
        if line.strip().startswith("TYPES=")
    )
    assert set(declared.split()) == CANONICAL_LABELS


# --- derivation -----------------------------------------------------------


@pytest.mark.parametrize(
    "title,expected",
    [
        ("feat: add baker agent (#1234)", "feature"),
        ("fix: correct the archived-repo filter (#7177)", "bug"),
        ("docs: rewrite the readme", "docs"),
        ("chore: bump deps", "chore"),
        ("refactor: split the resolver", "refactor"),
        ("test: cover the parser", "test"),
        ("perf: speed up the token cache", "perf"),
        ("ci: bump actions", "chore"),
        ("build: update the lockfile", "chore"),
        ("style: reformat", "chore"),
        ("docs(readme): fix a link", "docs"),
        ("feat(api)!: breaking change", "feature"),
        ("FEAT: shouting", "feature"),
        ("feat: a title with: a second colon", "feature"),
        ("  feat: leading whitespace", "feature"),
    ],
)
def test_derives_label_from_title(harness, title, expected):
    proc, edits = harness(title)
    assert proc.returncode == 0, proc.stderr
    assert f"--add-label {expected}" in edits


@pytest.mark.parametrize(
    "title",
    [
        "no type here",
        "wip",
        "feat add thing",
        "Merge pull request #65 from eriksjaastad/x",
        "featuring: a near miss",
        "",
        "🚀 feat: emoji prefix",
    ],
)
def test_unrecognizable_title_fails_loudly(harness, title):
    proc, edits = harness(title)
    assert proc.returncode == 1
    assert "no recognizable type" in proc.stdout
    assert edits == "", "must not label a PR it could not classify"


def test_title_cannot_inject_shell(harness, tmp_path):
    """PR_TITLE is attacker-influenced on any repo taking outside PRs.

    The canary lives under tmp_path, not /tmp: a literal path would survive a
    regression and then keep failing this test on that machine forever, long
    after the underlying bug was fixed.
    """
    canary = tmp_path / "pwned"
    proc, edits = harness(f"fix: $(touch {canary}) `id`; rm -rf /")
    assert proc.returncode == 0
    assert "--add-label bug" in edits
    assert not canary.exists()


# --- existing labels ------------------------------------------------------


@pytest.mark.parametrize("override", ["enhancement", "hotfix", "security"])
def test_manual_override_labels_are_never_touched(harness, override):
    proc, edits = harness("feat: would otherwise derive feature", labels=(override,))
    assert proc.returncode == 0
    assert "Manual override label present" in proc.stdout
    assert edits == ""


def test_correct_label_is_left_alone(harness):
    proc, edits = harness("feat: already labelled", labels=("feature",))
    assert proc.returncode == 0
    assert "already correct" in proc.stdout
    assert edits == ""


def test_stale_derived_label_is_swapped_after_a_title_edit(harness):
    """A title corrected from feat: to fix: must not keep both labels."""
    proc, edits = harness("fix: retitled from feat", labels=("feature",))
    assert proc.returncode == 0
    assert "--add-label bug" in edits
    assert "--remove-label feature" in edits


def test_add_happens_before_remove(harness):
    """Order matters: a failed add must not leave the PR with no type label.

    If the removal ran first and the add then failed, a PR that had `feature`
    would end up with nothing at all -- worse than when the job started.
    """
    proc, edits = harness("fix: retitled from feat", labels=("feature",))
    assert proc.returncode == 0
    lines = edits.splitlines()
    add_at = next(i for i, ln in enumerate(lines) if "--add-label" in ln)
    rm_at = next(i for i, ln in enumerate(lines) if "--remove-label" in ln)
    assert add_at < rm_at


def test_correct_label_alongside_a_stray_one_is_cleaned_up(harness):
    """The reason the removal loop cannot sit behind the already-correct exit.

    A PR carrying both `feature` (correct for its title) and a leftover `chore`
    would otherwise keep both forever -- no later event would ever clean it.
    """
    proc, edits = harness("feat: x", labels=("feature", "chore"))
    assert proc.returncode == 0
    assert "--remove-label chore" in edits
    assert "--add-label" not in edits, "correct label was already present"


def test_hand_set_derived_label_is_overridden_by_the_title(harness):
    """Documents a deliberate design choice, so a future change is a decision.

    Hand-setting `chore` on a `feat:`-titled PR does NOT stick: the seven
    derived labels are tied to the title. To recategorize, edit the title --
    which is also what lands in the merge commit. `enhancement`, `hotfix` and
    `security` exist for the cases that genuinely need a human override.
    """
    proc, edits = harness("feat: still a feature", labels=("chore",))
    assert proc.returncode == 0
    assert "--add-label feature" in edits
    assert "--remove-label chore" in edits


def test_unrelated_non_type_labels_survive(harness):
    proc, edits = harness("feat: x", labels=("needs-discussion",))
    assert proc.returncode == 0
    assert "--add-label feature" in edits
    assert "--remove-label" not in edits


# --- failure modes --------------------------------------------------------


def test_api_read_failure_is_not_mistaken_for_no_labels(harness):
    """A broken `gh pr view` must abort, not silently derive from scratch."""
    proc, edits = harness("feat: x", GH_VIEW_FAILS=1)
    assert proc.returncode != 0
    assert edits == "", "must not write labels on an unverified read"


def test_label_write_failure_explains_the_fork_case(harness):
    proc, _ = harness("feat: x", GH_EDIT_FAILS="add")
    assert proc.returncode == 1
    assert "Could not apply label" in proc.stdout
    assert "read-only token" in proc.stdout


def test_failing_to_remove_a_stray_label_does_not_fail_the_check(harness):
    """The check's contract is met once the right label is on; cleanup is not.

    `check-label` is a required status check in six repos. Hard-failing here
    would block a merge over a spare label on the strength of a transient rate
    limit, when the state left behind -- correct label plus a duplicate -- is
    exactly what this workflow produced for months before it cleaned up at all.
    """
    proc, edits = harness(
        "fix: retitled from feat", labels=("feature",), GH_EDIT_FAILS="remove"
    )
    assert proc.returncode == 0, "a cosmetic cleanup failure must not block a merge"
    assert "--add-label bug" in edits, "the label that matters still got applied"
    assert "::warning::" in proc.stdout
    assert "::error::" not in proc.stdout


def test_add_failure_still_fails_the_check(harness):
    """The complement: failing to apply the label IS a real failure."""
    proc, edits = harness("fix: x", labels=("feature",), GH_EDIT_FAILS="add")
    assert proc.returncode == 1
    assert "::error::" in proc.stdout
    assert "--remove-label" not in edits, "must not strip the old label after a failed add"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
def test_run_block_is_valid_shell():
    proc = subprocess.run(
        ["bash", "-n"],
        input=_run_block(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
