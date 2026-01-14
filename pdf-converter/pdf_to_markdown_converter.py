#!/usr/bin/env python3
"""
PDF to Markdown Converter
Converts all PDFs in the projects directory to markdown format,
excluding system/library files like matplotlib icons.
"""

import os
import sys
import logging
from pathlib import Path
import argparse
from datetime import datetime

try:
    import pymupdf  # PyMuPDF for better PDF extraction
except ImportError:
    print("PyMuPDF not found. Installing...")
    os.system("pip install pymupdf")
    import pymupdf

# Set up logging
def setup_logging():
    """Set up logging configuration"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pdf_conversion_{timestamp}.log"
    
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
    """Check if a PDF path should be excluded from conversion"""
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

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using PyMuPDF"""
    try:
        doc = pymupdf.open(pdf_path)
        text_content = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            
            if text.strip():  # Only add non-empty pages
                text_content.append(f"## Page {page_num + 1}\n\n{text}\n")
        
        doc.close()
        return "\n".join(text_content)
    
    except Exception as e:
        logging.error(f"Error extracting text from {pdf_path}: {str(e)}")
        return None

def create_markdown_content(pdf_path, extracted_text, base_dir):
    """Create well-formatted markdown content"""
    pdf_name = pdf_path.stem
    try:
        relative_path = pdf_path.relative_to(base_dir)
    except ValueError:
        relative_path = pdf_path  # fallback to absolute path
    
    markdown_content = f"""# {pdf_name}

**Source:** `{relative_path}`  
**Converted:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Original Format:** PDF

---

{extracted_text}

---

*This document was automatically converted from PDF to Markdown.*
"""
    return markdown_content

def convert_pdf_to_markdown(pdf_path, base_dir):
    """Convert a single PDF to markdown"""
    try:
        logger.info(f"Converting: {pdf_path}")
        
        # Extract text
        extracted_text = extract_text_from_pdf(pdf_path)
        if not extracted_text:
            logger.warning(f"No text extracted from {pdf_path}")
            return False
        
        # Create markdown content
        markdown_content = create_markdown_content(pdf_path, extracted_text, base_dir)
        
        # Determine output path (same directory, .md extension)
        md_path = pdf_path.with_suffix('.md')
        
        # Write markdown file
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        logger.info(f"✅ Successfully converted: {pdf_path} → {md_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to convert {pdf_path}: {str(e)}")
        return False

def find_pdfs_to_convert(base_dir):
    """Find all PDFs that should be converted"""
    base_path = Path(base_dir)
    all_pdfs = list(base_path.rglob("*.pdf"))
    
    # Filter out excluded paths
    valid_pdfs = [pdf for pdf in all_pdfs if not should_exclude_path(pdf)]
    
    logger.info(f"Found {len(all_pdfs)} total PDFs")
    logger.info(f"Excluding {len(all_pdfs) - len(valid_pdfs)} system/library PDFs")
    logger.info(f"Will convert {len(valid_pdfs)} PDFs")
    
    return valid_pdfs

def main():
    """Main conversion function"""
    global logger
    logger = setup_logging()
    
    parser = argparse.ArgumentParser(description='Convert PDFs to Markdown')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be converted without actually converting')
    parser.add_argument('--base-dir', default='.', 
                       help='Base directory to search for PDFs (default: current directory)')
    
    args = parser.parse_args()
    
    base_dir = Path(args.base_dir).resolve()
    logger.info(f"Starting PDF to Markdown conversion in: {base_dir}")
    
    # Find PDFs to convert
    pdfs_to_convert = find_pdfs_to_convert(base_dir)
    
    if not pdfs_to_convert:
        logger.info("No PDFs found to convert.")
        return
    
    if args.dry_run:
        logger.info("DRY RUN - Files that would be converted:")
        for pdf in pdfs_to_convert:
            logger.info(f"  {pdf}")
        return
    
    # Convert PDFs
    successful_conversions = 0
    failed_conversions = 0
    
    for pdf_path in pdfs_to_convert:
        if convert_pdf_to_markdown(pdf_path, base_dir):
            successful_conversions += 1
        else:
            failed_conversions += 1
    
    # Summary
    logger.info(f"\n🎉 Conversion Summary:")
    logger.info(f"  ✅ Successful: {successful_conversions}")
    logger.info(f"  ❌ Failed: {failed_conversions}")
    logger.info(f"  📊 Total: {len(pdfs_to_convert)}")
    
    if failed_conversions > 0:
        logger.warning(f"Check the log file for details on failed conversions.")

if __name__ == "__main__":
    main()
