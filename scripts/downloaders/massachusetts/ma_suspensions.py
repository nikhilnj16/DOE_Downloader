from ma_base_scraper import MABaseScraper

def main():
    scraper = MABaseScraper()
    scraper.download_report(
        report_endpoint='ssdr.aspx',
        output_dir='../../../data/massachusetts/raw/suspensions',
        dataset_name='suspensions',
        report_type='District'
    )

if __name__ == '__main__':
    main()
