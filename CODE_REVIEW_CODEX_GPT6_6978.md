# Code review — remaining board cleanup

Reviewed 2026-09-06 against `origin/main` at `e00ba70`.
Scope: #6978 cache validation and #6503 repository documentation.
Merging remains manual. External installed-hook deployment and dashboard
verification are separate from this PR.

## Verification and data flow

The exact CI command passed **563 tests**, including 61 token-cache tests.
The 29 new cases failed before the reader fix and pass afterward. Governance
secrets, absolute-path and API-wrapper checks pass. `PROGRESS.md` exists,
is ignored and untracked, and is excluded from this change.

For a cached JSON array, the reader now returns a cache miss before field access.
`generate_token` calls the mocked mint function once, atomically writes the
replacement, and reuses it on the second call. Equivalent tests exercise null,
numeric expiry, naive expiry, numeric token and whitespace-only token values.
Successful tokens are returned unchanged. Valid expiry still requires more than
300 seconds remaining and the existing identity configuration fingerprint.

Manual M2 review: `None` is the documented cache-miss signal, not successful
authentication. The caller must mint a replacement, and mint failures retain
their existing failure path. This is input validation within the existing cache
repair contract, authorized by the request to finish #6978; no retry loop or new
credential operation is introduced. H1: no subprocess calls are added or changed.

## SHARP

Dogfood: the offline tests exercised real cache reads and writes in temporary
directories. All intended malformed-cache cases reminted once and then hit the
replacement cache, with no output or token disclosure. There was no divergence
after the fix.

**Skeptic:** The cache remains optional. Field validation supports its documented
miss contract without adding a token-format assumption.

**Breaker:** Non-object JSON, invalid field types and naive timestamps are
rejected. Existing expiry-boundary, configuration-drift, permission, concurrent
writer and symlink-protection coverage still passes.

**Security auditor:** Test fixtures forbid live minting and network calls.
Only nonblank strings may leave the reader as tokens; no secrets are logged.

**Architect:** Changes stay in the cache reader and offline regressions.
The minting, identity, wrapper, transport and seat contracts remain intact.

**User proxy:** Corrupt cache content triggers normal replacement rather than
an attribute/type error or invalid token bundle. Local tests use the same
bounded dependencies and Python version as CI.

Remediation: no critical or major findings in the manager review.

## Documentation and limits

#6503 documents retained direct Ollama transport for project-pinned incumbents,
marks old local-first routing observations as historical, and corrects the MCP
server description. It makes no claim that a particular host is running.
The benchmark credential documentation retains its existing `.env` exception.
External `MODEL_HIERARCHY.md` still needs its owner's separate update.

Passing offline tests do not verify live GitHub credentials, installed hooks,
provider dashboard state, or availability of an Ollama endpoint. No live token
generation, key changes, shared-gate activation or external source edits are
part of this PR.
