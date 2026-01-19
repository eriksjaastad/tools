import pytest
from unittest.mock import MagicMock, patch
from src.litellm_bridge import LiteLLMBridge, BudgetExceededError

def test_preflight_allows_local():
    """Local models should always pass preflight."""
    with patch("src.litellm_bridge.get_budget_manager") as mock_bm:
        # can_afford returns (True, "OK")
        mock_bm.return_value.can_afford.return_value = (True, "OK")
        
        bridge = LiteLLMBridge()
        bridge._router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hello"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 10
        bridge._router.completion.return_value = mock_response

        # Use local model
        res = bridge.chat(messages=[{"role": "user", "content": "hi"}], task_type="default", preferred_model="local-fast")
        assert res["model"] == "local-fast"
        assert mock_bm.return_value.can_afford.called

def test_preflight_blocks_over_budget():
    """Should skip cloud models when over budget."""
    with patch("src.litellm_bridge.get_budget_manager") as mock_bm:
        mock_bm.return_value.can_afford.return_value = (False, "Over budget")
        
        bridge = LiteLLMBridge()
        
        # Force cloud-only chain for testing
        with patch.object(bridge, "_get_fallback_chain", return_value=["cloud-premium"]):
            with pytest.raises(BudgetExceededError) as excinfo:
                bridge.chat(messages=[{"role": "user", "content": "hi"}])
            assert "All cloud models skipped due to budget" in str(excinfo.value)

def test_budget_recorded_on_success():
    """Successful calls should record their cost."""
    with patch("src.litellm_bridge.get_budget_manager") as mock_bm:
        mock_bm.return_value.can_afford.return_value = (True, "OK")
        
        bridge = LiteLLMBridge()
        bridge._router = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hello"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        bridge._router.completion.return_value = mock_response

        bridge.chat(messages=[{"role": "user", "content": "hi"}], task_type="default", preferred_model="cloud-fast")
        
        # Should call budget.record_cost(...)
        assert mock_bm.return_value.record_cost.called
        args, kwargs = mock_bm.return_value.record_cost.call_args
        assert kwargs["model"] == "cloud-fast"
        assert kwargs["tokens_in"] == 100
        assert kwargs["tokens_out"] == 50
