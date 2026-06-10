
import time
from playwright.sync_api import sync_playwright
import os

def debug_bet365():
    """
    Diagnostic script to dump HTML and take a screenshot of Bet365 Tennis.
    Used to find correct selectors for the PRO scraper.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        url = "https://www.bet365.it/#/AS/B13/"
        print(f"Connecting to {url}...")
        
        page.goto(url, wait_until="networkidle")
        print("Waiting for page hydration...")
        page.wait_for_timeout(15000) # Give it plenty of time
        
        # Take a high-res screenshot
        page.screenshot(path="debug_bet365_hd.png")
        print("Screenshot saved as debug_bet365_hd.png")
        
        # Dump some HTML for analysis
        html = page.content()
        with open("debug_bet365_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML dump saved as debug_bet365_dump.html")
        
        # Check for participant names in the dump
        candidates = ["Alcaraz", "Sinner", "Djokovic", "Medvedev", "Fokina", "Tien"]
        for c in candidates:
            if c.lower() in html.lower():
                print(f"Found candidate '{c}' in the HTML dump!")
                
        # Try to find elements that look like match rows
        match_rows = page.query_selector_all(".gl-MarketGroup")
        print(f"Number of .gl-MarketGroup found: {len(match_rows)}")
        
        browser.close()

if __name__ == "__main__":
    debug_bet365()
