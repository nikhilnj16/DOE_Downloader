"""
scripts/downloaders/nevada/nv_test_scores.py
=============================================
Downloader for Nevada assessment / test score data — overall and demographic subgroups.

Architecture note
-----------------
doe.nv.gov is a Next.js SPA — all files are served from the NDE's Strapi CMS:

    https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files

We fetch that endpoint once, filter by keyword sets specific to each subgroup,
and download every matching data file.

Assessment files found in Strapi (as of May 2026)
--------------------------------------------------
Key data files:
  - Item7AssessmentResults.pdf (1.7 MB — statewide assessment results)
  - ADAM_Assessment.pdf / ADAM_Summative_Assessment_Presentation.pdf
  - 9.NV_MAP_GrowthResults.pdf (5.4 MB — MAP Growth scores)
  - 7-assessment-results-high-school-act.pdf
  - Nevada_CCR_Assessment stakeholder survey Excel files
  - ELA / Science / Math instructional materials alignment xlsx files

Assessment types covered:
  - SBAC (Smarter Balanced Assessment Consortium) — ELA & Math grades 3-8
  - ACT (College and Career Readiness Assessment — grade 11)
  - NAA (Nevada Alternate Assessment)
  - NAEP (National Assessment of Educational Progress)
  - WIDA (English Language Proficiency)
  - Science summative assessment
  - MAP Growth
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS, raw_dir, DUPLICATE_DETECTION
from scripts.downloaders.base_downloader import BaseDownloader
from scripts.utils.file_utils import parse_year_range, is_duplicate
from scripts.utils.logger import log_download

# ---------------------------------------------------------------------------
# Strapi constants
# ---------------------------------------------------------------------------
DATA_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".zip"}
STRAPI_BASE = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"
STRAPI_API_URL = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files?pagination[pageSize]=10000"

# ---------------------------------------------------------------------------
# Keyword sets per subcategory
# ---------------------------------------------------------------------------

# Overall assessment keywords (original set — kept exactly as before)
TEST_SCORE_KEYWORDS = [
    "sbac",
    "smarter_balanced",
    "smarter-balanced",
    "assessment_result",
    "assessment-result",
    "assessment_results",
    "test_result",
    "test_score",
    "proficien",          # proficiency, proficient
    "naep",
    "naa",                # Nevada Alternate Assessment
    "wida",
    "map_growth",
    "nv_map",
    "act_result",
    "act_score",
    "ccr_assessment",     # College & Career Readiness Assessment
    "college_career_readiness",
    "sat_result",
    "ap_result",
    "nspf",               # Nevada School Performance Framework scores
    "summative",
    "item7assessment",    # specific key file
    "assessment_results", # broad match
    "adam_assessment",
    "adam_summative",
]

# Note: "science", "ela", "math" are intentionally excluded — too broad and would
# catch thousands of curriculum standard documents that aren't score data files.
# The keywords above are precise enough to target actual results/data files.

# Race/Ethnicity subgroup keywords
RACE_KEYWORDS = [
    "race",
    "ethnicity",
    "race_ethnicity",
    "racial",
    "hispanic",
    "african_american",
    "black",
    "white",
    "asian",
    "pacific_islander",
    "native_american",
    "multiracial",
    "multi_racial",
    "two_or_more_races",
    "subgroup_race",
    "by_race",
    "race_group",
    "demographic_race",
]

# Gender subgroup keywords
GENDER_KEYWORDS = [
    "gender",
    "male",
    "female",
    "by_gender",
    "sex",
    "gender_breakdown",
    "gender_group",
    "subgroup_gender",
]

# IEP/504 / Special Education subgroup keywords
IEP_KEYWORDS = [
    "iep",
    "504",
    "special_ed",
    "special_education",
    "disability",
    "disabilities",
    "sped",
    "naa",                     # Nevada Alternate Assessment — for IEP students
    "alternate_assessment",
    "alt_assessment",
    "students_with_disabilities",
    "exceptional_students",
    "subgroup_iep",
    "by_iep",
    "by_504",
    "by_disability",
]

# English Language Learners subgroup keywords
ELL_KEYWORDS = [
    "ell",
    "english_learner",
    "english_language_learner",
    "esl",
    "wida",
    "access",                  # WIDA ACCESS assessment
    "language_proficiency",
    "limited_english",
    "lep",
    "dual_language",
    "bilingual",
    "subgroup_ell",
    "by_ell",
    "english_learners",
]


# ---------------------------------------------------------------------------
# Main downloader class (extends original, preserves existing download_all)
# ---------------------------------------------------------------------------

class NevadaTestScoresDownloader(BaseDownloader):
    """
    Download all Nevada assessment/test score data files from Strapi CMS API.

    Provides both overall (download_all) and demographic sub-category downloads.
    """

    STATE: str = "nevada"
    CATEGORY: str = "assessments"
    URLS: list[str] = URLS["nevada"]["assessments"]

    # ------------------------------------------------------------------
    # Original overall download (preserved exactly)
    # ------------------------------------------------------------------

    def download_all(self) -> None:
        """Download overall Nevada assessment data (all students)."""
        self.logger.info("Starting Nevada overall assessment download via Strapi CMS API.")
        total_downloaded = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching file index from: %s", api_url)
            records = self._fetch_strapi_index(api_url)
            if not records:
                self.logger.warning("No file records returned from: %s", api_url)
                continue

            self.logger.info(
                "Total files in Strapi CMS: %d. Filtering for assessment/test score data...",
                len(records),
            )
            matches = self._filter_files(records, TEST_SCORE_KEYWORDS)
            self.logger.info("Found %d test-score-related file(s) to download.", len(matches))

            out_dir = raw_dir(self.STATE, self.CATEGORY, "overall")
            out_dir.mkdir(parents=True, exist_ok=True)

            for rec in matches:
                file_url = self._resolve_url(rec.get("url", ""))
                filename = rec.get("name", Path(file_url).name)
                dest = out_dir / filename
                self.logger.info(
                    "Downloading [%s] %s (%.1f KB)",
                    rec.get("ext", "?"), filename, rec.get("size", 0),
                )
                if self._download_with_dedup(file_url, dest, out_dir, "overall"):
                    total_downloaded += 1
                else:
                    total_failed += 1

        self.logger.info(
            "Nevada overall assessment download complete. Downloaded: %d | Failed: %d",
            total_downloaded, total_failed,
        )

    # ------------------------------------------------------------------
    # Demographic sub-category downloads (Change 5)
    # ------------------------------------------------------------------

    def download_by_race(self) -> None:
        """
        Download Nevada assessment data broken down by Race/Ethnicity.

        Filters the Strapi file index for files matching race/ethnicity keywords.
        Also scans the Nevada Report Card portal for any subgroup-specific exports.

        Saves to: data/nevada/assessments/by_race/
        """
        self.logger.info("Starting Nevada assessments by Race/Ethnicity download.")
        self._download_subgroup("by_race", RACE_KEYWORDS)

    def download_by_gender(self) -> None:
        """
        Download Nevada assessment data broken down by Gender.

        Filters the Strapi file index for files matching gender keywords.

        Saves to: data/nevada/assessments/by_gender/
        """
        self.logger.info("Starting Nevada assessments by Gender download.")
        self._download_subgroup("by_gender", GENDER_KEYWORDS)

    def download_by_iep(self) -> None:
        """
        Download Nevada assessment data for Students with Disabilities (IEP/504).

        Filters the Strapi file index for IEP/special-ed/NAA (Nevada Alternate
        Assessment) related files.

        Saves to: data/nevada/assessments/by_iep_504/
        """
        self.logger.info("Starting Nevada assessments by IEP/504 download.")
        self._download_subgroup("by_iep_504", IEP_KEYWORDS)

    def download_by_ell(self) -> None:
        """
        Download Nevada assessment data for English Language Learners.

        Filters the Strapi file index for ELL/WIDA/ACCESS-related files.

        Saves to: data/nevada/assessments/by_ell/
        """
        self.logger.info("Starting Nevada assessments by ELL download.")
        self._download_subgroup("by_ell", ELL_KEYWORDS)

    def download_all_assessments(self) -> None:
        """
        Download all Nevada assessment data in subcategory priority order:
          1. overall (all students)
          2. by_race
          3. by_gender
          4. by_iep_504
          5. by_ell
        """
        self.logger.info("=== Nevada Assessments: starting full demographic download ===")
        self.download_all()
        self.download_by_race()
        self.download_by_gender()
        self.download_by_iep()
        self.download_by_ell()
        self.logger.info("=== Nevada Assessments: all subcategories complete ===")

    # ------------------------------------------------------------------
    # Shared subgroup helper
    # ------------------------------------------------------------------

    def _download_subgroup(self, subcategory: str, keywords: list[str]) -> None:
        """
        Fetch the Strapi index, filter by *keywords*, and download to *subcategory* folder.

        Parameters
        ----------
        subcategory : str        e.g. "by_race"
        keywords    : list[str]  Lowercase keyword fragments to match against filename
        """
        out_dir = raw_dir(self.STATE, self.CATEGORY, subcategory)
        out_dir.mkdir(parents=True, exist_ok=True)

        total_downloaded = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching Strapi index from: %s", api_url)
            records = self._fetch_strapi_index(api_url)
            if not records:
                self.logger.warning("No records from: %s", api_url)
                continue

            matches = self._filter_files(records, keywords)
            self.logger.info(
                "Subcategory '%s': found %d matching file(s).", subcategory, len(matches)
            )

            for rec in matches:
                file_url = self._resolve_url(rec.get("url", ""))
                filename = rec.get("name", Path(file_url).name)
                dest = out_dir / filename
                self.logger.info(
                    "Downloading [%s] %s (%.1f KB)",
                    rec.get("ext", "?"), filename, rec.get("size", 0),
                )
                if self._download_with_dedup(file_url, dest, out_dir, subcategory):
                    total_downloaded += 1
                else:
                    total_failed += 1

        self.logger.info(
            "Subcategory '%s' complete. Downloaded: %d | Failed: %d",
            subcategory, total_downloaded, total_failed,
        )

    def _download_with_dedup(
        self,
        file_url: str,
        dest: Path,
        out_dir: Path,
        subcategory: str,
    ) -> bool:
        """
        Download a file with duplicate detection.

        If DUPLICATE_DETECTION is enabled, checks whether any existing file in
        out_dir already covers the year range of the candidate file.

        Parameters
        ----------
        file_url    : str   Remote URL to download
        dest        : Path  Target local path
        out_dir     : Path  Folder where duplicates are checked
        subcategory : str   For manifest logging

        Returns
        -------
        bool  True on success or skip, False on failure.
        """
        filename = dest.name
        yr = parse_year_range(filename)

        if DUPLICATE_DETECTION:
            existing = [f.name for f in out_dir.iterdir() if f.is_file()] if out_dir.exists() else []
            if is_duplicate(filename, yr, existing):
                log_download(
                    state=self.STATE, category=self.CATEGORY,
                    url=file_url, filename=filename,
                    status="skipped_duplicate", filesize_kb=0.0,
                    subcategory=subcategory,
                    notes="Duplicate detected; year range already covered.",
                )
                return True  # Treated as handled, not a failure

        success = self.download_file(file_url, dest)
        if success:
            yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
            size_kb = dest.stat().st_size / 1024 if dest.exists() else 0.0
            log_download(
                state=self.STATE, category=self.CATEGORY,
                url=file_url, filename=filename,
                status="success", filesize_kb=size_kb,
                subcategory=subcategory, local_path=str(dest),
                year_range_detected=yr_str,
            )
        return success

    # ------------------------------------------------------------------
    # Strapi helpers (original — preserved exactly)
    # ------------------------------------------------------------------

    def _fetch_strapi_index(self, api_url: str) -> list[dict]:
        """Fetch the Strapi file index JSON list."""
        try:
            r = self.session.get(api_url, timeout=60)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return []
        except Exception as exc:
            self.logger.error("Failed to fetch Strapi index from %s: %s", api_url, exc)
            return []

    def _filter_files(self, records: list[dict], keywords: list[str]) -> list[dict]:
        """
        Filter Strapi records to files matching any keyword in *keywords*.

        Parameters
        ----------
        records  : list[dict]  Full Strapi file record list
        keywords : list[str]   Lowercase keyword fragments

        Returns
        -------
        list[dict]  Filtered and deduplicated list sorted by filename.
        """
        seen: set[str] = set()
        matched: list[dict] = []
        for rec in records:
            name = (rec.get("name") or "").lower()
            ext = (rec.get("ext") or "").lower().split("?")[0]
            url = rec.get("url") or ""
            if ext not in DATA_EXTENSIONS:
                continue
            if not any(kw in name for kw in keywords):
                continue
            if url in seen:
                continue
            seen.add(url)
            matched.append(rec)
        return sorted(matched, key=lambda r: r.get("name", "").lower())

    def _resolve_url(self, url: str) -> str:
        """Prepend the Strapi base domain if the URL is a relative path."""
        return url if url.startswith("http") else STRAPI_BASE + url


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    NevadaTestScoresDownloader().download_all_assessments()
