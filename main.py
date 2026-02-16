from tools.search import search_startups
from tools.scraper import scrape_url
from tools.extractor import extract_startup_info

query = "Indian startup founded in 2025"

urls = search_startups(query)

collected = []

for url in urls:
    print(f"\nProcessing: {url}")

    text = scrape_url(url)
    if not text:
        continue

    startup = extract_startup_info(text)
    if startup:
        startup.source_url = url
        collected.append(startup)
        print("Extracted:", startup.startup_name)

print(f"\nTotal collected: {len(collected)}")
