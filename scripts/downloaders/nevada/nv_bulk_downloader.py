"""
scripts/downloaders/nevada/nv_bulk_downloader.py
=================================================
Master downloader that fetches EVERY data file from the Nevada DOE's
Strapi CMS — no keyword filtering, no risk of missing documents.

Why this exists
---------------
The five category-specific downloaders (enrollment, test_scores, etc.) use
keyword matching to assign files to categories. There is always a risk that
a real data file has an unexpected name that doesn't match any keyword.

This script eliminates that risk by downloading the full Strapi file index
and saving every file whose extension is a recognised data format (.xlsx,
.xls, .csv, .pdf, .docx, .pptx, .zip).

The complete download lives in:
    data/nevada/raw/bulk/

Files are saved with their original Strapi filenames. You can then look
through the bulk folder and move files into the appropriate category folders
if needed.

Usage
-----
    python scripts/downloaders/nevada/nv_bulk_downloader.py

What it downloads
-----------------
From the ~8,695 files in Strapi CMS (as of May 2026):
    - .pdf:   7,596 files   (guidance, reports, agendas, data)
    - .xlsx:    244 files   (data spreadsheets)
    - .docx:    128 files   (Word documents)
    - .pptx:     57 files   (presentations)
    - images:   500+ files  → SKIPPED (not useful data)

Expected: ~8,025 files downloaded (all non-image files).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.downloaders.base_downloader import BaseDownloader

# Single Strapi API endpoint — returns ALL uploaded files in one response
STRAPI_API_URL = (
    "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"
    "/api/upload/files?pagination[pageSize]=10000"
)

STRAPI_BASE = "https://webapp-strapi-paas-prod-nde-001.azurewebsites.net"

# File types we want to download (skip images, SVGs, web fonts, etc.)
WANTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".zip", ".txt"}

# File types to explicitly skip
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".ico", ".woff", ".woff2"}


class NevadaBulkDownloader(BaseDownloader):
    """
    Download every data file from the NDE Strapi CMS with no keyword filtering.

    This is the safest approach — zero risk of missing a file due to a
    keyword mismatch.  All files land in data/nevada/raw/bulk/.
    """

    STATE: str = "nevada"
    CATEGORY: str = "bulk"           # saves to data/nevada/raw/bulk/
    URLS: list[str] = [STRAPI_API_URL]

    def download_all(self) -> None:
        self.logger.info("=" * 60)
        self.logger.info("Nevada BULK download — downloading ALL data files from Strapi CMS.")
        self.logger.info("Output directory: %s", self.output_dir)
        self.logger.info("=" * 60)

        total_downloaded = 0
        total_skipped = 0
        total_failed = 0

        for api_url in self.URLS:
            self.logger.info("Fetching full file index from: %s", api_url)
            records = self._fetch_strapi_index(api_url)

            if not records:
                self.logger.error("No records returned — aborting.")
                return

            self.logger.info("Total files in Strapi CMS: %d", len(records))

            # Separate into download vs skip
            to_download = []
            for rec in records:
                ext = (rec.get("ext") or "").lower().split("?")[0]
                if ext in WANTED_EXTENSIONS:
                    to_download.append(rec)
                else:
                    total_skipped += 1

            self.logger.info(
                "Will download: %d files | Skipping (images/SVG/etc.): %d files",
                len(to_download), total_skipped,
            )

            # Download every wanted file
            for i, rec in enumerate(to_download, 1):
                file_url = self._resolve_url(rec.get("url", ""))
                filename = rec.get("name", Path(file_url).name)
                dest = self.output_dir / filename
                ext = rec.get("ext", "?")
                size_kb = rec.get("size", 0)

                # Skip already-downloaded files (resume support)
                if dest.exists():
                    self.logger.debug("Already exists, skipping: %s", filename)
                    total_downloaded += 1
                    continue

                self.logger.info(
                    "[%d/%d] Downloading [%s] %s (%.1f KB)",
                    i, len(to_download), ext, filename, size_kb,
                )

                if self.download_file(file_url, dest):
                    total_downloaded += 1
                else:
                    total_failed += 1

        self.logger.info("=" * 60)
        self.logger.info(
            "Nevada BULK download complete.\n"
            "  Downloaded : %d\n"
            "  Failed     : %d\n"
            "  Skipped    : %d (images/non-data)\n"
            "  Output dir : %s",
            total_downloaded, total_failed, total_skipped, self.output_dir,
        )
        self.logger.info("=" * 60)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_strapi_index(self, api_url: str) -> list[dict]:
        """Fetch the full Strapi file list (all ~8,695 records in one response)."""
        try:
            self.logger.info("Sending request to Strapi API...")
            r = self.session.get(api_url, timeout=90)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            self.logger.error("Unexpected API response format: %s", type(data))
            return []
        except Exception as exc:
            self.logger.error("Failed to fetch Strapi index: %s", exc)
            return []

    def _resolve_url(self, url: str) -> str:
        """Make sure URL is absolute."""
        return url if url.startswith("http") else STRAPI_BASE + url


if __name__ == "__main__":
    downloader = NevadaBulkDownloader()
    downloader.download_all()
