# Governance System

A standalone, portable pre-commit hook system for enforcing code quality and security across projects.

## Overview

This governance system provides reusable git pre-commit hooks that can be installed in any project. The hooks run validators to catch common issues before they're committed:

- **Secrets Scanner**: Blocks commits containing API keys, tokens, and other secrets
- **Absolute Path Checker**: Blocks commits with hardcoded absolute paths
- **API Wrapper Checker**: Enforces the repository's provider-wrapper rules

The standalone **Silent Failure Checker** and portfolio dry-run reporter are
available for #6900 rollout review. They are not registered in the shared
pre-commit gate; M2 still requires manual review. See
[the rollout record](SILENT_FAILURE_ROLLOUT.md) before enabling enforcement.

## Directory Structure

```
governance/
├── README.md                      # This file
├── governance-check.sh            # Master script that runs all validators
├── install-hooks.sh               # Installs pre-commit hook in a project
├── uninstall-hooks.sh             # Removes pre-commit hook
└── validators/                    # Standalone validators
    ├── secrets-scanner.py         # Detects API keys and secrets
    └── absolute-path-check.py     # Detects hardcoded absolute paths
```

## Requirements

- **uv**: Python package manager (installed at `$HOME/.local/bin/uv`)
  - Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Python 3.11+**
- **Git** (for installing hooks in repositories)
- **trash** (optional, for safer deletion)

## Usage

### Installing Hooks in a Project

```bash
# Install in current directory
./install-hooks.sh

# Install in a specific project
./install-hooks.sh /path/to/project
```

This creates a `.git/hooks/pre-commit` file that will run governance checks on every commit.

### Uninstalling Hooks

```bash
# Uninstall from current directory
./uninstall-hooks.sh

# Uninstall from a specific project
./uninstall-hooks.sh /path/to/project
```

### Running Checks Manually

You can run governance checks manually on specific files:

```bash
# Check specific files
./governance-check.sh file1.py file2.js

# Check all staged files (same as pre-commit hook)
./governance-check.sh
```

### Running Individual Validators

Each validator can also be run independently:

```bash
# Scan for secrets
$HOME/.local/bin/uv run validators/secrets-scanner.py file1.py file2.js

# Check for absolute paths
$HOME/.local/bin/uv run validators/absolute-path-check.py file1.py file2.js
```

## Validators

### Silent Failure Checker (not yet installed as a gate)

This standard-library Python AST scanner reports two syntactic patterns:

- `SF001`: exception handlers containing only inert statements such as `pass`,
  ellipsis or a docstring.
- `SF002`: exception handlers returning empty/default values, including a
  logged failure followed by `return []`, `None`, zero or an empty constructor.

From the repository root:

```bash
uv run governance/validators/silent-failure-check.py module.py
uv run governance/validators/silent-failure-check.py --dry-run --json module.py
uv run governance/silent-failure-report.py --projects-root "$HOME/projects" --json
```

The scanner accepts explicit `.py`/`.pyi` paths and does no recursive discovery.
It exits `1` for findings and `2` for unreadable or invalid source. `--dry-run`
makes findings nonblocking, but scanning errors still exit `2`. Non-Python
paths are skipped. Output contains locations/rules, not source snippets.

The portfolio reporter examines immediate child Git repositories, including
worktrees, and only their tracked `.py` working-tree files. It records the
scanner hash, repository revisions and tracked dirty state. It does not import
project code or call services. Findings do not fail the report; incomplete
scans do. Zero-Python repositories are reported explicitly. Concurrent source
edits are not locked, so this is a working-tree snapshot, not a reproducible
checkout of every recorded HEAD.

An intentional exception can be documented with a rule-specific comment on
the handler line or the immediately preceding standalone comment:

```python
try:
    temporary_path.unlink()
except FileNotFoundError:  # governance: allow-silent SF001: missing temporary file is already cleaned up
    pass
```

The comment applies only to that handler and rule, requires a reason, and must
be an actual Python comment. A marker inside a string does not suppress findings.
Review the caller contract before using an exception; logging alone is not a
reason to hide a failed operation behind empty results.

This is a pattern scanner, not proof that error handling is correct. It does
not resolve aliases, assigned fallback values, shadowed constructor names,
implicit fallthrough, or full reachability. Returns in nested functions/classes
belong to their own scope. Determining whether a configuration fallback is
required or optional is also outside this version's scope. Those limitations
and the unresolved portfolio findings remain part of #6900 before gate activation.

### Secrets Scanner

**Purpose**: Prevent accidental commit of API keys, tokens, and other secrets.

**Detects**:
- OpenAI API keys (`sk-...`)
- Anthropic API keys (`sk-ant-...`)
- Google API keys (`AIza...`)
- AWS credentials (`AKIA...`)
- GitHub tokens (`ghp_...`, `gho_...`, etc.)
- Slack tokens (`xox...`)
- Stripe keys (`sk_live_...`, `sk_test_...`)
- Discord bot tokens
- Generic API key assignments

**Skips**: `.md` files, `.env.example`, `.env.template`, `.env.sample`

**Exit codes**:
- `0`: No secrets detected (pass)
- `1`: Secrets detected (block commit)

### Absolute Path Checker

**Purpose**: Prevent hardcoded absolute paths that break portability.

**Detects**:
- macOS user paths, e.g. `/Users/username/...`
- Linux user paths, e.g. `/home/username/...`
- Homebrew paths, e.g. `/opt/homebrew/...`
- Windows user paths, e.g. `C:\Users\username\...`

**Checks**: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.md`, `.yaml`, `.yml`, `.json`, `.sh`, `.bash`, `.zsh`, `.html`, `.css`, `.scss`, `.go`, `.rs`, `.rb`, `.toml`, `.ini`, `.cfg`, `.conf`, `Makefile`, `Dockerfile`

**Skips**: `.git/`, `node_modules/`, `__pycache__/`, `.env`, `.log`

**Exit codes**:
- `0`: No absolute paths detected (pass)
- `1`: Absolute paths detected (block commit)

## How It Works

1. **On Commit**: Git runs `.git/hooks/pre-commit`
2. **Hook Calls**: `governance-check.sh` with staged files
3. **Runs Validators**: Each validator in `validators/` is executed
4. **Reports Results**: Clear pass/fail for each validator
5. **Blocks if Needed**: Commit is blocked if any validator fails

## Exit Codes

- **governance-check.sh**: `0` = all pass, `1` = one or more failed
- **Validators**: `0` = pass, `1` = fail
- **Scripts**: `0` = success, `1` = error

## Customization

### Adding New Validators

1. Create a new Python script in `validators/`
2. Accept file paths as arguments: `sys.argv[1:]`
3. Exit with `0` (pass) or `1` (fail)
4. Add to `VALIDATORS` array in `governance-check.sh`

Example validator structure:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        sys.exit(0)  # No files to check
    
    has_issues = False
    
    for file_path_str in sys.argv[1:]:
        file_path = Path(file_path_str)
        # ... your validation logic ...
        if found_issue:
            print(f"Issue in {file_path}", file=sys.stderr)
            has_issues = True
    
    sys.exit(1 if has_issues else 0)

if __name__ == "__main__":
    main()
```

### Disabling Specific Validators

Edit `governance-check.sh` and remove validators from the `VALIDATORS` array.

## Troubleshooting

### Hook Not Running

```bash
# Check if hook exists and is executable
ls -la .git/hooks/pre-commit

# Make it executable if needed
chmod +x .git/hooks/pre-commit
```

### uv Not Found

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
$HOME/.local/bin/uv --version
```

### Bypassing Hooks (Emergency Use Only)

```bash
# Skip pre-commit hooks for a single commit
git commit --no-verify -m "emergency fix"
```

**⚠️ Use sparingly!** Bypassing hooks defeats the purpose of governance.

## Examples

### Example: Blocked Secret

```bash
$ git commit -m "Add API integration"
Checking 2 file(s)...
Running secrets-scanner.py... ✗ FAIL

🚨 POTENTIAL SECRETS DETECTED

File: src/api.py
  - OpenAI API Key: sk-proj1...f9Az

If these are real secrets, use environment variables instead:
  - os.getenv('API_KEY')
  - Doppler for secrets management

Validator secrets-scanner.py failed with exit code 1

✗ Governance checks failed - commit blocked
```

### Example: Blocked Absolute Path

```bash
$ git commit -m "Update config"
Checking 1 file(s)...
Running secrets-scanner.py... ✓ PASS
Running absolute-path-check.py... ✗ FAIL

🚫 HARDCODED ABSOLUTE PATHS DETECTED

File: config.yaml
  Line 12: data_dir: /Users/erik/project/data  # example: prohibited user path

Fix by using relative paths or environment variables instead.
Example: Use './data/file.csv' or '$PROJECT_ROOT/data/file.csv'

Validator absolute-path-check.py failed with exit code 1

✗ Governance checks failed - commit blocked
```

### Example: All Checks Pass

```bash
$ git commit -m "Clean commit"
Checking 3 file(s)...
Running secrets-scanner.py... ✓ PASS
Running absolute-path-check.py... ✓ PASS

✓ All governance checks passed
[main 1a2b3c4] Clean commit
 3 files changed, 42 insertions(+), 8 deletions(-)
```

## Relationship to Claude Hooks

There are two validation systems in the ecosystem:

| System | Location | Trigger | Purpose |
|--------|----------|---------|---------|
| **Governance** | `_tools/governance/` | Git pre-commit | Blocks bad commits (all agents) |
| **Claude Hooks** | `.claude/hooks/validators/` | File write | Real-time feedback (Claude only) |

Both systems check for secrets and absolute paths, but have different interfaces:
- Governance validators take file paths as arguments
- Claude validators read from stdin (JSON format)

The goal is universal enforcement: Claude gets real-time feedback, while git hooks catch anything that slips through regardless of which agent made the change.

## Best Practices

1. **Install in all projects**: Use consistent governance across your codebase
2. **Review blocked commits**: Understand why a commit was blocked before bypassing
3. **Use environment variables**: For secrets (`.env` files, Doppler, etc.)
4. **Use relative paths**: Or environment variables like `$PROJECT_ROOT`
5. **Keep validators updated**: Pull latest validators from this repo periodically

## Integration with CI/CD

You can also run governance checks in CI/CD pipelines:

```bash
# In your CI script
cd /path/to/governance
./governance-check.sh $(git diff --name-only HEAD~1)
```

## License

Part of the `_tools` collection. Internal use.
