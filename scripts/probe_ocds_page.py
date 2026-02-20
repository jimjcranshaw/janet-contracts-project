import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("probe_page")

# Likely slugs from OCP registry
slugs = [
    "united-kingdom-contracts-finder",
    "united_kingdom_contracts_finder",
    "united-kingdom",
    "gbr-contracts-finder",
    "gb-contracts-finder",
    "contracts-finder"
]

base_urls = [
    "https://data.open-contracting.org/en/publication-dataset/",
    "https://data.open-contracting.org/en/publication/",
    "https://data.open-contracting.org/en/dataset/"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for base in base_urls:
    for slug in slugs:
        url = f"{base}{slug}/"
        try:
            r = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
            if r.status_code == 200:
                logger.info(f"PAGE FOUND: {url}")
                # Now try to get the full page and find JSON links
                pagesrc = requests.get(url, headers=headers).text
                if "2024" in pagesrc:
                    logger.info(f"Page contains '2024': {url}")
                    # Look for links
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(pagesrc, 'html.parser')
                    for a in soup.find_all('a', href=True):
                        if '2024' in a['href'] and ('.json' in a['href'] or '.gz' in a['href']):
                            print(f"DOWNLOAD_LINK_FOUND: {a['href']}")
        except Exception as e:
            pass
