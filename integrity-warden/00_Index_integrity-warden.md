---
tags:
  - map/project
  - p/integrity-warden
  - type/tool
  - domain/maintenance
  - status/active
created: 2026-01-16
---

# Integrity Warden

Tool for maintaining ecosystem health, cleaning up technical dust, and remediating structural issues. This project contains scripts for DNA sterilization, deep cleanup, and managing index renames.

## Key Components

### Maintenance Scripts
- [[integrity_warden.py]] - Core logic for scanning and fixing integrity issues.
- [[deep_cleanup.py]] - Utility for removing "digital dust" (caches, venvs, logs).
- [[remediate_renames.py]] - Handles bulk renaming of files and updating references.
- [[rename_indices.py]] - Specifically manages the transition to `00_Index_*.md` standards.

### Documentation
- [[README.md]] - Project overview and usage.
- [[fix-prompt-dependencies.md]] - Guide for resolving prompt-level dependency chains.

## Status
**Status:** #status/active  
**Purpose:** Automated ecosystem maintenance
