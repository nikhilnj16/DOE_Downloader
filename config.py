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
            # Nevada Report Card — downloadable assessment data
            "https://nevadareportcard.nv.gov/DI/DownloadData",
            # Statewide data downloads (NDE)
            "https://doe.nv.gov/Stats_Data/Statewide_Data/",
            # CRT / SBAC results
            "https://doe.nv.gov/Stats_Data/Statewide_Data/Test_Results/",
        ],

        "financials": [
            # Per-pupil expenditure and district financial reports
            "https://doe.nv.gov/Finance_Administration/",
            "https://doe.nv.gov/Finance_Administration/Financial_Reports/",
            "https://doe.nv.gov/Finance_Administration/Per_Pupil_Expenditure/",
        ],

        "teacher_records": [
            # Licensed educator counts and experience data
            "https://doe.nv.gov/Stats_Data/Statewide_Data/Educator_Data/",
            "https://doe.nv.gov/Licensing/Statistics/",
        ],

        "enrollment": [
            # Enrollment by grade, school, and district
            "https://doe.nv.gov/Stats_Data/Statewide_Data/Enrollment/",
            "https://nevadareportcard.nv.gov/DI/DownloadData",
        ],

        "suspensions": [
            # Discipline / suspension data
            "https://doe.nv.gov/Stats_Data/Statewide_Data/Discipline/",
            "https://nevadareportcard.nv.gov/DI/DownloadData",
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
