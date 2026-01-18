# Claude CLI

Simple command-line interface for chatting with Claude via the Anthropic API.

## Features

- **Single message mode:** Quick one-off queries
- **Interactive mode:** Ongoing conversation session
- **Simple setup:** Just needs `ANTHROPIC_API_KEY`

## Installation

```bash
cd claude-cli
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Setup

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY='your-key-here'
```

Or add to `~/.zshrc` for persistence.

## Usage

### Single Message
```bash
./claude-cli.py "What is the capital of France?"
```

### Interactive Mode
```bash
./claude-cli.py -i
# or just
./claude-cli.py
```

**Interactive commands:**
- `help` - Show available commands
- `quit` / `exit` / `q` - End session
- `clear` - Clear screen

## Model

Currently uses `claude-3-5-sonnet-20241022` with 1000 max tokens.

## Requirements

- Python 3.11+
- `anthropic` package

## Related Projects

- [claude-mcp](../claude-mcp) - MCP hub for agent communication
- [ollama-mcp](../ollama-mcp) - Local model integration
