from ma_base_scraper import MABaseScraper

def main():
    scraper = MABaseScraper()
    scraper.download_report(
        report_endpoint='teacherdata.aspx',
        output_dir='../../../data/massachusetts/raw/teacher_records',
        dataset_name='teacher_records',
        report_type='District'
    )

if __name__ == '__main__':
    main()
