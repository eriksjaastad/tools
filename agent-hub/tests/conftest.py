import pytest
from pathlib import Path

@pytest.fixture
def handoff_dir(tmp_path):
    d = tmp_path / "_handoff"
    d.mkdir()
    return d

@pytest.fixture
def project_dir(tmp_path):
    return tmp_path
