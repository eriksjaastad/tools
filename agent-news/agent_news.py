import json
import subprocess
import sys
import os

# Configuration: News sources and local version commands
AGENTS = {
    "gemini": {
        "version_cmd": "gemini --version",
        "latest_v": "0.32.0",
        "features": [
            "Generalist Agent & Task Routing for specialized sub-tasks.",
            "Interactive 'Plan Mode' enhancements (external editor support).",
            "Parallel Extension Loading (MCP) for faster startup."
        ],
        "project": "_tools"
    },
    "claude": {
        "version_cmd": "claude --version",
        "latest_v": "2.1.71",
        "features": [
            "Autonomous Agent Teams (parallel sub-agents).",
            "Voice Mode (STT/TTS) for hands-free coding.",
            "Shared Context/Auto-memory across Git worktrees."
        ],
        "project": "_tools"
    },
    "openclaw": {
        "version_cmd": "codex --version",
        "latest_v": "2026.3.2",
        "features": [
            "Unified 'sendPayload' Adapter for cross-platform messaging.",
            "External Secrets Management encrypted vault.",
            "Reliable Cron & Background Tasks overhaul."
        ],
        "project": "_tools"
    }
}

PT_CLI = "/Users/eriksjaastad/projects/project-tracker/pt"

def get_local_version(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout.strip() or result.stderr.strip()
        parts = output.split()
        for part in parts:
            if not part: continue
            if part[0].isdigit() or (len(part) > 1 and part[0] == 'v' and part[1].isdigit()):
                return part.lstrip('v')
        return output
    except Exception:
        return "unknown"

def create_pt_card(agent_name, local_v, latest_v, features):
    title = f"[FEATURE] {agent_name.capitalize()} Update: v{latest_v} (Local: v{local_v})"
    # Features as a bulleted list for the description
    feature_list = "\n".join([f"- {f}" for f in features])
    description = f"New features in {agent_name} v{latest_v}:\n\n{feature_list}\n\nAction: Review documentation and update configuration if needed."
    
    # Check if task already exists to avoid duplicates
    check_cmd = [PT_CLI, "tasks", "list", "-p", AGENTS[agent_name]["project"], "--json"]
    try:
        # Note: pt tasks list might return a direct list or a safety warning + JSON
        raw_output = subprocess.check_output(check_cmd, text=True)
        # Handle cases where output includes safety warning text
        if "[" in raw_output:
            json_str = raw_output[raw_output.find("["):]
            existing = json.loads(json_str)
            if any(latest_v in t.get('title', '') for t in existing):
                print(f"  [Skip] Card for {agent_name} v{latest_v} already exists.")
                return
    except Exception as e:
        print(f"  [Warn] Could not check for existing tasks: {e}")

    extra_args = ["-p", AGENTS[agent_name]["project"], "-s", "Backlog"]
    cmd = [PT_CLI, "tasks", "create", title] + extra_args
    subprocess.run(cmd)
    print(f"  [Created] Feature card for {agent_name} v{latest_v}")

def main():
    print("Agent Updates Audit & News")
    print("==========================")
    for name, info in AGENTS.items():
        local_v = get_local_version(info["version_cmd"])
        print(f"\n{name.capitalize()}:")
        print(f"  Local:  {local_v}")
        print(f"  Latest: {info['latest_v']}")
        
        # Simple comparison - string match or version parse
        if local_v != info["latest_v"]:
            create_pt_card(name, local_v, info["latest_v"], info["features"])
        else:
            print("  [OK] Up to date.")

if __name__ == "__main__":
    main()
