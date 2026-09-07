"""An incomplete read must never produce a verified audit or a zero exit."""

import sys
from pathlib import Path

import pytest

import integrity_warden as warden


@pytest.mark.parametrize("failure", [PermissionError("denied"), FileNotFoundError("gone"), UnicodeError("invalid text")])
def test_cli_reports_incomplete_coverage(tmp_path, monkeypatch, capsys, failure):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "README.md"
    source.write_text("[[required-evidence]]")
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == source:
            raise failure
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(warden, "CHECKERS", [warden.WikiLinkChecker()])
    monkeypatch.setattr(sys, "argv", ["integrity_warden.py", "--root", str(tmp_path)])
    assert warden.main() == 2
    output = capsys.readouterr().out
    assert "AUDIT INCOMPLETE" in output
    assert str(source) in output
    assert type(failure).__name__ in output
    assert "INTEGRITY VERIFIED" not in output


def test_empty_readable_evidence_can_complete(tmp_path, monkeypatch, capsys):
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("")
    monkeypatch.setattr(warden, "CHECKERS", [warden.WikiLinkChecker()])
    monkeypatch.setattr(sys, "argv", ["integrity_warden.py", "--root", str(tmp_path)])
    assert warden.main() == 0
    assert "INTEGRITY VERIFIED" in capsys.readouterr().out
