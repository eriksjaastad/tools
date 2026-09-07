# Initial `_tools` triage (#6900)

Reviewed 2026-09-06 against the portfolio dry-run. All 26 local findings are
accounted for below. These are proposed dispositions, not approved suppressions
or completed fixes. All rows are owned by `_tools`; no production code was
changed during triage. Other projects' findings still require their owners'
review before shared blocking enforcement.

## Defects to remediate (12)

| Path:line | Rule | Failure distinction to preserve |
|---|---|---|
| `claude-hooks/pr-enforcement.py:64` | SF001 | Failed Git inspection must report that the multi-concern check was unavailable. |
| `ensure_grepai.py:11` | SF002 | Failed inspection must not become “not running” and trigger startup. |
| `integrity-warden/integrity_warden.py:185` | SF002 | Failed file reads must record incomplete audit coverage instead of skipping evidence. |
| `model-bench/model_bench/registry.py:302` | SF002 | Failed model listing must not become “Not installed.” Preserve transport and model contracts. |
| `route/claude_reader.py:48` | SF002 | Failed stats reads must not feed empty usage into an unqualified total shadow cost. |
| `route/claude_reader.py:207` | SF002 | Unreadable sessions must not disappear from an apparently complete session list. |
| `route/claude_reader.py:262` | SF002 | Invalid requested dates must not become successful empty results. |
| `route/codex_reader.py:36` | SF001 | Unreadable model configuration must not silently select an assumed pricing model. |
| `route/codex_reader.py:72` | SF001 | Failed reads must distinguish missing or partial token evidence from complete results. |
| `route/codex_reader.py:97` | SF001 | Failed metadata parsing must not silently remove a session from usage totals. |
| `route/codex_reader.py:141` | SF001 | Invalid requested dates must not silently disable filtering. |
| `route/codex_reader.py:162` | SF001 | Invalid session timestamps must not bypass a requested date comparison. |

## Candidate justified exceptions (8)

Verify and document each caller contract before adding a local exception. A
warning message or a filename containing `cache` is not sufficient justification.

| Path:line | Rule | Proposed justification |
|---|---|---|
| `_archive/multi-layer-delegation/multi-layer-delegation/adapters/claude_code.py:129` | SF001 | Optional structured-response parsing falls back to preserved assistant text. Archive status alone does not justify it. |
| `claude-cli/claude-cli.py:51` | SF002 | Missing dependency prints a diagnostic; the single-message caller exits 1 and the interactive caller displays failure. |
| `claude-cli/claude-cli.py:54` | SF002 | API failure is printed; both callers handle the sentinel as failure. |
| `ensure_grepai.py:28` | SF002 | Startup failure is printed and `False` reaches a nonzero process exit. |
| `github-app-token.py:163` | SF002 | Documented cache miss causes `generate_token` to mint a fresh token. Production changes require approval; #6978 stays separate. |
| `github-app-token.py:193` | SF001 | Narrow `FileNotFoundError` means the old temporary file is already absent; protected exclusive creation follows. |
| `model-bench/model_bench/registry.py:289` | SF002 | Availability predicate deliberately reports unreachable service as false; its caller distinguishes offline status. |
| `model-bench/model_bench/seat_runner.py:376` | SF002 | Return follows setting affected results' `judge_error`; the scorer counts that structured failure. |

## Contracts needing further review (6)

| Path:line | Rule | Open decision |
|---|---|---|
| `pdf-converter/cleanup_converted_pdfs.py:91` | SF002 | Failed deletion is counted and summarized, but the batch exits successfully. Establish automation exit-status requirements. |
| `pdf-converter/pdf_to_markdown_converter.py:73` | SF002 | Extraction failure increments a failure count but shares the empty-extraction path; batch exits successfully. |
| `pdf-converter/pdf_to_markdown_converter.py:125` | SF002 | Failed conversion is counted; determine whether a zero batch exit is acceptable. |
| `route/claude_reader.py:108` | SF002 | Missing mtime preserves the session with an empty timestamp and changes sort order; determine whether metadata is required. |
| `ssh_agent/src/ssh_mcp/ssh_ops.py:56` | SF001 | Initial-newline timeout may be expected, but broad suppression also catches EOF and unexpected connection failures. |
| `ssh_agent/src/ssh_mcp/ssh_ops.py:83` | SF001 | Empty-buffer timeout may be expected, but broad suppression can hide connection failure before a command is sent. |

## External acceptance example

`auxesis-research-labs/src/auxesis_research_labs/panel/web_search.py:100` reports
SF002 despite logging at line 99. The handler returns `[]` after a failed
request; callers can render that as a search with no results. This reproduces
the motivating shape without importing the provider SDK or using credentials.

The recorded findings are syntactic candidates, not a count of confirmed bugs.
No portfolio files or installed hooks were edited to make the report green.
