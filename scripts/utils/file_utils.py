"""
scripts/utils/file_utils.py
============================
File-system utility functions for the education data pipeline.

Provides:
  - create_dir_structure()  : creates all data directories for every state+category+subcategory
  - get_file_extension()    : detects extension from Content-Type or URL
  - safe_filename()         : converts a URL into a clean local filename
  - parse_year_range()      : extracts (min_year, max_year) from a filename using regex
  - is_duplicate()          : checks if a new file's year range is already covered
"""

import logging
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

# Make sure config is importable when this script is run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import STATES, CATEGORIES, DATA_DIR

logger = logging.getLogger(__name__)

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
    Create the primary category directories flatly under data/{state}/
    idempotently (exist_ok=True).
    """
    for state in STATES:
        for category in CATEGORIES:
            target = DATA_DIR / state / category
            target.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured directory: %s", target)


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


# ---------------------------------------------------------------------------
# Duplicate detection (Change 3)
# ---------------------------------------------------------------------------

# Regex: matches 4-digit years in range 1990–2030.
# Uses a simple pattern: 19[9]\d covers 1990-1999, 20[012]\d covers 2000-2029,
# plus exactly 2030. The \b word-boundary prevents matching mid-number sequences.
_YEAR_RE = re.compile(r"(?<!\d)(199\d|20[012]\d|2030)(?!\d)")


def parse_year_range(filename: str) -> tuple[int, int] | None:
    """
    Extract a (min_year, max_year) tuple from a filename using regex.

    Looks for all 4-digit years in the range 1990–2030 within *filename*.
    Handles both full 4-digit (2020-2022) and abbreviated 2-digit suffixes
    (2020-21 → treated as 2020-2021 if < current match).

    Parameters
    ----------
    filename : str
        The filename to parse (basename only, or full path string).

    Returns
    -------
    tuple[int, int] | None
        (min_year, max_year) if at least one year found; None otherwise.

    Examples
    --------
    >>> parse_year_range("NV_Enrollment_2020-2022.xlsx")
    (2020, 2022)
    >>> parse_year_range("report.pdf")
    None
    """
    stem = Path(filename).stem
    matches = _YEAR_RE.findall(stem)
    if not matches:
        return None
    years = [int(y) for y in matches]
    return (min(years), max(years))


def is_duplicate(
    new_filename: str,
    new_year_range: tuple[int, int] | None,
    existing_files_list: list[str],
) -> bool:
    """
    Return True if *new_filename* is fully covered by an existing file in the folder.

    A file is considered a duplicate if its year range is completely contained
    within the year range of an already-downloaded file of the same type.
    """
    if new_year_range is None:
        return False

    new_min, new_max = new_year_range
    new_stem = Path(new_filename).stem
    # Remove year groups from stem to get the 'fingerprint' of the file layout
    new_fingerprint = _YEAR_RE.sub('', new_stem)
    new_fingerprint = re.sub(r'[-_]+', '_', new_fingerprint).strip('_')

    for existing in existing_files_list:
        ex_range = parse_year_range(existing)
        if ex_range is None:
            continue
        
        ex_stem = Path(existing).stem
        ex_fingerprint = _YEAR_RE.sub('', ex_stem)
        ex_fingerprint = re.sub(r'[-_]+', '_', ex_fingerprint).strip('_')

        # Only compare ranges if the base file characteristics (subgroup, grade, category) match
        if ex_fingerprint == new_fingerprint:
            ex_min, ex_max = ex_range
            if ex_min <= new_min and ex_max >= new_max:
                logger.info(
                    "SKIP duplicate: '%s' (years %d-%d) already covered by '%s' (years %d-%d)",
                    new_filename, new_min, new_max,
                    Path(existing).name, ex_min, ex_max,
                )
                return True

    return False

