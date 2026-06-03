from ma_base_scraper import MABaseScraper

def main():
    scraper = MABaseScraper()
    scraper.download_report(
        report_endpoint='mcas.aspx',
        output_dir='../../../data/massachusetts/raw/test_scores',
        dataset_name='test_scores',
        report_type='District'
    )

if __name__ == '__main__':
    main()
