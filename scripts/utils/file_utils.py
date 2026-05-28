"""
scripts/utils/file_utils.py
============================
File-system utility functions for the education data pipeline.

Provides:
  - create_dir_structure()  : creates all raw/cleaned directories for every state+category
  - get_file_extension()    : detects extension from Content-Type or URL
  - safe_filename()         : converts a URL into a clean local filename
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

# Make sure config is importable when this script is run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import STATES, CATEGORIES, raw_dir, cleaned_dir

# ---------------------------------------------------------------------------
# Content-Type → file extension mapping
# ---------------------------------------------------------------------------
_CONTENT_TYPE_MAP: dict[str, str] = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "text/csv": ".csv",
    "application/csv": ".csv",
    "application/pdf": ".pdf",
    "text/html": ".html",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/octet-stream": "",          # unknown, fall back to URL
}


def create_dir_structure() -> None:
    """
    Create the full raw / cleaned directory tree for every state and category.

    The structure matches:
        data/{state}/raw/{category}/
        data/{state}/cleaned/{category}/

    All directories are created idempotently (exist_ok=True).
    """
    for state in STATES:
        for category in CATEGORIES:
            raw_dir(state, category).mkdir(parents=True, exist_ok=True)
            cleaned_dir(state, category).mkdir(parents=True, exist_ok=True)


def get_file_extension(url: str, response: requests.Response | None = None) -> str:
    """
    Determine the most appropriate file extension for a downloaded resource.

    Strategy (in priority order):
    1. Parse the Content-Type header from the HTTP response.
    2. Fall back to the file extension embedded in the URL path.
    3. Return an empty string if no extension can be determined.

    Parameters
    ----------
    url      : str
        The source URL.
    response : requests.Response | None
        The HTTP response object (may be None when testing offline).

    Returns
    -------
    str
        Extension string including the leading dot (e.g. ".xlsx"), or "".
    """
    # 1. Try Content-Type header
    if response is not None:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type in _CONTENT_TYPE_MAP:
            ext = _CONTENT_TYPE_MAP[content_type]
            if ext:
                return ext

    # 2. Fall back to the URL path
    parsed_path = urlparse(url).path
    suffix = Path(parsed_path).suffix
    if suffix:
        return suffix.lower()

    return ""


def safe_filename(url: str) -> str:
    """
    Convert a URL into a safe, human-readable local filename (without extension).

    The function strips the scheme + domain, replaces path separators and
    query-string characters with underscores, and truncates to 200 characters.

    Parameters
    ----------
    url : str
        Source URL to convert.

    Returns
    -------
    str
        A filesystem-safe filename stem (no extension).

    Examples
    --------
    >>> safe_filename("https://doe.nv.gov/Stats_Data/Enrollment/2023_enroll.xlsx")
    'Stats_Data_Enrollment_2023_enroll'
    """
    parsed = urlparse(url)
    # Combine path + query into a single string to preserve uniqueness
    raw = f"{parsed.path}_{parsed.query}" if parsed.query else parsed.path

    # Remove leading slash, replace non-alphanumeric chars with underscores
    raw = raw.lstrip("/")
    raw = re.sub(r"[^A-Za-z0-9._-]", "_", raw)

    # Collapse consecutive underscores
    raw = re.sub(r"_+", "_", raw).strip("_")

    # Remove known extension suffixes so the caller can append the detected one
    raw = re.sub(r"\.(xlsx|xls|csv|pdf|zip|html)$", "", raw, flags=re.IGNORECASE)

    return raw[:200]
