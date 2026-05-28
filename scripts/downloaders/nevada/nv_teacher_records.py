"""
scripts/downloaders/nevada/nv_teacher_records.py
=================================================
Downloader for Nevada educator / teacher records.

Sources
-------
- NDE Educator Data page (doe.nv.gov/Stats_Data/Statewide_Data/Educator_Data/)
- NDE Licensing Statistics page (doe.nv.gov/Licensing/Statistics/)

Site-specific notes
-------------------
Educator data files are published as Excel workbooks (.xlsx) covering
licensed educator counts, experience bands, and assignment areas.
The licensing statistics page publishes annual summary PDFs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class NevadaTeacherRecordsDownloader(BaseDownloader):
    """Download Nevada teacher and educator records."""

    STATE: str = "nevada"
    CATEGORY: str = "teacher_records"
    URLS: list[str] = URLS["nevada"]["teacher_records"]

    def download_all(self) -> None:
        """Download each teacher records URL."""
        self.logger.info(
            "Starting Nevada teacher records download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Nevada teacher records download complete.")


if __name__ == "__main__":
    downloader = NevadaTeacherRecordsDownloader()
    downloader.download_all()
