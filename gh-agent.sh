#!/bin/bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <agent> <gh args...>" >&2
  echo "   or: $0 <agent> -- git <args...>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
agent="$1"
shift

case "$agent" in
  claude)       botname="claude-opus-erik[bot]" ;;
  antigravity)  botname="antigravity-ide-erik[bot]" ;;
  codex)        botname="codex-mini-erik[bot]" ;;
  openclaw)     botname="openclaw-ceo-erik[bot]" ;;
  gemini)       botname="gemini-cli-erik[bot]" ;;
  *)
    echo "Unknown agent: $agent" >&2
    exit 1
    ;;
esac

export GH_TOKEN="$(
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
  uv run --with PyJWT --with cryptography "$SCRIPT_DIR/github-app-token.py" "$agent"
)"

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
  git_subcommand="$2"
  case "$git_subcommand" in
    add|commit|push|status|log|rev-parse)
      ;;
    *)
      echo "Git subcommand not allowed: $git_subcommand" >&2
      exit 1
      ;;
  esac
  echo "[$agent] git $git_subcommand" >&2
  exec "$@"
fi

exec gh "$@"
