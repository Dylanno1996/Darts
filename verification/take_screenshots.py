from playwright.sync_api import sync_playwright
import time

def generate_visuals():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1600, "height": 1200})

        print("Navigating...")
        page.goto("http://localhost:8501")
        page.wait_for_selector("text=IDL Stats", timeout=20000)
        time.sleep(3)

        # 1. Player Stats Tab
        print("Capturing Player Stats...")
        try:
            page.get_by_role("tab", name="📊 Player Stats").click()
        except:
            page.locator("div[data-testid='stTabs'] button").nth(3).click()

        time.sleep(3)
        page.screenshot(path="verification/player_stats_table.png")
        page.screenshot(path="verification/full_overview.png", full_page=True)

        # 2. Individual Tab
        print("Capturing Individual Tab...")
        try:
            page.get_by_role("tab", name="👤 Individual").click()
        except:
            page.locator("div[data-testid='stTabs'] button").nth(4).click()

        time.sleep(3)

        # Capture Trend Section
        trend_header = page.locator("h3:has-text('Average Over Time')")
        if trend_header.is_visible():
            # Scroll to it
            trend_header.scroll_into_view_if_needed()
            time.sleep(1)
            page.screenshot(path="verification/individual_trend.png")

        # Capture H2H Section
        h2h_header = page.locator("h3:has-text('Head-to-Head')")
        if h2h_header.is_visible():
            h2h_header.scroll_into_view_if_needed()
            time.sleep(1)
            page.screenshot(path="verification/individual_h2h.png")

        browser.close()
        print("Done.")

if __name__ == "__main__":
    try:
        generate_visuals()
    except Exception as e:
        print(f"Error: {e}")
