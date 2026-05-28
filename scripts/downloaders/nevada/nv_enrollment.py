"""
scripts/downloaders/nevada/nv_enrollment.py
============================================
Downloader for Nevada enrollment data.

Sources
-------
- NDE Statewide Enrollment page
- Nevada Report Card download portal

Site-specific notes
-------------------
Enrollment data is published as Excel workbooks (.xlsx) broken out by school,
district, grade level, and subgroup. Annual files are typically released in
late autumn for the prior academic year. Pagination or year-selection forms
on the listing page may need to be handled here with BeautifulSoup.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class NevadaEnrollmentDownloader(BaseDownloader):
    """Download Nevada enrollment data files."""

    STATE: str = "nevada"
    CATEGORY: str = "enrollment"
    URLS: list[str] = URLS["nevada"]["enrollment"]

    def download_all(self) -> None:
        """Download each enrollment data URL."""
        self.logger.info(
            "Starting Nevada enrollment download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Nevada enrollment download complete.")


if __name__ == "__main__":
    downloader = NevadaEnrollmentDownloader()
    downloader.download_all()
