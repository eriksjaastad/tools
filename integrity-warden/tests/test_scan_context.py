"""Tests for ScanContext class."""

import pytest
from pathlib import Path
from integrity_warden import ScanContext


class TestScanContextBuild:
    """Test ScanContext.build() initialization."""
    
    def test_build_creates_empty_context(self, tmp_path):
        """Test building context on an empty directory."""
        ctx = ScanContext.build(tmp_path)
        
        assert ctx.root_path == tmp_path
        assert isinstance(ctx.md_files, dict)
        assert isinstance(ctx.projects, list)
        assert isinstance(ctx.all_files, list)
        assert len(ctx.md_files) == 0
        assert len(ctx.projects) == 0
        assert len(ctx.all_files) == 0
    
    def test_index_md_files(self, project_with_markdown):
        """Test that markdown files are correctly indexed."""
        docs_dir = project_with_markdown / "docs"
        
        ctx = ScanContext.build(project_with_markdown.parent)
        
        # Should have indexed all markdown files by stem
        assert "README" in ctx.md_files
        assert "ARCHITECTURE" in ctx.md_files
        assert "API" in ctx.md_files
        
        # Each stem should map to a list of paths
        assert isinstance(ctx.md_files["README"], list)
        assert len(ctx.md_files["README"]) > 0
        
        # Paths should be Path objects
        for path_list in ctx.md_files.values():
            for path in path_list:
                assert isinstance(path, Path)
                assert path.exists()
    
    def test_index_projects(self, multi_project_root):
        """Test that projects are correctly discovered."""
        ctx = ScanContext.build(multi_project_root)
        
        assert "project-alpha" in ctx.projects
        assert "project-beta" in ctx.projects
        assert "project-gamma" in ctx.projects
        
        # Projects should be sorted by length (longest first)
        assert ctx.projects == sorted(ctx.projects, key=len, reverse=True)
    
    def test_index_all_files(self, project_with_markdown):
        """Test that all text files are indexed."""
        ctx = ScanContext.build(project_with_markdown.parent)
        
        assert len(ctx.all_files) > 0
        
        # All indexed files should exist
        for file_path in ctx.all_files:
            assert file_path.exists()
    
    def test_exclude_dirs_are_skipped(self, tmp_projects_root):
        """Test that excluded directories are not scanned."""
        # Create excluded directories
        excluded = tmp_projects_root / "my-project" / ".git" / "objects"
        excluded.mkdir(parents=True)
        (excluded / "file.txt").write_text("content")
        
        venv = tmp_projects_root / "my-project" / ".venv"
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("config")
        
        # Create non-excluded file
        docs = tmp_projects_root / "my-project" / "docs"
        docs.mkdir(parents=True)
        (docs / "README.md").write_text("# Doc")
        
        ctx = ScanContext.build(tmp_projects_root)
        
        # Should not include files from excluded directories
        excluded_files = [str(f) for f in ctx.all_files if ".git" in str(f) or ".venv" in str(f)]
        assert len(excluded_files) == 0
        
        # Should include markdown file
        assert len(ctx.md_files) > 0
    
    def test_exclude_files_are_skipped(self, tmp_projects_root):
        """Test that excluded files are not indexed."""
        project_dir = tmp_projects_root / "my-project"
        project_dir.mkdir(parents=True)
        
        # Create an excluded file
        (project_dir / "WARDEN_LOG.yaml").write_text("log: content")
        
        # Create a normal file
        (project_dir / "README.md").write_text("# Readme")
        
        ctx = ScanContext.build(tmp_projects_root)
        
        # Should not include WARDEN_LOG
        warden_files = [f for f in ctx.all_files if f.name == "WARDEN_LOG.yaml"]
        assert len(warden_files) == 0
        
        # Should include README
        assert "README" in ctx.md_files
    
    def test_context_root_path_is_correct(self, tmp_path):
        """Test that context root_path is set correctly."""
        ctx = ScanContext.build(tmp_path)
        assert ctx.root_path == tmp_path
    
    def test_multiple_md_files_with_same_stem(self, tmp_projects_root):
        """Test that multiple files with same stem are both indexed."""
        # Create two projects with same-named files
        proj_a = tmp_projects_root / "project-a" / "docs"
        proj_a.mkdir(parents=True)
        (proj_a / "README.md").write_text("# Project A")
        
        proj_b = tmp_projects_root / "project-b" / "docs"
        proj_b.mkdir(parents=True)
        (proj_b / "README.md").write_text("# Project B")
        
        ctx = ScanContext.build(tmp_projects_root)
        
        # Should have README indexed
        assert "README" in ctx.md_files
        
        # Should have two paths for README
        assert len(ctx.md_files["README"]) == 2
    
    def test_text_extensions_are_indexed(self, tmp_projects_root):
        """Test that various text file extensions are indexed."""
        project_dir = tmp_projects_root / "my-project"
        project_dir.mkdir(parents=True)
        
        # Create files with various extensions
        extensions_to_create = [
            ("README.md", "# Doc"),
            ("script.py", "print('hi')"),
            ("setup.sh", "#!/bin/bash"),
            ("config.yaml", "key: value"),
            ("notes.txt", "Some notes"),
        ]
        
        for filename, content in extensions_to_create:
            (project_dir / filename).write_text(content)
        
        ctx = ScanContext.build(tmp_projects_root)
        
        # All files should be indexed
        assert len(ctx.all_files) >= len(extensions_to_create)
    
    def test_non_text_files_excluded(self, tmp_projects_root):
        """Test that non-text files are not indexed."""
        project_dir = tmp_projects_root / "my-project"
        project_dir.mkdir(parents=True)
        
        # Create various file types
        (project_dir / "image.png").write_bytes(b"PNG")
        (project_dir / "archive.zip").write_bytes(b"PK")
        (project_dir / "data.json").write_text('{"key": "value"}')
        (project_dir / "README.md").write_text("# Doc")
        
        ctx = ScanContext.build(tmp_projects_root)
        
        # Should not include binary files (json also excluded)
        file_names = [f.name for f in ctx.all_files]
        assert "image.png" not in file_names
        assert "archive.zip" not in file_names
        assert "data.json" not in file_names
        
        # Should include markdown
        assert "README" in ctx.md_files


class TestScanContextIndexMdFiles:
    """Test ScanContext._index_md_files() method."""
    
    def test_index_md_files_empty_directory(self, tmp_path):
        """Test indexing with no markdown files."""
        ctx = ScanContext(root_path=tmp_path)
        ctx._index_md_files()
        
        assert ctx.md_files == {}
    
    def test_index_md_files_nested(self, tmp_projects_root):
        """Test indexing markdown files in nested directories."""
        # Create nested structure
        docs = tmp_projects_root / "project" / "docs" / "guides"
        docs.mkdir(parents=True)
        
        (docs / "intro.md").write_text("# Intro")
        (docs / "advanced.md").write_text("# Advanced")
        (tmp_projects_root / "project" / "README.md").write_text("# Root")
        
        ctx = ScanContext(root_path=tmp_projects_root)
        ctx._index_md_files()
        
        assert "intro" in ctx.md_files
        assert "advanced" in ctx.md_files
        assert "README" in ctx.md_files
    
    def test_md_files_keyed_by_stem(self, project_with_markdown):
        """Test that markdown files are keyed by their stem."""
        ctx = ScanContext(root_path=project_with_markdown.parent)
        ctx._index_md_files()
        
        # All keys should be stems (no .md extension)
        for key in ctx.md_files.keys():
            assert not key.endswith(".md")
            assert "." not in key or key.count(".") == 0


class TestScanContextIndexProjects:
    """Test ScanContext._index_projects() method."""
    
    def test_index_projects_empty(self, tmp_path):
        """Test indexing with no projects."""
        ctx = ScanContext(root_path=tmp_path)
        ctx._index_projects()
        
        assert ctx.projects == []
    
    def test_index_projects_sorted_by_length(self, multi_project_root):
        """Test that projects are sorted by length (longest first)."""
        ctx = ScanContext(root_path=multi_project_root)
        ctx._index_projects()
        
        # Should be sorted by length, longest first
        for i in range(len(ctx.projects) - 1):
            assert len(ctx.projects[i]) >= len(ctx.projects[i + 1])
    
    def test_index_projects_excludes_special_dirs(self, tmp_path):
        """Test that special directories are excluded."""
        root = tmp_path / "root"
        root.mkdir()
        
        # Create some excluded directories
        (root / ".venv").mkdir()
        (root / "node_modules").mkdir()
        
        # Create a valid project
        (root / "my-project").mkdir()
        
        ctx = ScanContext(root_path=root)
        ctx._index_projects()
        
        # Should only have the valid project
        assert "my-project" in ctx.projects
        assert ".venv" not in ctx.projects
        assert "node_modules" not in ctx.projects


class TestScanContextIndexAllFiles:
    """Test ScanContext._index_all_files() method."""
    
    def test_index_all_files_empty(self, tmp_path):
        """Test indexing with no files."""
        ctx = ScanContext(root_path=tmp_path)
        ctx._index_all_files()
        
        assert ctx.all_files == []
    
    def test_index_all_files_text_only(self, tmp_projects_root):
        """Test that only text files are indexed."""
        project_dir = tmp_projects_root / "my-project"
        project_dir.mkdir(parents=True)
        
        # Create various files
        (project_dir / "text.txt").write_text("text")
        (project_dir / "script.py").write_text("python")
        (project_dir / "image.png").write_bytes(b"PNG")
        
        ctx = ScanContext(root_path=tmp_projects_root)
        ctx._index_all_files()
        
        # Should only have text-based files
        assert len(ctx.all_files) >= 2
        
        file_names = [f.name for f in ctx.all_files]
        assert "text.txt" in file_names
        assert "script.py" in file_names
        assert "image.png" not in file_names
