#!/usr/bin/env bash
#
# deepcode-run.sh — launch DeepCode CLI with its API key sourced from Doppler.
#
# WHY THIS EXISTS
#   DeepCode reads its API key ONLY from ~/.deepcode/settings.json (the `env.API_KEY`
#   field). It has no environment-variable fallback — verified against the bundled
#   dist of @vegamo/deepcode-cli@0.3.1:
#       apiKey: trimString(env6.API_KEY) || void 0
#   where `env6` comes from the settings file and is NOT merged with process.env.
#   Setting API_KEY, or OPENAI_API_KEY, in the environment does nothing.
#
#   That collides with the standing rule: secrets live in Doppler, never in files.
#   This wrapper is the compromise that keeps Doppler as the single source of truth:
#   the settings file is generated at launch, mode 0600, then cleared and moved
#   to Trash when DeepCode exits normally or receives a catchable signal.
#
# USAGE
#   deepcode-run.sh [any deepcode args]
#   deepcode-run.sh -x -p "explain this error"
#
# CONFIG
#   Override via environment if needed:
#     DEEPCODE_DOPPLER_PROJECT  (default: agent-runtime-config)
#     DEEPCODE_DOPPLER_CONFIG   (default: prd)
#     DEEPCODE_SECRET_NAME      (default: DEEPSEEK_API_KEY)
#     DEEPCODE_BASE_URL         (default: https://api.deepseek.com)
#     DEEPCODE_MODEL            (default: deepseek-v4-pro)
#         Valid IDs as of 2026-08-27: deepseek-v4-pro, deepseek-v4-flash,
#         deepseek-v4-flash-vision-exp. Plain "deepseek-v4" is REJECTED (HTTP 400).
#         Use DEEPCODE_MODEL=deepseek-v4-flash for cheap/bulk work.
#
# WHICH KEY
#   Uses agent-runtime-config/prd DEEPSEEK_API_KEY — the key Erik created ~2026-05-01
#   when standing up the runtime-doctor gate. Verified live (HTTP 200) on 2026-08-27.
#   The same account's key is also in auxesis/prd.
#   Do NOT use synth-insight-labs/prd DEEPSEEK_CLI_API_KEY — that one is REVOKED (401).

set -euo pipefail

PROJECT="${DEEPCODE_DOPPLER_PROJECT:-agent-runtime-config}"
CONFIG="${DEEPCODE_DOPPLER_CONFIG:-prd}"
SECRET="${DEEPCODE_SECRET_NAME:-DEEPSEEK_API_KEY}"
BASE_URL="${DEEPCODE_BASE_URL:-https://api.deepseek.com}"
MODEL="${DEEPCODE_MODEL:-deepseek-v4-pro}"

SETTINGS_DIR="$HOME/.deepcode"
SETTINGS_FILE="$SETTINGS_DIR/settings.json"
SETTINGS_HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/settings_file.py"
REUSE_EXISTING=0
WE_CREATED=0
CREATED_INODE=""
SOURCE_ARGS=(--project "$PROJECT" --config "$CONFIG" --secret "$SECRET" \
             --base-url "$BASE_URL" --model "$MODEL")

command -v doppler >/dev/null 2>&1 || { echo "deepcode-run: doppler not found on PATH" >&2; exit 1; }
EXPECTED_SOURCE="$(python3 "$SETTINGS_HELPER" fingerprint "$SETTINGS_FILE" "${SOURCE_ARGS[@]}")"

# Resolve the REAL deepcode binary, skipping any shim in ~/bin that points back at
# this script. Both `deepseek` and `deepcode` in ~/bin are symlinks to this file, so
# a naive `deepcode "$@"` at the bottom would re-enter this script forever.
REAL_DEEPCODE=""
# `type -aP` (bash) lists every executable named deepcode on PATH, in order.
# Note: `command -v -a` is NOT valid in bash — that's a zsh/POSIX-ism.
for cand in $(type -aP deepcode 2>/dev/null); do
  resolved="$(readlink -f "$cand" 2>/dev/null || echo "$cand")"
  case "$resolved" in
    *deepcode-run.sh) continue ;;   # that's us — keep looking
  esac
  REAL_DEEPCODE="$cand"; break
done
[ -n "$REAL_DEEPCODE" ] || { echo "deepcode-run: real deepcode binary not found on PATH" >&2; exit 1; }

# DeepCode's -x path requires a terminal even when a manager invokes it through
# a pipe. The PTY helper owns a bounded process group and returns its exit code.
if [[ "${DEEPCODE_PTY_ACTIVE:-0}" != 1 ]] && [[ ! -t 0 || ! -t 1 ]]; then
  for arg in "$@"; do
    if [[ "$arg" == "-x" || "$arg" == "--execute" ]]; then
      exec python3 "$(dirname "$SETTINGS_HELPER")/deepseek-pty-exec.py" \
        --cwd "$PWD" --timeout "${DEEPCODE_TIMEOUT:-300}" --bin "$0" -- "$@"
    fi
  done
fi

cleanup() {
  local rc=$?
  # Hand the tab back to Warp: clear our custom title so the pane reverts to the
  # normal working-directory label instead of claiming DeepSeek is still running.
  # `type -t` guards the case where we die before warp_notify is defined.
  if [ -t 1 ] && [ "$(type -t warp_notify 2>/dev/null)" = "function" ]; then
    warp_notify stop
    printf '\033]0;\007' > /dev/tty 2>/dev/null || true
  fi
  # Remove the settings file ONLY if we still own it.
  #
  # Both `deepcode` and `deepseek` are symlinks to this script, so two concurrent
  # sessions are an expected usage pattern, and they share one fixed settings
  # path. An earlier design backed the file up and restored it on exit; that was
  # wrong in both directions — the first session to exit deleted the second
  # session's live file, and the second session then "restored" the first
  # session's key permanently onto disk after both had exited, defeating the
  # entire point of the script.
  #
  # Ownership by PID fixes the key-at-rest half without locking: only the writer
  # removes the file, and nobody touches a file they did not write.
  #
  # DeepCode reads its settings once at startup. A writer can therefore clear
  # the file while another already-started session continues to run.
  # Two separate reasons to delete, and they must NOT be OR'd loosely:
  #
  #   1. We own it — the marker says so. Normal case.
  #   2. We created an EMPTY file and never got to write a marker, because the
  #      doppler fetch failed. Left behind, that empty file would look unmarked to
  #      the next run.
  #
  # WE_CREATED alone is not sufficient for (2): it is a latch that stays set for
  # the life of the process, so a session that lost a create race would go on to
  # delete the winner's live file at its own exit — reintroducing exactly the
  # cross-session deletion this whole design exists to prevent. Requiring the file
  # to still be EMPTY confines it to the pre-marker window it was written for: once
  # anyone has written a marker, only the marked owner may delete.
  if [[ "$(owner_of "$SETTINGS_FILE")" == "$$" ]] || [[ "$WE_CREATED" -eq 1 ]]; then
    if ! python3 "$SETTINGS_HELPER" owner "$SETTINGS_FILE" --pid "$$" --inode "$CREATED_INODE"; then
      rc=1
    fi
  fi
  exit "$rc"
}

# Read our ownership marker out of a settings file. Empty when the file is
# absent, unparseable, or was not written by this script.
owner_of() {
  [ -f "$1" ] || return 0
  python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        print(json.load(f).get('_deepcode_run_owner_pid', '') or '')
except Exception:
    print('')
" "$1" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$SETTINGS_DIR"
chmod 700 "$SETTINGS_DIR"

# Refuse to clobber a settings file this script did not write — that would be the
# user's own hand-written config, and silently moving it around is how the old
# backup/restore design lost track of whose key was on disk.
if [[ -f "$SETTINGS_FILE" ]]; then
  # An EMPTY file is not a hand-written config — a hand-written one has content.
  # It means some session ran `install` and is still waiting on doppler (the
  # slowest step here, so this window is wide in practice), or its fetch died.
  # Treating that as "hand-written, refuse to start" made opening a second tab
  # shortly after the first fail outright, telling the user to delete a live
  # sibling's in-progress config. Wait briefly for a marker to appear instead.
  if [[ ! -s "$SETTINGS_FILE" ]]; then
    for _ in $(seq 1 "${DEEPCODE_CREATE_WAIT_STEPS:-40}"); do
      [[ -s "$SETTINGS_FILE" ]] && break
      [[ -f "$SETTINGS_FILE" ]] || break   # sibling failed and cleaned up; go claim it
      sleep 0.5
    done
    if [[ -f "$SETTINGS_FILE" ]] && [[ ! -s "$SETTINGS_FILE" ]]; then
      # Still empty after the wait — an abandoned shell from a killed session.
      empty_inode="$(python3 "$SETTINGS_HELPER" identity "$SETTINGS_FILE")"
      python3 "$SETTINGS_HELPER" empty "$SETTINGS_FILE" --inode "$empty_inode"
    fi
  fi
fi

if [[ -f "$SETTINGS_FILE" ]]; then
  existing_owner="$(owner_of "$SETTINGS_FILE")"
  if [[ -z "$existing_owner" ]]; then
    echo "deepcode-run: $SETTINGS_FILE exists with no ownership marker and has content." >&2
    echo "  It looks hand-written. This script will not touch a file it did not write." >&2
    echo "  Inspect and move your own config aside before re-running." >&2
    exit 1
  fi
  if [[ "$existing_owner" != "$$" ]] && kill -0 "$existing_owner" 2>/dev/null; then
    # Another live session owns it. Its key came from the same Doppler secret, so
    # reuse the file as-is; that session's cleanup will remove it. We skip the
    # write but still take the normal launch path below, so this session gets the
    # same Warp treatment as any other.
    REUSE_EXISTING=1
  else
    # Stale file from a session that was SIGKILLed or died with the machine.
    stale_inode="$(python3 "$SETTINGS_HELPER" identity "$SETTINGS_FILE")"
    python3 "$SETTINGS_HELPER" stale "$SETTINGS_FILE" --pid "$existing_owner" --inode "$stale_inode"
  fi
fi

if [[ "$REUSE_EXISTING" -eq 0 ]]; then
# Claim the right to create ATOMICALLY. `install` truncates whatever is there, so
# two sessions that independently decided to create — a cold-start collision, or
# several siblings waking together from the reclaim wait above — would both write
# to this path and one write would be silently discarded. Worse, the loser could
# then launch DeepCode against a file the winner has already cleaned up.
#
# `set -o noclobber` makes `>` an O_EXCL create: it fails if the path exists, so
# exactly one session wins the race and the losers fall through to the reuse path
# rather than trampling it. No lock file, so nothing to leak or go stale.
#
# The file is empty between creation and chmod, so the brief umask-default window
# exposes nothing — the secret only lands after the mode is tightened.
if (set -o noclobber; : > "$SETTINGS_FILE") 2>/dev/null; then
  chmod 600 "$SETTINGS_FILE"
  WE_CREATED=1
  CREATED_INODE="$(python3 "$SETTINGS_HELPER" identity "$SETTINGS_FILE")"
else
  # Lost the race. Someone else is creating it; wait for their marker and reuse.
  for _ in $(seq 1 "${DEEPCODE_CREATE_WAIT_STEPS:-40}"); do
    [[ -s "$SETTINGS_FILE" ]] && break
    [[ -f "$SETTINGS_FILE" ]] || break
    sleep 0.5
  done
  if [[ -s "$SETTINGS_FILE" ]]; then
    REUSE_EXISTING=1
  else
    echo "deepcode-run: lost the settings-file race and the winner never wrote a key." >&2
    echo "  Re-run; if this repeats, check for a stuck session or remove $SETTINGS_FILE." >&2
    exit 1
  fi
fi
fi

if [[ "$REUSE_EXISTING" -eq 0 ]]; then

# The helper bounds Doppler to 30 seconds, validates its output, and writes the
# credential only to this mode-0600 file. It never logs the key.
if ! python3 "$SETTINGS_HELPER" fetch "$SETTINGS_FILE" --pid "$$" \
    "${SOURCE_ARGS[@]}" \
    --doppler-timeout "${DEEPCODE_DOPPLER_TIMEOUT:-30}" > "$SETTINGS_FILE"; then
  echo "deepcode-run: failed to read $SECRET from doppler ($PROJECT/$CONFIG)" >&2
  exit 1
fi
fi  # REUSE_EXISTING

if [[ "$REUSE_EXISTING" -eq 1 ]]; then
  actual_source="$(python3 "$SETTINGS_HELPER" source "$SETTINGS_FILE")"
  if [[ "$actual_source" != "$EXPECTED_SOURCE" ]]; then
    echo "deepcode-run: another live session uses different DeepCode settings; refusing credential reuse" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Warp terminal integration.
#
# Problem this solves: with vertical tabs set to primary_info="working_directory",
# a DeepCode tab is visually indistinguishable from a plain shell, so it's easy to
# close by accident. Warp gives `claude`/`codex` a brand icon because it recognizes
# them; it does not know `deepcode`.
#
# Two mechanisms, belt and braces:
#   1. OSC 0 sets the tab title to "🐋 DeepSeek — <dir>". Requires
#      WARP_DISABLE_AUTO_TITLE=true or Warp's shell bootstrap overwrites it.
#   2. OSC 777 emits a warp://cli-agent session_start event so Warp treats the pane
#      as an agent session (status badge) rather than a bare terminal.
#
# Both are no-ops in other terminals — unknown OSC sequences are ignored — and are
# skipped entirely when stdout isn't a TTY (e.g. `deepseek -x -p ... | jq`).
# ---------------------------------------------------------------------------
warp_notify() {
  [ -t 1 ] || return 0
  local dir_name session_id
  dir_name="$(basename "$PWD")"
  session_id="${DC_SESSION_ID:-unknown}"
  {
    printf '\033]0;🐋 DeepSeek — %s\007' "$dir_name"
    printf '\033]777;notify;warp://cli-agent;{"v":1,"agent":"deepcode","event":"%s","session_id":"%s","cwd":"%s","project":"%s"}\007' \
      "$1" "$session_id" "$PWD" "$dir_name"
  } > /dev/tty 2>/dev/null || true
}

export WARP_DISABLE_AUTO_TITLE=true
DC_SESSION_ID="$(uuidgen 2>/dev/null || echo "dc-$$")"
warp_notify session_start

# NOT `exec` — exec would replace this shell and the EXIT trap would never fire,
# leaving the key on disk. Run as a child so cleanup always runs.
"$REAL_DEEPCODE" "$@"
