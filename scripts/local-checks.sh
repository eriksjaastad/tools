#!/usr/bin/env bash
# Local checks for tools (#7828): what .github/workflows/tests.yml runs on each
# pull request.
#
# The shared pre-push (claude-user-config hooks/git-local-checks.py) runs this
# in a fresh worktree of the pushed commit, with LOCAL_CHECKS_SHA and
# LOCAL_CHECKS_BASE set, and bounds the whole run (LOCAL_CHECKS_TIMEOUT,
# default 30 minutes). Run it by hand from a checkout to check that checkout's
# HEAD against its merge-base with origin/main.
#
# content-guard.yml is not replaced yet: its client-name patterns exist only as
# a GitHub secret. When CONTENT_GUARD_PATTERNS or CONTENT_GUARD_PATTERNS_FILE
# is set, the guard runs here too; otherwise this script says it did not run,
# and the GitHub workflow (public repository, free minutes) stays the gate.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
sha="$(git rev-parse HEAD)"
if [ -n "${LOCAL_CHECKS_SHA:-}" ] && [ "$sha" != "$(git rev-parse "$LOCAL_CHECKS_SHA^{commit}")" ]; then
    echo "local checks: this checkout is at $sha, not the pushed $LOCAL_CHECKS_SHA" >&2
    exit 2
fi
base="${LOCAL_CHECKS_BASE:-$(git merge-base "$sha" origin/main)}"

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
# The validator compares --base with HEAD, which is the pushed commit here.
step "changed Python deletion sites" py governance/validators/source-deletion-check.py --base "$base"
# As in CI: PYTHONPATH=integrity-warden, and no content-guard secret, which
# test_content_guard expects to be unset.
step "test suites" env -u CONTENT_GUARD_PATTERNS -u CONTENT_GUARD_PATTERNS_FILE PYTHONPATH=integrity-warden \
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
if [ -n "${CONTENT_GUARD_PATTERNS:-}${CONTENT_GUARD_PATTERNS_FILE:-}" ]; then
    step "content guard" "$UV" run -q --no-project --python 3.12 python -I governance/validators/content-guard.py --tracked
else
    echo "== content guard: NOT RUN here (no CONTENT_GUARD_PATTERNS); the GitHub content-guard workflow is still the gate"
fi

if [ "${#failed[@]}" -gt 0 ]; then
    printf 'local checks FAILED: %s\n' "${failed[@]}"
    exit 1
fi
echo "local checks passed"
