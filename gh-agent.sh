#!/bin/bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <identity> <gh args...>" >&2
  echo "   or: $0 <identity> -- git <args...>" >&2
  echo "   or: $0 --auto <gh args...>" >&2
  echo "   or: $0 --auto -- git <args...>" >&2
  echo "   or: $0 --auto whoami" >&2
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

# `whoami` answers "which identity am I about to act as?" from values this
# script already holds. GitHub offers no endpoint that can answer it for an
# installation token: `gh api user` returns 403 because such a token is not a
# user, and `gh api /app` returns 401 because that route wants a signed JWT.
# Both failures read like a broken wrapper and neither is.
#
# It makes no `gh` call and never prints the token, but it is NOT free: it
# runs after resolution, so a cold token cache still costs a Doppler read and
# a real mint (github-app-token.py: generate_token -> mint_token). That is
# deliberate — whoami then also proves the whole credential chain works, and
# it reuses the one fail-closed path above instead of forking identity
# resolution into a second implementation that could drift from it.
#
# `gh` has no `whoami` subcommand today, so this shadows nothing. If it ever
# ships one, this intercept will silently shadow it with different output —
# revisit here rather than assuming the comment is still true.
if [ "${1:-}" = "whoami" ]; then
  shift
  # Refuse trailing args rather than ignoring them: `gha whoami --json` must
  # not exit 0 having quietly printed a format the caller did not ask for.
  if [ "$#" -ne 0 ]; then
    echo "gh-agent: whoami takes no arguments (got: $*)" >&2
    exit 1
  fi
  printf 'identity:   %s\n' "$identity"
  printf 'bot:        %s\n' "$botname"
  printf 'git author: %s <%s>\n' "$GIT_AUTHOR_NAME" "$GIT_AUTHOR_EMAIL"
  printf 'cwd:        %s\n' "$PWD"
  exit 0
fi

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
