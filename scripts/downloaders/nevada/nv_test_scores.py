"""
scripts/downloaders/nevada/nv_test_scores.py
=============================================
Downloader for Nevada assessment / test score data.

Architecture note
-----------------
doe.nv.gov is a Next.js SPA — all files are served from the NDE's Strapi CMS:

    https://webapp-strapi-paas-prod-nde-001.azurewebsites.net/api/upload/files

We fetch that endpoint once, filter by assessment/test-score keywords, and
download every matching data file.

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

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader

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

DATA_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".zip"}
STRAPI_BASE = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"


class NevadaTestScoresDownloader(BaseDownloader):
    """Download all Nevada assessment/test score data files from Strapi CMS API."""

    STATE: str = "nevada"
    CATEGORY: str = "test_scores"
    URLS: list[str] = URLS["nevada"]["test_scores"]

    def download_all(self) -> None:
        self.logger.info("Starting Nevada test scores download via Strapi CMS API.")
        total_downloaded = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching file index from: %s", api_url)
            records = self._fetch_strapi_index(api_url)
            if not records:
                self.logger.warning("No file records returned from: %s", api_url)
                continue

            self.logger.info("Total files in Strapi CMS: %d. Filtering for assessment/test score data...", len(records))
            matches = self._filter_files(records)
            self.logger.info("Found %d test-score-related file(s) to download.", len(matches))

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
            "Nevada test scores download complete. Files downloaded: %d | Failed: %d",
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
            if not any(kw in name for kw in TEST_SCORE_KEYWORDS):
                continue
            if url in seen:
                continue
            seen.add(url)
            matched.append(rec)
        return sorted(matched, key=lambda r: r.get("name", "").lower())

    def _resolve_url(self, url: str) -> str:
        return url if url.startswith("http") else STRAPI_BASE + url


if __name__ == "__main__":
    NevadaTestScoresDownloader().download_all()
