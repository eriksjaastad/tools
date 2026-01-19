import pytest
from src.router import Router

def test_router_selection():
    # Use a dummy config or mock
    router = Router()
    # triage/simple -> local
    selection = router.route("triage", "simple")
    assert selection.tier == "local"
    assert "ollama" in selection.model

def test_router_complexity_routing():
    router = Router()
    # judge/complex -> premium
    selection = router.route("judge", "complex")
    assert selection.tier == "premium"
    assert "anthropic" in selection.model or "claude" in selection.model
