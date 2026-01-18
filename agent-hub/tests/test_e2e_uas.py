"""
End-to-End tests for Unified Agent System.

These tests validate full workflows across multiple components.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestModelRoutingE2E:
    """E2E tests for model routing with fallbacks."""

    @pytest.fixture
    def temp_paths(self, tmp_path):
        return {
            "budget": tmp_path / "budget.json",
            "audit": tmp_path / "audit.ndjson",
            "circuit": tmp_path / "circuit.json",
        }

    def test_local_model_success_path(self, temp_paths):
        """Local model succeeds - no fallback needed."""
        from src.budget_manager import BudgetManager
        from src.audit_logger import AuditLogger, EventType

        budget = BudgetManager(budget_path=temp_paths["budget"])
        audit = AuditLogger(audit_path=temp_paths["audit"])

        # Simulate successful local call
        can, _ = budget.can_afford("local-coder", 1000, 500)
        assert can is True  # Local always affordable

        # Record the call
        cost = budget.record_cost("local-coder", 1000, 500)
        assert cost == 0.0  # Local is free

        audit.log_model_call("local-coder", 1000, 500, 1500.0, True)

        # Verify audit
        events = audit.get_events(event_type=EventType.MODEL_CALL_SUCCESS)
        assert len(events) == 1
        assert events[0]["data"]["model"] == "local-coder"

    def test_fallback_to_cloud_path(self, temp_paths):
        """Local model fails, falls back to cloud."""
        from src.budget_manager import BudgetManager
        from src.audit_logger import AuditLogger, EventType

        budget = BudgetManager(budget_path=temp_paths["budget"], session_limit=10.0)
        audit = AuditLogger(audit_path=temp_paths["audit"])

        # Simulate local failure, cloud success
        audit.log_model_call("local-coder", 0, 0, 100.0, False, error="Model not loaded")

        # Fallback to cloud
        can, _ = budget.can_afford("cloud-fast", 1000, 500)
        assert can is True

        cost = budget.record_cost("cloud-fast", 1000, 500, was_fallback=True)
        assert cost > 0

        audit.log_model_call("cloud-fast", 1000, 500, 2000.0, True, was_fallback=True)

        # Verify fallback was logged
        events = audit.get_events(event_type=EventType.MODEL_FALLBACK)
        assert len(events) == 1

    def test_budget_blocks_expensive_model(self, temp_paths):
        """Budget blocks expensive models."""
        from src.budget_manager import BudgetManager
        from src.audit_logger import AuditLogger, EventType

        # Very low budget
        budget = BudgetManager(budget_path=temp_paths["budget"], session_limit=0.001)
        audit = AuditLogger(audit_path=temp_paths["audit"])

        # Should not afford premium model
        can, reason = budget.can_afford("cloud-premium", 10000, 5000)
        assert can is False
        assert "Session limit" in reason

        audit.log(EventType.BUDGET_CHECK_FAILED, "litellm_bridge", {
            "model": "cloud-premium",
            "reason": reason
        })

        # Verify audit
        events = audit.get_events(event_type=EventType.BUDGET_CHECK_FAILED)
        assert len(events) == 1


class TestMessageFlowE2E:
    """E2E tests for bi-directional messaging."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        return tmp_path / "test_hub.db"

    def test_ask_reply_cycle(self, temp_db, monkeypatch):
        """Worker asks question, parent replies, worker receives."""
        monkeypatch.setenv("UAS_SQLITE_BUS", "1")

        from src.state_adapter import SQLiteStateAdapter

        adapter = SQLiteStateAdapter(temp_db)

        # Worker asks
        msg_id = adapter.ask_parent("run-e2e", "worker-1", "What API should I use?")
        assert msg_id is not None

        # Parent sees pending
        pending = adapter.get_pending_questions("run-e2e")
        assert len(pending) == 1
        assert pending[0]["question"] == "What API should I use?"

        # Parent replies
        adapter.reply_to_worker(msg_id, "Use REST API with JSON")

        # Worker receives
        answer = adapter.check_answer(msg_id)
        assert answer == "Use REST API with JSON"

        # No longer pending
        pending = adapter.get_pending_questions("run-e2e")
        assert len(pending) == 0

    def test_multiple_workers_isolated(self, temp_db, monkeypatch):
        """Multiple workers' messages don't interfere."""
        monkeypatch.setenv("UAS_SQLITE_BUS", "1")

        from src.state_adapter import SQLiteStateAdapter

        adapter = SQLiteStateAdapter(temp_db)

        # Two workers ask
        msg1 = adapter.ask_parent("run-e2e", "worker-1", "Question 1")
        msg2 = adapter.ask_parent("run-e2e", "worker-2", "Question 2")

        # Both pending
        pending = adapter.get_pending_questions("run-e2e")
        assert len(pending) == 2

        # Answer worker-1
        adapter.reply_to_worker(msg1, "Answer 1")

        # Only worker-2 still pending
        pending = adapter.get_pending_questions("run-e2e")
        assert len(pending) == 1
        assert pending[0]["subagent_id"] == "worker-2"


class TestDegradationE2E:
    """E2E tests for graceful degradation."""

    def test_ollama_failure_triggers_degradation(self):
        """Ollama failures trigger Low Power Mode."""
        from src.degradation import DegradationManager

        manager = DegradationManager()

        with patch("src.degradation.httpx") as mock_httpx:
            # Simulate connection failure
            mock_httpx.Client.side_effect = Exception("Connection refused")

            with patch("src.circuit_breakers.get_circuit_breaker") as mock_cb:
                mock_cb.return_value.record_ollama_failure = MagicMock()

                # First failure
                manager.check_ollama_health()
                assert manager.is_degraded() is False

                # Second failure triggers degradation
                manager.check_ollama_health()
                assert manager.is_degraded() is True

                # Model selection uses fallback (must be inside mock context)
                model = manager.get_best_available_model("local-coder")
                assert model == "cloud-fast"


class TestCircuitBreakerE2E:
    """E2E tests for circuit breaker."""

    @pytest.fixture
    def temp_paths(self, tmp_path, monkeypatch):
        state = tmp_path / "cb_state.json"
        halt = tmp_path / "ERIK_HALT.md"

        from src import circuit_breakers
        monkeypatch.setattr(circuit_breakers, "HALT_FILE", halt)
        monkeypatch.setattr(circuit_breakers, "ROUTER_FAILURE_THRESHOLD", 3)

        return {"state": state, "halt": halt}

    def test_repeated_failures_trigger_halt(self, temp_paths):
        """Repeated router failures trigger halt."""
        from src.circuit_breakers import CircuitBreaker, HaltReason

        cb = CircuitBreaker(state_path=temp_paths["state"])

        # Three failures
        cb.record_router_failure("Error 1")
        cb.record_router_failure("Error 2")

        assert cb.should_halt() is False

        cb.record_router_failure("Error 3")

        assert cb.should_halt() is True
        assert temp_paths["halt"].exists()

        # Halt file has context
        content = temp_paths["halt"].read_text()
        assert "router_exhausted" in content
        assert "Error 3" in content

    def test_success_resets_failure_count(self, temp_paths):
        """Successful calls reset failure counts."""
        from src.circuit_breakers import CircuitBreaker

        cb = CircuitBreaker(state_path=temp_paths["state"])

        cb.record_router_failure("Error 1")
        cb.record_router_failure("Error 2")
        assert cb._state.router_failures == 2

        cb.record_router_success()
        assert cb._state.router_failures == 0


class TestFullWorkflowE2E:
    """E2E test for complete agent workflow."""

    @pytest.fixture
    def temp_paths(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UAS_SQLITE_BUS", "1")
        return {
            "db": tmp_path / "hub.db",
            "budget": tmp_path / "budget.json",
            "audit": tmp_path / "audit.ndjson",
            "circuit": tmp_path / "circuit.json",
        }

    def test_complete_task_workflow(self, temp_paths):
        """
        Complete workflow:
        1. Task assigned
        2. Worker needs clarification
        3. Parent answers
        4. Worker completes with local model
        5. Cost tracked
        """
        from src.state_adapter import SQLiteStateAdapter
        from src.budget_manager import BudgetManager
        from src.audit_logger import AuditLogger, EventType

        # Setup
        adapter = SQLiteStateAdapter(temp_paths["db"])
        budget = BudgetManager(budget_path=temp_paths["budget"])
        audit = AuditLogger(audit_path=temp_paths["audit"])

        run_id = "workflow-test-1"
        audit.set_run_id(run_id)

        # 1. Task assigned (simulated)
        audit.log(EventType.SESSION_START, "orchestrator", {"run_id": run_id})

        # 2. Worker needs clarification
        msg_id = adapter.ask_parent(run_id, "coder-worker", "Which testing framework?")
        audit.log(EventType.QUESTION_ASKED, "coder-worker", {"question": "Which testing framework?"})

        # 3. Parent answers
        adapter.reply_to_worker(msg_id, "Use pytest")
        audit.log(EventType.QUESTION_ANSWERED, "orchestrator", {"answer": "Use pytest"})

        # 4. Worker receives and completes
        answer = adapter.check_answer(msg_id)
        assert answer == "Use pytest"

        # 5. Work done with local model
        can, _ = budget.can_afford("local-coder", 2000, 1000)
        assert can is True

        budget.record_cost("local-coder", 2000, 1000, task_type="implementation")
        audit.log_model_call("local-coder", 2000, 1000, 3000.0, True, task_type="implementation")

        # Verify complete trail
        summary = audit.get_session_summary()
        assert summary["total_events"] >= 4

        # Verify no cloud cost
        status = budget.get_status()
        assert status["session_cloud_cost"] == 0.0
        assert status["local_calls"] == 1
