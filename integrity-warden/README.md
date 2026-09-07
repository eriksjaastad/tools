# Integrity Warden

A suite of tools for maintaining ecosystem integrity, performing deep cleanups, and managing document indices.

## Tools

- [Integrity Warden](integrity_warden.py) - Core logic for verifying ecosystem health and enforcing standards.
- [Deep Cleanup](deep_cleanup.py) - Utility for aggressive cleanup of temporary and unnecessary files.
- [Remediate Renames](remediate_renames.py) - Tool for fixing broken links and metadata after file renamings.
- [Rename Indices](rename_indices.py) - Standardizes index file naming across projects.

## Documentation
- [Fix Prompt Dependencies](fix-prompt-dependencies.md) - Guide for resolving prompt-related issues.

## Audit completion

The checker exits `0` only for a completed audit with no issues, and `1` when
issues are found. Missing, unreadable, or invalid UTF-8 evidence stops the audit
with `AUDIT INCOMPLETE` and exit `2`, identifying the checker and file. Fix the
read failure and rerun; an incomplete audit cannot verify ecosystem integrity.
