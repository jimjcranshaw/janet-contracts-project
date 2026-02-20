import requests
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("download_fts_sample")

url = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
# Get last 2 days of data to ensure we get something
from datetime import datetime, timedelta
yesterday = (datetime.now() - timedelta(days=2)).isoformat() + "Z"

params = {
    "updatedFrom": yesterday,
    "limit": 100
}

try:
    logger.info(f"Downloading FTS sample from {url}...")
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    
    data = r.json()
    os.makedirs("data", exist_ok=True)
    with open("data/fts_sample.json", "w") as f:
        json.dump(data, f, indent=2)
        
    logger.info(f"Successfully downloaded FTS sample. bytes: {len(r.content)}")
    print(f"SAMPLE_DOWNLOADED: data/fts_sample.json")
    
except Exception as e:
    logger.error(f"Error downloading FTS sample: {e}")
