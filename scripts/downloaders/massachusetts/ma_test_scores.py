"""
scripts/downloaders/massachusetts/ma_test_scores.py
====================================================
Downloader for Massachusetts MCAS assessment data — all demographic subgroups.

Covers:
  - Overall MCAS results (all students)
  - By Race/Ethnicity
  - By Gender
  - By IEP/504 (Students with Disabilities + Alternate Assessment + Special Ed)
  - By ELL (English Language Learners + ACCESS assessment)

Architecture note
-----------------
The MA DOE profiles site (profiles.doe.mass.edu/statereport/mcas.aspx) is an
ASP.NET WebForms page. Selecting a subgroup, year, grade, and POSTing the page
with the hidden field ctl00$ContentPlaceHolder1$hfExport set to 'Excel' triggers
an Excel file download.

This requests-based implementation queries all required combinations for years 
2017-2025 and grades AL (ALL), 10 (Grade 10), and HS (HS SCI) without requiring 
Playwright, making it robust, fast, and light.
"""

import logging
import sys
import time
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import raw_dir, DUPLICATE_DETECTION
from scripts.utils.file_utils import parse_year_range, is_duplicate
from scripts.utils.logger import log_download, setup_logger

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = setup_logger("downloader.massachusetts.assessments")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STATE = "massachusetts"
CATEGORY = "assessments"

MCAS_URL = "https://profiles.doe.mass.edu/statereport/mcas.aspx"
MCAS_ALT_URL = "https://profiles.doe.mass.edu/statereport/mcas_alt.aspx"
SPECIAL_ED_URL = "https://profiles.doe.mass.edu/statereport/special_education.aspx"
ACCESS_URL = "https://profiles.doe.mass.edu/statereport/access.aspx"
ACCESS_ELEMENTS_URL = "https://profiles.doe.mass.edu/statereport/accessreportingelements.aspx"

# Grade parameters to cover all grade levels
GRADES = ["AL", "10", "HS"]

# Years to download
YEARS = ["2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017"]

# Subgroup definitions
SUBGROUPS = {
    "overall": {
        "100": "all_students"
    },
    "by_race": {
        "501": "black",
        "502": "american_indian",
        "503": "asian",
        "504": "hispanic",
        "505": "multirace",
        "506": "pacific_islander",
        "507": "white"
    },
    "by_gender": {
        "601": "male",
        "602": "female"
    },
    "by_iep_504": {
        "301": "students_with_disabilities"
    },
    "by_ell": {
        "401": "english_learners"
    }
}


class MassachusettsAssessmentsDownloader:
    """
    Download Massachusetts assessment data (MCAS & ACCESS) via HTTP POST requests.
    """
    STATE = STATE
    CATEGORY = CATEGORY

    def __init__(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        })
        retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.logger = logger

    def download_all(self) -> None:
        """Run all assessment downloads."""
        self.download_all_assessments()

    def download_overall(self) -> list[Path]:
        dest_dir = raw_dir(STATE, CATEGORY, "overall")
        dest_dir.mkdir(parents=True, exist_ok=True)
        return self._download_mcas_combinations(dest_dir, SUBGROUPS["overall"], "overall")

    def download_by_race(self) -> list[Path]:
        dest_dir = raw_dir(STATE, CATEGORY, "by_race")
        dest_dir.mkdir(parents=True, exist_ok=True)
        return self._download_mcas_combinations(dest_dir, SUBGROUPS["by_race"], "by_race")

    def download_by_gender(self) -> list[Path]:
        dest_dir = raw_dir(STATE, CATEGORY, "by_gender")
        dest_dir.mkdir(parents=True, exist_ok=True)
        return self._download_mcas_combinations(dest_dir, SUBGROUPS["by_gender"], "by_gender")

    def download_by_iep_504(self) -> list[Path]:
        dest_dir = raw_dir(STATE, CATEGORY, "by_iep_504")
        dest_dir.mkdir(parents=True, exist_ok=True)
        downloaded = self._download_mcas_combinations(dest_dir, SUBGROUPS["by_iep_504"], "by_iep_504")
        downloaded.extend(self._download_direct_reports(MCAS_ALT_URL, dest_dir, "mcas_alt", "by_iep_504"))
        downloaded.extend(self._download_direct_reports(SPECIAL_ED_URL, dest_dir, "special_ed", "by_iep_504"))
        return downloaded

    def download_by_iep(self) -> list[Path]:
        return self.download_by_iep_504()

    def download_by_ell(self) -> list[Path]:
        dest_dir = raw_dir(STATE, CATEGORY, "by_ell")
        dest_dir.mkdir(parents=True, exist_ok=True)
        downloaded = self._download_mcas_combinations(dest_dir, SUBGROUPS["by_ell"], "by_ell")
        downloaded.extend(self._download_direct_reports(ACCESS_URL, dest_dir, "access", "by_ell"))
        downloaded.extend(self._download_direct_reports(ACCESS_ELEMENTS_URL, dest_dir, "access_elements", "by_ell"))
        return downloaded

    def download_all_assessments(self) -> dict[str, list[Path]]:
        """
        Download MA assessments across all subcategories.
        """
        self.logger.info("=== Massachusetts Assessments: starting full download ===")
        results = {
            "overall": self.download_overall(),
            "by_race": self.download_by_race(),
            "by_gender": self.download_by_gender(),
            "by_iep_504": self.download_by_iep_504(),
            "by_ell": self.download_by_ell()
        }

        total = sum(len(v) for v in results.values())
        self.logger.info(
            "=== Massachusetts Assessments complete: %d files downloaded ===", total
        )
        return results

    def _download_mcas_combinations(self, dest_dir: Path, subgroups: dict, subcategory: str) -> list[Path]:
        """
        Download combinations of year, grade, and subgroup for mcas.aspx
        """
        downloaded = []
        
        # Initial GET to retrieve ASP.NET validation inputs
        try:
            resp = self.session.get(MCAS_URL, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            self.logger.error("Failed to load MCAS initial page: %s", e)
            return downloaded

        soup = BeautifulSoup(resp.text, 'html.parser')
        try:
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
            viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']
            eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']
        except TypeError:
            self.logger.error("Could not find ASP.NET hidden fields on MCAS page.")
            return downloaded

        base_payload = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstategen,
            '__EVENTVALIDATION': eventvalidation,
            'ctl00$ContentPlaceHolder1$hfExport': 'Excel',
            'ctl00$ContentPlaceHolder1$ddReportType': 'DISTRICT'
        }

        for year in YEARS:
            for grade in GRADES:
                for sg_val, sg_name in subgroups.items():
                    filename = f"mcas_{year}_{grade}_{sg_name}.xlsx"
                    dest = dest_dir / filename
                    
                    # Duplicate check
                    existing = [f.name for f in dest_dir.iterdir() if f.is_file()] if dest_dir.exists() else []
                    yr = parse_year_range(filename)
                    if DUPLICATE_DETECTION and is_duplicate(filename, yr, existing):
                        log_download(
                            state=STATE, category=CATEGORY, url=MCAS_URL, filename=filename,
                            status="skipped_duplicate", filesize_kb=0.0, subcategory=subcategory,
                            notes="Duplicate year range already covered."
                        )
                        continue

                    # POST payload for this specific combination
                    payload = base_payload.copy()
                    payload.update({
                        'ctl00$ContentPlaceHolder1$ddYear': year,
                        'ctl00$ContentPlaceHolder1$ddGrade': grade,
                        'ctl00$ContentPlaceHolder1$ddSubGroup': sg_val
                    })

                    try:
                        self.logger.debug("Downloading: %s", filename)
                        post_resp = self.session.post(MCAS_URL, data=payload, timeout=60)
                        
                        ct = post_resp.headers.get("Content-Type", "").lower()
                        is_excel = "excel" in ct or "spreadsheet" in ct or "openxmlformats" in ct
                        is_attachment = "attachment" in post_resp.headers.get("Content-Disposition", "").lower()
                        
                        if post_resp.status_code == 200 and (is_excel or is_attachment):
                            # Resolve final filename extension
                            ext = ".xlsx"
                            if len(post_resp.content) > 0 and post_resp.content[:2] == b"PK":
                                ext = ".xlsx"
                            elif len(post_resp.content) > 0 and post_resp.content[:4] == b"\xd0\xcf\x11\xe0":
                                ext = ".xls"
                            
                            if ext == ".xls":
                                filename = filename[:-5] + ext
                                dest = dest_dir / filename

                            dest.write_bytes(post_resp.content)
                            size_kb = len(post_resp.content) / 1024
                            yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
                            
                            log_download(
                                state=STATE, category=CATEGORY, url=MCAS_URL, filename=filename,
                                status="success", filesize_kb=size_kb, subcategory=subcategory,
                                local_path=str(dest), year_range_detected=yr_str
                            )
                            downloaded.append(dest)
                            self.logger.info("Saved: %s (%.1f KB)", filename, size_kb)
                        else:
                            self.logger.warning("Failed combo: %s (Status: %d, Content-Type: %s)", filename, post_resp.status_code, ct)
                    except Exception as exc:
                        self.logger.error("Error downloading %s: %s", filename, exc)
                    
                    time.sleep(1) # Be friendly to the server

        return downloaded

    def _download_direct_reports(self, url: str, dest_dir: Path, prefix: str, subcategory: str) -> list[Path]:
        """
        Download reports from statereport pages that only have Year and ReportType dropdowns.
        """
        downloaded = []
        
        try:
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            self.logger.error("Failed to load page %s: %s", url, e)
            return downloaded

        soup = BeautifulSoup(resp.text, 'html.parser')
        try:
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
            viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']
            eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']
        except TypeError:
            self.logger.error("Could not find ASP.NET hidden fields on page %s", url)
            return downloaded

        base_payload = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstategen,
            '__EVENTVALIDATION': eventvalidation,
            'ctl00$ContentPlaceHolder1$hfExport': 'Excel'
        }

        # Check if ReportType dropdown exists on the page
        has_report_type = soup.find('select', {'name': 'ctl00$ContentPlaceHolder1$ddReportType'}) is not None
        if has_report_type:
            base_payload['ctl00$ContentPlaceHolder1$ddReportType'] = 'DISTRICT'

        for year in YEARS:
            filename = f"{prefix}_{year}.xlsx"
            dest = dest_dir / filename
            
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()] if dest_dir.exists() else []
            yr = parse_year_range(filename)
            if DUPLICATE_DETECTION and is_duplicate(filename, yr, existing):
                log_download(
                    state=STATE, category=CATEGORY, url=url, filename=filename,
                    status="skipped_duplicate", filesize_kb=0.0, subcategory=subcategory,
                    notes="Duplicate year range already covered."
                )
                continue

            payload = base_payload.copy()
            payload['ctl00$ContentPlaceHolder1$ddYear'] = year

            try:
                post_resp = self.session.post(url, data=payload, timeout=60)
                ct = post_resp.headers.get("Content-Type", "").lower()
                is_excel = "excel" in ct or "spreadsheet" in ct or "openxmlformats" in ct
                is_attachment = "attachment" in post_resp.headers.get("Content-Disposition", "").lower()

                if post_resp.status_code == 200 and (is_excel or is_attachment):
                    ext = ".xlsx"
                    if len(post_resp.content) > 0 and post_resp.content[:2] == b"PK":
                        ext = ".xlsx"
                    elif len(post_resp.content) > 0 and post_resp.content[:4] == b"\xd0\xcf\x11\xe0":
                        ext = ".xls"
                    
                    if ext == ".xls":
                        filename = filename[:-5] + ext
                        dest = dest_dir / filename

                    dest.write_bytes(post_resp.content)
                    size_kb = len(post_resp.content) / 1024
                    yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
                    
                    log_download(
                        state=STATE, category=CATEGORY, url=url, filename=filename,
                        status="success", filesize_kb=size_kb, subcategory=subcategory,
                        local_path=str(dest), year_range_detected=yr_str
                    )
                    downloaded.append(dest)
                    self.logger.info("Saved: %s (%.1f KB)", filename, size_kb)
            except Exception as exc:
                self.logger.error("Error downloading %s from %s: %s", filename, url, exc)
            
            time.sleep(1)

        return downloaded


if __name__ == "__main__":
    MassachusettsAssessmentsDownloader().download_all()
