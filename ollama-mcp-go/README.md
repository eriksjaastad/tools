# ollama-mcp-go

`ollama-mcp-go` is a Go MCP server exposing Ollama generation, model listing,
draft-file operations, and an iterative agent loop. Its
[server entry point](cmd/server/main.go) registers `ollama_run`,
`ollama_run_many`, `ollama_list_models`, the `draft_*` tools, and `agent_loop`.

The server reads `OLLAMA_HOST`, defaulting to `http://localhost:11434`.
Deployment must supply a reachable Ollama endpoint; no particular machine is
required. `SANDBOX_ROOT` selects the draft-file root and defaults to the current
directory with a warning. `LOG_LEVEL` controls logging.

Local-first generation routing was retired in July 2026. This source remains
available, while the [benchmark's retained Ollama transport](../model-bench/README.md#retained-ollama-transport)
supports project-pinned incumbents through direct HTTP calls. The benchmark
does not depend on this MCP server. The historical routing notes are preserved
in [local-model-learnings.md](../local-model-learnings.md).
