---
tags:
  - map/project
  - p/ssh-agent
  - type/tool
  - domain/infrastructure
  - status/active
created: 2026-01-16
---

# SSH Agent

Tool for managing SSH connections and executing commands across remote hosts via a queue-based system. Enables AI assistants to perform remote operations safely and efficiently.

## Key Components

### Core Logic
- [[agent.py]] - Main agent loop for processing SSH requests.
- [[start_agent.sh]] - Script to initialize and run the agent.

### Configuration
- [[ssh_hosts.yaml]] - Inventory of remote hosts and connection parameters.
- [[requirements.txt]] - Python dependencies.

### Data
- `queue/` - Directory for requests and results (JSON Lines).
- [[agent_log.txt]] - Runtime activity logs.

## Status
**Status:** #status/active  
**Purpose:** Secure remote command execution
