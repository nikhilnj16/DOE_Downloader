import os
import requests
from bs4 import BeautifulSoup
import time
from pathlib import Path
import itertools
import random
import re

class MABaseScraper:
    def __init__(self):
        self.base_url = "https://profiles.doe.mass.edu/statereport/"
        self.session = requests.Session()
        
        # We will use this to fake a realistic user-agent if needed, 
        # though MA DOE doesn't seem to block default requests yet.
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        })
        
    def download_report(self, report_endpoint: str, output_dir: str, dataset_name: str, report_type: str = 'District', limit: int = None):
        """
        Downloads the specified ASP.NET WebForm report for random combinations of filters.
        
        :param report_endpoint: The endpoint e.g., 'enrollmentbygrade.aspx'
        :param output_dir: The directory to save the files (e.g., 'data/massachusetts/raw/enrollment/')
        :param dataset_name: Prefix for the downloaded files
        :param report_type: Used as a fallback or default, but combinations handle all selects.
        :param limit: Maximum number of random combinations to download (e.g., 10 for testing)
        """
        url = self.base_url + report_endpoint
        print(f"[{dataset_name}] Accessing {url} ...")
        
        # 1. GET request to fetch viewstate and valid options
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

        # Build base data payload
        base_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstategen,
            '__EVENTVALIDATION': eventvalidation,
            'ctl00$ContentPlaceHolder1$hfExport': 'Excel'
        }

        # Dynamically extract all <select> tags and their options
        selects_options = {}
        friendly_names = {}
        
        for select in soup.find_all('select'):
            name = select.get('name')
            if not name: continue
            
            options = []
            for opt in select.find_all('option'):
                val = opt.get('value')
                if val is not None and val != '':
                    options.append(val)
                    # Use a short, sanitized friendly name
                    raw_text = opt.text.strip()
                    friendly = re.sub(r'[^a-zA-Z0-9]+', '_', raw_text).strip('_').lower()
                    if not friendly:
                        friendly = "opt"
                    friendly_names[val] = friendly
                    
            if options:
                selects_options[name] = options

        if not selects_options:
            print(f"[{dataset_name}] No select dropdowns found. Cannot generate combinations.")
            return

        select_names = list(selects_options.keys())
        options_lists = [selects_options[k] for k in select_names]
        
        # Generate Cartesian product
        combinations = list(itertools.product(*options_lists))
        print(f"[{dataset_name}] Found {len(combinations)} total possible filter combinations.")

        if limit is not None and limit < len(combinations):
            print(f"[{dataset_name}] Randomly sampling {limit} combinations...")
            # Use a fixed seed based on dataset_name to be reproducible but different per dataset
            random.seed(hash(dataset_name))
            sample = random.sample(combinations, limit)
        else:
            sample = combinations

        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 2. Iterate and POST to download Excel for each combination
        for i, combo in enumerate(sample):
            data = base_data.copy()
            
            # Populate data payload and build dynamic filename
            filename_parts = [dataset_name]
            for j, select_name in enumerate(select_names):
                val = combo[j]
                data[select_name] = val
                friendly_text = friendly_names[val]
                # Try to keep filename from getting insanely long by truncating very long parts
                if len(friendly_text) > 20:
                    friendly_text = friendly_text[:20]
                filename_parts.append(friendly_text)
            
            # Some reports might have no data or just be very generic, 
            # so we ensure it's a unique name by appending index if needed, but the combo should be unique
            filename = "_".join(filename_parts) + ".xlsx"
            filepath = os.path.join(output_dir, filename)
            
            print(f"  Downloading [{i+1}/{len(sample)}]: {filename}")
            
            post_resp = self.session.post(url, data=data)
            
            content_type = post_resp.headers.get('Content-Type', '').lower()
            is_excel = 'excel' in content_type or 'spreadsheet' in content_type or 'openxmlformats' in content_type
            is_attachment = 'attachment' in post_resp.headers.get('Content-Disposition', '').lower()
            
            if post_resp.status_code == 200 and (is_excel or is_attachment):
                # Determine extension based on content type or bytes
                ext = '.xlsx'
                if len(post_resp.content) > 0 and post_resp.content[:4] == b'\xd0\xcf\x11\xe0':
                    ext = '.xls' # Old OLE format
                elif len(post_resp.content) > 0 and post_resp.content[:2] == b'PK':
                    ext = '.xlsx'
                else:
                    ext = '.xls' # fallback
                
                # if the extension was resolved to xls, fix the filepath
                if ext == '.xls':
                    filepath = filepath[:-5] + ext
                    
                with open(filepath, 'wb') as f:
                    f.write(post_resp.content)
                
                print(f"    Saved ({len(post_resp.content)} bytes)")
            else:
                print(f"    Failed. HTTP: {post_resp.status_code}, Content-Type: {content_type}")
                
            time.sleep(1) # Be nice to the server
            
        print(f"[{dataset_name}] Completed downloading {len(sample)} files.")
