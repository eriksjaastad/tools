"""Offline batch accounting and exit-status contracts for PDF utilities."""

import importlib.util
import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_pdf_module(name):
    path = ROOT / "pdf-converter" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"pdf_remediation_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def converter(monkeypatch):
    # Prevent the legacy optional-dependency import from installing packages.
    monkeypatch.setitem(sys.modules, "pymupdf", SimpleNamespace(open=Mock()))
    module = load_pdf_module("pdf_to_markdown_converter")
    module.logger = logging.getLogger("pdf-conversion-test")
    monkeypatch.setattr(module, "setup_logging", lambda: module.logger)
    return module


@pytest.fixture
def cleanup(monkeypatch):
    module = load_pdf_module("cleanup_converted_pdfs")
    module.logger = logging.getLogger("pdf-cleanup-test")
    monkeypatch.setattr(module, "setup_logging", lambda: module.logger)
    return module


def test_extraction_error_propagates_and_closes_document(converter):
    document = Mock()
    document.__len__ = Mock(return_value=1)
    document.load_page.side_effect = RuntimeError("unreadable page")
    converter.pymupdf.open.return_value = document
    with pytest.raises(RuntimeError, match="unreadable page"):
        converter.extract_text_from_pdf(Path("synthetic.pdf"))
    document.close.assert_called_once_with()


def test_extraction_keeps_successful_text_and_empty_result_distinct(converter):
    document = Mock()
    document.__len__ = Mock(return_value=2)
    document.load_page.side_effect = [SimpleNamespace(get_text=lambda: "hello"), SimpleNamespace(get_text=lambda: " ")]
    converter.pymupdf.open.return_value = document
    assert converter.extract_text_from_pdf(Path("synthetic.pdf")) == "## Page 1\n\nhello\n"
    document.close.assert_called_once_with()
    document.__len__.return_value = 0
    assert converter.extract_text_from_pdf(Path("empty.pdf")) == ""


def test_conversion_mixed_batch_preserves_success_and_exits_nonzero(converter, monkeypatch, tmp_path, caplog):
    good, broken, empty = [tmp_path / name for name in ("good.pdf", "broken.pdf", "empty.pdf")]
    for path in (good, broken, empty):
        path.touch()
    monkeypatch.setattr(converter, "find_pdfs_to_convert", lambda base: [broken, good, empty])

    def extract(path):
        if path == broken:
            raise RuntimeError("damaged document")
        return "text" if path == good else ""

    monkeypatch.setattr(converter, "extract_text_from_pdf", extract)
    with caplog.at_level(logging.INFO):
        assert converter.main(["--base-dir", str(tmp_path)]) == 1
    assert "text" in good.with_suffix(".md").read_text()
    assert not broken.with_suffix(".md").exists()
    assert not empty.with_suffix(".md").exists()
    assert "Successful: 1" in caplog.text
    assert "Failed: 2" in caplog.text
    assert "damaged document" in caplog.text
    assert f"No text extracted from {broken}" not in caplog.text
    assert f"No text extracted from {empty}" in caplog.text


def test_conversion_write_failure_is_accounted(converter, monkeypatch, tmp_path):
    source = tmp_path / "blocked.pdf"
    source.touch()
    source.with_suffix(".md").mkdir()
    monkeypatch.setattr(converter, "extract_text_from_pdf", lambda path: "text")
    assert converter.main(["--base-dir", str(tmp_path)]) == 1
    assert source.exists()


@pytest.mark.parametrize("mode", ["success", "no-work", "dry-run"])
def test_conversion_successful_modes_exit_zero(converter, monkeypatch, tmp_path, mode):
    source = tmp_path / "input.pdf"
    if mode != "no-work":
        source.touch()
    extract = Mock(return_value="text")
    monkeypatch.setattr(converter, "extract_text_from_pdf", extract)
    args = ["--base-dir", str(tmp_path)] + (["--dry-run"] if mode == "dry-run" else [])
    assert converter.main(args) == 0
    assert source.with_suffix(".md").exists() is (mode == "success")
    if mode != "success":
        extract.assert_not_called()


def eligible_pdf(tmp_path, name):
    source = tmp_path / name
    source.touch()
    source.with_suffix(".md").write_text("a" * 101)
    return source


def test_cleanup_mixed_deletions_continue_and_count_failure(cleanup, monkeypatch, tmp_path, caplog):
    denied = eligible_pdf(tmp_path, "denied.pdf")
    good = eligible_pdf(tmp_path, "good.pdf")
    monkeypatch.setattr(cleanup, "find_convertible_pdfs", lambda base: [denied, good])
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    real_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == denied:
            raise PermissionError("deletion refused")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    with caplog.at_level(logging.INFO):
        assert cleanup.main(["--base-dir", str(tmp_path)]) == 1
    assert denied.exists() and not good.exists()
    assert "Successfully deleted: 1" in caplog.text
    assert "Failed to delete: 1" in caplog.text


@pytest.mark.parametrize("mode", ["delete", "dry-run", "cancel"])
def test_cleanup_read_error_keeps_pdf_and_never_becomes_success(cleanup, monkeypatch, tmp_path, caplog, mode):
    unreadable = eligible_pdf(tmp_path, "unreadable.pdf")
    unreadable.with_suffix(".md").write_bytes(b"\xff")
    good = eligible_pdf(tmp_path, "good.pdf")
    monkeypatch.setattr(cleanup, "find_convertible_pdfs", lambda base: [unreadable, good])
    monkeypatch.setattr("builtins.input", lambda prompt: "no" if mode == "cancel" else "yes")
    args = ["--base-dir", str(tmp_path)] + (["--dry-run"] if mode == "dry-run" else [])
    with caplog.at_level(logging.INFO):
        assert cleanup.main(args) == 1
    assert unreadable.exists()
    assert good.exists() is (mode != "delete")
    assert "Failed eligibility checks: 1" in caplog.text


def test_cleanup_all_checks_failed_returns_nonzero_without_prompt(cleanup, monkeypatch, tmp_path):
    source = eligible_pdf(tmp_path, "unreadable.pdf")
    source.with_suffix(".md").write_bytes(b"\xff")
    prompt = Mock(side_effect=AssertionError("must not prompt without eligible PDFs"))
    monkeypatch.setattr("builtins.input", prompt)
    assert cleanup.main(["--base-dir", str(tmp_path)]) == 1
    prompt.assert_not_called()
    assert source.exists()


@pytest.mark.parametrize("mode", ["success", "no-work", "dry-run", "cancel", "ineligible"])
def test_cleanup_successful_modes_exit_zero(cleanup, monkeypatch, tmp_path, mode):
    source = tmp_path / "input.pdf"
    if mode != "no-work":
        source = eligible_pdf(tmp_path, "input.pdf")
    if mode == "ineligible":
        source.with_suffix(".md").write_text("too short")
    monkeypatch.setattr("builtins.input", lambda prompt: "no" if mode == "cancel" else "yes")
    args = ["--base-dir", str(tmp_path)] + (["--dry-run"] if mode == "dry-run" else [])
    assert cleanup.main(args) == 0
    assert source.exists() is (mode not in {"success", "no-work"})


def test_delete_unexpected_programming_errors_propagate(cleanup, monkeypatch, tmp_path):
    source = eligible_pdf(tmp_path, "input.pdf")
    monkeypatch.setattr(Path, "unlink", Mock(side_effect=RuntimeError("unexpected")))
    with pytest.raises(RuntimeError, match="unexpected"):
        cleanup.delete_pdf_safely(source)


@pytest.mark.parametrize("script", ["pdf_to_markdown_converter", "cleanup_converted_pdfs"])
def test_pdf_script_entrypoints_exit_nonzero_for_failed_batch(tmp_path, script):
    source = tmp_path / "synthetic.pdf"
    source.touch()
    source.with_suffix(".md").write_bytes(b"\xff")
    bootstrap = """
import runpy, sys
from types import SimpleNamespace
def fail_open(path):
    raise RuntimeError('synthetic extraction failure')
sys.modules['pymupdf'] = SimpleNamespace(open=fail_open)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    command = [sys.executable, "-c", bootstrap, str(ROOT / "pdf-converter" / f"{script}.py"), "--base-dir", str(tmp_path)]
    with pytest.raises(subprocess.CalledProcessError) as error:
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True, text=True, timeout=30)
    assert error.value.returncode == 1
    assert source.exists()
