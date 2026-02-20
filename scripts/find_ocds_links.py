import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("find_urls")

urls = [
    "https://data.open-contracting.org/en/publication-dataset/united-kingdom-contracts-finder/",
    "https://data-registry.open-contracting.org/en/publication-dataset/united-kingdom-contracts-finder/"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for url in urls:
    try:
        logger.info(f"Scraping {url}...")
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        links = soup.find_all('a', href=True)
        found = False
        for a in links:
            href = a['href']
            if '2024' in href and ('.json' in href or '.gz' in href):
                print(f"FOUND: {href}")
                found = True
        if not found:
            logger.info("No matching links found on this page.")
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
