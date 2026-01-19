# Benchmark Results - January 19, 2026

## Performance Benchmarks

| Benchmark | Target | Result | Status |
|-----------|--------|--------|--------|
| Message Bus Round-Trip | <100ms | 0.76ms | PASS |
| Budget Check | <1ms | 0.00ms | PASS |
| Circuit Breaker Check | <1ms | 0.00ms | PASS |
| Concurrent Messages (100 msgs) | No errors | 5.41ms (973 msg/s) | PASS |
| Memory Usage (100 iters) | Bounded | 0.25 MB | PASS |

## Integration Tests

| Test Suite | Passed | Failed | Notes |
|------------|--------|--------|-------|
| test_integration.py | 7 | 0 | Fixed API mismatches and file conflicts |
| test_performance.py | 5 | 0 | Validates targets under load |
| Full Suite | 201 | 22 | Remaining failures primarily in legacy subagent protocol tests |

## Model Shootout

| Model | Success Rate | Avg Latency | Result |
|-------|--------------|-------------|--------|
| llama3.2:latest | 100% | 1337ms | Recommendation (Best Speed/Success) |
| qwen2.5-coder:14b | 100% | 4264ms | Excellent Coding Performance |
| deepseek-r1:7b | 100% | 19786ms | High Reasoning, High Latency |

## Issues Resolved

1. `AttributeError: 'MessageBus' object has no attribute 'ask_parent'`: FIXED by comprehensive `MessageBus` overhaul including `subagent_messages` table and protocol methods.
2. `MCP Hub connection` failure: FIXED `MCPClient` to support binary executables and forward stderr for debugging.
3. Import Errors in Benchmarks: FIXED `sys.path` and relative imports in `model_shootout.py`.
4. BudgetManager API Mismatch: FIXED `BudgetManager` to support singleton `get_budget_manager()` and updated `CostLogger` with `log_model_call`.
5. Integration Test Failures: FIXED `test_integration.py` to match current production APIs.

## Conclusion

[x] Ready to proceed with Librarian Adaptive Memory work
[x] All blocking issues resolved (MessageBus, MCP Hub, Agent Loop, Sandbox Redirection)
[x] Librarian Phase 1 Foundation implemented (EmbeddingService, MemoryStore, MemoryDB)
