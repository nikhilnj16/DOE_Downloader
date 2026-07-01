"""
scripts/downloaders/massachusetts/ma_enrollment.py
===================================================
Downloader for Massachusetts enrollment and attendance/truancy data.

Downloads enrollment by grade and district, plus suspension/truancy reports
from the MA DOE profiles site using ASP.NET form POST export.

Saves to: data/massachusetts/enrollment_attendance/
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import raw_dir, DUPLICATE_DETECTION
from scripts.utils.file_utils import parse_year_range, is_duplicate
from scripts.utils.logger import log_download, setup_logger

logger = setup_logger("downloader.massachusetts.enrollment_attendance")

STATE = "massachusetts"
CATEGORY = "enrollment_attendance"

ENROLLMENT_ENDPOINTS = [
    # Enrollment by grade
    ("https://profiles.doe.mass.edu/statereport/enrollmentbygrade.aspx", "enrollmentbygrade"),
    # Student Safety and Discipline Report (Suspensions / Truancy / Discipline)
    ("https://profiles.doe.mass.edu/statereport/ssdr.aspx", "ssdr"),
    # Attendance / chronic absenteeism
    ("https://profiles.doe.mass.edu/statereport/attendance.aspx", "attendance"),
    # Dropout rates
    ("https://profiles.doe.mass.edu/statereport/dropout.aspx", "dropout"),
]


def _post_export(session, url: str, dest_dir: Path, label: str) -> list[Path]:
    """
    POST to an ASP.NET WebForms page to trigger an Excel export.

    Parameters
    ----------
    session  : requests.Session
    url      : str   Full URL of the statereport page
    dest_dir : Path  Directory to save downloaded file into
    label    : str   Short label for logging

    Returns
    -------
    list[Path]  Successfully downloaded files.
    """
    from bs4 import BeautifulSoup

    downloaded: list[Path] = []
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        resp = session.get(url, timeout=60)
        if resp.status_code != 200:
            logger.error("[%s] Failed to load page: HTTP %d", label, resp.status_code)
            log_download(
                state=STATE, category=CATEGORY, url=url, filename="",
                status="failed", filesize_kb=0.0,
                notes=f"HTTP {resp.status_code} on GET",
            )
            return downloaded

        soup = BeautifulSoup(resp.text, "html.parser")
        vs = soup.find("input", {"id": "__VIEWSTATE"})
        vsg = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})
        ev = soup.find("input", {"id": "__EVENTVALIDATION"})

        if not vs:
            logger.warning("[%s] No ASP.NET VIEWSTATE at %s — skipping.", label, url)
            return downloaded

        data = {
            "__VIEWSTATE": vs["value"],
            "__VIEWSTATEGENERATOR": vsg["value"] if vsg else "",
            "__EVENTVALIDATION": ev["value"] if ev else "",
            "ctl00$ContentPlaceHolder1$hfExport": "Excel",
        }

        post = session.post(url, data=data, timeout=120)
        ct = post.headers.get("Content-Type", "").lower()
        cd = post.headers.get("Content-Disposition", "").lower()
        is_file = (
            "excel" in ct or "spreadsheet" in ct or "openxmlformats" in ct
            or "attachment" in cd
        )

        if post.status_code == 200 and is_file:
            filename = None
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip().strip('"')
            if not filename:
                ext = ".xlsx" if post.content[:2] == b"PK" else ".xls"
                filename = f"{label}_export{ext}"

            dest = dest_dir / filename
            yr = parse_year_range(filename)
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()]

            if DUPLICATE_DETECTION and is_duplicate(filename, yr, existing):
                log_download(
                    state=STATE, category=CATEGORY, url=url, filename=filename,
                    status="skipped_duplicate", filesize_kb=0.0,
                    notes="Duplicate detected.",
                )
            else:
                dest.write_bytes(post.content)
                size_kb = len(post.content) / 1024
                yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
                log_download(
                    state=STATE, category=CATEGORY, url=url, filename=filename,
                    status="success", filesize_kb=size_kb,
                    local_path=str(dest), year_range_detected=yr_str,
                )
                downloaded.append(dest)
                logger.info("Saved: %s (%.1f KB)", filename, size_kb)
        else:
            logger.warning(
                "[%s] Export not a file. HTTP %d, CT: %s", label, post.status_code, ct
            )
            log_download(
                state=STATE, category=CATEGORY, url=url, filename="",
                status="failed", filesize_kb=0.0,
                notes=f"HTTP {post.status_code}, Content-Type: {ct}",
            )

    except Exception as exc:
        logger.error("[%s] Error: %s", label, exc)
        log_download(
            state=STATE, category=CATEGORY, url=url, filename="",
            status="failed", filesize_kb=0.0, notes=str(exc),
        )

    return downloaded


class MassachusettsEnrollmentDownloader:
    """
    Download MA DOE enrollment and attendance/truancy data.

    Saves to: data/massachusetts/enrollment_attendance/
    """

    STATE = STATE
    CATEGORY = CATEGORY

    def __init__(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        self.logger = logger
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        })
        retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session = session
        self.output_dir = raw_dir(STATE, CATEGORY)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_all(self) -> None:
        """Download all MA enrollment and attendance data files."""
        self.logger.info("Starting Massachusetts enrollment/attendance download.")
        total = 0
        for url, label in ENROLLMENT_ENDPOINTS:
            files = _post_export(self.session, url, self.output_dir, label)
            total += len(files)
            time.sleep(1.5)
        self.logger.info(
            "Massachusetts enrollment/attendance complete. Files downloaded: %d", total
        )


if __name__ == "__main__":
    MassachusettsEnrollmentDownloader().download_all()
