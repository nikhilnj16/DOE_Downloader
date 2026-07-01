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

STATES = ["nevada", "massachusetts", "alaska"]


# New primary category list (Change 2)
CATEGORIES = ["assessments", "financials", "teacher_staff", "enrollment_attendance"]

# Assessment sub-category breakdown (Change 2)
ASSESSMENT_SUBCATEGORIES = {
    "overall":    "overall",
    "by_race":    "by_race",
    "by_gender":  "by_gender",
    "by_iep_504": "by_iep_504",
    "by_ell":     "by_ell",
}

# ---------------------------------------------------------------------------
# Pipeline behaviour flags (Change 2)
# ---------------------------------------------------------------------------
KEEP_ORIGINAL_FILENAME = True   # Never rename what the server provides
SKIP_CLEANING = True            # Raw download only — no cleaning step
ENABLE_DRIVE_UPLOAD = True      # Upload every downloaded file to Google Drive
DRIVE_FOLDER_ID = ""            # Legacy single-folder ID (fill in manually)
DUPLICATE_DETECTION = True      # Skip files whose year range is already covered

# ---------------------------------------------------------------------------
# Google Drive / service-account settings (Change 6)
# ---------------------------------------------------------------------------
GOOGLE_SERVICE_ACCOUNT_JSON = "credentials/service_account.json"
DRIVE_ROOT_FOLDER_ID = ""       # Root Drive folder — fill in manually

# ---------------------------------------------------------------------------
# Build path helpers
# ---------------------------------------------------------------------------

def raw_dir(state: str, category: str, subcategory: str | None = None) -> Path:
    """
    Return the raw data directory for a given state, category, and optional subcategory.

    New layout (Change 1):
        data/{state}/{category}/                           (no subcategory)
        data/{state}/{category}/{subcategory}/             (with subcategory)

    Parameters
    ----------
    state       : str  e.g. "nevada"
    category    : str  e.g. "assessments"
    subcategory : str | None  e.g. "by_race" (optional)

    Returns
    -------
    pathlib.Path
    """
    if subcategory:
        return DATA_DIR / state / category / subcategory
    return DATA_DIR / state / category


def cleaned_dir(state: str, category: str) -> Path:
    """
    Return the cleaned data directory for a given state and category.

    Cleaning is disabled (SKIP_CLEANING = True) but the helper is kept
    for backward compatibility with any tooling that imports it.
    """
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
#
# Old category keys (test_scores, teacher_records, enrollment, suspensions)
# are kept for backward compatibility with any existing scripts that import them.
# New keys map to the updated category names.
# ---------------------------------------------------------------------------
URLS: dict[str, dict[str, list[str]]] = {

    # -----------------------------------------------------------------------
    # Nevada
    # -----------------------------------------------------------------------
    "nevada": {

        # New category keys ---------------------------------------------------
        "assessments": [
            # NDE Strapi CMS upload API — single endpoint listing ALL uploaded files.
            # doe.nv.gov is a Next.js SPA; raw HTML does not contain file links.
            # Covers: SBAC, ACT, NAA, NAEP, WIDA, science assessments, etc.
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "financials": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "teacher_staff": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "enrollment_attendance": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        # Legacy keys (kept for backward compatibility) -----------------------
        "test_scores": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "teacher_records": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "enrollment": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],

        "suspensions": [
            "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000",
        ],
    },

    # -----------------------------------------------------------------------
    # Massachusetts
    # -----------------------------------------------------------------------
    "massachusetts": {

        # New category keys ---------------------------------------------------
        "assessments": [
            # MCAS results page
            "https://www.doe.mass.edu/mcas/results.html",
            # State report — MCAS achievement (all subgroups via dropdown)
            "https://profiles.doe.mass.edu/statereport/mcas.aspx",
            # SAT / AP participation
            "https://profiles.doe.mass.edu/statereport/sat.aspx",
            # Alternate assessment (IEP students)
            "https://profiles.doe.mass.edu/statereport/mcas_alt.aspx",
            # ACCESS assessment (ELL students)
            "https://profiles.doe.mass.edu/statereport/access.aspx",
            "https://profiles.doe.mass.edu/statereport/accessreportingelements.aspx",
        ],

        "financials": [
            # Per-pupil expenditure
            "https://www.doe.mass.edu/finance/statistics/",
            # District financial reports
            "https://profiles.doe.mass.edu/statereport/finance.aspx",
        ],

        "teacher_staff": [
            # Educator counts and experience
            "https://profiles.doe.mass.edu/statereport/teacherdata.aspx",
            # Educator licensure
            "https://profiles.doe.mass.edu/statereport/teacherlicensure.aspx",
        ],

        "enrollment_attendance": [
            # Enrollment by grade, school, district
            "https://www.doe.mass.edu/infoservices/reports/enroll/",
            "https://profiles.doe.mass.edu/statereport/enrollment.aspx",
            # Suspensions / attendance / truancy
            "https://profiles.doe.mass.edu/statereport/suspensions.aspx",
            "https://profiles.doe.mass.edu/statereport/inschoolsuspensions.aspx",
        ],

        # Legacy keys (kept for backward compatibility) -----------------------
        "test_scores": [
            "https://www.doe.mass.edu/mcas/results.html",
            "https://profiles.doe.mass.edu/statereport/mcas.aspx",
            "https://profiles.doe.mass.edu/statereport/sat.aspx",
        ],

        "teacher_records": [
            "https://profiles.doe.mass.edu/statereport/teacherdata.aspx",
            "https://profiles.doe.mass.edu/statereport/teacherlicensure.aspx",
        ],

        "enrollment": [
            "https://www.doe.mass.edu/infoservices/reports/enroll/",
            "https://profiles.doe.mass.edu/statereport/enrollment.aspx",
        ],

        "suspensions": [
            "https://profiles.doe.mass.edu/statereport/suspensions.aspx",
            "https://profiles.doe.mass.edu/statereport/inschoolsuspensions.aspx",
        ],
    },

    # -----------------------------------------------------------------------
    # Alaska
    # -----------------------------------------------------------------------
    "alaska": {
        "assessments": [
            "https://education.alaska.gov/assessments/results",
            "https://education.alaska.gov/assessment-results/Statewide/StatewideResults",
        ],
        "financials": [
            "https://education.alaska.gov/data-center",
        ],
        "teacher_staff": [
            "https://education.alaska.gov/data-center",
        ],
        "enrollment_attendance": [
            "https://education.alaska.gov/data-center",
        ],
    },
}
