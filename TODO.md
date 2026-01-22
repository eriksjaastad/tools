# _tools - Master TODO (Updated 2026-01-20)

> **Status:** MCP Migration Complete. Librarian Adaptive Memory Implemented.
> **Assignee:** Floor Manager

---

## Completed Tasks

- [x] **Task 1: Fix generate_mcp_config.py** - Paths updated to Go binaries, added Librarian MCP.
- [x] **Task 2: Fix test_mcp_communication.py** - Binary paths and tool names updated.
- [x] **Task 3: Fix .env.example** - Updated with Go binary paths.
- [x] **Task 4: Update watchdog.py MCP paths** - Integrated with central config.
- [x] **Task 5: Update dispatch_task.py** - Path to Go binary verified.
- [x] **Task 6: Update documentation** - Paths and tool names synced across docs.
- [x] **Task 7: Delete HALT.md** - Budget unblocked.
- [x] **Task 8: Create .env from example** - Done and verified.
- [x] **Task 9: Write E2E pipeline test** - `tests/test_e2e_mcp_pipeline.py` created and passing.
- [x] **Task 10: Verify Ollama integration** - Verified with `ollama_run` and `ollama_list_models`.
- [x] **Task 11: Add `ollama_list_models` tool to Go server** - Implemented and tested.
- [x] **Phase 1-3: Librarian Adaptive Memory** - Core implementation, feedback tools, and eviction logic finished.

---

## Remaining / Next Steps

### Phase 4: Librarian Validation & Polish
- [ ] **Benchmark performance** - Compare cached vs. computed query latency.
- [ ] **Tune thresholds** - Adjust similarity threshold (currently 0.15) based on real-world recall.
- [ ] **Documentation** - Add usage examples for `librarian_feedback` to `API.md`.
- [ ] **Code review** - Final audit of the `librarian-mcp/venv` setup and dependency management.

### Maintenance
- [ ] **Monitor transition.ndjson** - Ensure state transitions remain valid under load.
- [ ] **Audit memory growth** - Verify eviction logic triggers correctly at `MAX_CACHED` limit.
- [ ] **Sync skill.json** - Ensure version numbers and configurations are consistent with the latest builds.
