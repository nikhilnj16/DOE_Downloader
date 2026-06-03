"""
config.py
=========
Central configuration for the education data pipeline.

All source URLs, directory paths, and request settings live here.
No hardcoded absolute paths — everything is resolved relative to
this file's location (the project root).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root — the directory that contains this file.
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Data directories
# ---------------------------------------------------------------------------
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

STATES = ["nevada", "massachusetts"]
CATEGORIES = ["test_scores", "financials", "teacher_records", "enrollment", "suspensions"]

# Build path helpers:  DATA_DIR / state / "raw" / category, etc.
def raw_dir(state: str, category: str) -> Path:
    """Return the raw data directory for a given state and category."""
    return DATA_DIR / state / "raw" / category


def cleaned_dir(state: str, category: str) -> Path:
    """Return the cleaned data directory for a given state and category."""
    return DATA_DIR / state / "cleaned" / category


# ---------------------------------------------------------------------------
# Log files
# ---------------------------------------------------------------------------
MANIFEST_CSV = LOGS_DIR / "download_manifest.csv"
PIPELINE_LOG = LOGS_DIR / "pipeline.log"

# ---------------------------------------------------------------------------
# HTTP request settings
# ---------------------------------------------------------------------------
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; EducationDataPipeline/1.0; "
        "+https://github.com/your-org/doe_downloaders)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REQUEST_TIMEOUT = 60          # seconds per request
MAX_RETRIES = 3               # total retry attempts
BACKOFF_FACTOR = 1.5          # exponential back-off multiplier
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# ---------------------------------------------------------------------------
# Source URLs  —  URLS[state][category] = [list of URLs]
# ---------------------------------------------------------------------------
URLS: dict[str, dict[str, list[str]]] = {

    # -----------------------------------------------------------------------
    # Nevada
    # -----------------------------------------------------------------------
    "nevada": {

        "test_scores": [
            # NDE Strapi CMS upload API — single endpoint that lists ALL uploaded files.
            # doe.nv.gov is a Next.js SPA; raw HTML does not contain file links.
            # We query this API once, filter by test-score keywords, and download matches.
            # Covers: SBAC, ACT, NAA, NAEP, WIDA, science assessments, etc.
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "financials": [
            # NDE Strapi CMS upload API — single endpoint that lists ALL uploaded files.
            # Covers: per-pupil expenditure, district budgets, fiscal reports, grants.
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "teacher_records": [
            # NDE Strapi CMS upload API — single endpoint that lists ALL uploaded files.
            # Covers: educator licensure, teacher counts, staffing, NEPF data.
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "enrollment": [
            # NDE Strapi CMS upload API — single endpoint that lists ALL uploaded files.
            # The doe.nv.gov site is a Next.js SPA; file links are not in raw HTML.
            # We query this API once, filter by enrollment keywords, and download matches.
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "suspensions": [
            # NDE Strapi CMS upload API — single endpoint that lists ALL uploaded files.
            # Covers: discipline data, suspension reports, behavioral health data.
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],
    },

    # -----------------------------------------------------------------------
    # Massachusetts
    # -----------------------------------------------------------------------
    "massachusetts": {

        "test_scores": [
            # MCAS results
            "https://www.doe.mass.edu/mcas/results.html",
            # State report — MCAS achievement
            "https://profiles.doe.mass.edu/statereport/mcas.aspx",
            # SAT / AP participation
            "https://profiles.doe.mass.edu/statereport/sat.aspx",
        ],

        "financials": [
            # Per-pupil expenditure
            "https://www.doe.mass.edu/finance/statistics/",
            # District financial reports
            "https://profiles.doe.mass.edu/statereport/finance.aspx",
        ],

        "teacher_records": [
            # Educator counts and experience
            "https://profiles.doe.mass.edu/statereport/teacherdata.aspx",
            # Educator licensure
            "https://profiles.doe.mass.edu/statereport/teacherlicensure.aspx",
        ],

        "enrollment": [
            # Enrollment by grade, school, district
            "https://www.doe.mass.edu/infoservices/reports/enroll/",
            "https://profiles.doe.mass.edu/statereport/enrollment.aspx",
        ],

        "suspensions": [
            # In-school and out-of-school suspensions
            "https://profiles.doe.mass.edu/statereport/suspensions.aspx",
            "https://profiles.doe.mass.edu/statereport/inschoolsuspensions.aspx",
        ],
    },
}
