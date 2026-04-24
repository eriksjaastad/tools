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

Credentials are stored in Doppler (synth-insight-labs/dev) with the naming convention:
    GITHUB_APP_ID_{NAME}
    GITHUB_APP_PRIVATE_KEY_{NAME}
    GITHUB_APP_INSTALLATION_ID_{NAME}

Output: prints only the token to stdout (suitable for piping into gh auth or curl).
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request

import jwt


from pathlib import Path

DOPPLER_CONFIG = "dev"

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


def doppler_get(key: str, project: str) -> str:
    result = subprocess.run(
        ["doppler", "secrets", "get", key,
         "--project", project, "--config", DOPPLER_CONFIG, "--plain"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        print(f"Error: Could not fetch {key} from Doppler project '{project}'", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def generate_token(identity: str) -> str:
    entry = IDENTITY_MAP.get(identity)
    if not entry:
        print(f"Error: Unknown identity '{identity}'. Valid: {', '.join(IDENTITY_MAP.keys())}", file=sys.stderr)
        sys.exit(1)
    suffix, project, _botname = entry

    # Legacy identities store everything in synth-insight-labs/dev with a
    # per-bot suffix (e.g. GITHUB_APP_ID_AI_MEMORY). New identities use an
    # empty suffix and keep their secrets in their own Doppler project.
    key_suffix = f"_{suffix}" if suffix else ""
    app_id = doppler_get(f"GITHUB_APP_ID{key_suffix}", project)
    installation_id = doppler_get(f"GITHUB_APP_INSTALLATION_ID{key_suffix}", project)
    private_key = doppler_get(f"GITHUB_APP_PRIVATE_KEY{key_suffix}", project)

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
            return data["token"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Error: GitHub API returned {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


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

    Queries the GitHub API once with a freshly-minted token for the bot's
    numeric user ID. The caller is expected to hit this rarely (set-repo-
    bot-identity.sh uses it once per repo at setup time).
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
    args = parser.parse_args()

    # Resolve identity
    identity = args.identity
    if args.auto or identity is None:
        identity = detect_role_from_cwd()
        print(f"Auto-detected identity: {identity}", file=sys.stderr)

    if identity not in IDENTITY_MAP:
        print(f"Error: Unknown identity '{identity}'. Valid: {', '.join(IDENTITY_MAP.keys())}", file=sys.stderr)
        sys.exit(1)

    if args.botname:
        print(get_botname(identity))
        return

    if args.email:
        print(get_bot_email(identity))
        return

    if args.verify:
        suffix, project, _botname = IDENTITY_MAP[identity]
        # Match generate_token's key-naming convention: empty suffix → bare
        # key (`GITHUB_APP_ID`); non-empty suffix → `GITHUB_APP_ID_<SUFFIX>`.
        key_suffix = f"_{suffix}" if suffix else ""
        app_id = doppler_get(f"GITHUB_APP_ID{key_suffix}", project)
        private_key = doppler_get(f"GITHUB_APP_PRIVATE_KEY{key_suffix}", project)
        now = int(time.time())
        encoded_jwt = jwt.encode({"iat": now, "exp": now + 300, "iss": str(app_id)},
                                  private_key, algorithm="RS256")
        req = urllib.request.Request(
            "https://api.github.com/app",
            headers={"Authorization": f"Bearer {encoded_jwt}",
                     "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            app_data = json.loads(resp.read().decode())
            print(f"Authenticated as: {app_data['name']}", file=sys.stderr)

    token = generate_token(identity)
    print(token)


if __name__ == "__main__":
    main()
