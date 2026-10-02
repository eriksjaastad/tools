#!/usr/bin/env bash
# Local checks for tools (#7828): what .github/workflows/tests.yml runs on each
# pull request.
#
# Only the shared runner (claude-user-config hooks/git-local-checks.py) runs
# this: on every push, and by hand with `~/.claude/hooks/git-local-checks.py
# --head`. It checks the commit out in a fresh worktree, sets the
# LOCAL_CHECKS_* variables and bounds the run.
#
# content-guard.yml is not replaced: its client-name patterns are private, and
# the workflow scans with trusted code from the base branch. This script runs
# the pushed commit's own code, so it never runs the guard and never passes the
# pattern variables to any check. The GitHub workflow (public repository, free
# minutes) stays the content-guard gate.
set -euo pipefail
unset CONTENT_GUARD_PATTERNS CONTENT_GUARD_PATTERNS_FILE

if [ "${LOCAL_CHECKS_CLEAN:-}" != 1 ]; then
    echo "local checks: run them with the shared runner, which checks HEAD in a fresh worktree:" >&2
    echo "  ~/.claude/hooks/git-local-checks.py --head" >&2
    exit 2
fi
cd "$(git rev-parse --show-toplevel)"
sha="$(git rev-parse HEAD)"
if [ "$sha" != "$(git rev-parse "${LOCAL_CHECKS_SHA}^{commit}")" ]; then
    echo "local checks: this checkout is at $sha, not $LOCAL_CHECKS_SHA" >&2
    exit 2
fi
echo "local checks: $sha in $(pwd -P)"

UV="$(command -v uv || echo "$HOME/.local/bin/uv")"

# Run one named check, record a failure, and return its status.
failed=()
check() {
    local name="$1" status=0
    shift
    echo "== $name"
    "$@" || status=$?
    if [ "$status" -ne 0 ]; then
        failed+=("$name")
    fi
    return "$status"
}
# A check nothing else depends on: its failure is recorded, and the run goes on.
step() { check "$@" || true; }

py() { "$UV" run -q --python 3.12 "$@"; }

step "silent-failure gate" py governance/silent-failure-gate.py
# The deletion check compares a base with HEAD (the pushed commit). The runner
# leaves the base empty when the remote has no default branch; then there is no
# range to compare, and this says so instead of refusing the push.
if [ -n "${LOCAL_CHECKS_BASE:-}" ]; then
    step "changed Python deletion sites" py governance/validators/source-deletion-check.py --base "$LOCAL_CHECKS_BASE"
else
    echo "== changed Python deletion sites: NOT RUN (no base: the remote has no default branch to compare with)"
fi
# As in CI: PYTHONPATH=integrity-warden.
step "test suites" env PYTHONPATH=integrity-warden \
    "$UV" run -q --python 3.12 --with 'pytest>=8,<10' --with 'PyJWT>=2,<3' \
    --with 'httpx>=0.27,<1' --with 'typer>=0.12,<1' --with 'rich>=13,<15' \
    --with 'PyYAML>=6,<7' pytest -q -p no:cacheprovider \
    governance/validators/tests/ \
    integrity-warden/tests/ \
    tests/auth/ \
    tests/hooks/ \
    tests/remediation/ \
    tests/startup-cleanup/ \
    tests/workflows/ \
    route/test_pricing.py \
    route/test_readers.py

if [ "${#failed[@]}" -gt 0 ]; then
    printf 'local checks FAILED: %s\n' "${failed[@]}"
    exit 1
fi
echo "local checks passed"
