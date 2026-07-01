"""
scripts/downloaders/alaska/ak_downloader.py
===========================================
Downloader for Alaska Department of Education & Early Development (DEED) data.

Covers:
  - Assessments (Overall and demographics combined directly in data/alaska/assessments/)
  - Financials (Audited Operating Revenues + Budgets/Actuals + Foundation Funding)
  - Teacher/Staff (Staff counts + Certifications + TRR reports)
  - Enrollment & Attendance (District/School enrollment + dropouts + Special Ed 618 + Truancy)
"""

import sys
import time
import re
from pathlib import Path
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import raw_dir, DUPLICATE_DETECTION, URLS
from scripts.utils.file_utils import parse_year_range, is_duplicate
from scripts.utils.logger import log_download, setup_logger

logger = setup_logger("downloader.alaska")

STATE = "alaska"

# WAF Bypass Desktop Headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class AlaskaDownloader:
    """
    Downloader for Alaska education data.
    """
    STATE = STATE
    assessments_run = False

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
        """Run all Alaska downloads."""
        self.download_assessments()
        self.download_financials()
        self.download_teacher_staff()
        self.download_enrollment_attendance()

    def download_overall(self) -> None:
        self.download_assessments()

    def download_by_race(self) -> None:
        self.download_assessments()

    def download_by_gender(self) -> None:
        self.download_assessments()

    def download_by_iep(self) -> None:
        self.download_assessments()

    def download_by_ell(self) -> None:
        self.download_assessments()

    # ---------------------------------------------------------------------------
    # 1. Assessments
    # ---------------------------------------------------------------------------
    def download_assessments(self) -> None:
        """Download all Alaska assessment data."""
        if AlaskaDownloader.assessments_run:
            self.logger.debug("Alaska assessments already executed, skipping rerun.")
            return
        AlaskaDownloader.assessments_run = True
        self.logger.info("=== Starting Alaska Assessments Download ===")
        dest_dir = raw_dir(STATE, "assessments")
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Scrape all files linked from the designated assessment pages
        assessment_urls = [
            "https://education.alaska.gov/assessments/results",
            "https://education.alaska.gov/assessments/results/results2024",
            "https://education.alaska.gov/assessments/results/results2023",
            "https://education.alaska.gov/assessments/results/results2022",
            "https://education.alaska.gov/assessments/results/results2024/2024-access-results",
            "https://education.alaska.gov/assessments/akstar/results",
            "https://education.alaska.gov/assessments/science/results",
            "https://education.alaska.gov/akassessments/AKAssessment_Brief_2024.pdf",
            "https://education.alaska.gov/tls/assessments/results/2024/1 - AA StateResults 23-24 SuppAccessible_for webpage 20240822.xlsx",
            "https://education.alaska.gov/tls/assessments/results/2024/2 - AA DistrictResults 23-24 Suppressed Accessible_20240822.xlsx"
        ]

        for url in assessment_urls:
            self._download_static_or_page_files(url, dest_dir, "assessments")

        # Scrape historical interactive statewide tables (overall + subgroups combined in one CSV per grade/subject)
        hubs = self._get_assessment_year_hubs()
        for year_str, hub_url in hubs.items():
            self.logger.info("Scraping assessment tables for year: %s", year_str)
            self._scrape_assessment_subgroups(year_str)

    def _get_assessment_year_hubs(self) -> dict[str, str]:
        """Scrape yearly assessment result hubs from education.alaska.gov/assessments/results."""
        hubs = {}
        url = "https://education.alaska.gov/assessments/results"
        try:
            resp = self.session.get(url, timeout=60)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a in soup.find_all('a'):
                    href = a.get('href') or ''
                    text = a.text.strip()
                    if 'results' in href.lower() and re.search(r'\b(20[12]\d)\b', text):
                        full_href = urljoin("https://education.alaska.gov", href)
                        hubs[text] = full_href
        except Exception as e:
            self.logger.error("Failed to fetch assessment year hubs: %s", e)
        return hubs

    def _scrape_assessment_subgroups(self, year_label: str) -> None:
        """Scrape subgroup tables directly from Statewide Results page and save full tables to CSV."""
        match = re.search(r'(\d{4}-\d{4})', year_label)
        if not match:
            year_match = re.search(r'(\d{4})', year_label)
            if year_match:
                y = int(year_match.group(1))
                school_year = f"{y-1}-{y}"
            else:
                self.logger.warning("Could not resolve school year from label: %s", year_label)
                return
        else:
            school_year = match.group(1)

        # Download ELA, Math, Science
        for is_science in [False, True]:
            subj_label = "Science" if is_science else "ELA_Math"
            url = f"https://education.alaska.gov/assessment-results/Statewide/StatewideResults?schoolYear={school_year}&isScience={is_science}"
            
            try:
                resp = self.session.get(url, timeout=60)
                if resp.status_code != 200:
                    continue
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                for tr in soup.find_all('tr'):
                    a = tr.find('a')
                    if a and 'SubGroup' in (a.get('href') or ''):
                        subgroup_href = a.get('href')
                        subgroup_url = urljoin("https://education.alaska.gov", subgroup_href)
                        self._scrape_subgroup_page(subgroup_url, school_year, subj_label)
            except Exception as e:
                self.logger.error("Failed to scrape Statewide results for %s: %s", school_year, e)

    def _scrape_subgroup_page(self, url: str, school_year: str, subject_key: str) -> None:
        """Scrape subgroup tables as single combined CSV files saved directly under assessments folder."""
        try:
            resp = self.session.get(url, timeout=60)
            if resp.status_code != 200:
                return
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            tables = soup.find_all('table')
            if not tables:
                return

            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            grade = params.get('grade', [''])[0].replace(' ', '_').lower()
            subject = params.get('subject', [subject_key])[0]
            
            dest_dir = raw_dir(STATE, "assessments")
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"ak_assessment_subgroups_{school_year}_{grade}_{subject}.csv"
            dest = dest_dir / filename
            
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
            yr = parse_year_range(filename)
            if DUPLICATE_DETECTION and is_duplicate(filename, yr, existing):
                return

            for table in tables:
                headers = [th.text.strip() for th in table.find_all('th')]
                if not headers or 'subgroup' not in [h.lower() for h in headers]:
                    continue
                
                rows = []
                for tr in table.find_all('tr')[1:]:
                    cols = [td.text.strip() for td in tr.find_all('td')]
                    if len(cols) >= 5:
                        rows.append(cols)

                import csv
                with open(dest, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Subgroup", "Adv_Prof_Count", "Adv_Prof_Pct", "Appr_Needs_Count", "Appr_Needs_Pct", "Enrollment", "Participation_Rate"])
                    writer.writerows(rows)
                
                size_kb = dest.stat().st_size / 1024
                log_download(
                    state=STATE, category="assessments", url=url, filename=filename,
                    status="success", filesize_kb=size_kb, subcategory="",
                    local_path=str(dest), year_range_detected=school_year
                )
                self.logger.info("Saved subgroup table CSV: %s (%.1f KB)", filename, size_kb)

        except Exception as e:
            self.logger.error("Failed to scrape subgroup page %s: %s", url, e)

    # ---------------------------------------------------------------------------
    # 2. Financials
    # ---------------------------------------------------------------------------
    def download_financials(self) -> None:
        """Download all financial documents and Audited Operating Revenues."""
        self.logger.info("=== Starting Alaska Financials Download ===")
        dest_dir = raw_dir(STATE, "financials")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Financial static urls and pages
        financial_urls = [
            "https://education.alaska.gov/SchoolFinance",
            "https://education.alaska.gov/schoolfinance/budgetsactual",
            "https://education.alaska.gov/schoolfinance/foundationfunding",
            "https://education.alaska.gov/schoolfinance/docs/2025-09-09_Report_$ADMHistoryFY1988-FY2025.xlsx",
            "https://education.alaska.gov/SchoolFinance/docs/2026-01-02_Report_StateAidFY1988-FY2025.xlsx",
            "https://education.alaska.gov/schoolfinance/pdf/$Pencil Chart Base Allocation FY99-FY25_7-2024.pdf",
            "https://education.alaska.gov/publications/chart_of_accounts.pdf"
        ]

        for url in financial_urls:
            self._download_static_or_page_files(url, dest_dir, "financials")

        # Also download options from Prior annual revenues dropdown (form19-select)
        self._download_datacenter_dropdown("form19-select", dest_dir, "financials")

    # ---------------------------------------------------------------------------
    # 3. Teacher / Staff Records
    # ---------------------------------------------------------------------------
    def download_teacher_staff(self) -> None:
        """Download staff certification and TRR working group files."""
        self.logger.info("=== Starting Alaska Teacher/Staff Download ===")
        dest_dir = raw_dir(STATE, "teacher_staff")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        teacher_urls = [
            "https://education.alaska.gov/teachercertification",
            "https://education.alaska.gov/trr",
            "https://education.alaska.gov/data-dashboards"
        ]

        for url in teacher_urls:
            self._download_static_or_page_files(url, dest_dir, "teacher_staff")

        # Also download Teacher/Admin counts from dropdown form8-select
        self._download_datacenter_dropdown("form8-select", dest_dir, "teacher_staff")

    # ---------------------------------------------------------------------------
    # 4. Enrollment & Attendance
    # ---------------------------------------------------------------------------
    def download_enrollment_attendance(self) -> None:
        """Download enrollment spreadsheets, dropout rates, SpEd profiles and truancy reports."""
        self.logger.info("=== Starting Alaska Enrollment/Attendance Download ===")
        dest_dir = raw_dir(STATE, "enrollment_attendance")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        enrollment_urls = [
            "https://education.alaska.gov/Stats/GraduationRates/1 - DropoutRatesByEthnicity1991to2025.xlsx",
            "https://education.alaska.gov/Stats/GraduationRates/2 - DropoutRatesByDistrict1991to2025.xlsx",
            "https://education.alaska.gov/safeschools/suspexptruancy",
            "https://education.alaska.gov/rcsped/",
            "https://education.alaska.gov/sped/618data"
        ]

        for url in enrollment_urls:
            self._download_static_or_page_files(url, dest_dir, "enrollment_attendance")

        # Dropdowns on data-center to scrape:
        dropdowns = [
            "form1-select", "form2-select", "form3-select", "form4-select", 
            "form5-select", "form6-select", "form7-select", "form9-select", 
            "form10-select", "form14-select", "form15-select", "form16-select", "form17-select"
        ]
        for select_id in dropdowns:
            self._download_datacenter_dropdown(select_id, dest_dir, "enrollment_attendance")

    # ---------------------------------------------------------------------------
    # URL Harvester & Page Crawler Helper
    # ---------------------------------------------------------------------------
    def _download_static_or_page_files(self, url: str, dest_dir: Path, category: str) -> None:
        """Download the file directly if static document; otherwise, harvest and download all file attachments from the HTML."""
        # Clean url spaces
        clean_url = url.replace(" ", "%20")
        
        # Check if the url itself points to a file
        if any(clean_url.lower().endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip']):
            self._download_static_file(clean_url, dest_dir, category)
            return

        # Otherwise, parse the page and pull all file attachments
        self.logger.info("Crawling page for files: %s", clean_url)
        try:
            resp = self.session.get(clean_url, timeout=60)
            if resp.status_code != 200:
                self.logger.warning("Failed to fetch crawl page %s (HTTP %d)", clean_url, resp.status_code)
                return
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            links_found = 0
            for a in soup.find_all('a'):
                href = a.get('href') or ''
                # Convert to absolute URL
                abs_url = urljoin(clean_url, href)
                
                # Check for standard document file extensions
                if any(abs_url.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip']):
                    self._download_static_file(abs_url, dest_dir, category)
                    links_found += 1

            # Crawl dropdown selects for documents
            for select in soup.find_all('select'):
                for opt in select.find_all('option'):
                    val = opt.get('value') or ''
                    if not val or val == '#' or val == 'default':
                        continue
                    abs_url = urljoin(clean_url, val)
                    if any(abs_url.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip']):
                        self._download_static_file(abs_url, dest_dir, category)
                        links_found += 1

            self.logger.info("Completed page crawl for %s. Found %d files.", clean_url, links_found)
        except Exception as e:
            self.logger.error("Crawl error on page %s: %s", clean_url, e)

    def _download_static_file(self, full_url: str, dest_dir: Path, category: str) -> None:
        """Download a static link directly and log/save it."""
        try:
            # Decode file name to write locally
            from urllib.parse import unquote
            filename = Path(unquote(full_url)).name
            
            # Replace character formatting
            filename = filename.replace('$', '').replace(' ', '_')
            
            dest = dest_dir / filename
            
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
            yr = parse_year_range(filename)
            if DUPLICATE_DETECTION and is_duplicate(filename, yr, existing):
                return

            self.logger.info("Downloading file: %s", filename)
            f_resp = self.session.get(full_url, timeout=120)
            if f_resp.status_code == 200:
                dest.write_bytes(f_resp.content)
                size_kb = len(f_resp.content) / 1024
                yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
                
                log_download(
                    state=STATE, category=category, url=full_url, filename=filename,
                    status="success", filesize_kb=size_kb, subcategory="",
                    local_path=str(dest), year_range_detected=yr_str
                )
                self.logger.info("Saved static file: %s (%.1f KB)", filename, size_kb)
            else:
                self.logger.warning("Failed download for static file: %s (HTTP %d)", filename, f_resp.status_code)
            time.sleep(0.5) # Throttle requests
        except Exception as ex:
            self.logger.error("Error downloading file %s: %s", full_url, ex)

    # ---------------------------------------------------------------------------
    # Dropdown Downloader Helper
    # ---------------------------------------------------------------------------
    def _download_datacenter_dropdown(self, select_id: str, dest_dir: Path, category: str) -> None:
        """Scrape all options from the given select dropdown and download the target files."""
        url = "https://education.alaska.gov/data-center"
        try:
            resp = self.session.get(url, timeout=60)
            if resp.status_code != 200:
                return
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            select = soup.find('select', {'id': select_id})
            if not select:
                self.logger.warning("Select dropdown ID '%s' not found on data-center.", select_id)
                return

            options = select.find_all('option')
            self.logger.info("Dropdown %s: found %d options.", select_id, len(options))
            
            for opt in options:
                val = opt.get('value') or ''
                # Skip placeholder select options
                if not val or val == '#' or not any(val.lower().endswith(ext) for ext in ['.xlsx', '.xls', '.pdf']):
                    continue
                
                full_url = urljoin("https://education.alaska.gov", val)
                filename = Path(val).name
                dest = dest_dir / filename
                
                existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
                yr = parse_year_range(filename)
                if DUPLICATE_DETECTION and is_duplicate(filename, yr, existing):
                    continue

                try:
                    f_resp = self.session.get(full_url, timeout=120)
                    if f_resp.status_code == 200:
                        dest.write_bytes(f_resp.content)
                        size_kb = len(f_resp.content) / 1024
                        yr_str = f"{yr[0]}-{yr[1]}" if yr else ""
                        
                        log_download(
                            state=STATE, category=category, url=full_url, filename=filename,
                            status="success", filesize_kb=size_kb, subcategory="",
                            local_path=str(dest), year_range_detected=yr_str
                        )
                        self.logger.info("Saved dropdown file: %s (%.1f KB)", filename, size_kb)
                    else:
                        self.logger.warning("Failed download for option: %s (HTTP %d)", filename, f_resp.status_code)
                except Exception as ex:
                    self.logger.error("Error downloading file %s: %s", filename, ex)
                
                time.sleep(0.5)

        except Exception as e:
            self.logger.error("Failed to parse dropdown %s on data-center: %s", select_id, e)


if __name__ == "__main__":
    AlaskaDownloader().download_all()
