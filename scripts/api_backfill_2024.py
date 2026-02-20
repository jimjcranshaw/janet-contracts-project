import requests
import json
import time
import os
import logging
from datetime import datetime
from app.database import SessionLocal
from app.models import ServiceProfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_backfill")

BASE_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

class MeshFilter:
    def __init__(self):
        self.cpv_prefixes = self._load_mesh()

    def _load_mesh(self):
        db = SessionLocal()
        try:
            profiles = db.query(ServiceProfile).all()
            cpv_pool = set()
            for p in profiles:
                if p.inferred_cpv_codes:
                    cpv_pool.update(c[:4] for c in p.inferred_cpv_codes)
            logger.info(f"MeshFilter loaded with {len(cpv_pool)} CPV prefixes.")
            return cpv_pool
        finally:
            db.close()

    def is_match(self, release):
        """Checks if any CPV code in the release matches the mesh."""
        cpv_codes = [c.get('code') for c in release.get('tender', {}).get('items', []) if c.get('code')]
        if not cpv_codes:
            # Check other locations for CPVs in OCDS if needed
            return False
            
        for code in cpv_codes:
            if code[:4] in self.cpv_prefixes:
                return True
        return False

def fetch_period(start_date, end_date, mesh_filter):
    """Fetches and filters OCDS release packages for a specific date range."""
    page = 1
    total_found = 0
    total_kept = 0
    all_releases = []

    while True:
        logger.info(f"Fetching {start_date} to {end_date} - Page {page}...")
        try:
            params = {
                "publishedFrom": f"{start_date}T00:00:00Z",
                "publishedTo": f"{end_date}T23:59:59Z",
                "page": page
            }
            r = requests.get(BASE_URL, params=params, timeout=30)
            if r.status_code == 429:
                logger.warning("Rate limited. Sleeping 10s...")
                time.sleep(10)
                continue
            r.raise_for_status()
            
            data = r.json()
            releases = data.get("releases", [])
            if not releases:
                break
                
            total_found += len(releases)
            filtered = [r for r in releases if mesh_filter.is_match(r)]
            total_kept += len(filtered)
            all_releases.extend(filtered)
            
            if page % 50 == 0:
                logger.info(f"Progress: Page {page} | Found: {total_found} | Kept: {total_kept} (Mesh Match)")
            
            if len(releases) < 20: 
                break
            
            page += 1
            time.sleep(1) 
            
        except Exception as e:
            logger.error(f"Error on page {page}: {e}")
            break

    logger.info(f"Period complete. Found {total_found}, Kept {total_kept} (Mesh Match).")
    return all_releases

def run_backfill_2024():
    os.makedirs("data/backfill_2024", exist_ok=True)
    mesh_filter = MeshFilter()
    
    # Iterate through 2024 month by month
    for month in range(1, 13):
        start = f"2024-{month:02d}-01"
        end = f"2024-{month:02d}-31" 
        if month == 2: end = "2024-02-29"
        if month in [4, 6, 9, 11]: end = f"2024-{month:02d}-30"

        logger.info(f"--- Processing {start} ---")
        releases = fetch_period(start, end, mesh_filter)
        
        if releases:
            package = {
                "releases": releases,
                "publishedDate": datetime.now().isoformat() + "Z",
                "publisher": {"name": "Grants AI Backfill Service (Filtered)"}
            }
            
            with open(f"data/backfill_2024/{start}.json", "w") as f:
                json.dump(package, f)
                
            logger.info(f"Saved {len(releases)} mesh-matched records to data/backfill_2024/{start}.json")
        else:
            logger.info(f"No mesh-matched records for {start}. Skipping file creation.")

if __name__ == "__main__":
    run_backfill_2024()
