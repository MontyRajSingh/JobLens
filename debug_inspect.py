"""
Inspect actual DOM for the failing scrapers. Dumps page source to files
so we can find the real CSS selectors.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from utils.driver_utils import setup_driver
from bs4 import BeautifulSoup

PAGES = {
    "levelsfyi": "https://www.levels.fyi/jobs?searchText=data+scientist&location=New+York",
    "payscale": "https://www.payscale.com/research/US/Job=Data_Scientist/Salary",
    "salarycom": "https://www.salary.com/research/salary/benchmark/data-scientist-salary",
    "wellfound": "https://wellfound.com/role/data-scientist",
}

os.makedirs("debug_dumps", exist_ok=True)

for name, url in PAGES.items():
    print(f"\n─── {name}: {url}")
    driver = None
    try:
        driver = setup_driver()
        driver.get(url)
        time.sleep(6)

        # Scroll
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        html = driver.page_source
        with open(f"debug_dumps/{name}.html", "w", encoding="utf-8") as f:
            f.write(html)

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        # Save first 3000 chars of text
        with open(f"debug_dumps/{name}_text.txt", "w", encoding="utf-8") as f:
            f.write(text[:5000])

        print(f"    Saved HTML ({len(html)} bytes) and text ({len(text)} chars)")
        print(f"    Title: {soup.title.string if soup.title else 'N/A'}")

        # Look for job-related elements
        for sel in ["a[href*='job']", "[class*='job']", "[class*='Job']",
                     "[class*='listing']", "[class*='result']", "[class*='card']",
                     "[class*='salary']", "[class*='Salary']", "[data-testid]"]:
            els = soup.select(sel)
            if els:
                print(f"    {sel}: {len(els)} elements found")

    except Exception as e:
        print(f"    ERROR: {e}")
    finally:
        if driver:
            try: driver.quit()
            except: pass

print("\n✅ Done. Check debug_dumps/ for HTML and text files.")
