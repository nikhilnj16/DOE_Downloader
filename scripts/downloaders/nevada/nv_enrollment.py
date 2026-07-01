"""
scripts/downloaders/nevada/nv_enrollment.py
============================================
Downloader for Nevada public school enrollment data.

Architecture note
-----------------
The Nevada DOE website (doe.nv.gov) is a Next.js Single Page Application.
Its data pages are rendered client-side by JavaScript — plain HTTP requests
receive only an empty shell HTML, not the actual content or file links.

All uploaded files (Excel, PDF, CSV) are stored in and served by the NDE's
Strapi CMS backend hosted on Azure:

    https://webapp-strapi-paas-prod-nde-001.azurewebsites.net

The Strapi /api/upload/files endpoint returns a JSON array listing every
uploaded file with its direct download URL.  We query this single endpoint
once, filter for enrollment-related filenames, and download every match.

This collects ALL available school years automatically.

Enrollment files found in Strapi (as of May 2026)
--------------------------------------------------
Data files (.xlsx):
  - 2015-2016SYStudentCounts.xlsx
  - 2022-2023_enrollment_numbers.xlsx
  - 2023-2024-school-year-validation-day-student-counts.xlsx
  - 2024-2025-school-year-validation-day-student-counts.xlsx
  - suppressed-2025-2026-school-year-enrollment-counts-for-website-11-03-25.xlsx
  - NV_Fall_One_Two_Year_College_Enrollment.xlsx
  - PCFPModel_FY2023Revisedweightedenrollment.xlsx

Reference files (.pdf):
  - Private school enrollment data PDFs (2020-21 through 2024-25)
  - SY2021 IDEA and GATE Enrollment Counts PDF
  - Various enrollment policy/guidance documents
"""

import sys
from pathlib import Path

# Project root on sys.path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader

# Keyword patterns that identify enrollment-related files.
# Matched case-insensitively against the filename.
ENROLLMENT_KEYWORDS = [
    "enroll",
    "student_count",
    "studentcount",
    "student-count",
    "student_counts",
    "fy_student",
    "sy_student",
    "school_year",           # catches "school-year-validation-day-student-counts"
    "validation_day",
    "college_enrollment",
    "private_school_enroll",
    "gate_enrollment",
    "idea_enrollment",
    "enrollment_counts",
    "enrollment_numbers",
    "enrollment_data",
    "enrollment_details",
    "sy_student_counts",
]

# File extensions we consider data files worth downloading
DATA_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".zip"}

# The Strapi CDN base (files whose url starts with "/" are relative to this)
STRAPI_BASE = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"


class NevadaEnrollmentDownloader(BaseDownloader):
    """
    Download all Nevada enrollment data files from the NDE Strapi CMS API.

    Strategy
    --------
    1. GET the Strapi /api/upload/files endpoint (returns JSON list of all
       ~8,700 uploaded files in a single response).
    2. Filter the list to files whose name contains an enrollment keyword
       AND whose extension is a recognised data type.
    3. Download every matching file to data/nevada/raw/enrollment/.

    All school years present in the CMS are downloaded automatically.
    """

    STATE: str = "nevada"
    CATEGORY: str = "enrollment_attendance"
    URLS: list[str] = URLS["nevada"]["enrollment_attendance"]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def download_all(self) -> None:
        """
        Fetch the Strapi file index, filter for enrollment files, download all.
        """
        self.logger.info(
            "Starting Nevada enrollment download via Strapi CMS API."
        )

        total_downloaded = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching file index from: %s", api_url)
            file_records = self._fetch_strapi_index(api_url)

            if not file_records:
                self.logger.warning("No file records returned from: %s", api_url)
                continue

            self.logger.info(
                "Total files in Strapi CMS: %d. Filtering for enrollment data...",
                len(file_records),
            )

            matches = self._filter_enrollment_files(file_records)
            self.logger.info(
                "Found %d enrollment-related file(s) to download.", len(matches)
            )

            for record in matches:
                file_url = self._resolve_url(record.get("url", ""))
                filename = record.get("name", Path(file_url).name)
                dest = self.output_dir / filename

                self.logger.info(
                    "Downloading [%s] %s (%.1f KB)",
                    record.get("ext", "?"),
                    filename,
                    record.get("size", 0),
                )

                success = self.download_file(file_url, dest)
                if success:
                    total_downloaded += 1
                else:
                    total_failed += 1

        self.logger.info(
            "Nevada enrollment download complete. "
            "Files downloaded: %d | Failed: %d",
            total_downloaded,
            total_failed,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_strapi_index(self, api_url: str) -> list[dict]:
        """
        Call the Strapi upload/files endpoint and return the JSON list.

        Parameters
        ----------
        api_url : str
            Full URL of the Strapi /api/upload/files endpoint.

        Returns
        -------
        list[dict]
            List of file record dicts (keys: name, url, ext, size, …).
            Returns empty list on any error.
        """
        try:
            response = self.session.get(api_url, timeout=60)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            # Strapi sometimes wraps in {"data": [...]}
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            self.logger.error("Unexpected Strapi response format: %s", type(data))
            return []
        except Exception as exc:
            self.logger.error("Failed to fetch Strapi index from %s: %s", api_url, exc)
            return []

    def _filter_enrollment_files(self, records: list[dict]) -> list[dict]:
        """
        Return only records whose filename matches enrollment keywords
        and whose extension is a recognised data type.

        Parameters
        ----------
        records : list[dict]
            Full list of Strapi file records.

        Returns
        -------
        list[dict]
            Filtered and deduplicated list, sorted by filename.
        """
        seen_urls: set[str] = set()
        matched: list[dict] = []

        for rec in records:
            name: str = (rec.get("name") or "").lower()
            ext: str = (rec.get("ext") or "").lower()
            url: str = rec.get("url") or ""

            # Skip non-data files (images, SVGs, etc.)
            if ext not in DATA_EXTENSIONS:
                continue

            # Normalise ext — sometimes Strapi includes query params
            clean_ext = ext.split("?")[0]
            if clean_ext not in DATA_EXTENSIONS:
                continue

            # Match against enrollment keywords
            if not any(kw in name for kw in ENROLLMENT_KEYWORDS):
                continue

            # Deduplicate by URL
            if url in seen_urls:
                continue
            seen_urls.add(url)
            matched.append(rec)

        return sorted(matched, key=lambda r: r.get("name", "").lower())

    def _resolve_url(self, url: str) -> str:
        """Prepend the Strapi base domain if the URL is a relative path."""
        if url.startswith("http"):
            return url
        return STRAPI_BASE + url


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    downloader = NevadaEnrollmentDownloader()
    downloader.download_all()
