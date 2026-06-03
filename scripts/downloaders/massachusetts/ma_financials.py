from ma_base_scraper import MABaseScraper

def main():
    scraper = MABaseScraper()
    scraper.download_report(
        report_endpoint='ppx.aspx',
        output_dir='../../../data/massachusetts/raw/financials',
        dataset_name='financials',
        report_type='District'
    )

if __name__ == '__main__':
    main()
