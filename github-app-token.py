#!/usr/bin/env python3
"""
Generate a GitHub App installation token for any registered agent.

Usage:
    uv run --with PyJWT --with cryptography _tools/github-app-token.py claude
    uv run --with PyJWT --with cryptography _tools/github-app-token.py gemini
    uv run --with PyJWT --with cryptography _tools/github-app-token.py openclaw
    uv run --with PyJWT --with cryptography _tools/github-app-token.py antigravity

Credentials are stored in Doppler (synth-insight-labs/dev) with the naming convention:
    GITHUB_APP_ID_{AGENT}
    GITHUB_APP_PRIVATE_KEY_{AGENT}
    GITHUB_APP_INSTALLATION_ID_{AGENT}

Output: prints only the token to stdout (suitable for piping into gh auth or curl).
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request

import jwt


DOPPLER_CONFIG = "dev"

# Per-agent Doppler project mapping.
# openclaw keys live in the 'openclaw' project; all others in 'synth-insight-labs'.
AGENT_MAP = {
    "claude": ("CLAUDE", "synth-insight-labs"),
    "gemini": ("GEMINI", "synth-insight-labs"),
    "openclaw": ("OPENCLAW", "openclaw"),
    "antigravity": ("ANTIGRAVITY", "synth-insight-labs"),
    "codex": ("CODEX", "synth-insight-labs"),
}


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


def generate_token(agent: str) -> str:
    entry = AGENT_MAP.get(agent)
    if not entry:
        print(f"Error: Unknown agent '{agent}'. Valid: {', '.join(AGENT_MAP.keys())}", file=sys.stderr)
        sys.exit(1)
    suffix, project = entry

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


def main():
    parser = argparse.ArgumentParser(description="Generate GitHub App installation token")
    parser.add_argument("agent", choices=list(AGENT_MAP.keys()),
                        help="Agent to generate token for")
    parser.add_argument("--verify", action="store_true",
                        help="Verify token by calling /app endpoint")
    args = parser.parse_args()

    if args.verify:
        # Verify JWT first
        suffix, project = AGENT_MAP[args.agent]
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

    token = generate_token(args.agent)
    print(token)


if __name__ == "__main__":
    main()
