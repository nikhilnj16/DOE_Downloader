from ma_base_scraper import MABaseScraper

def main():
    scraper = MABaseScraper()
    scraper.download_report(
        report_endpoint='enrollmentbygrade.aspx',
        output_dir='../../../data/massachusetts/raw/enrollment',
        dataset_name='enrollment',
        report_type='District'
    )

if __name__ == '__main__':
    main()
