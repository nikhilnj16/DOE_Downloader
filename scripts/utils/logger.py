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

# ---------------------------------------------------------------------------
# Manifest CSV column order (Change 7)
# ---------------------------------------------------------------------------
MANIFEST_COLUMNS = [
    "timestamp",
    "state",
    "category",
    "subcategory",
    "original_filename",
    "source_url",
    "local_path",
    "drive_uploaded",
    "drive_file_id",
    "file_size_kb",
    "year_range_detected",
    "status",
    "notes",
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
    # New parameters (all optional for backward-compat with existing callers)
    subcategory: str = "",
    local_path: str = "",
    drive_uploaded: bool = False,
    drive_file_id: str = "",
    year_range_detected: str = "",
    notes: str = "",
) -> None:
    """
    Append a single download record to the manifest CSV.

    Creates the CSV and writes the header row if the file does not yet exist.

    Parameters
    ----------
    state               : str   e.g. "nevada"
    category            : str   e.g. "assessments"
    url                 : str   Source URL that was downloaded
    filename            : str   Original filename as provided by the server
    status              : str   "success" | "skipped_duplicate" | "failed"
    filesize_kb         : float File size in kilobytes (0.0 on failure)
    subcategory         : str   e.g. "by_race" (blank for non-assessment categories)
    local_path          : str   Absolute local path where file was saved
    drive_uploaded      : bool  True if successfully uploaded to Drive
    drive_file_id       : str   Google Drive file ID after upload (blank if not uploaded)
    year_range_detected : str   Parsed year range e.g. "2020-2023" (blank if not found)
    notes               : str   Additional context (e.g. skip reason, error message)
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    file_exists = MANIFEST_CSV.exists()

    with MANIFEST_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp":           datetime.now(tz=timezone.utc).isoformat(),
                "state":               state,
                "category":            category,
                "subcategory":         subcategory,
                "original_filename":   filename,
                "source_url":          url,
                "local_path":          local_path,
                "drive_uploaded":      drive_uploaded,
                "drive_file_id":       drive_file_id,
                "file_size_kb":        round(filesize_kb, 2),
                "year_range_detected": year_range_detected,
                "status":              status,
                "notes":               notes,
            }
        )
