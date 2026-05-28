"""
scripts/downloaders/nevada/nv_financials.py
============================================
Downloader for Nevada education financial data.

Sources
-------
- NDE Finance Administration landing page (doe.nv.gov/Finance_Administration/)
- Per-Pupil Expenditure reports
- District Financial Reports

Site-specific notes
-------------------
Financial data is published as Excel workbooks (.xlsx) and PDFs on static
listing pages. The download_all() method fetches each configured URL; if
a URL resolves to an HTML page listing multiple files, extend the
_scrape_links() helper to extract direct file URLs via BeautifulSoup.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class NevadaFinancialsDownloader(BaseDownloader):
    """Download Nevada education financial reports."""

    STATE: str = "nevada"
    CATEGORY: str = "financials"
    URLS: list[str] = URLS["nevada"]["financials"]

    def download_all(self) -> None:
        """Download each financial data URL."""
        self.logger.info(
            "Starting Nevada financials download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Nevada financials download complete.")


if __name__ == "__main__":
    downloader = NevadaFinancialsDownloader()
    downloader.download_all()
