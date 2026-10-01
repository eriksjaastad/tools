#!/usr/bin/env bash
# Local checks for tools (#7828): what .github/workflows/tests.yml runs on each
# pull request. The shared pre-push runs this with LOCAL_CHECKS_SHA/
# LOCAL_CHECKS_BASE set (claude-user-config hooks/git-local-checks.py); run it
# by hand from the repo root and the base is the merge-base with origin/main.
#
# content-guard.yml is not replaced yet: its client-name patterns exist only as
# a GitHub secret. When CONTENT_GUARD_PATTERNS or CONTENT_GUARD_PATTERNS_FILE
# is set, the guard runs here too; otherwise this script says it did not run,
# and the GitHub workflow (public repository, free minutes) stays the gate.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
base="${LOCAL_CHECKS_BASE:-$(git merge-base HEAD origin/main)}"

# Every step runs even after a failure, so one run reports every broken gate.
failed=()
step() {
    local name="$1"
    shift
    echo "== $name"
    if ! "$@"; then
        failed+=("$name")
    fi
}

py() { "$UV" run -q --python 3.12 "$@"; }

step "silent-failure gate" py governance/silent-failure-gate.py
step "changed Python deletion sites" py governance/validators/source-deletion-check.py --base "$base"
# CI ran the suites without the content-guard secret; test_content_guard expects it unset.
step "test suites" env -u CONTENT_GUARD_PATTERNS -u CONTENT_GUARD_PATTERNS_FILE "$UV" run -q --python 3.12 --with 'pytest>=8,<10' --with 'PyJWT>=2,<3' \
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
