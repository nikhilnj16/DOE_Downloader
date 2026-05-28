"""
scripts/utils/logger.py
========================
Logging utilities for the education data pipeline.

Provides:
  - setup_logger()        : returns a configured Python Logger writing to logs/pipeline.log
  - log_download()        : appends a row to logs/download_manifest.csv
"""

import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import paths from config so there are no hardcoded paths here.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import MANIFEST_CSV, PIPELINE_LOG, LOGS_DIR

# Manifest CSV column order
MANIFEST_COLUMNS = [
    "timestamp",
    "state",
    "category",
    "url",
    "filename",
    "status",
    "filesize_kb",
]


def setup_logger(name: str = "pipeline", level: int = logging.DEBUG) -> logging.Logger:
    """
    Create and return a configured Logger instance.

    The logger writes at DEBUG level and above to logs/pipeline.log,
    and INFO level and above to stdout.

    Parameters
    ----------
    name : str
        Logger name (default: "pipeline").
    level : int
        Root logging level (default: logging.DEBUG).

    Returns
    -------
    logging.Logger
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers when called multiple times
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- File handler (DEBUG+) ---
    fh = logging.FileHandler(PIPELINE_LOG, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # --- Stream handler (INFO+) ---
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def log_download(
    state: str,
    category: str,
    url: str,
    filename: str,
    status: str,
    filesize_kb: float,
) -> None:
    """
    Append a single download record to the manifest CSV.

    Creates the CSV and writes the header row if the file does not yet exist.

    Parameters
    ----------
    state       : str   e.g. "nevada"
    category    : str   e.g. "test_scores"
    url         : str   Source URL that was downloaded
    filename    : str   Local filename that was saved
    status      : str   "success" | "failed" | "skipped"
    filesize_kb : float File size in kilobytes (0.0 on failure)
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    file_exists = MANIFEST_CSV.exists()

    with MANIFEST_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "state": state,
                "category": category,
                "url": url,
                "filename": filename,
                "status": status,
                "filesize_kb": round(filesize_kb, 2),
            }
        )
