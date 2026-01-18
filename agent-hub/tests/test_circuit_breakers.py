import pytest
import os
from pathlib import Path
from src.circuit_breakers import CircuitBreaker, HaltReason, HALT_FILE

@pytest.fixture
def temp_state(tmp_path):
    return tmp_path / "cb_state.json"

@pytest.fixture
def temp_halt(tmp_path, monkeypatch):
    halt_file = tmp_path / "ERIK_HALT.md"
    monkeypatch.setattr("src.circuit_breakers.HALT_FILE", halt_file)
    return halt_file

def test_circuit_breaker_init(temp_state):
    cb = CircuitBreaker(state_path=temp_state)
    assert cb._state.router_failures == 0
    assert cb._state.is_halted is False

def test_router_failure_counting(temp_state):
    cb = CircuitBreaker(state_path=temp_state)
    cb.record_router_failure("Test error")
    assert cb._state.router_failures == 1

    cb.record_router_success()
    assert cb._state.router_failures == 0

def test_router_threshold_triggers_halt(temp_state, temp_halt, monkeypatch):
    monkeypatch.setenv("UAS_ROUTER_FAILURE_LIMIT", "2")
    # Need to reimport to get new threshold? No, we can just monkeypatch it if it's already imported
    # However, thresholds are calculated at module load time.
    # In circuit_breakers.py: ROUTER_FAILURE_THRESHOLD = int(os.getenv("UAS_ROUTER_FAILURE_LIMIT", "5"))
    from src import circuit_breakers
    monkeypatch.setattr(circuit_breakers, "ROUTER_FAILURE_THRESHOLD", 2)

    cb = CircuitBreaker(state_path=temp_state)
    cb.record_router_failure("Error 1")
    assert cb._state.is_halted is False

    cb.record_router_failure("Error 2")
    assert cb._state.is_halted is True
    assert temp_halt.exists()

def test_sqlite_failure_counting(temp_state):
    cb = CircuitBreaker(state_path=temp_state)
    cb.record_sqlite_failure("Connection error")
    assert cb._state.sqlite_failures == 1

def test_ollama_degraded_mode(temp_state, monkeypatch):
    from src import circuit_breakers
    monkeypatch.setattr(circuit_breakers, "OLLAMA_FAILURE_THRESHOLD", 2)

    cb = CircuitBreaker(state_path=temp_state)
    cb.record_ollama_failure("Connection refused")
    assert cb.is_ollama_degraded() is False

    cb.record_ollama_failure("Connection refused again")
    assert cb.is_ollama_degraded() is True
    # Should NOT halt, just degrade
    assert cb._state.is_halted is False

def test_reset(temp_state, temp_halt):
    cb = CircuitBreaker(state_path=temp_state)
    cb._state.router_failures = 5
    cb._state.is_halted = True
    temp_halt.write_text("test")

    cb.reset()

    assert cb._state.router_failures == 0
    assert cb._state.is_halted is False
    assert not temp_halt.exists()

def test_halt_callback(temp_state, temp_halt, monkeypatch):
    from src import circuit_breakers
    monkeypatch.setattr(circuit_breakers, "ROUTER_FAILURE_THRESHOLD", 1)

    callback_called = []

    cb = CircuitBreaker(state_path=temp_state)
    cb.register_halt_callback(lambda r, c: callback_called.append((r, c)))

    cb.record_router_failure("Trigger halt")

    assert len(callback_called) == 1
    assert callback_called[0][0] == HaltReason.ROUTER_EXHAUSTED

def test_get_status(temp_state):
    cb = CircuitBreaker(state_path=temp_state)
    cb.record_router_failure("Test")

    status = cb.get_status()
    assert status["router_failures"] == 1
    assert "thresholds" in status
