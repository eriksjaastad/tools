import pytest
from unittest.mock import patch
from src.adaptive_poller import AdaptivePoller, FixedPoller, create_poller

def test_adaptive_poller_backoff():
    """Test that the interval increases on idle."""
    with patch("time.sleep") as mock_sleep:
        poller = AdaptivePoller(min_interval=1.0, max_interval=10.0, backoff_factor=2.0)
        
        # Cycle 1: Idle
        poller.wait(had_activity=False)
        assert poller.current_interval == 2.0
        
        # Cycle 2: Idle
        poller.wait(had_activity=False)
        assert poller.current_interval == 4.0
        
        # Cycle 3: Idle
        poller.wait(had_activity=False)
        assert poller.current_interval == 8.0
        
        # Cycle 4: Idle (should cap)
        poller.wait(had_activity=False)
        assert poller.current_interval == 10.0

def test_adaptive_poller_reset():
    """Test that activity resets the interval."""
    with patch("time.sleep") as mock_sleep:
        poller = AdaptivePoller(min_interval=1.0, max_interval=10.0, backoff_factor=2.0)
        
        # Back off
        poller.wait(had_activity=False)
        poller.wait(had_activity=False)
        assert poller.current_interval == 4.0
        
        # Activity resets
        poller.wait(had_activity=True)
        assert poller.current_interval == 1.0

def test_fixed_poller():
    """Test that FixedPoller always uses the same interval."""
    with patch("time.sleep") as mock_sleep:
        poller = FixedPoller(interval=5.0)
        
        poller.wait(had_activity=False)
        assert poller.current_interval == 5.0
        
        poller.wait(had_activity=True)
        assert poller.current_interval == 5.0

def test_poller_factory():
    """Test the factory function."""
    assert isinstance(create_poller(adaptive=True), AdaptivePoller)
    assert isinstance(create_poller(adaptive=False), FixedPoller)

def test_stats():
    """Test stats output."""
    poller = AdaptivePoller(min_interval=1.0, max_interval=10.0)
    stats = poller.stats()
    assert "current_interval" in stats
    assert "consecutive_idle" in stats
    assert "at_max_interval" in stats
