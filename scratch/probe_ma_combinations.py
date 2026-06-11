import requests
from bs4 import BeautifulSoup
import itertools
import random
import re

url = "https://profiles.doe.mass.edu/statereport/mcas.aspx"
session = requests.Session()
resp = session.get(url)
soup = BeautifulSoup(resp.text, 'html.parser')

viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value']
eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']

selects = {}
friendly_names = {}

for select in soup.find_all('select'):
    name = select.get('name')
    if not name: continue
    
    options = []
    for opt in select.find_all('option'):
        if opt.has_attr('value') and opt['value'] != '':
            options.append(opt['value'])
            friendly_names[opt['value']] = opt.text.strip()
            
    if options:
        selects[name] = options

print("Selects found:", list(selects.keys()))

# Generate cartesian product
keys = list(selects.keys())
lists = [selects[k] for k in keys]
combinations = list(itertools.product(*lists))

print(f"Total combinations possible: {len(combinations)}")

# Pick 3 random combinations for the probe
sample = random.sample(combinations, 3)

for combo in sample:
    data = {
        '__VIEWSTATE': viewstate,
        '__VIEWSTATEGENERATOR': viewstategen,
        '__EVENTVALIDATION': eventvalidation,
        'ctl00$ContentPlaceHolder1$hfExport': 'Excel'
    }
    
    filename_parts = ["mcas"]
    for i, key in enumerate(keys):
        val = combo[i]
        data[key] = val
        
        # Sanitize friendly name
        friendly = friendly_names[val]
        friendly = re.sub(r'[^a-zA-Z0-9]+', '_', friendly).strip('_').lower()
        filename_parts.append(friendly)
        
    filename = "_".join(filename_parts) + ".xlsx"
    print(f"Trying combination -> {filename}")
    
    post_resp = session.post(url, data=data)
    if post_resp.status_code == 200 and 'Excel' in post_resp.headers.get('Content-Type', ''):
        print(f"  SUCCESS! Downloaded {len(post_resp.content)} bytes")
    else:
        print(f"  FAILED. Status {post_resp.status_code}, Content-Type: {post_resp.headers.get('Content-Type', '')}")
