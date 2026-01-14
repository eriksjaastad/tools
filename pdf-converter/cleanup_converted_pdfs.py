#!/usr/bin/env python3
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
        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if len(content) > 100:  # Has substantial content
                    return True, f"Markdown file exists with {len(content)} characters"
                else:
                    return False, f"Markdown file exists but is too small ({len(content)} characters)"
        except Exception as e:
            return False, f"Error reading markdown file: {str(e)}"
    else:
        return False, "No corresponding markdown file found"

def delete_pdf_safely(pdf_path, dry_run=False):
    """Safely delete a PDF file"""
    try:
        if dry_run:
            logger.info(f"[DRY RUN] Would delete: {pdf_path}")
            return True
        else:
            pdf_path.unlink()
            logger.info(f"✅ Deleted: {pdf_path}")
            return True
    except Exception as e:
        logger.error(f"❌ Failed to delete {pdf_path}: {str(e)}")
        return False

def main():
    """Main cleanup function"""
    global logger
    logger = setup_logging()
    
    parser = argparse.ArgumentParser(description='Clean up successfully converted PDFs')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--base-dir', default='..', 
                       help='Base directory to search for PDFs (default: parent directory)')
    
    args = parser.parse_args()
    
    base_dir = Path(args.base_dir).resolve()
    logger.info(f"Starting PDF cleanup in: {base_dir}")
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No files will be deleted")
    
    # Find PDFs that could have been converted
    candidate_pdfs = find_convertible_pdfs(base_dir)
    
    if not candidate_pdfs:
        logger.info("No PDFs found to check for cleanup.")
        return
    
    # Check each PDF for cleanup eligibility
    pdfs_to_delete = []
    pdfs_to_keep = []
    
    for pdf_path in candidate_pdfs:
        can_delete, reason = check_pdf_for_cleanup(pdf_path)
        
        if can_delete:
            pdfs_to_delete.append(pdf_path)
            logger.info(f"✅ Can delete {pdf_path.name}: {reason}")
        else:
            pdfs_to_keep.append(pdf_path)
            logger.info(f"⚠️  Keeping {pdf_path.name}: {reason}")
    
    logger.info(f"\nSummary:")
    logger.info(f"  📄 PDFs eligible for deletion: {len(pdfs_to_delete)}")
    logger.info(f"  🔒 PDFs to keep: {len(pdfs_to_keep)}")
    
    if not pdfs_to_delete:
        logger.info("No PDFs are eligible for deletion.")
        return
    
    if args.dry_run:
        logger.info("\nDRY RUN - PDFs that would be deleted:")
        for pdf in pdfs_to_delete:
            logger.info(f"  {pdf}")
        return
    
    # Confirm deletion if not dry run
    print(f"\nReady to delete {len(pdfs_to_delete)} PDF files.")
    print("These PDFs have been successfully converted to markdown.")
    response = input("Continue? (yes/no): ").lower().strip()
    
    if response not in ['yes', 'y']:
        logger.info("Deletion cancelled by user.")
        return
    
    # Delete PDFs
    successful_deletions = 0
    failed_deletions = 0
    
    for pdf_path in pdfs_to_delete:
        if delete_pdf_safely(pdf_path, dry_run=False):
            successful_deletions += 1
        else:
            failed_deletions += 1
    
    # Final summary
    logger.info(f"\n🎉 Cleanup Summary:")
    logger.info(f"  ✅ Successfully deleted: {successful_deletions}")
    logger.info(f"  ❌ Failed to delete: {failed_deletions}")
    logger.info(f"  🔒 PDFs kept (no markdown): {len(pdfs_to_keep)}")
    logger.info(f"  📊 Total checked: {len(candidate_pdfs)}")
    
    if failed_deletions > 0:
        logger.warning(f"Check the log file for details on failed deletions.")

if __name__ == "__main__":
    main()





