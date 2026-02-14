import requests
import time
import logging
from typing import Iterator, Dict, Optional
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class FTSClient:
    """
    Client for 'Find a Tender' Service (FTS) OCDS API.
    Docs: https://www.find-tender.service.gov.uk/api/1.0/ocds/documentation
    """
    BASE_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _get_page(self, url: str) -> Dict:
        """Helper to fetch a single page with retry logic."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=self.timeout)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e.response.status_code}")
            # Log first 500 chars of body to avoid massive logs if it's HTML
            logger.error(f"Response Body (partial): {e.response.text[:500]}")
            raise
        return response.json()

    def fetch_releases(self, updated_after: datetime) -> Iterator[Dict]:
        """
        Yields individual releases from the FTS API starting from `updated_after`.
        """
        # Format date as ISO 8601 (e.g., 2023-10-01T00:00:00Z)
        params = f"?updatedFrom={updated_after.strftime('%Y-%m-%dT00:00:00Z')}"
        next_url = f"{self.BASE_URL}{params}"

        logger.info(f"Starting FTS fetch from: {next_url}")

        while next_url:
            try:
                data = self._get_page(next_url)
                
                # Yield releases in this page
                for release in data.get('releases', []):
                    yield release

                # Check for pagination
                links = data.get('links', {})
                next_url = links.get('next')
                
                if next_url:
                    logger.debug(f"Fetching next page: {next_url}")
                    
            except Exception as e:
                logger.error(f"Error fetching page {next_url}: {str(e)}")
                raise  # Propagate error so worker knows it failed
