import pytest
import time
from unittest.mock import MagicMock, patch
from src.litellm_bridge import LiteLLMBridge

@pytest.fixture
def mock_router():
    with patch("src.litellm_bridge.Router") as mock:
        yield mock

@pytest.fixture
def bridge():
    return LiteLLMBridge()

def test_fallback_chain_selection(bridge):
    assert bridge._get_fallback_chain("default") == ["local-fast", "cloud-fast", "cloud-premium"]
    assert bridge._get_fallback_chain("code") == ["local-coder", "cloud-fast", "cloud-premium"]
    assert bridge._get_fallback_chain("reasoning") == ["local-reasoning", "cloud-premium"]

def test_cooldown_logic(bridge):
    model = "local-fast"
    
    # 3 failures triggers cooldown
    for _ in range(3):
        bridge._record_failure(model)
    
    assert bridge._is_cooled_down(model) is True
    
    # Check status
    status = bridge.get_cooldown_status()
    assert status[model]["in_cooldown"] is True
    assert status[model]["fail_count"] == 3

def test_success_resets_failures(bridge):
    model = "local-fast"
    bridge._record_failure(model)
    bridge._record_failure(model)
    assert bridge._fail_counts[model] == 2
    
    bridge._record_success(model)
    assert bridge._fail_counts[model] == 0

def test_chat_fallback_on_failure(bridge, mock_router):
    router_instance = mock_router.return_value
    
    # First model fails, second succeeds
    side_effects = [
        Exception("Conn error"),
        MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))], usage=MagicMock(prompt_tokens=10, completion_tokens=10))
    ]
    router_instance.completion.side_effect = side_effects
    
    with patch("src.cost_logger.log_model_call"):
        response = bridge.chat(messages=[{"role": "user", "content": "hi"}])
    
    assert response["model"] == "cloud-fast"
    assert response["fallback_used"] is True
    assert response["content"] == "Success"

def test_chat_all_fail(bridge, mock_router):
    router_instance = mock_router.return_value
    router_instance.completion.side_effect = Exception("Global outage")
    
    with pytest.raises(RuntimeError, match="All models in chain"):
        bridge.chat(messages=[{"role": "user", "content": "hi"}])
