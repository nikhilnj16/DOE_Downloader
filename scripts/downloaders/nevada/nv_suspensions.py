"""
scripts/downloaders/nevada/nv_suspensions.py
=============================================
Downloader for Nevada student discipline / suspension data.

Sources
-------
- NDE Statewide Discipline page
- Nevada Report Card download portal

Site-specific notes
-------------------
Discipline data covers in-school suspensions (ISS), out-of-school suspensions
(OSS), and expulsions broken down by school, district, infraction type, and
student subgroup. Files are typically Excel (.xlsx) workbooks. If the Report
Card portal requires AJAX requests with form payloads, add those request
parameters in download_all() below.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class NevadaSuspensionsDownloader(BaseDownloader):
    """Download Nevada student discipline and suspension data."""

    STATE: str = "nevada"
    CATEGORY: str = "suspensions"
    URLS: list[str] = URLS["nevada"]["suspensions"]

    def download_all(self) -> None:
        """Download each discipline data URL."""
        self.logger.info(
            "Starting Nevada suspensions download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Nevada suspensions download complete.")


if __name__ == "__main__":
    downloader = NevadaSuspensionsDownloader()
    downloader.download_all()
