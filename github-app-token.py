#!/usr/bin/env python3
"""
Generate a GitHub App installation token for any registered agent or project.

Usage (agent-based):
    uv run --with PyJWT --with cryptography _tools/github-app-token.py claude

Usage (project-based):
    uv run --with PyJWT --with cryptography _tools/github-app-token.py ai-memory
    uv run --with PyJWT --with cryptography _tools/github-app-token.py hypocrisynow

Usage (auto-detect from cwd):
    uv run --with PyJWT --with cryptography _tools/github-app-token.py --auto

Usage (identity + botname + token in one call, for gh-agent.sh):
    uv run --with PyJWT --with cryptography _tools/github-app-token.py --auto --bundle

Credentials are stored in Doppler (synth-insight-labs/dev) with the naming convention:
    GITHUB_APP_ID_{NAME}
    GITHUB_APP_PRIVATE_KEY_{NAME}
    GITHUB_APP_INSTALLATION_ID_{NAME}

Installation tokens are cached under ~/.cache/gh-agent/<identity>.json (mode
0600) until shortly before the expiry GitHub reports, so repeated calls in a
session skip both the Doppler round-trip and the token exchange. The token is
stored opaquely -- nothing here parses, measures, or pattern-matches it, so the
upcoming stateless ghs_ token format is a non-event.

Output: prints only the token to stdout (suitable for piping into gh auth or curl).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt

DOPPLER_CONFIG = "dev"

# Re-mint this many seconds before GitHub's stated expiry, so a token can't
# lapse mid-command on a slow call.
EXPIRY_SAFETY_MARGIN = 300

CACHE_DIR = Path.home() / ".cache" / "gh-agent"

# Maps identity names to (DOPPLER_SUFFIX, DOPPLER_PROJECT, BOT_NAME).
# Resolves to Doppler keys GITHUB_APP_ID_<SUFFIX>, GITHUB_APP_INSTALLATION_ID_<SUFFIX>,
# GITHUB_APP_PRIVATE_KEY_<SUFFIX>. Empty suffix → un-prefixed keys read from the
# identity's own Doppler project.
IDENTITY_MAP = {
    # Canonical identities (2026-04-24 cutover). Bot login = App slug + [bot].
    # Erik's display names (Architect, Manager) were taken on GitHub, so the App
    # slugs got "-identity" suffixed. Auxesis-Coder was clean.
    "architect":     ("ARCHITECT",     "synth-insight-labs", "architect-identity[bot]"),
    "auxesis-coder": ("AUXESIS_CODER", "synth-insight-labs", "auxesis-coder[bot]"),
    "manager":       ("MANAGER",       "synth-insight-labs", "manager-identity[bot]"),
}


def detect_role_from_cwd() -> str:
    """Pick the canonical identity based on cwd position.

    cwd at ~/projects root (cross-cutting context) → architect.
    cwd inside a project dir → manager.
    auxesis-coder is never auto-picked; it must be requested explicitly.
    """
    cwd = Path.cwd()
    projects_root = Path.home() / "projects"
    if cwd == projects_root:
        return "architect"
    try:
        cwd.relative_to(projects_root)
        return "manager"
    except ValueError:
        return "architect"  # Outside ~/projects — default to architect


def doppler_get_many(keys: list, project: str) -> dict:
    """Fetch several secrets in a single Doppler call.

    Batching replaces one subprocess spawn and one network round-trip per key,
    which is where most of the pre-cache latency went. Values are captured in
    this process and never written to stdout.
    """
    result = subprocess.run(
        ["doppler", "secrets", "get", *keys,
         "--project", project, "--config", DOPPLER_CONFIG, "--json"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f"Error: Could not fetch {', '.join(keys)} from Doppler project "
              f"'{project}': {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Error: Doppler returned unparseable JSON for {', '.join(keys)}",
              file=sys.stderr)
        sys.exit(1)

    values = {}
    for key in keys:
        entry = payload.get(key)
        # Doppler returns {"KEY": {"computed": "...", "raw": "..."}} in JSON mode.
        if isinstance(entry, dict):
            entry = entry.get("computed", entry.get("raw"))
        if entry is None:
            print(f"Error: Doppler project '{project}' has no secret '{key}'",
                  file=sys.stderr)
            sys.exit(1)
        values[key] = entry.strip() if isinstance(entry, str) else entry
    return values


def doppler_get(key: str, project: str) -> str:
    """Single-secret convenience wrapper over doppler_get_many."""
    return doppler_get_many([key], project)[key]


def _cache_path(identity: str) -> Path:
    return CACHE_DIR / f"{identity}.json"


def _read_cached_token(identity: str):
    """Return a still-valid cached token, or None.

    Any malformed, unreadable, or expired entry is treated as a miss. A bad
    cache must only ever be able to slow authentication down, never break it.
    """
    path = _cache_path(identity)
    try:
        with path.open() as fh:
            entry = json.load(fh)
        expires_at = datetime.fromisoformat(
            entry["expires_at"].replace("Z", "+00:00")
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None

    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= EXPIRY_SAFETY_MARGIN:
        return None
    token = entry.get("token")
    return token if token else None


def _write_cached_token(identity: str, token: str, expires_at: str) -> None:
    """Persist a token 0600 in a 0700 dir. Cache failures are non-fatal."""
    path = _cache_path(identity)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(CACHE_DIR, 0o700)  # also tighten a dir that already existed
        # Write via a private temp file so a reader never sees a partial token.
        # Per-process temp name: two agents resolving to the same identity
        # concurrently must not interleave writes into a shared temp file.
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"token": token, "expires_at": expires_at}, fh)
        os.replace(tmp, path)
    except OSError as e:
        print(f"Warning: could not cache token for {identity}: {e}", file=sys.stderr)


def mint_token(identity: str) -> tuple:
    """Mint a fresh installation token. Returns (token, expires_at)."""
    entry = IDENTITY_MAP.get(identity)
    if not entry:
        print(f"Error: Unknown identity '{identity}'. Valid: {', '.join(IDENTITY_MAP.keys())}", file=sys.stderr)
        sys.exit(1)
    suffix, project, _botname = entry

    # Legacy identities store everything in synth-insight-labs/dev with a
    # per-bot suffix (e.g. GITHUB_APP_ID_AI_MEMORY). New identities use an
    # empty suffix and keep their secrets in their own Doppler project.
    key_suffix = f"_{suffix}" if suffix else ""
    id_key = f"GITHUB_APP_ID{key_suffix}"
    installation_key = f"GITHUB_APP_INSTALLATION_ID{key_suffix}"
    private_key_key = f"GITHUB_APP_PRIVATE_KEY{key_suffix}"

    secrets = doppler_get_many([id_key, installation_key, private_key_key], project)
    app_id = secrets[id_key]
    installation_id = secrets[installation_key]
    private_key = secrets[private_key_key]

    # Generate JWT
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 300,
        "iss": str(app_id),
    }
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")

    # Exchange for installation token
    req = urllib.request.Request(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        method="POST",
        headers={
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data["token"], data.get("expires_at")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Error: GitHub API returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


def generate_token(identity: str, use_cache: bool = True) -> str:
    """Return an installation token, reusing a cached one when still valid."""
    if use_cache:
        cached = _read_cached_token(identity)
        if cached:
            return cached

    token, expires_at = mint_token(identity)
    if use_cache and expires_at:
        _write_cached_token(identity, token, expires_at)
    return token


def get_botname(identity: str) -> str:
    """Return the bot display name for an identity."""
    entry = IDENTITY_MAP.get(identity)
    if not entry:
        return f"{identity}[bot]"
    return entry[2]


def get_bot_email(identity: str) -> str:
    """
    Return the bot's GitHub noreply email, e.g.
    "271073502+project-tracker-manager[bot]@users.noreply.github.com".

    Queries the GitHub API once for the bot's numeric user ID. The caller is
    expected to hit this rarely (set-repo-bot-identity.sh uses it once per repo
    at setup time).
    """
    botname = get_botname(identity)  # e.g. "project-tracker-manager[bot]"
    login = botname.removesuffix("[bot]")  # GitHub API login form
    token = generate_token(identity)
    req = urllib.request.Request(
        f"https://api.github.com/users/{login}%5Bbot%5D",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return f"{data['id']}+{botname}@users.noreply.github.com"
    except urllib.error.HTTPError as e:
        print(
            f"Error: GitHub API /users/{login}[bot] returned {e.code}: "
            f"{e.read().decode()}",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub App installation token")
    parser.add_argument("identity", nargs="?", default=None,
                        help=f"Agent or project name. Valid: {', '.join(IDENTITY_MAP.keys())}")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect project from current working directory")
    parser.add_argument("--verify", action="store_true",
                        help="Verify token by calling /app endpoint")
    parser.add_argument("--botname", action="store_true",
                        help="Print the bot display name instead of a token")
    parser.add_argument("--email", action="store_true",
                        help="Print the bot's GitHub noreply email "
                             "(<user-id>+<botname>@users.noreply.github.com). "
                             "Makes one API call to resolve the numeric user ID.")
    parser.add_argument("--bundle", action="store_true",
                        help="Print identity, botname, and token on three lines. "
                             "Lets callers get all three from one invocation "
                             "instead of paying interpreter startup twice.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore any cached token and mint a fresh one.")
    args = parser.parse_args()

    # Resolve identity
    identity = args.identity
    if args.auto or identity is None:
        identity = detect_role_from_cwd()
        if not args.bundle:
            # --bundle returns the identity on stdout line 1, so this note is
            # redundant there -- and emitting it forces callers to redirect
            # stderr, which would swallow real errors.
            print(f"Auto-detected identity: {identity}", file=sys.stderr)

    if identity not in IDENTITY_MAP:
        print(f"Error: Unknown identity '{identity}'. Valid: {', '.join(IDENTITY_MAP.keys())}", file=sys.stderr)
        sys.exit(1)

    use_cache = not args.no_cache

    if args.bundle:
        token = generate_token(identity, use_cache=use_cache)
        print(identity)
        print(get_botname(identity))
        print(token)
        return

    if args.botname:
        print(get_botname(identity))
        return

    if args.email:
        print(get_bot_email(identity))
        return

    if args.verify:
        suffix, project, _botname = IDENTITY_MAP[identity]
        # Match mint_token's key-naming convention: empty suffix → bare
        # key (`GITHUB_APP_ID`); non-empty suffix → `GITHUB_APP_ID_<SUFFIX>`.
        key_suffix = f"_{suffix}" if suffix else ""
        id_key = f"GITHUB_APP_ID{key_suffix}"
        private_key_key = f"GITHUB_APP_PRIVATE_KEY{key_suffix}"
        secrets = doppler_get_many([id_key, private_key_key], project)
        now = int(time.time())
        encoded_jwt = jwt.encode({"iat": now, "exp": now + 300, "iss": str(secrets[id_key])},
                                 secrets[private_key_key], algorithm="RS256")
        req = urllib.request.Request(
            "https://api.github.com/app",
            headers={"Authorization": f"Bearer {encoded_jwt}",
                     "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            app_data = json.loads(resp.read().decode())
            print(f"Authenticated as: {app_data['name']}", file=sys.stderr)

    print(generate_token(identity, use_cache=use_cache))


if __name__ == "__main__":
    main()
