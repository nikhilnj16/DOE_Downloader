"""
scripts/downloaders/ohio/oh_downloader.py
=========================================
Downloader for Ohio Department of Education data.

Covers:
  - School Report Card bulk downloads (Direct Azure Blob listings for years 2006 to 2025)
  - ELA, Math, Science, Social Studies OST tests and demographic breakdowns
  - Financial rankings, pupil expenditures, and fiscal data projects
  - Teacher certifications, salaries, demographics, and pass rates
  - Enrollment counts, absenteeism, graduation, and discipline reports
"""

import sys
import time
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import raw_dir, DUPLICATE_DETECTION
from scripts.utils.file_utils import parse_year_range, is_duplicate
from scripts.utils.logger import log_download, setup_logger

logger = setup_logger("downloader.ohio")

STATE = "ohio"
SAS_TOKEN = "?sv=2020-08-04&ss=b&srt=sco&sp=rlx&se=2031-07-28T05:10:18Z&st=2021-07-27T21:10:18Z&spr=https&sig=nPOvW%2Br2caitHi%2F8WhYwU7xqalHo0dFrudeJq%2B%2Bmyuo%3D"
BASE_STORAGE_URL = "https://eduprdreportcardstorage1.blob.core.windows.net"

# Desktop Headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class OhioDownloader:
    """
    Downloader for Ohio education data.
    """
    STATE = STATE
    bulk_downloaded = False

    def __init__(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.logger = logger

    def download_all(self) -> None:
        """Run all Ohio downloads."""
        self.download_assessments()
        self.download_financials()
        self.download_teacher_staff()
        self.download_enrollment_attendance()

    # ---------------------------------------------------------------------------
    # 1. Assessments
    # ---------------------------------------------------------------------------
    def download_assessments(self) -> None:
        """Download Ohio bulk report card data and crawl assessments topic pages."""
        self.logger.info("=== Starting Ohio Assessments Download ===")
        
        # Download all files from Azure bulk storage containers first
        self._download_bulk_report_cards()

        # Crawl static testing links
        testing_urls = [
            "https://education.ohio.gov/Topics/Testing",
            "https://education.ohio.gov/Topics/Testing/Ohios-State-Test-in-ELA-Math-Science-SocialStudies",
            "https://education.ohio.gov/Topics/Testing/Statistical-Summaries-and-Item-Analysis-Reports",
            "https://education.ohio.gov/Topics/Testing/Ohios-ELPA21",
            "https://education.ohio.gov/Topics/Testing/alt-oelpa",
            "https://education.ohio.gov/Topics/Testing-old/Ohio-s-State-Tests/Ohios-Alternate-Assessment-for-Students-with-Sign",
            "https://education.ohio.gov/Topics/Testing/State-Funded-ACT-Test",
            "https://education.ohio.gov/Topics/Testing/State-Funded-SAT-Test",
            "https://education.ohio.gov/Topics/Testing/Ohio-Graduation-Test-OGT",
            "https://education.ohio.gov/Topics/Special-Education/Special-Education-Data-and-Funding/Enrollment-Testing-and-Discipline-Data-for-Student"
        ]

        dest_dir = raw_dir(STATE, "assessments")
        dest_dir.mkdir(parents=True, exist_ok=True)
        for url in testing_urls:
            self._download_static_or_page_files(url, dest_dir, "assessments")

    def _download_bulk_report_cards(self) -> None:
        """Query Azure Blob Storage REST API to list and download all bulk files."""
        if OhioDownloader.bulk_downloaded:
            return
        OhioDownloader.bulk_downloaded = True
        
        self.logger.info("Listing files in Ohio Report Card Azure containers...")
        for yr in range(2006, 2026):
            container = f"data-download-{yr}"
            list_url = f"{BASE_STORAGE_URL}/{container}{SAS_TOKEN}&restype=container&comp=list"
            
            try:
                resp = self.session.get(list_url, timeout=60)
                if resp.status_code != 200:
                    self.logger.warning("Could not list container %s (HTTP %d)", container, resp.status_code)
                    continue

                root = ET.fromstring(resp.content)
                blobs = root.findall(".//Blob")
                self.logger.info("Container %s: found %d files.", container, len(blobs))
                
                for idx, blob in enumerate(blobs):
                    name_el = blob.find("Name")
                    if name_el is None or not name_el.text:
                        continue
                    blob_name = name_el.text.strip()
                    
                    # Classify download destination directory based on keyword rules
                    blob_name_lower = blob_name.lower()
                    assess_keys = ['ost', 'achievement', 'test', 'elpa', 'act', 'sat', 'alternate', 'testing', 'proficiency', 'value_added', 'va_org', 'va_dist', 'va_cs', 'dorp_va', 'gap_closing', 'performance_index', 'prepared_for_success', 'reading_guarantee', 'early_lit', 'amo', 'gifted']
                    fin_keys = ['expenditure', 'finance', 'salary', 'funds', 'revenue', 'financial', 'spend', 'pupil', 'rankings', 'efm', 'expanded_list']
                    staff_keys = ['staff', 'teacher', 'principal', 'educator']

                    if any(k in blob_name_lower for k in assess_keys):
                        cat = "assessments"
                    elif any(k in blob_name_lower for k in fin_keys):
                        cat = "financials"
                    elif any(k in blob_name_lower for k in staff_keys):
                        cat = "teacher_staff"
                    else:
                        cat = "enrollment_attendance"
                    
                    dest_dir = raw_dir(STATE, cat)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Clean space formatting for saving locally
                    clean_filename = blob_name.replace(' ', '_').replace('$', '')
                    dest = dest_dir / clean_filename
                    
                    existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
                    if clean_filename in existing:
                        continue
                    yr_range = parse_year_range(clean_filename)
                    if DUPLICATE_DETECTION and is_duplicate(clean_filename, yr_range, existing):
                        continue

                    # Download with SAS token authentication
                    blob_encoded = quote(blob_name)
                    download_url = f"{BASE_STORAGE_URL}/{container}/{blob_encoded}{SAS_TOKEN}"
                    
                    try:
                        self.logger.info("[%s] Downloading bulk blob: %s", container, blob_name)
                        f_resp = self.session.get(download_url, timeout=120)
                        if f_resp.status_code == 200:
                            dest.write_bytes(f_resp.content)
                            size_kb = len(f_resp.content) / 1024
                            yr_str = f"{yr_range[0]}-{yr_range[1]}" if yr_range else f"{yr-1}-{yr}"
                            
                            log_download(
                                state=STATE, category=cat, url=download_url.split('?')[0], filename=clean_filename,
                                status="success", filesize_kb=size_kb, subcategory="",
                                local_path=str(dest), year_range_detected=yr_str
                            )
                            self.logger.info("Saved bulk blob: %s (%.1f KB)", clean_filename, size_kb)
                        else:
                            self.logger.warning("Failed download for blob: %s (HTTP %d)", blob_name, f_resp.status_code)
                    except Exception as download_err:
                        self.logger.error("Error downloading blob %s: %s", blob_name, download_err)
                    
                    time.sleep(0.2)

            except Exception as e:
                self.logger.error("Failed to process Azure container %s: %s", container, e)

    # ---------------------------------------------------------------------------
    # 2. Financials
    # ---------------------------------------------------------------------------
    def download_financials(self) -> None:
        """Download financials files."""
        self.logger.info("=== Starting Ohio Financials Download ===")
        dest_dir = raw_dir(STATE, "financials")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        finance_urls = [
            "https://education.ohio.gov/Topics/Finance-and-Funding/Finance-Data-and-Information",
            "https://education.ohio.gov/Topics/Finance-and-Funding/Finance-Data-and-Information/Expenditure-Per-Pupil-Rankings",
            "https://education.ohio.gov/Topics/Finance-and-Funding/Finance-Data-and-Information/Education-Fiscal-Data-Project",
            "https://education.ohio.gov/Topics/Finance-and-Funding/Finance-Data-and-Information/Tuition-Letters-and-Rates",
            "https://education.ohio.gov/Topics/Finance-and-Funding/Finance-Data-and-Information/Set-asides"
        ]

        for url in finance_urls:
            self._download_static_or_page_files(url, dest_dir, "financials")
            
        # Log public transparency checkbook as a source
        log_download(
            state=STATE, category="financials", url="https://checkbook.ohio.gov/", filename="ohio_checkbook_portal.txt",
            status="skipped", filesize_kb=0, subcategory="",
            local_path="", year_range_detected="", notes="Public transparency dashboard portal; files queried via Azure bulk download instead."
        )

    # ---------------------------------------------------------------------------
    # 3. Teacher / Staff Records
    # ---------------------------------------------------------------------------
    def download_teacher_staff(self) -> None:
        """Download raw credentials lists and certification reports."""
        self.logger.info("=== Starting Ohio Teacher/Staff Download ===")
        dest_dir = raw_dir(STATE, "teacher_staff")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Direct large credential files
        credentials_urls = [
            "http://public.education.ohio.gov/misc/credentials.txt",
            "http://public.education.ohio.gov/misc/issued_credentials.txt"
        ]
        for url in credentials_urls:
            self._download_static_file(url, dest_dir, "teacher_staff")

        # Page crawls
        teacher_urls = [
            "https://education.ohio.gov/Topics/Data/Frequently-Requested-Data/Staff-Data",
            "https://data.ohio.gov/wps/portal/gov/data/view/ode-education-staff-demographics-and-jobs-report-public",
            "https://data.ohio.gov/wps/portal/gov/data/view/education-employee-positions-and-demographics---secured",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Staff-Data/2014-SY-Ohio-Teacher-and-Principal-Evaluations.xlsx.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Staff-Data/2023-Equitable-Access-to-Excellent-Educators-Longitudinal-Ohio.xlsx.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Staff-Data/20171005_RESA_Pass_Rates_by_Org_Type_.pdf.aspx",
            "https://reports.education.ohio.gov/"
        ]

        for url in teacher_urls:
            self._download_static_or_page_files(url, dest_dir, "teacher_staff")

    # ---------------------------------------------------------------------------
    # 4. Enrollment & Attendance
    # ---------------------------------------------------------------------------
    def download_enrollment_attendance(self) -> None:
        """Download headcount spreadsheets and historical bulk enrollment files."""
        self.logger.info("=== Starting Ohio Enrollment/Attendance Download ===")
        dest_dir = raw_dir(STATE, "enrollment_attendance")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Direct static Excel file links
        direct_files = [
            # Fall Headcounts
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy26.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy25.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy24.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy23.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy22.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy21.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy20.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy19.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy18.xls.aspx?lang=en-US",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy17.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy16.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy15.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/Fall-Enrollment-Headcount-October-2013-Public-Districts-and-Buildings.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_hdcnt_fy13.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/web_oct_hdcnt_fy12.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/web_oct_hdcnt_fy11.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/web__FY10_hdcnt.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/oct_08_fy09_hdcnt.xls.aspx",
            # Historical Bulk Files
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/web_district_2000-2008.XLS.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/web_district_1990-1999.XLS.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/web_district_1980-1989.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/2000-2008-Building.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/1993-1999-Building.xls.aspx",
            "https://education.ohio.gov/getattachment/Topics/Data/Frequently-Requested-Data/Enrollment-Data/2014-2019-NonPublic.xlsx.aspx?lang=en-US"
        ]

        for url in direct_files:
            self._download_static_file(url, dest_dir, "enrollment_attendance")

        # Page crawls
        crawled_urls = [
            "https://education.ohio.gov/Topics/Chronic-Absenteeism",
            "https://education.ohio.gov/Topics/Data/Frequently-Requested-Data/Enrollment-Data"
        ]
        for url in crawled_urls:
            self._download_static_or_page_files(url, dest_dir, "enrollment_attendance")

    # ---------------------------------------------------------------------------
    # Crawling Helpers
    # ---------------------------------------------------------------------------
    def _download_static_or_page_files(self, url: str, dest_dir: Path, category: str) -> None:
        """Download file directly if static link; otherwise, crawl the page for links/select options."""
        clean_url = url.replace(" ", "%20")
        
        # Static check
        if any(clean_url.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
            self._download_static_file(clean_url, dest_dir, category)
            return

        self.logger.info("Crawling Ohio page: %s", clean_url)
        try:
            resp = self.session.get(clean_url, timeout=60)
            if resp.status_code != 200:
                self.logger.warning("Failed to fetch Ohio page %s (HTTP %d)", clean_url, resp.status_code)
                return
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            links_found = 0
            
            # 1. Parse standard a links
            for a in soup.find_all('a'):
                href = a.get('href') or ''
                abs_url = urljoin(clean_url, href)
                if any(abs_url.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
                    self._download_static_file(abs_url, dest_dir, category)
                    links_found += 1

            # 2. Parse dropdown select options
            for select in soup.find_all('select'):
                for opt in select.find_all('option'):
                    val = opt.get('value') or ''
                    if not val or val == '#' or val == 'default':
                        continue
                    abs_url = urljoin(clean_url, val)
                    if any(abs_url.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
                        self._download_static_file(abs_url, dest_dir, category)
                        links_found += 1

            self.logger.info("Completed crawl for %s. Found %d documents.", clean_url, links_found)
        except Exception as e:
            self.logger.error("Crawl error on Ohio page %s: %s", clean_url, e)

    def _download_static_file(self, full_url: str, dest_dir: Path, category: str) -> None:
        """Download a single static document directly and save/log it."""
        try:
            # Clean SAS token query params for filename determination
            parsed_url = urllib.parse.urlparse(full_url)
            filename = Path(urllib.parse.unquote(parsed_url.path)).name
            if not filename or '.' not in filename:
                return

            # Clean spaces/special characters
            clean_filename = filename.replace('$', '').replace(' ', '_')
            
            # Remove redundant attachment extensions (e.g. .aspx)
            if clean_filename.lower().endswith('.aspx'):
                # Check if it has a secondary extension before it
                base_name = clean_filename[:-5]
                if any(base_name.lower().endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
                    clean_filename = base_name

            dest = dest_dir / clean_filename
            
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
            if clean_filename in existing:
                return

            yr = parse_year_range(clean_filename)
            if DUPLICATE_DETECTION and is_duplicate(clean_filename, yr, existing):
                return

            self.logger.info("Downloading Ohio file: %s", clean_filename)
            f_resp = self.session.get(full_url, timeout=120)
            if f_resp.status_code == 200:
                dest.write_bytes(f_resp.content)
                size_kb = len(f_resp.content) / 1024
                yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
                
                log_download(
                    state=STATE, category=category, url=full_url, filename=clean_filename,
                    status="success", filesize_kb=size_kb, subcategory="",
                    local_path=str(dest), year_range_detected=yr_str
                )
                self.logger.info("Saved Ohio static file: %s (%.1f KB)", clean_filename, size_kb)
            else:
                self.logger.warning("Failed download for Ohio static file: %s (HTTP %d)", clean_filename, f_resp.status_code)
            time.sleep(0.3)
        except Exception as ex:
            self.logger.error("Error downloading file %s: %s", full_url, ex)


if __name__ == "__main__":
    OhioDownloader().download_all()
