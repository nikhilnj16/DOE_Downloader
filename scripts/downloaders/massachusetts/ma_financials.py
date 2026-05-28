"""
scripts/downloaders/massachusetts/ma_financials.py
===================================================
Downloader for Massachusetts education financial data.

Sources
-------
- DESE finance statistics page (doe.mass.edu/finance/statistics/)
- State report — finance (profiles.doe.mass.edu/statereport/finance.aspx)

Site-specific notes
-------------------
The DESE finance statistics page hosts annual per-pupil expenditure Excel
workbooks going back several decades. The state report page generates
HTML tables; look for an "Export to Excel" or CSV link in the page source.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class MassachusettsFinancialsDownloader(BaseDownloader):
    """Download Massachusetts education financial data."""

    STATE: str = "massachusetts"
    CATEGORY: str = "financials"
    URLS: list[str] = URLS["massachusetts"]["financials"]

    def download_all(self) -> None:
        """Download each financial data URL."""
        self.logger.info(
            "Starting Massachusetts financials download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Massachusetts financials download complete.")


if __name__ == "__main__":
    downloader = MassachusettsFinancialsDownloader()
    downloader.download_all()
