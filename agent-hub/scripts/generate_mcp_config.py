#!/usr/bin/env python3
"""
MCP Config Generator - Sync MCP configuration across environments.

Usage:
    python scripts/generate_mcp_config.py --env all
    python scripts/generate_mcp_config.py --env cursor
    python scripts/generate_mcp_config.py --env claude-cli
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any

# Base MCP server definitions (source of truth)
MCP_SERVERS = {
    "ollama-mcp": {
        "command": str(Path.home() / "projects" / "_tools" / "ollama-mcp-go" / "bin" / "server"),
        "args": [],
        "env": {"SANDBOX_ROOT": str(Path.home() / "projects")},
        "description": "Ollama MCP - local model inference via Go server",
    },
    "claude-mcp": {
        "command": str(Path.home() / "projects" / "_tools" / "claude-mcp-go" / "bin" / "claude-mcp-go"),
        "args": [],
        "description": "Claude MCP - hub messaging and review tools",
    },
    "librarian-mcp": {
        "command": str(Path.home() / "projects" / "_tools" / "librarian-mcp" / "venv" / "bin" / "python3"),
        "args": ["-m", "librarian_mcp.server"],
        "cwd": str(Path.home() / "projects" / "_tools" / "librarian-mcp" / "src"),
        "env": {
            "LIBRARIAN_PROJECTS_ROOT": str(Path.home() / "projects"),
        },
        "description": "Librarian MCP - knowledge graph queries for project discovery",
        "enabled": True,
    },
}


def generate_claude_cli_config() -> dict:
    """Generate config for Claude CLI."""
    servers = {}
    for name, config in MCP_SERVERS.items():
        if config.get("enabled", True):
            server_config = {
                "command": config["command"],
                "args": config["args"],
            }
            if "env" in config:
                server_config["env"] = config["env"]
            if "cwd" in config:
                server_config["cwd"] = config["cwd"]
            servers[name] = server_config
    return {"mcpServers": servers}


def generate_cursor_config() -> dict:
    """Generate config for Cursor IDE."""
    servers = {}
    for name, config in MCP_SERVERS.items():
        if config.get("enabled", True):
            server_config = {
                "command": config["command"],
                "args": config["args"],
            }
            if "env" in config:
                server_config["env"] = config["env"]
            if "cwd" in config:
                server_config["cwd"] = config["cwd"]
            servers[name] = server_config
    return {"mcpServers": servers}


def generate_antigravity_config() -> dict:
    """Generate config for Anti-Gravity IDE."""
    # AG might use a different format - adapt as needed
    servers = []
    for name, config in MCP_SERVERS.items():
        if config.get("enabled", True):
            server_config = {
                "name": name,
                "command": config["command"],
                "args": config["args"],
                "description": config.get("description", ""),
            }
            if "env" in config:
                server_config["env"] = config["env"]
            if "cwd" in config:
                server_config["cwd"] = config["cwd"]
            servers.append(server_config)
    return {"servers": servers}


def write_config(env: str, config: dict, dry_run: bool = False) -> Path:
    """Write config to appropriate location."""
    paths = {
        "claude-cli": Path.home() / ".claude" / "claude_desktop_config.json",
        "cursor": Path.home() / ".cursor" / "mcp.json",
        "antigravity": Path.home() / ".antigravity" / "mcp_config.json",
    }

    path = paths.get(env)
    if not path:
        raise ValueError(f"Unknown environment: {env}")

    if dry_run:
        print(f"[DRY RUN] Would write to {path}:")
        print(json.dumps(config, indent=2))
        return path

    path.parent.mkdir(parents=True, exist_ok=True)

    # Merge with existing config if present
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            # Preserve non-MCP settings
            if "mcpServers" in config:
                if "mcpServers" not in existing:
                    existing["mcpServers"] = {}
                existing["mcpServers"].update(config["mcpServers"])
            else:
                existing.update(config)
            config = existing
        except json.JSONDecodeError:
            print(f"Warning: Could not parse existing config at {path}, overwriting.")

    path.write_text(json.dumps(config, indent=2))
    print(f"Wrote config to {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate MCP configs")
    parser.add_argument("--env", choices=["all", "claude-cli", "cursor", "antigravity"],
                        default="all", help="Target environment(s)")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    parser.add_argument("--list", action="store_true", help="List configured servers")
    args = parser.parse_args()

    if args.list:
        print("Configured MCP Servers:")
        for name, config in MCP_SERVERS.items():
            status = "enabled" if config.get("enabled", True) else "disabled"
            print(f"  {name}: {config.get('description', 'No description')} [{status}]")
        return

    generators = {
        "claude-cli": generate_claude_cli_config,
        "cursor": generate_cursor_config,
        "antigravity": generate_antigravity_config,
    }

    envs = list(generators.keys()) if args.env == "all" else [args.env]

    for env in envs:
        print(f"\n=== {env} ===")
        config = generators[env]()
        write_config(env, config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
