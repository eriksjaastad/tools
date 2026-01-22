#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Secrets Scanner - Standalone Git Hook Validator

Purpose: Catch API keys and secrets before they get committed
Used by: Pre-commit hooks

Exit codes:
- 0: No secrets found, continue
- 1: Secrets detected, BLOCK commit

Usage:
  python secrets-scanner.py file1.py file2.js ...
"""

import re
import sys
from pathlib import Path

# Patterns for common API keys and secrets
# Each tuple: (pattern, name, description)
SECRET_PATTERNS = [
    # OpenAI
    (r"sk-[a-zA-Z0-9]{48,}", "OpenAI API Key", "Starts with sk- followed by 48+ chars"),

    # Anthropic
    (r"sk-ant-[a-zA-Z0-9\-]{40,}", "Anthropic API Key", "Starts with sk-ant-"),

    # Google AI / Firebase
    (r"AIza[a-zA-Z0-9_\-]{35}", "Google API Key", "Starts with AIza"),

    # AWS
    (r"AKIA[A-Z0-9]{16}", "AWS Access Key ID", "Starts with AKIA"),
    (r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])", "Potential AWS Secret Key", "40-char base64 string"),

    # GitHub
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token", "Starts with ghp_"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token", "Starts with gho_"),
    (r"ghu_[a-zA-Z0-9]{36}", "GitHub User Token", "Starts with ghu_"),
    (r"ghs_[a-zA-Z0-9]{36}", "GitHub Server Token", "Starts with ghs_"),
    (r"ghr_[a-zA-Z0-9]{36}", "GitHub Refresh Token", "Starts with ghr_"),

    # Slack
    (r"xox[baprs]-[a-zA-Z0-9\-]{10,}", "Slack Token", "Starts with xox[baprs]-"),

    # Stripe
    (r"sk_live_[a-zA-Z0-9]{24,}", "Stripe Live Secret Key", "Starts with sk_live_"),
    (r"sk_test_[a-zA-Z0-9]{24,}", "Stripe Test Secret Key", "Starts with sk_test_"),

    # Discord
    (r"[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}", "Discord Bot Token", "Discord token pattern"),

    # Generic patterns (more prone to false positives, check last)
    (r"(?i)api[_-]?key\s*[=:]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", "Generic API Key Assignment", "api_key = '...'"),
    (r"(?i)secret[_-]?key\s*[=:]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", "Generic Secret Key Assignment", "secret_key = '...'"),
]

# Files/patterns to skip (env templates, documentation, etc.)
SKIP_PATTERNS = [
    r"\.env\.example$",
    r"\.env\.template$",
    r"\.env\.sample$",
    r"README\.md$",
    r"\.md$",  # Skip all markdown - usually documentation
]


def should_skip_file(file_path: str) -> bool:
    """Check if this file type should be skipped."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return True
    return False


def scan_for_secrets(content: str) -> list[dict]:
    """
    Scan content for potential secrets.

    Returns list of findings: [{"type": "...", "match": "...", "description": "..."}]
    """
    findings = []

    for pattern, secret_type, description in SECRET_PATTERNS:
        matches = re.findall(pattern, content)
        for match in matches:
            # Mask the secret for logging (show first 8 and last 4 chars)
            if len(match) > 16:
                masked = match[:8] + "..." + match[-4:]
            else:
                masked = match[:4] + "..."

            findings.append({
                "type": secret_type,
                "match": masked,
                "description": description,
            })

    return findings


def main():
    if len(sys.argv) < 2:
        print("Usage: secrets-scanner.py <file1> [file2] ...", file=sys.stderr)
        sys.exit(0)

    all_findings = []
    
    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)
        
        # Skip if file doesn't exist or should be skipped
        if not file_path.exists():
            continue
            
        if should_skip_file(str(file_path)):
            continue

        try:
            content = file_path.read_text()
        except (UnicodeDecodeError, PermissionError):
            # Skip binary files or files we can't read
            continue

        # Scan for secrets
        findings = scan_for_secrets(content)
        
        if findings:
            all_findings.append({
                "file": str(file_path),
                "findings": findings
            })

    if all_findings:
        print("\n🚨 POTENTIAL SECRETS DETECTED\n", file=sys.stderr)
        
        for file_result in all_findings:
            print(f"File: {file_result['file']}", file=sys.stderr)
            for finding in file_result['findings']:
                print(f"  - {finding['type']}: {finding['match']}", file=sys.stderr)
            print("", file=sys.stderr)

        print("If these are real secrets, use environment variables instead:", file=sys.stderr)
        print("  - os.getenv('API_KEY')", file=sys.stderr)
        print("  - Doppler for secrets management", file=sys.stderr)
        print("", file=sys.stderr)
        print("If these are false positives (documentation, examples),", file=sys.stderr)
        print("consider if this content belongs in a .md file instead.", file=sys.stderr)
        
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
