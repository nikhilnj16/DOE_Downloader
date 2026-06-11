import requests
from bs4 import BeautifulSoup

url = "https://profiles.doe.mass.edu/statereport/mcas.aspx"
resp = requests.get(url)
soup = BeautifulSoup(resp.text, 'html.parser')

for select in soup.find_all('select'):
    print(f"Select Name: {select.get('name')} ID: {select.get('id')}")
    options = select.find_all('option')
    print(f"  Options ({len(options)}):")
    for opt in options[:5]:
        print(f"    - Text: '{opt.text.strip()}' Value: '{opt.get('value')}'")
    if len(options) > 5:
        print("    ... and more")
