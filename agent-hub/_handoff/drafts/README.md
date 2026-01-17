# Sandbox Drafts Directory

**Purpose:** Isolated workspace for local model file edits.

## Security Model

This directory is the ONLY location where Ollama workers can write files.
The Floor Manager gates all changes before they reach production code.

## Workflow

1. Worker requests draft via `ollama_request_draft`
2. Original file is copied here as `{filename}.{task_id}.draft`
3. Worker edits the draft via `ollama_write_draft`
4. Worker submits via `ollama_submit_draft`
5. Floor Manager diffs, validates, accepts/rejects
6. Accepted drafts are copied to original location
7. All drafts are cleaned up after task completion

## Contents

- `*.draft` - Working drafts (temporary)
- `*.submission.json` - Submission metadata (temporary)
- Cleaned up after each task cycle

## Security Rules

- Workers CANNOT write outside this directory
- Workers CANNOT delete files
- Workers CANNOT execute commands
- All paths are validated before any operation
- Floor Manager is the ONLY gatekeeper to production
