from playwright.sync_api import sync_playwright
import time

def generate_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Navigate to the app
        print("Navigating to app...")
        page.goto("http://localhost:8501")

        # Wait for Streamlit to load
        print("Waiting for load...")
        page.wait_for_selector("text=IDL Stats", timeout=20000)

        # 2. Click on the "Experimental Stats" tab
        # Streamlit tabs are usually buttons with role "tab"
        print("Clicking tab...")
        page.get_by_role("tab", name="🧪 Experimental Stats").click()

        # Wait for the tab content to load
        # Look for headers we added
        page.wait_for_selector("text=Experimental Statistics", timeout=10000)
        time.sleep(3) # Extra wait for charts to render

        # 3. Take screenshots
        print("Taking screenshots...")

        # Full page
        page.screenshot(path="verification/experimental_stats_full.png", full_page=True)

        # Section 1: Player Averages
        avg_section = page.locator("h3:has-text('Player Averages')").locator("..")
        # Just take viewport screenshot of top part
        page.set_viewport_size({"width": 1280, "height": 800})
        page.screenshot(path="verification/experimental_stats_top.png")

        # Scroll down to see charts
        page.evaluate("window.scrollBy(0, 800)")
        time.sleep(1)
        page.screenshot(path="verification/experimental_stats_middle.png")

        page.evaluate("window.scrollBy(0, 800)")
        time.sleep(1)
        page.screenshot(path="verification/experimental_stats_bottom.png")

        browser.close()
        print("Done.")

if __name__ == "__main__":
    try:
        generate_screenshots()
    except Exception as e:
        print(f"Error: {e}")
