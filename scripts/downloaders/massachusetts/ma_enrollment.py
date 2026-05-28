"""
scripts/downloaders/massachusetts/ma_enrollment.py
===================================================
Downloader for Massachusetts enrollment data.

Sources
-------
- DESE enrollment reports (doe.mass.edu/infoservices/reports/enroll/)
- State report — enrollment (profiles.doe.mass.edu/statereport/enrollment.aspx)

Site-specific notes
-------------------
The enrollment reports page hosts Excel workbooks for each academic year
going back to the 1990s. The state-report page generates HTML that may
contain an "Export" link. Scrape the listing page for all .xlsx/.csv hrefs
using BeautifulSoup and download each one individually.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class MassachusettsEnrollmentDownloader(BaseDownloader):
    """Download Massachusetts student enrollment data."""

    STATE: str = "massachusetts"
    CATEGORY: str = "enrollment"
    URLS: list[str] = URLS["massachusetts"]["enrollment"]

    def download_all(self) -> None:
        """Download each enrollment data URL."""
        self.logger.info(
            "Starting Massachusetts enrollment download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Massachusetts enrollment download complete.")


if __name__ == "__main__":
    downloader = MassachusettsEnrollmentDownloader()
    downloader.download_all()
