"""
scripts/downloaders/nevada/nv_financials.py
============================================
Downloader for Nevada school financial data.

Architecture note
-----------------
doe.nv.gov is a Next.js SPA — all files are served from the NDE's Strapi CMS:

    https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files

We fetch that endpoint once, filter by financial keywords, and download every
matching data file.

Financial files found in Strapi (as of May 2026)
-------------------------------------------------
Data files:
  - NV_ConsolidatedApplicationBudget.xlsx
  - PBSRequestFundsReportExpenditures.xlsx
  - PBSDOEFinalFinancialReportExpenseSummary.xlsx
  - BudgetFormSFP_840-01State-FederalBudgetExpenditureSummary.xlsx
  - PCFPModel_FY2023Revisedweightedenrollment.xlsx (pupil-centered funding)
  - Various grant budget templates and fiscal summary PDFs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader

FINANCIAL_KEYWORDS = [
    "expenditure",
    "expend",
    "per_pupil",
    "perpupil",
    "per-pupil",
    "budget",
    "financial",
    "finance",
    "fiscal",
    "revenue",
    "fund",
    "funding",
    "pcfp",           # Pupil-Centered Funding Plan
    "consolidated_application",
    "state_federal_budget",
    "expense_summary",
    "financial_report",
    "grant_budget",
]

DATA_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".zip"}
STRAPI_BASE = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"


class NevadaFinancialsDownloader(BaseDownloader):
    """Download all Nevada financial data files from Strapi CMS API."""

    STATE: str = "nevada"
    CATEGORY: str = "financials"
    URLS: list[str] = URLS["nevada"]["financials"]

    def download_all(self) -> None:
        self.logger.info("Starting Nevada financials download via Strapi CMS API.")
        total_downloaded = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching file index from: %s", api_url)
            records = self._fetch_strapi_index(api_url)
            if not records:
                self.logger.warning("No file records returned from: %s", api_url)
                continue

            self.logger.info("Total files in Strapi CMS: %d. Filtering for financial data...", len(records))
            matches = self._filter_files(records)
            self.logger.info("Found %d financial file(s) to download.", len(matches))

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
            "Nevada financials download complete. Files downloaded: %d | Failed: %d",
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
            if not any(kw in name for kw in FINANCIAL_KEYWORDS):
                continue
            if url in seen:
                continue
            seen.add(url)
            matched.append(rec)
        return sorted(matched, key=lambda r: r.get("name", "").lower())

    def _resolve_url(self, url: str) -> str:
        return url if url.startswith("http") else STRAPI_BASE + url


if __name__ == "__main__":
    NevadaFinancialsDownloader().download_all()
