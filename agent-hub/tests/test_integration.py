"""
System Integration Test - Full UAS Workflow.

This test validates that all components work together correctly.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestSystemIntegration:
    """
    Full system integration test.

    Tests the complete workflow:
    1. Configuration validation
    2. Budget management
    3. Message bus communication
    4. Circuit breaker monitoring
    5. Audit logging
    6. Degradation handling
    """

    @pytest.fixture
    def integration_env(self, tmp_path, monkeypatch):
        """Set up isolated environment for integration test."""
        # Enable all features
        monkeypatch.setenv("UAS_SQLITE_BUS", "1")
        monkeypatch.setenv("UAS_SESSION_BUDGET", "10.00")
        monkeypatch.setenv("UAS_DAILY_BUDGET", "50.00")

        # Set paths to temp directory
        paths = {
            "db": tmp_path / "hub.db",
            "budget": tmp_path / "budget.json",
            "audit": tmp_path / "audit.ndjson",
            "circuit": tmp_path / "circuit.json",
            "halt": tmp_path / "ERIK_HALT.md",
        }

        # Patch halt file location
        from src import circuit_breakers
        monkeypatch.setattr(circuit_breakers, "HALT_FILE", paths["halt"])

        return paths

    def test_configuration_valid(self, integration_env):
        """Step 1: Configuration should be valid."""
        from src.config_validator import validate_config

        result = validate_config()
        assert result.valid, f"Config invalid: {result}"

    def test_budget_lifecycle(self, integration_env):
        """Step 2: Budget manager lifecycle."""
        from src.budget_manager import BudgetManager

        budget = BudgetManager(budget_path=integration_env["budget"])

        # Initial state
        status = budget.get_status()
        assert status["session_cloud_cost"] == 0.0

        # Can afford local
        can, reason = budget.can_afford("local-fast", 1000, 500)
        assert can is True
        assert "Local" in reason

        # Can afford cloud within budget
        can, reason = budget.can_afford("cloud-fast", 1000, 500)
        assert can is True

        # Record cost
        cost = budget.record_cost("cloud-fast", 10000, 5000, task_type="test")
        assert cost > 0

        # Status updated
        status = budget.get_status()
        assert status["session_cloud_cost"] == cost

        # Override mechanism
        budget.request_override("Integration test", duration_minutes=1)
        assert budget.is_override_active() is True
        budget.clear_override()
        assert budget.is_override_active() is False

    def test_message_bus_lifecycle(self, integration_env, monkeypatch):
        """Step 3: Message bus communication lifecycle."""
        from src.state_adapter import get_state_adapter, SQLiteStateAdapter

        # Force SQLite adapter
        adapter = SQLiteStateAdapter(integration_env["db"])

        with patch("src.state_adapter.get_state_adapter", return_value=adapter):
            run_id = "integration-test-run"

            # Worker asks question
            msg_id = adapter.ask_parent(run_id, "test-worker", "What is the API format?")
            assert msg_id is not None

            # Question is pending
            pending = adapter.get_pending_questions(run_id)
            assert len(pending) == 1
            assert pending[0]["message_id"] == msg_id

            # Parent answers
            success = adapter.reply_to_worker(msg_id, "Use JSON REST API")
            assert success is True

            # Worker retrieves answer
            answer = adapter.check_answer(msg_id)
            assert answer == "Use JSON REST API"

            # No longer pending
            pending = adapter.get_pending_questions(run_id)
            assert len(pending) == 0

    def test_circuit_breaker_lifecycle(self, integration_env):
        """Step 4: Circuit breaker monitoring."""
        from src.circuit_breakers import CircuitBreaker

        cb = CircuitBreaker(state_path=integration_env["circuit"])

        # Initial state
        assert cb.should_halt() is False
        status = cb.get_status()
        assert status["router_failures"] == 0

        # Record failures (below threshold)
        cb.record_router_failure("Test error 1")
        cb.record_router_failure("Test error 2")
        assert cb.should_halt() is False

        # Success resets count
        cb.record_router_success()
        assert cb._state.router_failures == 0

        # Ollama failures trigger degraded mode, not halt
        cb.record_ollama_failure("Connection refused")
        cb.record_ollama_failure("Connection refused")
        cb.record_ollama_failure("Connection refused")
        assert cb.is_ollama_degraded() is True
        assert cb.should_halt() is False  # Degraded, not halted

    def test_audit_logging_lifecycle(self, integration_env):
        """Step 5: Audit logging captures events."""
        from src.audit_logger import AuditLogger, EventType

        audit = AuditLogger(audit_path=integration_env["audit"])
        audit.set_run_id("integration-test")

        # Log various events
        audit.log(EventType.SESSION_START, "integration_test", {"phase": 6})

        audit.log_model_call(
            model="local-coder",
            tokens_in=1000,
            tokens_out=500,
            latency_ms=150.0,
            success=True,
            task_type="test"
        )

        audit.log(EventType.BUDGET_CHECK_PASSED, "budget_manager", {
            "model": "cloud-fast",
            "estimated_cost": 0.001
        })

        # Query events
        events = audit.get_events()
        assert len(events) >= 3

        # Filter by type
        model_events = audit.get_events(event_type=EventType.MODEL_CALL_SUCCESS)
        assert len(model_events) == 1

        # Session summary
        summary = audit.get_session_summary()
        assert summary["total_events"] >= 3

    def test_degradation_lifecycle(self, integration_env):
        """Step 6: Degradation handling."""
        from src.degradation import DegradationManager

        manager = DegradationManager()

        # Initially not degraded
        assert manager.is_degraded() is False

        # Mock Ollama failure
        with patch("src.degradation.httpx") as mock_httpx:
            mock_httpx.Client.side_effect = Exception("Connection refused")

            with patch("src.circuit_breakers.get_circuit_breaker") as mock_cb:
                mock_cb.return_value.record_ollama_failure = MagicMock()

                # Trigger degradation
                manager.check_ollama_health()
                manager.check_ollama_health()

                assert manager.is_degraded() is True

                # Model selection uses fallback
                model = manager.get_best_available_model("local-coder")
                assert model == "cloud-fast"

    def test_full_workflow(self, integration_env):
        """
        Complete workflow test:
        1. Validate config
        2. Check budget
        3. Worker asks question
        4. Parent answers
        5. Log to audit
        6. Track circuit breaker
        """
        from src.config_validator import validate_config
        from src.budget_manager import BudgetManager
        from src.state_adapter import SQLiteStateAdapter
        from src.audit_logger import AuditLogger, EventType
        from src.circuit_breakers import CircuitBreaker

        # 1. Config valid
        result = validate_config()
        assert result.valid

        # 2. Setup components
        budget = BudgetManager(budget_path=integration_env["budget"])
        adapter = SQLiteStateAdapter(integration_env["db"])
        audit = AuditLogger(audit_path=integration_env["audit"])
        cb = CircuitBreaker(state_path=integration_env["circuit"])

        run_id = "full-workflow-test"
        audit.set_run_id(run_id)

        # 3. Log session start
        audit.log(EventType.SESSION_START, "orchestrator", {"run_id": run_id})

        # 4. Check budget before work
        can, _ = budget.can_afford("local-coder", 2000, 1000)
        assert can is True
        audit.log(EventType.BUDGET_CHECK_PASSED, "orchestrator", {"model": "local-coder"})

        # 5. Worker needs clarification
        msg_id = adapter.ask_parent(run_id, "coder-worker", "Which database?")
        audit.log(EventType.QUESTION_ASKED, "coder-worker", {"question": "Which database?"})

        # 6. Parent answers
        adapter.reply_to_worker(msg_id, "PostgreSQL")
        audit.log(EventType.QUESTION_ANSWERED, "orchestrator", {"answer": "PostgreSQL"})

        # 7. Worker gets answer and completes
        answer = adapter.check_answer(msg_id)
        assert answer == "PostgreSQL"

        # 8. Record successful work
        budget.record_cost("local-coder", 2000, 1000, task_type="code")
        audit.log_model_call("local-coder", 2000, 1000, 250.0, True, task_type="code")
        cb.record_router_success()

        # 9. Log session end
        audit.log(EventType.SESSION_END, "orchestrator", {"status": "success"})

        # 10. Verify complete audit trail
        events = audit.get_events()
        event_types = [e["event_type"] for e in events]

        assert "session_start" in event_types
        assert "budget_check_passed" in event_types
        assert "question_asked" in event_types
        assert "question_answered" in event_types
        assert "model_call_success" in event_types
        assert "session_end" in event_types

        # 11. Verify budget recorded
        status = budget.get_status()
        assert status["local_calls"] == 1

        # 12. Verify circuit breaker healthy
        assert cb.should_halt() is False
