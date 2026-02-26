import json
from pathlib import Path
from unittest.mock import patch


def _make_contract(task_id: str, status: str, project_dir: Path) -> dict:
    return {
        "task_id": task_id,
        "project": "TestProj",
        "status": status,
        "timestamps": {"updated_at": "2026-01-17T00:00:00Z", "created_at": "2026-01-17T00:00:00Z"},
        "git": {"repo_root": str(project_dir), "base_branch": "main"},
        "limits": {"timeout_minutes": {"any": 10}},
        "breaker": {}
    }


def test_watchdog_contract_path_override_and_default(handoff_dir, project_dir, monkeypatch, capsys):
    # Ensure config picks up test paths
    monkeypatch.setenv("HANDOFF_DIR", str(handoff_dir))

    # Create dummy server files to satisfy config validation
    dummy_hub = project_dir / "dummy_hub.js"
    dummy_hub.write_text("// dummy")
    dummy_mcp = project_dir / "dummy_mcp.js"
    dummy_mcp.write_text("// dummy")
    monkeypatch.setenv("HUB_SERVER_PATH", str(dummy_hub))
    monkeypatch.setenv("MCP_SERVER_PATH", str(dummy_mcp))

    # Reset config singleton so it reloads env
    import src.config
    src.config._config = None

    default_path = handoff_dir / "TASK_CONTRACT.json"
    custom_path = handoff_dir / "CUSTOM_CONTRACT.json"

    # Write two different contracts
    default_contract = _make_contract("TASK-DEFAULT", "pending_implementer", project_dir)
    custom_contract = _make_contract("TASK-CUSTOM", "judge_review_in_progress", project_dir)
    default_path.write_text(json.dumps(default_contract))
    custom_path.write_text(json.dumps(custom_contract))

    # Patch hub availability
    with patch("src.watchdog.check_hub_available", return_value=True):
        from src.watchdog import main

        # 1) Default path (no --contract)
        main(["watchdog.py", "status"])  # prints status for default contract
        out = capsys.readouterr().out
        assert "TASK ID:   TASK-DEFAULT" in out
        assert "STATUS:    PENDING_IMPLEMENTER" in out

        # 2) Explicit override via --contract
        main(["watchdog.py", "status", "--contract", str(custom_path)])
        out = capsys.readouterr().out
        assert "TASK ID:   TASK-CUSTOM" in out
        assert "STATUS:    JUDGE_REVIEW_IN_PROGRESS" in out
