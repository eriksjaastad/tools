# PDF-Converter

`pdf_to_markdown_converter.py` extracts existing PDF text with PyMuPDF and
writes a Markdown file beside each successfully converted PDF. Empty extraction
and read/write failures count as failed conversions. Other files continue to be
processed, and the summary preserves success and failure counts.

`cleanup_converted_pdfs.py` offers to delete PDFs whose corresponding Markdown
files contain more than 100 characters. Missing or short Markdown files keep
their PDFs. An unreadable Markdown file also keeps its PDF and records a failed
eligibility check. Deletion requires interactive confirmation; `--dry-run`
reports the proposed files without deleting them.

Both scripts accept `--base-dir` and return exit status 1 if any attempted
conversion, eligibility check, or deletion fails. Successful batches, no-work
runs, dry runs with successful checks, and user cancellation exit 0. Cancellation
does not clear an eligibility error already found. Each batch logs its summary.
