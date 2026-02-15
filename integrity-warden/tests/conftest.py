"""Pytest fixtures and configuration for integrity-warden tests."""

import pytest
from pathlib import Path
from typing import Dict, List


@pytest.fixture
def tmp_projects_root(tmp_path) -> Path:
    """Create a temporary projects root directory structure."""
    return tmp_path / "projects"


@pytest.fixture
def simple_project(tmp_projects_root: Path) -> Path:
    """Create a simple project structure with basic files."""
    project_dir = tmp_projects_root / "my-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


@pytest.fixture
def project_with_markdown(simple_project: Path) -> Path:
    """Create a project with markdown files."""
    simple_project.mkdir(exist_ok=True)
    
    # Create main docs
    docs_dir = simple_project / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    (docs_dir / "README.md").write_text("# My Project\n\nWelcome!")
    (docs_dir / "ARCHITECTURE.md").write_text("# Architecture\n\nDetails here")
    (docs_dir / "API.md").write_text("# API Reference")
    
    return simple_project


@pytest.fixture
def project_with_wikilinks(project_with_markdown: Path) -> Path:
    """Create a project with WikiLink references."""
    docs_dir = project_with_markdown / "docs"
    
    # File with valid wikilinks
    (docs_dir / "GUIDE.md").write_text("""
# Guide

See [[README]] for overview.
Check [[ARCHITECTURE]] for design.
Refer to [[API]] for endpoints.
""")
    
    # File with broken wikilinks
    (docs_dir / "BROKEN.md").write_text("""
# Issues

[[NonExistent]] file reference
Check [[MissingGuide]] for details
See [[NOTFOUND.md]] for info
""")
    
    return project_with_markdown


@pytest.fixture
def project_with_markdown_links(project_with_markdown: Path) -> Path:
    """Create a project with markdown link references."""
    docs_dir = project_with_markdown / "docs"
    
    # File with valid links
    (docs_dir / "LINKS.md").write_text("""
# Links

- [Main README](README.md)
- [Architecture Guide](ARCHITECTURE.md)
- [External Link](https://example.com)
- [Anchor Link](#section)
""")
    
    # File with broken links
    (docs_dir / "BROKEN_LINKS.md").write_text("""
# Broken Links

- [Missing File](missing.md)
- [Bad Path](../nonexistent/file.md)
- [Deleted Guide](deleted-guide.md)
""")
    
    return project_with_markdown


@pytest.fixture
def project_with_scripts(simple_project: Path) -> Path:
    """Create a project with shell and python scripts."""
    scripts_dir = simple_project / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    
    # Create a valid shell source file
    (scripts_dir / "common.sh").write_text("""
#!/bin/bash
echo "Common utilities"
""")
    
    # Create a shell script that sources files
    (scripts_dir / "main.sh").write_text("""
#!/bin/bash
source ./common.sh
source /usr/local/lib/utility.sh
source ../nonexistent/library.sh
""")
    
    # Create a python module
    (scripts_dir / "__init__.py").write_text("")
    (scripts_dir / "utils.py").write_text("""
def helper():
    return True
""")
    
    return simple_project


@pytest.fixture
def project_with_paths(simple_project: Path) -> Path:
    """Create a project with absolute and relative path references."""
    root = simple_project
    
    # Create nested structure
    (root / "project-a").mkdir(exist_ok=True)
    (root / "project-b").mkdir(exist_ok=True)
    
    docs_a = root / "project-a" / "docs"
    docs_a.mkdir(exist_ok=True)
    
    docs_b = root / "project-b" / "docs"
    docs_b.mkdir(exist_ok=True)
    
    # File with absolute path references
    projects_root = simple_project.parent
    (docs_a / "README.md").write_text(f"""
# Project A

Reference: {projects_root}/my-project/project-a/file.md
Broken: {projects_root}/my-project/nonexistent.txt
Valid: {projects_root}/my-project/project-b/docs/README.md
""")
    
    # File with relative path references
    (docs_a / "GUIDE.md").write_text("""
# Guide

See ../project-b/docs/README.md for details
Check ../../project-b/file.md for info
Reference ../data/config.yaml
""")
    
    return simple_project


@pytest.fixture
def multi_project_root(tmp_projects_root: Path) -> Path:
    """Create a multi-project root with several projects."""
    projects = ["project-alpha", "project-beta", "project-gamma"]
    
    for proj_name in projects:
        proj_dir = tmp_projects_root / proj_name
        proj_dir.mkdir(parents=True, exist_ok=True)
        
        # Create basic structure
        docs_dir = proj_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "README.md").write_text(f"# {proj_name}\n\nProject documentation")
    
    return tmp_projects_root


@pytest.fixture
def project_with_symlinks(simple_project: Path) -> Path:
    """Create a project with symbolic links."""
    import os
    
    # Create target files
    target_dir = simple_project / "target"
    target_dir.mkdir(exist_ok=True)
    (target_dir / "real_file.txt").write_text("Real content")
    
    # Create valid symlink
    valid_link = simple_project / "valid_link.txt"
    os.symlink(target_dir / "real_file.txt", valid_link)
    
    # Create broken symlink
    broken_link = simple_project / "broken_link.txt"
    os.symlink(target_dir / "nonexistent.txt", broken_link)
    
    return simple_project


@pytest.fixture
def temp_file_structure(tmp_path: Path) -> Dict[str, Path]:
    """Create a dictionary with various temporary file paths."""
    # Create a file structure for testing
    root = tmp_path / "structure"
    root.mkdir()
    
    # Create directories
    (root / "dir_a").mkdir()
    (root / "dir_b").mkdir()
    
    # Create files with various content
    (root / "file_empty.txt").write_text("")
    (root / "file_utf8.txt").write_text("UTF-8 content: é à ü")
    (root / "file_binary").write_bytes(b"\x00\x01\x02\x03")
    (root / "file_large.txt").write_text("x" * 100000)
    
    return {
        "root": root,
        "dir_a": root / "dir_a",
        "dir_b": root / "dir_b",
        "empty": root / "file_empty.txt",
        "utf8": root / "file_utf8.txt",
        "binary": root / "file_binary",
        "large": root / "file_large.txt",
    }
