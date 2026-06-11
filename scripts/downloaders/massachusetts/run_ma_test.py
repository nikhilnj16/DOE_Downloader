import sys
from pathlib import Path

# Add the project root to the python path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.downloaders.massachusetts.ma_base_scraper import MABaseScraper

def main():
    print("Running Massachusetts downloaders with a limit of 10 combinations per category...")
    
    scraper = MABaseScraper()
    
    print("\n--- Running Enrollment ---")
    scraper.download_report('enrollmentbygrade.aspx', 'data/massachusetts/raw/enrollment', 'enrollment', report_type='District', limit=10)
    
    print("\n--- Running Test Scores ---")
    scraper.download_report('mcas.aspx', 'data/massachusetts/raw/test_scores', 'test_scores', report_type='District', limit=10)
    
    print("\n--- Running Suspensions ---")
    scraper.download_report('ssdr.aspx', 'data/massachusetts/raw/suspensions', 'suspensions', report_type='District', limit=10)
    
    print("\n--- Running Teacher Records ---")
    scraper.download_report('teacherdata.aspx', 'data/massachusetts/raw/teacher_records', 'teacher_records', report_type='District', limit=10)
    
    print("\n--- Running Financials ---")
    scraper.download_report('ppx.aspx', 'data/massachusetts/raw/financials', 'financials', report_type='District', limit=10)

if __name__ == "__main__":
    main()
