#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["send2trash>=1.8,<2"]
# ///
"""
PDF Cleanup Script
Safely removes PDF files that have been successfully converted to markdown.
Only deletes PDFs if a corresponding .md file exists in the same location.
"""

import os
import sys
import logging
from pathlib import Path
import argparse
from datetime import datetime

def setup_logging():
    """Set up logging configuration"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pdf_cleanup_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def should_exclude_path(pdf_path):
    """Check if a PDF path should be excluded from cleanup"""
    excluded_patterns = [
        'venv/',
        'node_modules/',
        'site-packages/',
        '.git/',
        '__pycache__/',
        'matplotlib/mpl-data/images/'  # Specifically exclude matplotlib icons
    ]
    
    path_str = str(pdf_path)
    return any(pattern in path_str for pattern in excluded_patterns)

def find_convertible_pdfs(base_dir):
    """Find all PDFs that could have been converted (excluding system files)"""
    base_path = Path(base_dir)
    all_pdfs = list(base_path.rglob("*.pdf"))
    
    # Filter out excluded paths
    valid_pdfs = [pdf for pdf in all_pdfs if not should_exclude_path(pdf)]
    
    logger.info(f"Found {len(all_pdfs)} total PDFs")
    logger.info(f"Excluding {len(all_pdfs) - len(valid_pdfs)} system/library PDFs")
    logger.info(f"Checking {len(valid_pdfs)} PDFs for cleanup")
    
    return valid_pdfs

def check_pdf_for_cleanup(pdf_path):
    """Check if a PDF can be safely deleted (has corresponding .md file)"""
    md_path = pdf_path.with_suffix('.md')
    
    if md_path.exists():
        # Additional check: make sure the .md file has content
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if len(content) > 100:  # Has substantial content
                return True, f"Markdown file exists with {len(content)} characters"
            else:
                return False, f"Markdown file exists but is too small ({len(content)} characters)"
    else:
        return False, "No corresponding markdown file found"

def validate_scope(pdf_path, base_dir):
    """Refuse escaped/symlinked inputs, including their conversion evidence."""
    for path in (pdf_path, pdf_path.with_suffix('.md')):
        if path.is_symlink() or not path.resolve().is_relative_to(base_dir):
            raise OSError(f"Path is outside cleanup scope or is a symlink: {path}")
        if (path == pdf_path or path.exists()) and not path.is_file():
            raise OSError(f"Not a regular file: {path}")


def delete_pdf_safely(pdf_path, dry_run=False):
    """Safely delete a PDF file"""
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would delete: {pdf_path}")
            return True
        else:
            from send2trash import send2trash
            send2trash(str(pdf_path))
            logger.info(f"✅ Deleted: {pdf_path}")
            return True
    except (OSError, ImportError) as e:  # governance: allow-silent SF002: main counts this failed deletion and exits nonzero
        logger.error(f"❌ Failed to delete {pdf_path}: {str(e)}")
        return False

def main(argv=None):
    """Keep processing eligible files; inspection/deletion failures return 1."""
    global logger
    
    parser = argparse.ArgumentParser(description='Clean up successfully converted PDFs')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--base-dir', required=True,
                       help='Explicit directory to search recursively for PDFs')
    
    args = parser.parse_args(argv)
    
    base_dir = Path(args.base_dir).resolve()
    if not base_dir.is_dir():
        parser.error('--base-dir must name an existing directory')
    logger = setup_logging()
    logger.info(f"Starting PDF cleanup in: {base_dir}")
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be deleted")
    
    # Find PDFs that could have been converted
    candidate_pdfs = find_convertible_pdfs(base_dir)
    
    if not candidate_pdfs:
        logger.info("No PDFs found to check for cleanup.")
        return 0
    
    # Check each PDF for cleanup eligibility
    pdfs_to_delete = []
    pdfs_to_keep = []
    failed_checks = 0
    
    for pdf_path in candidate_pdfs:
        try:
            validate_scope(pdf_path, base_dir)
            can_delete, reason = check_pdf_for_cleanup(pdf_path)
        except (OSError, UnicodeError) as e:
            failed_checks += 1
            pdfs_to_keep.append(pdf_path)
            logger.error(f"❌ Could not verify {pdf_path.name}; keeping PDF: {e}")
            continue
        
        if can_delete:
            pdfs_to_delete.append(pdf_path)
            logger.info(f"✅ Can delete {pdf_path.name}: {reason}")
        else:
            pdfs_to_keep.append(pdf_path)
            logger.info(f"⚠️  Keeping {pdf_path.name}: {reason}")
    
    logger.info(f"\nSummary:")
    logger.info(f"  📄 PDFs eligible for deletion: {len(pdfs_to_delete)}")
    logger.info(f"  🔒 PDFs to keep: {len(pdfs_to_keep)}")
    logger.info(f"  ❌ Failed eligibility checks: {failed_checks}")
    
    if not pdfs_to_delete:
        logger.info("No PDFs are eligible for deletion.")
        return 1 if failed_checks else 0
    
    if args.dry_run:
        logger.info("\nDRY RUN - PDFs that would be deleted:")
        for pdf in pdfs_to_delete:
            logger.info(f"  {pdf}")
        return 1 if failed_checks else 0
    
    # Confirm deletion if not dry run
    print(f"\nReady to move {len(pdfs_to_delete)} PDF files to Trash under {base_dir}.")
    print("These PDFs have been successfully converted to markdown.")
    response = input("Continue? (yes/no): ").lower().strip()
    
    if response not in ['yes', 'y']:
        logger.info("Deletion cancelled by user.")
        return 1 if failed_checks else 0
    
    # Delete PDFs
    successful_deletions = 0
    failed_deletions = 0
    
    for pdf_path in pdfs_to_delete:
        try:
            validate_scope(pdf_path, base_dir)
            eligible, _ = check_pdf_for_cleanup(pdf_path)
            if not eligible:
                raise OSError('Markdown evidence changed after confirmation')
        except (OSError, UnicodeError) as e:
            failed_deletions += 1
            logger.error(f"Keeping {pdf_path}: {e}")
            continue
        if delete_pdf_safely(pdf_path, dry_run=False):
            successful_deletions += 1
        else:
            failed_deletions += 1
    
    # Final summary
    logger.info(f"\n🎉 Cleanup Summary:")
    logger.info(f"  ✅ Successfully deleted: {successful_deletions}")
    logger.info(f"  ❌ Failed to delete: {failed_deletions}")
    logger.info(f"  🔒 PDFs kept (ineligible or check failed): {len(pdfs_to_keep)}")
    logger.info(f"  ❌ Failed eligibility checks: {failed_checks}")
    logger.info(f"  📊 Total checked: {len(candidate_pdfs)}")
    
    if failed_deletions > 0:
        logger.warning(f"Check the log file for details on failed deletions.")
    return 1 if failed_deletions or failed_checks else 0

if __name__ == "__main__":
    sys.exit(main())


