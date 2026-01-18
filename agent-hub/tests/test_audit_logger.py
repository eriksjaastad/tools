import pytest
import json
from pathlib import Path
from src.audit_logger import AuditLogger, EventType, get_audit_logger

@pytest.fixture
def temp_audit(tmp_path):
    return tmp_path / "test_audit.ndjson"

def test_audit_logger_init(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    assert logger.session_id is not None
    assert len(logger.session_id) == 12

def test_log_event(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.log(EventType.SESSION_START, "test", {"message": "hello"})

    assert temp_audit.exists()

    with temp_audit.open("r") as f:
        event = json.loads(f.readline())
        assert event["event_type"] == "session_start"
        assert event["source"] == "test"
        assert event["data"]["message"] == "hello"

def test_log_model_call(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.log_model_call(
        model="local-coder",
        tokens_in=500,
        tokens_out=200,
        latency_ms=1500.0,
        success=True,
        task_type="code"
    )

    events = logger.get_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "model_call_success"

def test_log_model_fallback(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.log_model_call(
        model="cloud-fast",
        tokens_in=500,
        tokens_out=200,
        latency_ms=1500.0,
        success=True,
        was_fallback=True,
        task_type="code"
    )

    events = logger.get_events()
    # Should have both success and fallback events
    types = [e["event_type"] for e in events]
    assert "model_call_success" in types
    assert "model_fallback" in types

def test_get_events_filter_by_type(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.log(EventType.SESSION_START, "test", {})
    logger.log(EventType.MODEL_CALL_SUCCESS, "test", {})
    logger.log(EventType.SESSION_END, "test", {})

    events = logger.get_events(event_type=EventType.MODEL_CALL_SUCCESS)
    assert len(events) == 1
    assert events[0]["event_type"] == "model_call_success"

def test_get_events_filter_by_source(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.log(EventType.SESSION_START, "source_a", {})
    logger.log(EventType.SESSION_START, "source_b", {})

    events = logger.get_events(source="source_a")
    assert len(events) == 1
    assert events[0]["source"] == "source_a"

def test_get_events_limit(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    for i in range(10):
        logger.log(EventType.SESSION_START, "test", {"i": i})

    events = logger.get_events(limit=5)
    assert len(events) == 5

def test_get_session_summary(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.log(EventType.MODEL_CALL_SUCCESS, "test", {})
    logger.log(EventType.MODEL_CALL_SUCCESS, "test", {})
    logger.log(EventType.MODEL_CALL_FAILURE, "test", {})

    summary = logger.get_session_summary()
    assert summary["total_events"] == 3
    assert summary["event_counts"]["model_call_success"] == 2
    assert summary["event_counts"]["model_call_failure"] == 1

def test_set_run_id(temp_audit):
    logger = AuditLogger(audit_path=temp_audit)
    logger.set_run_id("run-123")
    logger.log(EventType.SESSION_START, "test", {})

    events = logger.get_events()
    assert events[0]["run_id"] == "run-123"
