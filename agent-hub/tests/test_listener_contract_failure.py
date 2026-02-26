import json
from pathlib import Path
import sys
import types

# Provide a minimal litellm stub before importing src.listener (which imports
# src.watchdog -> src.worker_client -> src.litellm_bridge).
if "litellm" not in sys.modules:
    litellm_stub = types.ModuleType("litellm")

    class Router:  # noqa: N801
        def __init__(self, *args, **kwargs):
            pass

    litellm_stub.Router = Router
    sys.modules["litellm"] = litellm_stub

from src.listener import MessageListener


def test_mark_contract_failed_sets_canonical_status_and_preserves_fields(tmp_path, monkeypatch):
    # Arrange: create a minimal valid-looking contract file
    handoff_dir = tmp_path / "_handoff"
    handoff_dir.mkdir()
    contract_path = handoff_dir / "TASK_CONTRACT.json"
    original = {
        "schema_version": "2.0",
        "task_id": "T-123",
        "project": "UnitTest",
        "status": "pending_implementer",
        "complexity": "minor",
        "specification": {"target_file": "src/app.py", "requirements": ["do a thing"]},
    }
    contract_path.write_text(json.dumps(original))

    # Capture atomic_write usage and preserve write behavior
    called = {"used": False}

    def fake_atomic_write(path: Path, content: str):
        called["used"] = True
        path.write_text(content)

    # Patch listener.atomic_write (module-level import used by listener functions)
    monkeypatch.setattr("src.listener.atomic_write", fake_atomic_write, raising=True)

    listener = MessageListener("floor_manager", Path("fake/hub"), handoff_dir)

    # Act
    listener._mark_contract_failed(contract_path, "Pipeline step failed: run-local-review", "stderr...trace")

    # Assert: atomic write was used
    assert called["used"] is True

    updated = json.loads(contract_path.read_text())
    # Canonical status updated, not legacy 'state'
    assert updated["status"] == "erik_consultation"
    assert "state" not in updated

    # Failure info preserved
    assert updated["failure_reason"].startswith("Pipeline step failed")
    assert updated["failure_details"] == "stderr...trace"
