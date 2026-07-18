"""
scripts/downloaders/new_jersey/nj_downloader.py
==============================================
Downloader for New Jersey Department of Education data.

Covers:
  - Assessments (NJSLA ELA, Math, Science, DLM, NJGPA, ACCESS for ELLs)
  - Financials (State aid summaries, Taxpayers' Guide, User-Friendly Budgets, ACFR, AMR)
  - Teacher/Staff records (ZIP staff registers, Non-Certified reports, EPPRs)
  - Enrollment & Attendance (ZIP enrollment registers, chronic absenteeism, safety/discipline)
"""

import sys
import time
import urllib.parse
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from config import raw_dir, DUPLICATE_DETECTION
from scripts.utils.file_utils import parse_year_range, is_duplicate
from scripts.utils.logger import log_download, setup_logger

logger = setup_logger("downloader.new_jersey")

STATE = "new_jersey"

# Desktop spoof headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Subpaths allowed for crawling to prevent escaping into unrelated NJ.gov portals
ALLOWED_SUBPATHS = [
    "/education/assessment/",
    "/education/doedata/",
    "/education/specialed/",
    "/education/spr/",
    "/education/stateaid/",
    "/education/guide/",
    "/education/budget/",
    "/education/fpp/",
    "/education/schoolfinance/",
    "/education/vandv/",
]


class NewJerseyDownloader:
    """
    Downloader for New Jersey education data.
    """
    STATE = STATE

    def __init__(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self.logger = logger
        self.visited_urls = set()
        self.filename_to_url = {}

        # Load existing download manifest to preserve filename -> URL mappings across runs
        manifest_path = Path("logs/download_manifest.csv")
        if manifest_path.exists():
            try:
                import csv
                with open(manifest_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("state") == STATE:
                            local_path = row.get("local_path")
                            source_url = row.get("source_url")
                            if local_path and source_url:
                                p = Path(local_path)
                                self.filename_to_url[(p.parent.name, p.name)] = source_url
            except Exception as e:
                self.logger.warning("Could not pre-populate filename mappings: %s", e)

    def download_all(self) -> None:
        """Run all New Jersey downloads."""
        self.download_assessments()
        self.download_financials()
        self.download_teacher_staff()
        self.download_enrollment_attendance()

    # ---------------------------------------------------------------------------
    # 1. Assessments
    # ---------------------------------------------------------------------------
    def download_assessments(self) -> None:
        """Crawl NJSLA/DLM report hubs and download assessment spreadsheets."""
        self.logger.info("=== Starting New Jersey Assessments Download ===")
        dest_dir = raw_dir(STATE, "assessments")
        dest_dir.mkdir(parents=True, exist_ok=True)

        assessment_hubs = [
            "https://www.nj.gov/education/assessment/results/reports/",
            "https://www.nj.gov/education/assessment/results/reports/2425/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/2324/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/2223/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/2122/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/2021/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/1819/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/1718/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/1617/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/1516/index.shtml",
            "https://www.nj.gov/education/assessment/results/reports/1415/index.shtml",
            "https://www.nj.gov/education/specialed/monitor/ideapublicdata/",
            "https://www.nj.gov/education/spr/download/"
        ]

        for url in assessment_hubs:
            self._crawl_and_download(url, dest_dir, "assessments", max_depth=2)

    # ---------------------------------------------------------------------------
    # 2. Financials
    # ---------------------------------------------------------------------------
    def download_financials(self) -> None:
        """Crawl budget, guides, state aid, and AMRs to harvest financial data."""
        self.logger.info("=== Starting New Jersey Financials Download ===")
        dest_dir = raw_dir(STATE, "financials")
        dest_dir.mkdir(parents=True, exist_ok=True)

        financial_hubs = [
            "https://www.nj.gov/education/doedata/",
            "https://www.nj.gov/education/stateaid/",
            "https://www.nj.gov/education/guide/",
            "https://www.nj.gov/education/budget/ufb/",
            "https://www.nj.gov/education/fpp/acfr/",
            "https://www.nj.gov/education/fpp/audit/index.shtml",
            "https://www.nj.gov/education/schoolfinance/datainfo/"
        ]

        for url in financial_hubs:
            self._crawl_and_download(url, dest_dir, "financials", max_depth=2)

    # ---------------------------------------------------------------------------
    # 3. Teacher / Staff Records
    # ---------------------------------------------------------------------------
    def download_teacher_staff(self) -> None:
        """Iterate and download ZIP certificated staff listings and crawl staff pages."""
        self.logger.info("=== Starting New Jersey Teacher/Staff Download ===")
        dest_dir = raw_dir(STATE, "teacher_staff")
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Direct Zip/XLSX certificated staff links (1999-00 to 2025-26)
        staff_files = {
            "2026": "https://www.nj.gov/education/doedata/cs/cs26/Certificated%20Staff%202026.zip",
            "2025": "https://www.nj.gov/education/doedata/cs/cs25/Certificated%20Staff%202025.xlsx",
            "2024": "https://www.nj.gov/education/doedata/cs/cs24/CertificatedStaff_2024.zip",
            "2023": "https://www.nj.gov/education/doedata/cs/cs23/Certificated%20Staff%202023.zip",
            "2022": "https://www.nj.gov/education/doedata/cs/cs22/Certificated%20Staff%202122.zip",
            "2021": "https://www.nj.gov/education/doedata/cs/cs21/Certificated%20Staff%202021.zip",
            "2020": "https://www.nj.gov/education/doedata/cs/cs20/cert_staff_state_1920.zip",
            "2019": "https://www.nj.gov/education/doedata/cs/cs19/cert.zip",
            "2018": "https://www.nj.gov/education/doedata/cs/cs18/cert.zip",
            "2017": "https://www.nj.gov/education/doedata/cs/cs18/cert.zip",
            "2016": "https://www.nj.gov/education/doedata/cs/cs17/cert.zip",
            "2015": "https://www.nj.gov/education/doedata/cs/cs16/cert.zip",
            "2014": "https://www.nj.gov/education/doedata/cs/cs15/cert.zip",
            "2013": "https://www.nj.gov/education/doedata/cs/cs14/cert.zip",
            "2012": "https://www.nj.gov/education/doedata/cs/cs13/cert.zip",
            "2011": "https://www.nj.gov/education/doedata/cs/cs12/cert.zip",
            "2010": "https://www.nj.gov/education/doedata/cs/cs11/cert.zip",
            "2009": "https://www.nj.gov/education/doedata/cs/cs10/cert.zip",
            "2008": "https://www.nj.gov/education/doedata/cs/cs09/cert.zip",
            "2007": "https://www.nj.gov/education/doedata/cs/cs08/cert.zip",
            "2006": "https://www.nj.gov/education/doedata/cs/cs07/cert.zip",
            "2005": "https://www.nj.gov/education/doedata/cs/cs06/cert.zip",
            "2004": "https://www.nj.gov/education/doedata/cs/cs05/cert.zip",
            "2003": "https://www.nj.gov/education/doedata/cs/cs04/cert.zip",
            "2002": "https://www.nj.gov/education/doedata/cs/cs03/cert.zip",
            "2001": "https://www.nj.gov/education/doedata/cs/cs02/cert.zip",
            "2000": "https://www.nj.gov/education/doedata/cs/cs01/cert.zip",
            "1999": "https://www.nj.gov/education/doedata/cs/cs00/cert.zip",
        }

        for yr_tag, url in staff_files.items():
            self._download_static_file(url, dest_dir, "teacher_staff", force_year_str=yr_tag)

        # Crawl staff index pages
        staff_hubs = [
            "https://www.nj.gov/education/doedata/ncs/index.shtml",
            "https://www.nj.gov/education/doedata/staff/index.shtml",
            "https://eppdata.doe.state.nj.us/",
            "https://www.nj.gov/education/budget/ufb/index.shtml"
        ]

        for url in staff_hubs:
            self._crawl_and_download(url, dest_dir, "teacher_staff", max_depth=2)

    # ---------------------------------------------------------------------------
    # 4. Enrollment & Attendance
    # ---------------------------------------------------------------------------
    def download_enrollment_attendance(self) -> None:
        """Iterate and download ZIP enrollment listings and crawl student behavior pages."""
        self.logger.info("=== Starting New Jersey Enrollment/Attendance Download ===")
        dest_dir = raw_dir(STATE, "enrollment_attendance")
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Direct Zip enrollment files (1998-99 to 2025-26)
        enrollment_files = {
            "2026": "https://www.nj.gov/education/doedata/enr/enr26/Enrollment_2526.zip",
            "2025": "https://www.nj.gov/education/doedata/enr/enr25/enrollment_2425.zip",
            "2023": "https://www.nj.gov/education/doedata/enr/enr23/enrollment_2223.zip",
            "2022": "https://www.nj.gov/education/doedata/enr/enr22/enrollment_2122.zip",
            "2021": "https://www.nj.gov/education/doedata/enr/enr21/enrollment_2021.zip",
            "2020": "https://www.nj.gov/education/doedata/enr/enr20/enrollment_1920.zip",
            "2019": "https://www.nj.gov/education/doedata/enr/enr19/enrollment_1819.zip",
            "2017": "https://www.nj.gov/education/doedata/enr/enr17/enrollment_1617.zip",
            "2016": "https://www.nj.gov/education/doedata/enr/enr16/enrollment_1516.zip",
            "2015": "https://www.nj.gov/education/doedata/enr/enr15/enrollment_1415.zip",
            "2014": "https://www.nj.gov/education/doedata/enr/enr14/enrollment_1314.zip",
            "2013": "https://www.nj.gov/education/doedata/enr/enr13/enrollment_1213.zip",
            "2012": "https://www.nj.gov/education/doedata/enr/enr13/enrollment_1213.zip",
            "2011": "https://www.nj.gov/education/doedata/enr/enr11/enrollment_1011.zip",
            "2010": "https://www.nj.gov/education/doedata/enr/enr10/enrollment_0910.zip",
            "2009": "https://www.nj.gov/education/doedata/enr/enr09/enrollment_0809.zip",
            "2008": "https://www.nj.gov/education/doedata/enr/enr08/enrollment_0708.zip",
            "2007": "https://www.nj.gov/education/doedata/enr/enr07/enrollment_0607.zip",
            "2006": "https://www.nj.gov/education/doedata/enr/enr06/enrollment_0506.zip",
            "2005": "https://www.nj.gov/education/doedata/enr/enr05/enrollment_0405.zip",
            "2004": "https://www.nj.gov/education/doedata/enr/enr04/enrollment_0304.zip",
            "2003": "https://www.nj.gov/education/doedata/enr/enr03/enrollment_0203.zip",
            "2002": "https://www.nj.gov/education/doedata/enr/enr02/enrollment_0102.zip",
            "2001": "https://www.nj.gov/education/doedata/enr/enr01/enrollment_0001.zip",
            "2000": "https://www.nj.gov/education/doedata/enr/enr00/enrollment_9900.zip",
            "1999": "https://www.nj.gov/education/doedata/enr/enr99/enrollment_9899.zip",
        }

        # Add any missing years that might be slightly different
        enrollment_files["2024"] = "https://www.nj.gov/education/doedata/enr/enr24/enrollment_2324.zip"

        for yr_tag, url in enrollment_files.items():
            self._download_static_file(url, dest_dir, "enrollment_attendance", force_year_str=yr_tag)

        # Crawl attendance/safety index pages
        enrollment_hubs = [
            "https://www.nj.gov/education/vandv/",
            "https://www.nj.gov/education/spr/download/",
            "https://www.nj.gov/education/doedata/drp/index.shtml",
            "https://www.nj.gov/education/spr/adddata/acgr.shtml"
        ]

        for url in enrollment_hubs:
            self._crawl_and_download(url, dest_dir, "enrollment_attendance", max_depth=2)

    # ---------------------------------------------------------------------------
    # Generic Crawling Logic
    # ---------------------------------------------------------------------------
    def _crawl_and_download(self, url: str, dest_dir: Path, category: str, max_depth: int = 2, current_depth: int = 1) -> None:
        """Crawl the given URL, download files of interest, and optionally traverse links recursively."""
        clean_url = url.split('#')[0].replace(" ", "%20")
        if not clean_url:
            return

        # Simple loops/visited guard
        if clean_url in self.visited_urls:
            return
        self.visited_urls.add(clean_url)

        # Check if URL looks like a static document file to download directly
        if any(clean_url.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
            self._download_static_file(clean_url, dest_dir, category)
            return

        # Restrict crawling recursion limits
        if current_depth > max_depth:
            return

        # Restrict crawling target directories to prevent trailing off to nj.gov homepages
        parsed_url = urllib.parse.urlparse(clean_url)
        if parsed_url.netloc and "nj.gov" not in parsed_url.netloc:
            # External domain check
            return
        
        path_lower = parsed_url.path.lower()
        # Verify subpaths
        if parsed_url.netloc and not any(sub in path_lower for sub in ALLOWED_SUBPATHS):
            return

        self.logger.info("Crawling NJ page [depth %d/%d]: %s", current_depth, max_depth, clean_url)
        try:
            resp = self.session.get(clean_url, timeout=60)
            if resp.status_code != 200:
                return

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. Scrape all standard href links
            for a in soup.find_all('a'):
                href = a.get('href') or ''
                abs_url = urljoin(clean_url, href)
                # Filter out external/unrelated links
                abs_url_clean = abs_url.split('#')[0]
                if any(abs_url_clean.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
                    self._download_static_file(abs_url_clean, dest_dir, category)
                elif current_depth < max_depth:
                    # Recursive crawl
                    self._crawl_and_download(abs_url_clean, dest_dir, category, max_depth, current_depth + 1)

            # 2. Scrape dropdown select option value elements
            for select in soup.find_all('select'):
                for opt in select.find_all('option'):
                    val = opt.get('value') or ''
                    if not val or val == '#' or val == 'default':
                        continue
                    abs_url = urljoin(clean_url, val)
                    abs_url_clean = abs_url.split('#')[0]
                    if any(abs_url_clean.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
                        self._download_static_file(abs_url_clean, dest_dir, category)
                    elif current_depth < max_depth:
                        self._crawl_and_download(abs_url_clean, dest_dir, category, max_depth, current_depth + 1)

        except Exception as e:
            self.logger.error("Crawl error on NJ page %s: %s", clean_url, e)

    def _get_unique_filename(self, original_clean: str, clean_url: str, dest_dir: Path, parsed_url) -> str:
        """
        Determine the correct filename for clean_url in dest_dir.
        If there's no collision, return original_clean.
        If a file with the same name exists but belongs to the same URL, return original_clean (it will be skipped).
        If it belongs to a different URL, generate a renamed version and check recursively.
        """
        key = (dest_dir.name, original_clean)
        file_path = dest_dir / original_clean
        if not file_path.exists():
            # No physical file on disk, so we can use this name!
            self.filename_to_url[key] = clean_url
            return original_clean

        # The file physically exists. Check if we know its URL.
        known_url = self.filename_to_url.get(key)
        if known_url:
            # Normalize URLs for comparison (ignoring scheme/www variation and case)
            def normalize_url(u):
                return u.replace("://nj.gov/", "://www.nj.gov/").replace(" ", "%20").lower()
            
            if normalize_url(known_url) == normalize_url(clean_url):
                # Same URL! No renaming needed, it will just be skipped/overwritten.
                return original_clean

        # Different URL or unknown URL: collision! We must rename the file.
        path_parts = [p for p in urllib.parse.unquote(parsed_url.path).split('/') if p]
        filename_parts = path_parts[-3:] if len(path_parts) >= 3 else path_parts
        renamed = "_".join(filename_parts)
        renamed = renamed.replace('$', '').replace(' ', '_').replace('%20', '_')
        
        # If the renamed filename is the same as the original, append a counter to avoid infinite loops
        if renamed == original_clean:
            base = Path(original_clean).stem
            ext = Path(original_clean).suffix
            counter = 1
            while True:
                candidate = f"{base}_{counter}{ext}"
                candidate_path = dest_dir / candidate
                candidate_key = (dest_dir.name, candidate)
                if not candidate_path.exists():
                    self.filename_to_url[candidate_key] = clean_url
                    return candidate
                candidate_url = self.filename_to_url.get(candidate_key)
                if candidate_url and normalize_url(candidate_url) == normalize_url(clean_url):
                    return candidate
                counter += 1
        
        # Otherwise, recursively call to make sure the renamed filename doesn't collide
        return self._get_unique_filename(renamed, clean_url, dest_dir, parsed_url)

    def _download_static_file(self, full_url: str, dest_dir: Path, category: str, force_year_str: str = "") -> None:
        """Download a single static file directly and save/log it."""
        try:
            # Simple loop guard for direct downloads
            clean_url = full_url.split('#')[0].replace(" ", "%20")
            if clean_url in self.visited_urls:
                return
            self.visited_urls.add(clean_url)

            parsed_url = urllib.parse.urlparse(clean_url)
            filename = Path(urllib.parse.unquote(parsed_url.path)).name
            if not filename or '.' not in filename:
                return

            original_clean = filename.replace('$', '').replace(' ', '_').replace('%20', '_')
            
            # Category routing check based on URL path to prevent misclassification
            url_lower = full_url.lower()
            if category == "assessments":
                if not any(k in url_lower for k in ["/assessment/", "/specialed/", "/spr/"]):
                    return
            elif category == "financials":
                if not any(k in url_lower for k in ["/stateaid/", "/guide/", "/budget/", "/fpp/", "/schoolfinance/"]):
                    return
            elif category == "teacher_staff":
                if not any(k in url_lower for k in ["/cs/", "/ncs/", "/staff/", "eppdata"]):
                    return
            elif category == "enrollment_attendance":
                if not any(k in url_lower for k in ["/enr/", "/drp/", "/vandv/", "/acgr.shtml", "/spr/"]):
                    return
            
            # Determine unique filename dynamically based on collisions
            clean_filename = self._get_unique_filename(original_clean, clean_url, dest_dir, parsed_url)
            
            # De-duplicate check
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
            if clean_filename in existing:
                return

            yr = parse_year_range(clean_filename)
            if DUPLICATE_DETECTION and is_duplicate(clean_filename, yr, existing):
                return

            self.logger.info("Downloading NJ file: %s", clean_filename)
            f_resp = self.session.get(full_url, timeout=120)
            if f_resp.status_code == 200:
                dest = dest_dir / clean_filename
                dest.write_bytes(f_resp.content)
                size_kb = len(f_resp.content) / 1024
                
                # Update filename mapping for the newly saved file
                self.filename_to_url[(dest_dir.name, clean_filename)] = clean_url

                # Determine Year range string representation
                if yr:
                    yr_str = f"{yr[0]}-{yr[1]}"
                elif force_year_str:
                    yr_str = force_year_str
                else:
                    yr_str = ""

                log_download(
                    state=STATE, category=category, url=full_url, filename=clean_filename,
                    status="success", filesize_kb=size_kb, subcategory="",
                    local_path=str(dest), year_range_detected=yr_str
                )
                self.logger.info("Saved NJ static file: %s (%.1f KB)", clean_filename, size_kb)
            else:
                self.logger.warning("Failed download for NJ static file: %s (HTTP %d)", clean_filename, f_resp.status_code)
            
            time.sleep(0.3)
        except Exception as ex:
            self.logger.error("Error downloading file %s: %s", full_url, ex)


if __name__ == "__main__":
    NewJerseyDownloader().download_all()
