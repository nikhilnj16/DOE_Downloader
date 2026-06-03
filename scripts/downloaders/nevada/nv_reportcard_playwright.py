"""
Nevada Report Card Playwright Scraper
======================================
Extracts data from the dynamic Next.js/Vue portal at nevadareportcard.nv.gov.

Instead of fighting the UI to find hidden export buttons, this script uses
Playwright's network interception to capture the raw JSON data that the
dashboard fetches from the backend API (`DIWAPI-NVReportCard/api/SummaryScores`).

This ensures we get the cleanest, most structured version of the data without
worrying about UI layout changes.
"""

import sys
import os
import json
import time
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.downloaders.base_downloader import BaseDownloader


class NevadaReportCardScraper(BaseDownloader):
    STATE = "nevada"
    CATEGORY = "reportcard_json"
    
    def __init__(self):
        super().__init__()
        # We will save the intercepted JSONs in test_scores and enrollment
        self.scores_dir = self.output_dir / "test_scores"
        self.enroll_dir = self.output_dir / "enrollment"
        self.scores_dir.mkdir(parents=True, exist_ok=True)
        self.enroll_dir.mkdir(parents=True, exist_ok=True)
        self.scores_dir.mkdir(parents=True, exist_ok=True)
        self.enroll_dir.mkdir(parents=True, exist_ok=True)

    def download_all(self):
        self.logger.info("Starting Playwright to scrape Nevada Report Card...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            
            # 1. Setup Network Interception
            def handle_response(response):
                if "DIWAPI-NVReportCard/api/SummaryScores" in response.url or "DIWAPI-NVReportCard/api/RosterScores" in response.url:
                    try:
                        data = response.json()
                        if not isinstance(data, list) or len(data) == 0:
                            return
                            
                        # Parse URL to get report name
                        parsed = urllib.parse.urlparse(response.url)
                        params = urllib.parse.parse_qs(parsed.query)
                        
                        report_name = params.get('report', ['unknown'])[0]
                        domain = params.get('domain', ['unknown'])[0]
                        org_id = params.get('organizationId', params.get('organization', ['unknown']))[0]
                        
                        # Decide where to save based on report type
                        out_dir = self.enroll_dir if 'student' in domain.lower() else self.scores_dir
                        
                        filename = f"{domain}_{report_name}_org{org_id}.json".replace('/', '_')
                        filepath = out_dir / filename
                        
                        with open(filepath, "w") as f:
                            json.dump(data, f, indent=2)
                            
                        self.logger.info(f"Intercepted API data: saved {len(data)} records to {filename}")
                    except Exception as e:
                        pass
                        
            page.on("response", handle_response)
            
            # 2. Navigate and bypass modal
            self.logger.info("Loading portal home page...")
            page.goto("https://nevadareportcard.nv.gov/di/", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            
            close_btn = page.locator(".modal__close").first
            if close_btn.count() > 0:
                close_btn.click()
                page.wait_for_timeout(1000)
                
            # 3. Set context to State
            self.logger.info("Setting context to 'State' level...")
            state_btn = page.locator("text=I want to see State")
            if state_btn.count() > 0:
                state_btn.first.click()
            else:
                page.get_by_text("State", exact=True).first.click()
            page.wait_for_timeout(2000)
            
            # 4. Open Domains Dashboard
            self.logger.info("Opening Data Details dashboard...")
            page.evaluate("DataPortal.Nav.ToDashboard('domains')")
            page.wait_for_timeout(4000)
            
            # 5. Click through the main data tabs to trigger API fetches
            tabs_to_click = ["Students", "Achievement", "Graduation", "Safety"]
            
            for tab_name in tabs_to_click:
                self.logger.info(f"Clicking top-level tab: {tab_name}")
                tab = page.locator(f"a:text-is('{tab_name}')").first
                if tab.count() > 0 and tab.is_visible():
                    tab.click()
                    page.wait_for_timeout(3000)
                    
                    # 6. Click through the side menu items for this tab
                    # The side menu items are usually in a specific container, but we can just find all links in the left column
                    # To be safe, we'll just click links that are visible and look like sidebar items
                    sidebar_items = page.locator(".domain-menu a, .report-list a, .nav-stacked a").all()
                    
                    if not sidebar_items:
                        # Fallback if specific class isn't found
                        self.logger.debug(f"Sidebar classes not found for {tab_name}, skipping deep click")
                        continue
                        
                    for i in range(len(sidebar_items)):
                        # Re-query to avoid stale elements
                        items = page.locator(".domain-menu a, .report-list a, .nav-stacked a").all()
                        if i < len(items) and items[i].is_visible():
                            name = items[i].inner_text().strip()
                            if name:
                                self.logger.info(f"  -> Loading sub-report: {name}")
                                items[i].click()
                                page.wait_for_timeout(2500) # Wait for network request to fire and complete
                else:
                    self.logger.warning(f"Tab '{tab_name}' not found or not visible.")

            browser.close()
            self.logger.info("Finished scraping Nevada Report Card.")

if __name__ == "__main__":
    scraper = NevadaReportCardScraper()
    scraper.download_all()
