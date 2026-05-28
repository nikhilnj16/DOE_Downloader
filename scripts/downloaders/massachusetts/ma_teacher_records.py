"""
scripts/downloaders/massachusetts/ma_teacher_records.py
========================================================
Downloader for Massachusetts educator / teacher records.

Sources
-------
- State report — teacher data (profiles.doe.mass.edu/statereport/teacherdata.aspx)
- State report — teacher licensure (profiles.doe.mass.edu/statereport/teacherlicensure.aspx)

Site-specific notes
-------------------
Both report pages render data as HTML tables with an optional export.
If no direct Excel/CSV link is available, consider using pandas.read_html()
to parse the HTML table directly and save the resulting DataFrame as CSV.
Add that logic inside download_all() as a fallback.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import URLS
from scripts.downloaders.base_downloader import BaseDownloader


class MassachusettsTeacherRecordsDownloader(BaseDownloader):
    """Download Massachusetts teacher and educator records."""

    STATE: str = "massachusetts"
    CATEGORY: str = "teacher_records"
    URLS: list[str] = URLS["massachusetts"]["teacher_records"]

    def download_all(self) -> None:
        """Download each teacher records URL."""
        self.logger.info(
            "Starting Massachusetts teacher records download — %d URL(s) configured.",
            len(self.URLS),
        )

        for url in self.URLS:
            stem = self.safe_filename(url)
            dest = self.output_dir / stem
            self.download_file(url, dest)

        self.logger.info("Massachusetts teacher records download complete.")


if __name__ == "__main__":
    downloader = MassachusettsTeacherRecordsDownloader()
    downloader.download_all()
