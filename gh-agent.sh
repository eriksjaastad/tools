#!/bin/bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <agent> <gh args...>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
agent="$1"
shift

export GH_TOKEN="$(
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" \
  uv run --with PyJWT --with cryptography "$SCRIPT_DIR/github-app-token.py" "$agent"
)"

exec gh "$@"
