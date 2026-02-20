import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("check_download")

# Inferred patterns from OCP registry
urls = [
    "https://data.open-contracting.org/downloads/united-kingdom/contracts-finder/2024.jsonl.gz",
    "https://data-registry.open-contracting.org/downloads/united-kingdom/contracts-finder/2024.jsonl.gz",
    "https://data.open-contracting.org/downloads/united-kingdom/contracts-finder/2024.json.gz",
    "https://data-registry.open-contracting.org/downloads/united-kingdom/contracts-finder/2024.json.gz",
    "https://data.open-contracting.org/downloads/united-kingdom/contracts-finder/2024.zip",
    "https://data.open-contracting.org/downloads/united-kingdom-contracts-finder/2024.jsonl.gz",
    "https://data.open-contracting.org/downloads/united-kingdom/contracts-finder/all.jsonl.gz"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for url in urls:
    try:
        r = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
        logger.info(f"URL: {url} | Status: {r.status_code}")
        if r.status_code == 200:
            print(f"SUCCESS: {url}")
            print(f"Content-Type: {r.headers.get('Content-Type')}")
            print(f"Content-Length: {r.headers.get('Content-Length')}")
    except Exception as e:
        logger.error(f"Error checking {url}: {e}")
