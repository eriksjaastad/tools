import pytest
import json
from pathlib import Path
from src.utils import atomic_write, atomic_write_json, safe_read, archive_file

def test_atomic_write(tmp_path):
    test_file = tmp_path / "test.txt"
    content = "hello world"
    atomic_write(test_file, content)
    
    assert test_file.exists()
    assert test_file.read_text() == content
    assert not test_file.with_suffix(".txt.tmp").exists()

def test_atomic_write_cleanup_on_error(tmp_path, monkeypatch):
    test_file = tmp_path / "test_error.txt"
    temp_file = test_file.with_suffix(".txt.tmp")
    
    def mock_write(*args, **kwargs):
        # Create the temp file manually to simulate it being there when error happens
        temp_file.write_text("partial")
        raise IOError("Simulated write error")
        
    # We need to mock 'open' or something that happens during the write
    # but since atomic_write is simple, let's just mock the 'os.replace' to fail
    # or better, mock the context manager 'open'
    
    # Actually, let's just mock os.replace to raise an exception
    import os
    original_replace = os.replace
    def fake_replace(src, dst):
        raise RuntimeError("Failure during replace")
    
    monkeypatch.setattr(os, "replace", fake_replace)
    
    with pytest.raises(RuntimeError):
        atomic_write(test_file, "content")
        
    assert not test_file.exists()
    assert not temp_file.exists()

def test_atomic_write_json(tmp_path):
    test_file = tmp_path / "test.json"
    data = {"key": "value"}
    atomic_write_json(test_file, data)
    
    assert test_file.exists()
    loaded_data = json.loads(test_file.read_text())
    assert loaded_data == data

def test_safe_read(tmp_path):
    test_file = tmp_path / "test_read.txt"
    
    # Test missing file
    assert safe_read(test_file) is None
    
    # Test existing file
    content = "reliable content"
    test_file.write_text(content)
    assert safe_read(test_file) == content

def test_archive_file(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    archive_dir = tmp_path / "archive"
    
    test_file = source_dir / "task.md"
    content = "task content"
    test_file.write_text(content)
    
    # Archive without suffix
    archived_path = archive_file(test_file, archive_dir)
    assert not test_file.exists()
    assert archived_path.exists()
    assert archived_path.parent == archive_dir
    assert archived_path.name == "task.md"
    assert archived_path.read_text() == content
    
    # Archive with suffix
    test_file_2 = source_dir / "task2.md"
    test_file_2.write_text("content 2")
    archived_path_2 = archive_file(test_file_2, archive_dir, suffix="BACKUP")
    assert archived_path_2.name == "task2_BACKUP.md"
    
    # Test collision
    test_file_3 = source_dir / "task2.md"
    test_file_3.write_text("content 3")
    archived_path_3 = archive_file(test_file_3, archive_dir, suffix="BACKUP")
    assert archived_path_3.name == "task2_BACKUP_1.md"
