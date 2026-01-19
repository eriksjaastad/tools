import time
import pytest
from src.adaptive_poller import AdaptivePoller

def test_poller_initial_interval():
    poller = AdaptivePoller(min_interval=1.0)
    assert poller.current_interval == 1.0

def test_poller_backoff():
    poller = AdaptivePoller(min_interval=1.0, backoff_factor=2.0)
    poller.wait(had_activity=False)
    # Note: wait() sleeps, so this test might be slow or we should mock time.sleep
    assert poller.current_interval == 2.0

def test_poller_reset():
    poller = AdaptivePoller(min_interval=1.0, backoff_factor=2.0)
    poller.wait(had_activity=False)
    assert poller.current_interval == 2.0
    poller.wait(had_activity=True)
    assert poller.current_interval == 1.0

def test_poller_max_cap():
    poller = AdaptivePoller(min_interval=1.0, max_interval=5.0, backoff_factor=10.0)
    poller.wait(had_activity=False)
    assert poller.current_interval == 5.0
