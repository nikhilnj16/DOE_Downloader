"""
scripts/downloaders/massachusetts/ma_test_scores.py
====================================================
Downloader for Massachusetts test score data (MCAS, SAT, AP).

Sources
-------
- MCAS results page (doe.mass.edu/mcas/results.html)
- State report — MCAS achievement (profiles.doe.mass.edu/statereport/mcas.aspx)
- SAT participation report (profiles.doe.mass.edu/statereport/sat.aspx)

Site-specific notes
-------------------
The DESE profiles site (profiles.doe.mass.edu/statereport/) renders
data as HTML tables with a hidden form that POST-submits selected
report parameters (year, school type, grade). The GET URLs in config
return HTML pages; link-scraping or form-submission logic may be required
here to obtain the actual downloadable Excel or CSV files.

To extend this downloader for form-based downloads, add a method like:
    def _submit_report_form(self, base_url, params) -> bytes: ...
and call it from download_all() for each desired parameter combination.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class MassachusettsTestScoresDownloader(BaseDownloader):
    """Download all publicly available Massachusetts test-score files."""

    STATE: str = "massachusetts"
    CATEGORY: str = "test_scores"
    URLS: list[str] = URLS["massachusetts"]["test_scores"]

    def download_all(self) -> None:
        """
        Download Massachusetts test score data files.

        For the MCAS results page and state-report pages, this method
        fetches each URL directly. Extend _scrape_download_links() to
        parse HTML and extract direct file links from listing pages.
        """
        self.logger.info(
            "Starting Massachusetts test scores download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Massachusetts test scores download complete.")


if __name__ == "__main__":
    downloader = MassachusettsTestScoresDownloader()
    downloader.download_all()
