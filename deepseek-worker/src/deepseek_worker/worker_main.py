"""Worker subprocess main entry point."""

import sys
from pathlib import Path

from .worker import run_stub_worker


def main():
    """Worker subprocess entry point."""
    if len(sys.argv) != 4:
        print("Usage: worker_main.py <job_id> <work_order_path> <job_dir>")
        sys.exit(2)

    job_id = sys.argv[1]
    work_order_path = Path(sys.argv[2])
    job_dir = Path(sys.argv[3])

    sys.exit(run_stub_worker(job_id, work_order_path, job_dir))


if __name__ == "__main__":
    main()
