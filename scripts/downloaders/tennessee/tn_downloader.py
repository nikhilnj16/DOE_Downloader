"""
scripts/downloaders/tennessee/tn_downloader.py
=============================================
Downloader for Tennessee Department of Education data.

Covers:
  - Assessments (Accountability files, Assessment Base files, ACT scores, WIDA/ELPA growth files, MSAA)
  - Financials (Report card expenditures, per-pupil spend, Annual Statistical Reports hub)
  - Teacher/Staff records (Educator counts, Educator experience/licensure, Educator race/ethnicity, retention, Educator Survey hub)
  - Enrollment & Attendance (Membership files, district/school profiles, chronic absenteeism, discipline/suspensions, dropouts)
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

logger = setup_logger("downloader.tennessee")

STATE = "tennessee"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class TennesseeDownloader:
    """
    Downloader for Tennessee Department of Education data.
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

    def download_all(self) -> None:
        """Run all Tennessee downloads."""
        self.download_assessments()
        self.download_financials()
        self.download_teacher_staff()
        self.download_enrollment_attendance()

    # ---------------------------------------------------------------------------
    # 1. Assessments
    # ---------------------------------------------------------------------------
    def download_assessments(self) -> None:
        """Download Tennessee assessment, ACT, and WIDA/ELPA spreadsheets."""
        self.logger.info("=== Starting Tennessee Assessments Download ===")
        dest_dir = raw_dir(STATE, "assessments")
        dest_dir.mkdir(parents=True, exist_ok=True)

        urls = [
            # Accountability Files
            "https://www.tn.gov/content/dam/tn/education/data/state_release_file_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district_release_file_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school_release_file_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/state_release_file_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district_release_file_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school_release_file_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/state_release_file_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/district_release_file_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/school_release_file_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2022/state_release_file_suppressed_2022.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2022/district_release_file_suppressed_2022.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2022/school_release_file_suppressed_2022.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/state_release_file_suppressed_2021.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/district_release_file_suppressed_2021.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/school_release_file_suppressed_2021.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/state_release_file_suppressed_(1).xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/district_release_file_suppressed_(1).xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/school_release_file_suppressed_(1).xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2018/state_release_file_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2018/district_release_file_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2018/school_release_file_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_state_agg_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_district_agg_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_school_agg_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2016_suppressed_state_numeric.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2016_suppressed_system_numeric.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2016_suppressed_school_numeric.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2015_state_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2015_district_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2015_school_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2014_state_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2014_district_accountability.xls",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2014_school_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2013_state_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2013_district_accountability.xls",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2013_school_accountability.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2012_AccountabilityFile-DISTRICTandSCHOOL.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2011_AccountabilityFile-DISTRICTandSCHOOL.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/acct/data_2010_AccountabilityFile-DISTRICTandSCHOOL.xlsx",

            # Assessment Base Files
            "https://www.tn.gov/content/dam/tn/education/accountability/2025/state_assessment_file_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2025/district_assessment_file_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2025/school_assessment_file_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2024/state_assessment_file_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2024/district_assessment_file_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2024/school_assessment_file_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2023/state_assessment_file_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2023/district_assessment_file_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2023/school_assessment_file_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2022/state_assessment_file_suppressed_upd32323.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2022/district_assessment_file_suppressed_upd32323.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2022/school_assessment_file_suppressed_upd32323.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/state_assessment_file_suppressed_upd422.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/district_assessment_file_suppressed_upd422.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/school_assessment_file_suppressed_upd422.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/state_assessment_file_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/district_assessment_file_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/school_assessment_file_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2018_state_base_grade_level.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2018_district_base.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2018_school_base.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_state_base.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_district_base.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_school_base.csv",
            "https://www.tn.gov/content/dam/tn/education/data/data_2016_suppressed_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2016_suppressed_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2016_suppressed_school_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2015_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2015_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2015_school_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2014_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2014_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2014_school_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2013_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2013_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2013_school_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2012_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2012_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2012_school_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2011_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2011_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2011_school_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2010_state_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2010_district_base.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2010_school_base.xlsx",

            # WIDA/ELPA Growth standard files
            "https://www.tn.gov/content/dam/tn/education/data/elpa_growth_standard_state_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/elpa_growth_standard_district_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/elpa_growth_standard_school_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/wida_growth_standard_state_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/wida_growth_standard_district_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/wida_growth_standard_school_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/wida_growth_standard_state_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/wida_growth_standard_district_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/wida_growth_standard_school_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021-22/wida_growth_standard_state_suppressed_upd8-19.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021-22/wida_growth_standard_district_suppressed_upd8-19.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021-22/wida_growth_standard_school_suppressed_upd8-19.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/wida_growth_standard_state_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/wida_growth_standard_district_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/wida_growth_standard_school_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/wida_growth_standard_district_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/wida_growth_standard_school_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2018/wida_growth_standard_district_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2018/wida_growth_standard_school_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/elpa_suppressed_system_level.csv",
            "https://www.tn.gov/content/dam/tn/education/data/elpa_suppressed_school_level.csv",

            # MSAA Alternate assessments
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/alt-test-pct-2019-2021.xlsx",

            # ACT Data
            "https://www.tn.gov/content/dam/tn/education/data/2024-25_ACT_district_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2024-25_ACT_school_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2023-24_ACT_district_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2023-24_ACT_school_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2022-23_ACT_district_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2022-23_ACT_school_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2021-22_ACT_district_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2021-22_ACT_school_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/ACT_district_suppressed_20-21.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/ACT_school_suppressed_20-21.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/ACT_district_suppressed_2020.csv",
            "https://www.tn.gov/content/dam/tn/education/data/ACT_school_suppressed_2020.csv",
            "https://www.tn.gov/content/dam/tn/education/data/ACT_district_suppressed_2019.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/ACT_school_suppressed_2019.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/2017-18%20ACT_district_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/2017-18%20ACT_school_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_ACT-Data-by-District-2016-17.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_suppressed_school_level_ACT_2016-17.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_2015-16_suppressed_district_level_act.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_suppressed_school_level_ACT_2015-16.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_ACT-Data-by-District-2014-15.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_ACT-Data-by-District-2013-14.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/act/data_ACT-Data-by-District-2012-13.xlsx",
        ]

        for url in urls:
            self._download_static_file(url, dest_dir, "assessments")

    # ---------------------------------------------------------------------------
    # 2. Financials
    # ---------------------------------------------------------------------------
    def download_financials(self) -> None:
        """Download Report Card data and crawl Annual Statistical Reports hub."""
        self.logger.info("=== Starting Tennessee Financials Download ===")
        dest_dir = raw_dir(STATE, "financials")
        dest_dir.mkdir(parents=True, exist_ok=True)

        urls = [
            # Report Card Financial Update / Per Pupil Expenditures
            "https://www.tn.gov/content/dam/tn/education/data/2024-25_RC.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2023-24_RC.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/Report_Card_02-14-24.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/per-pupil-expenditures-fy22.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/per-pupil-expenditures-fy21-updated-2023-02-17.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2019-20-finance_update.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/FinalReportCarddata2018201921.xlsx",
        ]

        for url in urls:
            self._download_static_file(url, dest_dir, "financials")

        # Crawl Annual Statistical Reports hub (contains PDFs + zipped excels)
        reports_hub = "https://www.tn.gov/education/districts/federal-programs-and-oversight/data/department-reports.html"
        self._crawl_and_download(reports_hub, dest_dir, "financials", max_depth=2, path_filter="department-reports")

    # ---------------------------------------------------------------------------
    # 3. Teacher / Staff Records
    # ---------------------------------------------------------------------------
    def download_teacher_staff(self) -> None:
        """Download teacher retention, licensure, counts, and crawl Educator Survey data."""
        self.logger.info("=== Starting Tennessee Teacher/Staff Download ===")
        dest_dir = raw_dir(STATE, "teacher_staff")
        dest_dir.mkdir(parents=True, exist_ok=True)

        urls = [
            # Educator Counts
            "https://www.tn.gov/content/dam/tn/education/data/staff-2024-25.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2023-24-final.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2022-23-final.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2021-2022-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2020-2021-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2019-2020-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2018-2019-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/staff-2017-2018-updated-2023-01-06.xlsx",

            # Educator Experience & Licensure
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData2025_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData2022.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData2021.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData1920.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/EducatorExperienceandLicensureData1819.xlsx",

            # Educator Race & Ethnicity
            "https://www.tn.gov/content/dam/tn/education/data/educator_race_and_ethnicity_2024_25.csv",
            "https://www.tn.gov/content/dam/tn/education/data/educator_race_and_ethnicity_2023_24.csv",
            "https://www.tn.gov/content/dam/tn/education/data/educator_race_and_ethnicity_2022_23_revised.csv",
            "https://www.tn.gov/content/dam/tn/education/data/race_and_ethnicity_2022.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/race_and_ethnicity_2021.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/race_and_ethnicity_1920_formatted.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2019_educator_race_ethnicity.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2018_educator_race_ethnicity.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/data_2017_educator_race_ethnicity_by_district.xlsx",

            # Teacher Retention
            "https://www.tn.gov/content/dam/tn/education/data/teacher_retention-2024-25.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher_retention-2023-24-final.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher_retention-2022-23.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher-retention-2021-2022-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher-retention-2020-2021-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher-retention-2019-2020-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher-retention-2018-2019-updated-2023-01-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/teacher-retention-2017-2018-updated-2023-01-06.xlsx",
        ]

        for url in urls:
            self._download_static_file(url, dest_dir, "teacher_staff")

        # Crawl Educator Survey hub page
        survey_hub = "https://www.tn.gov/education/districts/federal-programs-and-oversight/data/educator-survey.html"
        self._crawl_and_download(survey_hub, dest_dir, "teacher_staff", max_depth=2, path_filter="educator-survey")

    # ---------------------------------------------------------------------------
    # 4. Enrollment & Attendance
    # ---------------------------------------------------------------------------
    def download_enrollment_attendance(self) -> None:
        """Download enrollment registers, school/district profiles, truancy, discipline, and dropout files."""
        self.logger.info("=== Starting Tennessee Enrollment & Attendance Download ===")
        dest_dir = raw_dir(STATE, "enrollment_attendance")
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Base list of Membership files
        urls = [
            "https://www.tn.gov/content/dam/tn/education/data/school-profile-2024-2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-profile-2023-2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-profile-2022-2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-profile-2021-2022-updated-2022-12-06.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-profile-file-2020-21_upd120821.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/membership201920.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/201819_membership.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/membership/membership_school_2017-18.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/membership/membership_school_2016-17.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/membership/membership_school_2015-16.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/membership/membership_school_2014-15.csv",
            "https://www.tn.gov/content/dam/tn/education/data/membership/membership_school_2013-14.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/membership/membership_school_2012-13.xlsx",
        ]

        # Standard Profile Files patterns from 2010 to 2025
        profile_years = [
            "2024-2025", "2023-2024", "2022-2023", "2021-2022", "2020-2021",
            "2019-2020", "2018-2019", "2017-2018", "2016-2017", "2015-2016",
            "2014-2015", "2013-2014", "2012-2013", "2011-2012", "2010-2011"
        ]
        for yr in profile_years:
            urls.append(f"https://www.tn.gov/content/dam/tn/education/data/district-profile-{yr}.xlsx")
            urls.append(f"https://www.tn.gov/content/dam/tn/education/data/school-profile-{yr}.xlsx")

        # Chronic Absenteeism
        urls.extend([
            "https://www.tn.gov/content/dam/tn/education/data/state_chronic_absenteeism_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district_chronic_absenteeism_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school_chronic_absenteeism_suppressed_2025.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/state_chronic_absenteeism_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district_chronic_absenteeism_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school_chronic_absenteeism_suppressed_2024.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/state_chronic_absenteeism_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/district_chronic_absenteeism_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/school_chronic_absenteeism_suppressed_2023.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021-22/state_chronic_absenteeism_suppressed_upd8-19.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021-22/district_chronic_absenteeism_suppressed_upd8-19.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021-22/school_chronic_absenteeism_suppressed_upd8-19.xlsx",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/state_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/district_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2021/school_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2020/state_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2020/district_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2020/school_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/state_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/district_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/accountability/2019/school_chronic_absenteeism_suppressed.csv",
            "https://www.tn.gov/content/dam/tn/education/data/chr_abs_state-Level_Suppression_2017-18.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/chr_abs_District-Level_Suppression_2017-18.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/chr_abs_School-Level_Suppression_2017-18.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/chr_abs_state-Level_Suppression_2016-17.csv",
            "https://www.tn.gov/content/dam/tn/education/data/chr_abs_District-Level_Suppression_2016-17.xls",
            "https://www.tn.gov/content/dam/tn/education/data/chr_abs_School-Level_Suppression_2016-17.xls",
        ])

        # Discipline / Suspensions
        urls.extend([
            "https://www.tn.gov/content/dam/tn/education/data/discipline-district-2425.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline-school-2425.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline-district-2324.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline-school-2324.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline_district_suppressed_formatted_2022-23.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline_school_suppressed_formatted_2022-23.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district-discipline-2021-22-2023-06-05.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-discipline-2021-22-2023-06-05.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district-discipline-2020-21-2023-06-05.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-discipline-2020-21-2023-06-05.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/district-discipline-2019-20-2023-06-05.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/school-discipline-2019-20-2023-06-05.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline/discipline_201819.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/demo/discipline_2017-18.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline/data_discipline_2016-17.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline/data_discipline_2015-16.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline/data_discipline_2014-15.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline/data_discipline_2013-14.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/discipline/data_discipline_2012-13.xlsx",
        ])

        # Dropout Rates
        urls.extend([
            "https://www.tn.gov/content/dam/tn/education/data/2024-25_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2024-25_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2024-25_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2023-24_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2023-24_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2023-24_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2022-23_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2022-23_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2022-23_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2021-22_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2021-22_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2021-22_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2020-21_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2020-21_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2020-21_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2019-20_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2019-20_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2019-20_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2018-19_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2018-19_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2018-19_school_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2017-18_state_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2017-18_district_dropout_rate_suppressed.xlsx",
            "https://www.tn.gov/content/dam/tn/education/data/2017-18_school_dropout_rate_suppressed.xlsx",
        ])

        for url in urls:
            self._download_static_file(url, dest_dir, "enrollment_attendance")

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------
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

            clean_filename = filename.replace('$', '').replace(' ', '_').replace('%20', '_')
            
            # De-duplicate check
            existing = [f.name for f in dest_dir.iterdir() if f.is_file()]
            if clean_filename in existing:
                return

            yr = parse_year_range(clean_filename)
            if DUPLICATE_DETECTION and is_duplicate(clean_filename, yr, existing):
                return

            self.logger.info("Downloading TN file: %s", clean_filename)
            f_resp = self.session.get(full_url, timeout=120)
            if f_resp.status_code == 200:
                dest = dest_dir / clean_filename
                dest.write_bytes(f_resp.content)
                size_kb = len(f_resp.content) / 1024
                
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
                self.logger.info("Saved TN static file: %s (%.1f KB)", clean_filename, size_kb)
            else:
                self.logger.warning("Failed download for TN static file: %s (HTTP %d)", clean_filename, f_resp.status_code)
            
            time.sleep(0.3)
        except Exception as ex:
            self.logger.error("Error downloading file %s: %s", full_url, ex)

    def _crawl_and_download(self, url: str, dest_dir: Path, category: str, max_depth: int = 1, current_depth: int = 1, path_filter: str = "") -> None:
        """Crawl the given page and download any static files found."""
        try:
            clean_url = url.split('#')[0].replace(" ", "%20")
            self.logger.info("Crawling TN page [depth %d/%d]: %s", current_depth, max_depth, clean_url)
            resp = self.session.get(clean_url, timeout=60)
            if resp.status_code != 200:
                return

            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                val = a['href']
                if not val:
                    continue
                abs_url = urljoin(clean_url, val)
                abs_url_clean = abs_url.split('#')[0]

                # We only want to follow links that remain on tn.gov to avoid escaping
                parsed_abs = urllib.parse.urlparse(abs_url_clean)
                if "tn.gov" not in parsed_abs.netloc:
                    continue

                if any(abs_url_clean.lower().split('?')[0].endswith(ext) for ext in ['.xlsx', '.xls', '.csv', '.pdf', '.docx', '.zip', '.txt']):
                    if "content/dam/" in abs_url_clean.lower() or "/documents/" in abs_url_clean.lower() or "/reports/" in abs_url_clean.lower() or "/data/" in abs_url_clean.lower():
                        self._download_static_file(abs_url_clean, dest_dir, category)
                elif current_depth < max_depth:
                    if path_filter and path_filter in abs_url_clean.lower():
                        self._crawl_and_download(abs_url_clean, dest_dir, category, max_depth, current_depth + 1, path_filter)
        except Exception as e:
            self.logger.error("Crawl error on TN page %s: %s", url, e)


if __name__ == "__main__":
    TennesseeDownloader().download_all()
