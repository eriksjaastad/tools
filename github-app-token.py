#!/usr/bin/env python3
"""
Generate a GitHub App installation token for any registered agent or project.

Usage (agent-based):
    uv run --with PyJWT --with cryptography _tools/github-app-token.py claude
    uv run --with PyJWT --with cryptography _tools/github-app-token.py antigravity

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
# Supports both agent-based and project-based identities.
IDENTITY_MAP = {
    # Agent identities (legacy — still work)
    "claude": ("CLAUDE", "synth-insight-labs", "claude-opus-erik[bot]"),
    "gemini": ("GEMINI", "synth-insight-labs", "gemini-cli-erik[bot]"),
    "antigravity": ("ANTIGRAVITY", "synth-insight-labs", "antigravity-ide-erik[bot]"),
    "codex": ("CODEX", "synth-insight-labs", "codex-mini-erik[bot]"),
    # Project identities (new — per-project bots)
    "ai-memory": ("AI_MEMORY", "synth-insight-labs", "ai-memory-manager[bot]"),
    "smart-invoice-workflow": ("SMART_INVOICE_WORKFLOW", "synth-insight-labs", "siw-manager[bot]"),
    "hypocrisynow": ("HYPOCRISYNOW", "synth-insight-labs", "hypocrisynow-manager[bot]"),
    "project-tracker": ("PROJECT_TRACKER", "synth-insight-labs", "project-tracker-manager[bot]"),
    "tax-organizer": ("TAX_ORGANIZER", "synth-insight-labs", "tax-organizer-manager[bot]"),
    "_tools": ("TOOLS", "synth-insight-labs", "tools-manager[bot]"),
    "muffinpanrecipes": ("MUFFINPANRECIPES", "synth-insight-labs", "muffinpanrecipes-manager[bot]"),
    "synth-insight-labs": ("SYNTHINSIGHTLABS", "synth-insight-labs", "synth-insight-labs-manager[bot]"),
    "cortana-personal-ai": ("CORTANA_PERSONAL_AI", "synth-insight-labs", "cortana-personal-ai-manager[bot]"),
}

# Map project directory names to identity keys for auto-detection
PROJECT_DIR_MAP = {
    "ai-memory": "ai-memory",
    "smart-invoice-workflow": "smart-invoice-workflow",
    "hypocrisynow": "hypocrisynow",
    "project-tracker": "project-tracker",
    "tax-organizer": "tax-organizer",
    "_tools": "_tools",
    "muffinpanrecipes": "muffinpanrecipes",
    "synth-insight-labs": "synth-insight-labs",
    "cortana-personal-ai": "cortana-personal-ai",
}


def detect_project_from_cwd() -> str:
    """Walk up from cwd to find which project we're in. Falls back to 'claude'."""
    cwd = Path.cwd()
    projects_root = Path.home() / "projects"
    if not str(cwd).startswith(str(projects_root)):
        return "claude"  # Not in a project dir — use default
    relative = cwd.relative_to(projects_root)
    top_dir = str(relative).split("/")[0]
    return PROJECT_DIR_MAP.get(top_dir, "claude")  # Unknown project — use default


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

    app_id = doppler_get(f"GITHUB_APP_ID_{suffix}", project)
    installation_id = doppler_get(f"GITHUB_APP_INSTALLATION_ID_{suffix}", project)
    private_key = doppler_get(f"GITHUB_APP_PRIVATE_KEY_{suffix}", project)

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
    args = parser.parse_args()

    # Resolve identity
    identity = args.identity
    if args.auto or identity is None:
        identity = detect_project_from_cwd()
        if not identity:
            print("Error: Could not detect project from cwd. Specify identity explicitly.", file=sys.stderr)
            sys.exit(1)
        print(f"Auto-detected project: {identity}", file=sys.stderr)

    if identity not in IDENTITY_MAP:
        print(f"Error: Unknown identity '{identity}'. Valid: {', '.join(IDENTITY_MAP.keys())}", file=sys.stderr)
        sys.exit(1)

    if args.botname:
        print(get_botname(identity))
        return

    if args.verify:
        suffix, project, _botname = IDENTITY_MAP[identity]
        app_id = doppler_get(f"GITHUB_APP_ID_{suffix}", project)
        private_key = doppler_get(f"GITHUB_APP_PRIVATE_KEY_{suffix}", project)
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
