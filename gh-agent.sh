#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <identity> <gh args...>" >&2
  echo "   or: $0 <identity> -- git <args...>" >&2
  echo "   or: $0 --auto <gh args...>" >&2
  echo "   or: $0 --auto -- git <args...>" >&2
  echo "" >&2
  echo "Identities: claude, antigravity, codex, gemini," >&2
  echo "  ai-memory, smart-invoice-workflow, hypocrisynow," >&2
  echo "  project-tracker, tax-organizer, _tools, muffinpanrecipes" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOKEN_SCRIPT="$SCRIPT_DIR/github-app-token.py"

identity="$1"
shift

# Auto-detect: try project-based identity from cwd, fall back to claude
if [ "$identity" = "--auto" ]; then
  identity=$(uv run --with 'PyJWT>=2.9.0' --with 'cryptography>=42.0.0' "$TOKEN_SCRIPT" --auto --botname 2>/dev/null | head -1)
  if [ -z "$identity" ]; then
    echo "Auto-detect failed, falling back to claude" >&2
    identity="claude"
  fi
  # We got the botname, now get the token using auto
  export GH_TOKEN="$(
    uv run --with 'PyJWT>=2.9.0' --with 'cryptography>=42.0.0' "$TOKEN_SCRIPT" --auto 2>/dev/null
  )"
  botname="$identity"
else
  # Get botname from the token script
  botname=$(uv run --with 'PyJWT>=2.9.0' --with 'cryptography>=42.0.0' "$TOKEN_SCRIPT" "$identity" --botname 2>/dev/null)
  if [ -z "$botname" ]; then
    botname="${identity}[bot]"
  fi
  export GH_TOKEN="$(
    uv run --with 'PyJWT>=2.9.0' --with 'cryptography>=42.0.0' "$TOKEN_SCRIPT" "$identity"
  )"
fi

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
    add|commit|push|status|log|rev-parse|fetch|pull)
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
