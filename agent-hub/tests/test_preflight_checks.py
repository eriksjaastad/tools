import pytest
from unittest.mock import MagicMock, patch
from src.litellm_bridge import LiteLLMBridge, BudgetExceededError

@pytest.fixture
def temp_budget(tmp_path):
    return tmp_path / "test_budget.json"

def test_preflight_allows_local(temp_budget):
    """Local models should always pass preflight."""
    with patch("src.litellm_bridge.get_budget_manager") as mock_budget:
        mock_budget.return_value.can_afford.return_value = (True, "Local model")
        bridge = LiteLLMBridge()
        
        # We need to mock the router since we are not testing the actual API call
        bridge._router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hello"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 10
        bridge._router.completion.return_value = mock_response

        # Use local model
        res = bridge.chat(messages=[{"role": "user", "content": "hi"}], task_type="default", preferred_model="local-fast")
        assert res["model"] == "local-fast"
        assert mock_budget.return_value.can_afford.called

def test_preflight_blocks_over_budget(temp_budget):
    """Should skip cloud models when over budget."""
    from src.budget_manager import BudgetManager

    manager = BudgetManager(budget_path=temp_budget, session_limit=0.0001)

    with patch("src.litellm_bridge.get_budget_manager", return_value=manager):
        bridge = LiteLLMBridge()
        
        # Force cloud-only chain for testing
        with patch.object(bridge, "_get_fallback_chain", return_value=["cloud-premium"]):
            with pytest.raises(BudgetExceededError) as excinfo:
                bridge.chat(messages=[{"role": "user", "content": "hi"}] * 1000) # Large message to ensure cost
            assert "All cloud models skipped due to budget" in str(excinfo.value)

def test_preflight_allows_within_budget(temp_budget):
    """Should allow cloud models when within budget."""
    from src.budget_manager import BudgetManager

    manager = BudgetManager(budget_path=temp_budget, session_limit=10.00)

    with patch("src.litellm_bridge.get_budget_manager", return_value=manager):
        bridge = LiteLLMBridge()
        bridge._router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hello"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 10
        bridge._router.completion.return_value = mock_response

        res = bridge.chat(messages=[{"role": "user", "content": "hi"}], task_type="default", preferred_model="cloud-fast")
        assert res["model"] == "cloud-fast"

def test_budget_recorded_on_success(temp_budget):
    """Successful calls should record their cost."""
    from src.budget_manager import BudgetManager

    manager = BudgetManager(budget_path=temp_budget)
    
    with patch("src.litellm_bridge.get_budget_manager", return_value=manager):
        bridge = LiteLLMBridge()
        bridge._router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hello"
        mock_response.usage.prompt_tokens = 1000000 # 1M tokens
        mock_response.usage.completion_tokens = 0
        bridge._router.completion.return_value = mock_response

        initial_cost = manager.get_status()["session_cloud_cost"]
        bridge.chat(messages=[{"role": "user", "content": "hi"}], task_type="default", preferred_model="cloud-fast")
        
        new_cost = manager.get_status()["session_cloud_cost"]
        assert new_cost > initial_cost
