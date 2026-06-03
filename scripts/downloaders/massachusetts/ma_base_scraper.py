import os
import requests
from bs4 import BeautifulSoup
import time
from pathlib import Path

class MABaseScraper:
    def __init__(self):
        self.base_url = "https://profiles.doe.mass.edu/statereport/"
        self.session = requests.Session()
        
        # We will use this to fake a realistic user-agent if needed, 
        # though MA DOE doesn't seem to block default requests yet.
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        })
        
    def download_report(self, report_endpoint: str, output_dir: str, dataset_name: str, report_type: str = 'District'):
        """
        Downloads the specified ASP.NET WebForm report for all available years.
        
        :param report_endpoint: The endpoint e.g., 'enrollmentbygrade.aspx'
        :param output_dir: The directory to save the files (e.g., 'data/massachusetts/raw/enrollment/')
        :param dataset_name: Prefix for the downloaded files
        :param report_type: 'District', 'School', or 'State'
        """
        url = self.base_url + report_endpoint
        print(f"[{dataset_name}] Accessing {url} ...")
        
        # 1. GET request to fetch viewstate and available years
        resp = self.session.get(url)
        if resp.status_code != 200:
            print(f"[{dataset_name}] Failed to load page: HTTP {resp.status_code}")
            return
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        try:
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
            viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']
            eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']
        except TypeError:
            print(f"[{dataset_name}] Could not find ASP.NET hidden fields. Ensure this is a WebForm page.")
            return

        # Parse available years
        year_select = soup.find('select', {'id': 'ctl00_ContentPlaceHolder1_ddYear'})
        if not year_select:
            print(f"[{dataset_name}] Could not find year dropdown.")
            return
            
        years = [option['value'] for option in year_select.find_all('option')]
        print(f"[{dataset_name}] Found {len(years)} available years: {min(years)} to {max(years)}")
        
        # Find the correct value for the requested report_type
        report_type_val = report_type
        type_select = soup.find('select', {'id': 'ctl00_ContentPlaceHolder1_ddReportType'})
        if type_select:
            for option in type_select.find_all('option'):
                if option.text.strip().lower() == report_type.lower():
                    report_type_val = option['value']
                    break
        
        # Build base data payload with ALL select tags to satisfy ASP.NET
        base_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstategen,
            '__EVENTVALIDATION': eventvalidation,
            'ctl00$ContentPlaceHolder1$hfExport': 'Excel'
        }
        
        for select in soup.find_all('select'):
            name = select.get('name')
            if not name: continue
            
            # Find the selected option or fallback to the first option
            selected = select.find('option', selected=True)
            if selected and selected.has_attr('value'):
                val = selected['value']
            elif select.find('option') and select.find('option').has_attr('value'):
                val = select.find('option')['value']
            else:
                val = ''
                
            base_data[name] = val
            
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 2. Iterate and POST to download Excel for each year
        for year in years:
            print(f"  Downloading {year}...")
            
            data = base_data.copy()
            if type_select and type_select.get('name'):
                data[type_select.get('name')] = report_type_val
            data['ctl00$ContentPlaceHolder1$ddYear'] = year
            
            post_resp = self.session.post(url, data=data)
            
            if post_resp.status_code == 200 and 'Excel' in post_resp.headers.get('Content-Type', '') or 'spreadsheet' in post_resp.headers.get('Content-Type', '') or post_resp.headers.get('Content-Disposition', '').find('attachment') != -1:
                # Determine extension based on content type or bytes
                ext = '.xlsx'
                if len(post_resp.content) > 0 and post_resp.content[:4] == b'\xd0\xcf\x11\xe0':
                    ext = '.xls' # Old OLE format
                elif len(post_resp.content) > 0 and post_resp.content[:2] == b'PK':
                    ext = '.xlsx'
                else:
                    ext = '.xls' # fallback
                    
                filename = f"{dataset_name}_{report_type.lower()}_{year}{ext}"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(post_resp.content)
                
                print(f"    Saved to {filepath} ({len(post_resp.content)} bytes)")
            else:
                print(f"    Failed to download for year {year}. Status: {post_resp.status_code}")
                
            time.sleep(1) # Be nice to the server
            
        print(f"[{dataset_name}] Completed downloading {len(years)} files.")
