#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <identity> <gh args...>" >&2
  echo "   or: $0 <identity> -- git <args...>" >&2
  echo "   or: $0 --auto <gh args...>" >&2
  echo "   or: $0 --auto -- git <args...>" >&2
  echo "" >&2
  echo "Identities:" >&2
  echo "  architect     — cross-repo planning/review (auto-picked at ~/projects root)" >&2
  echo "  auxesis-coder — autonomous API code-dev (explicit only, scope-restricted)" >&2
  echo "  manager       — project-scoped execution (auto-picked inside a project dir)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOKEN_SCRIPT="$SCRIPT_DIR/github-app-token.py"

identity="$1"
shift

# Resolve identity, botname, and token in ONE interpreter start.
# --bundle prints three lines: identity, botname, token. Previously this ran
# the token script twice (once for --botname, once for the token), paying uv
# startup and a full Doppler + GitHub token exchange each time.
UV_ARGS=(--with 'PyJWT>=2.9.0' --with 'cryptography>=42.0.0')
# `|| bundle=""` keeps `set -e` from aborting here, so the explicit check
# below can report *why* resolution failed instead of exiting silently.
# stderr is deliberately not redirected: the token script's diagnostics are
# the only signal explaining a failure.
if [ "$identity" = "--auto" ]; then
  bundle="$(uv run "${UV_ARGS[@]}" "$TOKEN_SCRIPT" --auto --bundle)" || bundle=""
else
  bundle="$(uv run "${UV_ARGS[@]}" "$TOKEN_SCRIPT" "$identity" --bundle)" || bundle=""
fi

identity="$(printf '%s\n' "$bundle" | sed -n 1p)"
botname="$(printf '%s\n' "$bundle" | sed -n 2p)"
token="$(printf '%s\n' "$bundle" | sed -n 3p)"

# Fail closed: an unresolved identity or a missing token must never fall
# through to an unauthenticated or wrongly-attributed gh call.
if [ -z "$identity" ] || [ -z "$token" ]; then
  echo "gh-agent: could not resolve a GitHub identity (see error above)." >&2
  echo "gh-agent: refusing to run '$*' unauthenticated." >&2
  exit 1
fi
[ -n "$botname" ] || botname="${identity}[bot]"

export GH_TOKEN="$token"

export GIT_AUTHOR_NAME="$botname"
export GIT_AUTHOR_EMAIL="$botname@users.noreply.github.com"
export GIT_COMMITTER_NAME="$botname"
export GIT_COMMITTER_EMAIL="$botname@users.noreply.github.com"

if [ "${1:-}" = "--" ]; then
  shift
  if [ "$#" -lt 2 ] || [ "$1" != "git" ]; then
    echo "Usage: $0 <agent> -- git <subcommand> [args...]" >&2
    exit 1
  fi
  shift  # drop the literal 'git'
  git_subcommand="$1"
  case "$git_subcommand" in
    add|commit|push|status|log|rev-parse|fetch|pull|ls-remote)
      ;;
    *)
      echo "Git subcommand not allowed: $git_subcommand" >&2
      exit 1
      ;;
  esac
  echo "[$identity] git $git_subcommand" >&2
  # Inject a credential helper that serves GH_TOKEN for https github auth.
  # The first empty assignment clears any inherited helper (osxkeychain, etc.)
  # so we don't mix our App token with a cached personal token. The second
  # echoes username/password only on 'get' — store/erase are no-ops.
  exec git \
    -c credential.helper= \
    -c 'credential.helper=!f() { test "$1" = get && printf "username=x-access-token\npassword=%s\n" "$GH_TOKEN"; }; f' \
    "$@"
fi

exec gh "$@"
