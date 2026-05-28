"""
scripts/downloaders/nevada/nv_test_scores.py
=============================================
Downloader for Nevada test score data (ELA, Math, Science, AP, SAT, ACT).

Sources
-------
- Nevada Report Card download portal (nevadareportcard.nv.gov)
- NDE Statewide Data — Test Results page (doe.nv.gov)

Site-specific notes
-------------------
The Nevada Report Card portal uses dynamic AJAX requests to expose download
links. The URLs in config.URLS["nevada"]["test_scores"] point to known direct
download endpoints and the statewide-data listing page. If the portal changes
to a JavaScript-rendered interface, consider swapping the requests-based
approach here for a Playwright/Selenium strategy.
"""

import sys
from pathlib import Path

# Project root on path for standalone execution
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class NevadaTestScoresDownloader(BaseDownloader):
    """
    Download all publicly available Nevada test-score files.

    Inherits download_file(), retry logic, logging, and file-type detection
    from BaseDownloader. Only state/category-specific behaviour lives here.
    """

    STATE: str = "nevada"
    CATEGORY: str = "test_scores"
    URLS: list[str] = URLS["nevada"]["test_scores"]

    def download_all(self) -> None:
        """
        Iterate over every configured URL and download the target file.

        For simple direct-download URLs, calls self.download_file().
        Site-specific logic (e.g., HTML page scraping to find file links)
        should be added in this method.
        """
        self.logger.info(
            "Starting Nevada test scores download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem  # extension appended by download_file
            self.download_file(url, dest)

        self.logger.info("Nevada test scores download complete.")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    downloader = NevadaTestScoresDownloader()
    downloader.download_all()
