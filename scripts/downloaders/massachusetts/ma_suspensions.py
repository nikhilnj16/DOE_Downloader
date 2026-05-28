"""
scripts/downloaders/massachusetts/ma_suspensions.py
====================================================
Downloader for Massachusetts student discipline / suspension data.

Sources
-------
- State report — out-of-school suspensions
  (profiles.doe.mass.edu/statereport/suspensions.aspx)
- State report — in-school suspensions
  (profiles.doe.mass.edu/statereport/inschoolsuspensions.aspx)

Site-specific notes
-------------------
Both report pages render aggregated suspension counts as HTML tables by
district and school. Look for an "Export to Excel" button or link in the
page source; if none is present, use requests + BeautifulSoup to parse the
HTML table and save as CSV. The DESE profiles site may require specific
HTTP query parameters (e.g., year, reportType) to select the correct data
year — add these to the URL or as a POST payload in download_all().
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class MassachusettsSuspensionsDownloader(BaseDownloader):
    """Download Massachusetts student discipline and suspension data."""

    STATE: str = "massachusetts"
    CATEGORY: str = "suspensions"
    URLS: list[str] = URLS["massachusetts"]["suspensions"]

    def download_all(self) -> None:
        """Download each discipline data URL."""
        self.logger.info(
            "Starting Massachusetts suspensions download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Massachusetts suspensions download complete.")


if __name__ == "__main__":
    downloader = MassachusettsSuspensionsDownloader()
    downloader.download_all()
