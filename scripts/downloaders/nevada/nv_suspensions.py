"""
scripts/downloaders/nevada/nv_suspensions.py
=============================================
Downloader for Nevada school discipline / suspension data.

Architecture note
-----------------
doe.nv.gov is a Next.js SPA — all files are served from the NDE's Strapi CMS:

    https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files

We fetch that endpoint once (returns ~8,700 file records as JSON), filter by
discipline/suspension keywords, and download every matching data file.

Discipline files found in Strapi (as of May 2026)
--------------------------------------------------
Data files:
  - DisciplineData_08.28.2023.xlsx             (2.7 MB — full statewide data)
  - Nevada_Report_Card_19-20_SY_Discipline_Reporting_Template.xlsx
  - NV_Discipline_Data.pdf

Reference / guidance PDFs:
  - 10DisciplineChangesDataStrategies11.1.23.pdf
  - 23-04--UpdatesToDisciplineLawsDataReportingRequirementsAndRestorativeJustice.pdf
  - 9-information-and-discussion-regarding-discipline-data.pdf
  - NV_SchoolBehavioralHealthFactsheet.pdf
  - Workshop_Packet_StudentDiscipline.pdf
  - guidance-memo-23-04-...restorative-justice.pdf
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader

SUSPENSION_KEYWORDS = [
    "discipline",
    "disciplin",
    "suspension",
    "suspend",
    "expulsion",
    "expuls",
    "behavior",
    "behavioural",
    "restorative",
    "behavioral_health",
    "school_based_behavioral",
    "student_discipline",
]

DATA_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".zip"}
STRAPI_BASE = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"


class NevadaSuspensionsDownloader(BaseDownloader):
    """Download all Nevada discipline/suspension data files from Strapi CMS API."""

    STATE: str = "nevada"
    CATEGORY: str = "suspensions"
    URLS: list[str] = URLS["nevada"]["suspensions"]

    def download_all(self) -> None:
        self.logger.info("Starting Nevada suspensions/discipline download via Strapi CMS API.")
        total_downloaded = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching file index from: %s", api_url)
            records = self._fetch_strapi_index(api_url)
            if not records:
                self.logger.warning("No file records returned from: %s", api_url)
                continue

            self.logger.info("Total files in Strapi CMS: %d. Filtering for discipline data...", len(records))
            matches = self._filter_files(records)
            self.logger.info("Found %d discipline-related file(s) to download.", len(matches))

            for rec in matches:
                file_url = self._resolve_url(rec.get("url", ""))
                filename = rec.get("name", Path(file_url).name)
                dest = self.output_dir / filename
                self.logger.info("Downloading [%s] %s (%.1f KB)", rec.get("ext", "?"), filename, rec.get("size", 0))
                if self.download_file(file_url, dest):
                    total_downloaded += 1
                else:
                    total_failed += 1

        self.logger.info(
            "Nevada suspensions download complete. Files downloaded: %d | Failed: %d",
            total_downloaded, total_failed,
        )

    def _fetch_strapi_index(self, api_url: str) -> list[dict]:
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

    def _filter_files(self, records: list[dict]) -> list[dict]:
        seen: set[str] = set()
        matched: list[dict] = []
        for rec in records:
            name = (rec.get("name") or "").lower()
            ext = (rec.get("ext") or "").lower().split("?")[0]
            url = rec.get("url") or ""
            if ext not in DATA_EXTENSIONS:
                continue
            if not any(kw in name for kw in SUSPENSION_KEYWORDS):
                continue
            if url in seen:
                continue
            seen.add(url)
            matched.append(rec)
        return sorted(matched, key=lambda r: r.get("name", "").lower())

    def _resolve_url(self, url: str) -> str:
        return url if url.startswith("http") else STRAPI_BASE + url


if __name__ == "__main__":
    NevadaSuspensionsDownloader().download_all()
