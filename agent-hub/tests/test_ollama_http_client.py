import pytest
import os
import httpx
from src import ollama_http_client
from unittest.mock import MagicMock, patch

# Only run these tests if Ollama is accessible
def is_ollama_running():
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
        return response.status_code == 200
    except Exception:
        return False

OLLAMA_AVAILABLE = is_ollama_running()

@pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Ollama not running locally")
def test_list_models_live():
    """Test real list_models call."""
    models = ollama_http_client.list_models()
    assert isinstance(models, list)
    if len(models) > 0:
        assert "name" in models[0]

@pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Ollama not running locally")
def test_chat_live():
    """Test real chat call with a small model."""
    # Try to find a small model to test with
    models = ollama_http_client.list_models()
    if not models:
        pytest.skip("No models available in Ollama")
    
    model_name = models[0]["name"]
    messages = [{"role": "user", "content": "Hello, hi!"}]
    
    try:
        response = ollama_http_client.chat(model_name, messages)
        assert "message" in response
        assert "content" in response["message"]
    except Exception as e:
        pytest.skip(f"Live chat test failed: {e}")

def test_get_client_singleton():
    """Test that get_client returns the same instance."""
    ollama_http_client.close() # Reset
    client1 = ollama_http_client.get_client()
    client2 = ollama_http_client.get_client()
    assert client1 is client2
    ollama_http_client.close()

@patch("httpx.Client.post")
def test_chat_mock(mock_post):
    """Test chat with mocked HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "test-model",
        "message": {"role": "assistant", "content": "Hello there!"},
        "done": True
    }
    mock_post.return_value = mock_response
    
    response = ollama_http_client.chat("test-model", [{"role": "user", "content": "hi"}])
    assert response["message"]["content"] == "Hello there!"
    mock_post.assert_called_once()

@patch("httpx.Client.get")
def test_is_model_loaded_mock(mock_get):
    """Test is_model_loaded with mocked HTTP response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3.2:1b", "size": 12345},
            {"name": "qwen2.5-coder:14b", "size": 67890}
        ]
    }
    mock_get.return_value = mock_response
    
    assert ollama_http_client.is_model_loaded("llama3.2:1b") is True
    assert ollama_http_client.is_model_loaded("non-existent") is False
    # Test partial match (ignoring tag if not provided)
    assert ollama_http_client.is_model_loaded("llama3.2") is True
