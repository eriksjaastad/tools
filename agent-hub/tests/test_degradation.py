import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.degradation import DegradationManager, LOW_POWER_NOTIFICATION_FILE

@pytest.fixture
def manager():
    return DegradationManager()

@pytest.fixture
def mock_httpx_success():
    with patch("src.degradation.httpx") as mock:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value.status_code = 200
        mock.Client.return_value = mock_client
        yield mock

@pytest.fixture
def mock_httpx_failure():
    with patch("src.degradation.httpx") as mock:
        mock.Client.side_effect = Exception("Connection refused")
        yield mock

def test_healthy_ollama(manager, mock_httpx_success):
    assert manager.check_ollama_health() is True
    assert manager.is_degraded() is False

def test_unhealthy_ollama_enters_degraded(manager, mock_httpx_failure):
    with patch("src.circuit_breakers.get_circuit_breaker") as mock_cb:
        mock_cb.return_value.record_ollama_failure = MagicMock()

        # First failure
        manager.check_ollama_health()
        assert manager.is_degraded() is False

        # Second failure triggers degraded mode
        manager.check_ollama_health()
        assert manager.is_degraded() is True

def test_get_fallback_model(manager):
    assert manager.get_fallback_model() == "cloud-fast"

def test_get_best_available_healthy(manager, mock_httpx_success):
    model = manager.get_best_available_model("local-coder")
    assert model == "local-coder"

def test_get_best_available_degraded(manager, mock_httpx_failure):
    with patch("src.circuit_breakers.get_circuit_breaker") as mock_cb:
        mock_cb.return_value.record_ollama_failure = MagicMock()

        # Enter degraded mode
        manager.check_ollama_health()
        manager.check_ollama_health()

        model = manager.get_best_available_model("local-coder")
        assert model == "cloud-fast"

def test_recovery_clears_degraded(manager):
    """Test that recovery from degraded mode works."""
    # First, enter degraded mode with failure mock
    with patch("src.degradation.httpx") as mock_fail:
        mock_fail.Client.side_effect = Exception("Connection refused")
        with patch("src.circuit_breakers.get_circuit_breaker") as mock_cb:
            mock_cb.return_value.record_ollama_failure = MagicMock()

            # Enter degraded mode
            manager.check_ollama_health()
            manager.check_ollama_health()
            assert manager.is_degraded() is True

    # Now test recovery with success mock
    with patch("src.degradation.httpx") as mock_success:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value.status_code = 200
        mock_success.Client.return_value = mock_client

        assert manager.check_ollama_health() is True
        assert manager.is_degraded() is False

def test_notification_callback(manager, mock_httpx_failure):
    with patch("src.circuit_breakers.get_circuit_breaker") as mock_cb:
        mock_cb.return_value.record_ollama_failure = MagicMock()

        events = []
        manager.register_notification(lambda event, state: events.append(event))

        manager.check_ollama_health()
        manager.check_ollama_health()

        assert "degraded" in events

def test_get_status(manager):
    status = manager.get_status()
    assert "is_degraded" in status
    assert "ollama_url" in status
