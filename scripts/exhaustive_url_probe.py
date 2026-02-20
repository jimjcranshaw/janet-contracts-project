import requests
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("url_probe")

base_urls = [
    "https://data.open-contracting.org/downloads/",
    "https://data-registry.open-contracting.org/downloads/",
    "https://data.open-contracting.org/publication-dataset/",
    "https://data.open-contracting.org/en/publication-dataset/"
]

slugs = [
    "united-kingdom/contracts-finder",
    "united_kingdom_contracts_finder",
    "united-kingdom-contracts-finder",
    "contracts-finder",
    "gbr-contracts-finder",
    "gbr/contracts-finder"
]

files = [
    "2024.jsonl.gz",
    "2024.json.gz",
    "2024.zip",
    "all.jsonl.gz",
    "all.json.gz"
]

def check_url(url):
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        if r.status_code == 200:
            print(f"FOUND: {url} | Size: {r.headers.get('Content-Length')}")
            return url
    except:
        pass
    return None

test_urls = []
for base in base_urls:
    for slug in slugs:
        for f in files:
            test_urls.append(f"{base}{slug}/{f}")

print(f"Testing {len(test_urls)} permutations...")

with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(check_url, test_urls))

found = [r for r in results if r]
if not found:
    print("No URLs found.")
else:
    print(f"\nDiscovered {len(found)} working links.")
