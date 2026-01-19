import pytest
from unittest.mock import MagicMock, patch
from src.router import Router, ModelSelection

@patch("litellm.completion")
def test_fallback_logic(mock_completion):
    # Success on second try
    mock_completion.side_effect = [Exception("Local Failed"), MagicMock(choices=[MagicMock(message=MagicMock(content="Success"))])]
    
    router = Router()
    selection = ModelSelection(model="local", tier="local", fallback_chain=["cloud"])
    
    response = router.execute_with_fallback(selection, "Hello")
    assert mock_completion.call_count == 2
    assert response.choices[0].message.content == "Success"

def test_cooldown_mechanism():
    router = Router()
    router.add_to_cooldown("broken-model")
    assert router.is_model_cooled_down("broken-model") is False
