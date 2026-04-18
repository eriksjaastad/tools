#!/usr/bin/env bash
# Tests for package-audit.sh (#6013 Finding 2).
#
# Uses a fake `python3` that exits 42 so we can distinguish audit verdicts
# from shell passthrough:
#   - audit blocks        → exit 1
#   - audit passes + exec → exit 42
#   - audit skips + exec  → exit 42
#
# Run directly: bash tests/test_package_audit.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUDIT="$REPO_ROOT/package-audit.sh"

TMP="$(mktemp -d)"
# Per project rule: never use rm; use trash (auto-empties from /tmp eventually).
trap 'trash "$TMP" >/dev/null 2>&1 || true' EXIT

# Fake python3 that exits 42 — lets us detect when exec runs.
cat > "$TMP/python3" <<'EOF'
#!/usr/bin/env bash
exit 42
EOF
chmod +x "$TMP/python3"

# Use a clean workdir with no lockfile so the lockfile warning doesn't matter.
cd "$TMP"

PASSED=0
FAILED=0

run() {
    # Exec in a subshell with our fake python3 first on PATH so `exec "$@"`
    # inside package-audit.sh hits the fake, not a real python.
    PATH="$TMP:$PATH" bash "$AUDIT" "$@" > /dev/null 2>&1
    echo $?
}

expect_exit() {
    local label="$1" expected="$2"
    shift 2
    local actual
    actual="$(run "$@")"
    if [[ "$actual" == "$expected" ]]; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
        echo "  FAIL: $label — expected $expected, got $actual"
        echo "         args: $*"
    fi
}

# ── python -m pip install: audit runs ────────────────────────────────────

# Fresh install of a non-banned package → audit passes → exec → 42.
expect_exit "python3 -m pip install passthrough" 42 \
    python3 -m pip install requests

# Fresh install of a banned package → audit blocks → exit 1.
expect_exit "python3 -m pip install banned" 1 \
    python3 -m pip install litellm

# pip3 entrypoint also triggers install audit.
expect_exit "python3 -m pip3 install passthrough" 42 \
    python3 -m pip3 install requests

# ── python -m pip NON-INSTALL (#6013 Finding 2 fix) ──────────────────────
# Previously: `pip show X` set pkg_start=4 and audited X as an install,
# producing misleading block messages for read-only queries.
# Now: show / list / freeze / etc. skip the audit and exec through.

expect_exit "python3 -m pip show skips audit" 42 \
    python3 -m pip show litellm

expect_exit "python3 -m pip list skips audit" 42 \
    python3 -m pip list

expect_exit "python3 -m pip freeze skips audit" 42 \
    python3 -m pip freeze

# ── Direct pip invocations still work ────────────────────────────────────

# Use a fake pip that exits 42 too.
cat > "$TMP/pip" <<'EOF'
#!/usr/bin/env bash
exit 42
EOF
chmod +x "$TMP/pip"

expect_exit "pip install passthrough" 42 \
    pip install requests

expect_exit "pip install banned" 1 \
    pip install litellm

# ── Summary ──────────────────────────────────────────────────────────────

echo ""
echo "$PASSED passed, $FAILED failed, $((PASSED + FAILED)) total"
[[ $FAILED -eq 0 ]] && exit 0 || exit 1
