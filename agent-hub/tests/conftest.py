import pytest
from pathlib import Path

@pytest.fixture
def handoff_dir(tmp_path):
    d = tmp_path / "_handoff"
    d.mkdir()
    return d

@pytest.fixture
def project_dir(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    return d

@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset global singletons between tests."""
    yield

    # Reset all singleton instances
    import src.budget_manager as bm
    import src.audit_logger as al
    import src.circuit_breakers as cb
    import src.degradation as dg

    bm._budget_manager = None
    al._audit_logger = None
    cb._circuit_breaker = None
    dg._degradation_manager = None
