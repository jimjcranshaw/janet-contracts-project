"""
Client for fetching charity data from the Charity Commission register.
Uses the public register website (no API key required).
"""
import requests
import re
import logging
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# CC Register classification categories
WHAT_KEYWORDS = [
    "General Charitable Purposes", "Education/training", "Medical/health/sickness",
    "Disability", "Relief Of Poverty", "Overseas Aid", "Accommodation/housing",
    "Religious Activities", "Arts/culture", "Sport/recreation", "Animals",
    "Environment/conservation", "Economic/community Development", "Armed Forces",
    "Human Rights", "Advancement Of Health", "Saving Of Lives"
]

WHO_KEYWORDS = [
    "Children/young People", "Elderly/old People", "People With Disabilities",
    "People Of A Particular Ethnic", "Other Charities", "The General Public",
    "Other Defined Groups"
]

HOW_KEYWORDS = [
    "Makes Grants To Individuals", "Makes Grants To Organisations",
    "Provides Human Resources", "Provides Buildings/facilities/open Space",
    "Provides Services", "Provides Advocacy/advice/information",
    "Sponsors Or Undertakes Research", "Acts As An Umbrella"
]


class CharityCommissionClient:
    """
    Fetches structured charity data from the CC public register website.
    """
    BASE_URL = "https://register-of-charities.charitycommission.gov.uk/charity-search/-/charity-details"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; JanetContracts/1.0; research)",
            "Accept": "text/html"
        })

    def fetch_charity(self, charity_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetches all available data for a single charity from the public register.
        Combines the overview and what-who-how-where pages.
        """
        result = {
            "charity_number": str(charity_number),
            "name": None,
            "activities": None,
            "income": None,
            "what": [],
            "who": [],
            "how": [],
            "where": [],
        }

        # 1. Overview page → name, activities, income
        try:
            overview_url = f"{self.BASE_URL}/{charity_number}/charity-overview"
            resp = self.session.get(overview_url, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Name from <title> or <h1>
            title_tag = soup.find("title")
            if title_tag:
                # Format: "THE BRITISH RED CROSS SOCIETY - 220949"
                name = title_tag.text.strip().split(" - ")[0].strip()
                result["name"] = name.title()

            # Activities text
            body_text = soup.get_text(separator="\n")
            activities_match = re.search(
                r"Activities - how the charity spends its money\s*\n(.+?)(?:\n\s*\n|\nIncome and expenditure)",
                body_text, re.DOTALL
            )
            if activities_match:
                result["activities"] = activities_match.group(1).strip()

            # Income
            income_match = re.search(r"Total income:\s*£([\d,]+)", body_text)
            if income_match:
                result["income"] = int(income_match.group(1).replace(",", ""))

        except Exception as e:
            logger.error(f"Failed to fetch overview for {charity_number}: {e}")

        # 2. What/Who/How/Where page → classifications
        try:
            wwhw_url = f"{self.BASE_URL}/{charity_number}/what-who-how-where"
            resp = self.session.get(wwhw_url, timeout=self.timeout)
            resp.raise_for_status()
            body_text = resp.text

            # Parse classifications from the list items
            soup = BeautifulSoup(body_text, "html.parser")
            items = [li.get_text(strip=True) for li in soup.find_all("li")]

            for item in items:
                item_lower = item.lower()
                # What
                if any(kw.lower() in item_lower for kw in WHAT_KEYWORDS):
                    result["what"].append(item)
                # Who
                elif any(kw.lower() in item_lower for kw in WHO_KEYWORDS):
                    result["who"].append(item)
                # How
                elif any(kw.lower() in item_lower for kw in HOW_KEYWORDS):
                    result["how"].append(item)
                # Where (regions/countries)
                elif item.startswith("Throughout") or item in [
                    "Scotland", "Northern Ireland", "London", "South East",
                    "South West", "East Midlands", "West Midlands", "North East",
                    "North West", "Yorkshire And The Humber", "East Of England"
                ]:
                    result["where"].append(item)

        except Exception as e:
            logger.error(f"Failed to fetch WWHW for {charity_number}: {e}")

        # 3. Charitable objects page
        try:
            objects_url = f"{self.BASE_URL}/{charity_number}/governing-document"
            resp = self.session.get(objects_url, timeout=self.timeout)
            resp.raise_for_status()
            body_text = resp.get_text() if hasattr(resp, 'get_text') else resp.text
            soup = BeautifulSoup(body_text, "html.parser")
            full_text = soup.get_text(separator="\n")
            
            objects_match = re.search(
                r"Charitable objects\s*\n(.+?)(?:\nArea of benefit|\nGoverning document|\n\s*\n)",
                full_text, re.DOTALL
            )
            if objects_match:
                result["objects"] = objects_match.group(1).strip()
        except Exception as e:
            logger.warning(f"Could not fetch objects for {charity_number}: {e}")

        income_str = f"£{result['income']:,}" if result.get('income') else "N/A"
        logger.info(f"Fetched charity {charity_number}: {result['name']} (Income: {income_str})")
        return result
