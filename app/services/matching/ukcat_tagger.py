import csv
import re
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class UKCATTagger:
    """
    Tags text with UK Charity Activity Tags (UK-CAT) using regex patterns.
    Patterns are sourced from https://github.com/charity-classification/ukcat
    """
    
    _instance = None
    _patterns: List[Dict] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UKCATTagger, cls).__new__(cls)
            cls._instance._load_patterns()
        return cls._instance

    def _load_patterns(self):
        """Loads regex patterns from the CSV file."""
        csv_path = os.path.join(os.path.dirname(__file__), "../../../data/ukcat.csv")
        if not os.path.exists(csv_path):
            logger.error(f"UKCAT CSV not found at {csv_path}")
            return

        try:
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = row.get("Code")
                    regex_str = row.get("Regular expression")
                    exclude_regex_str = row.get("Exclude regular expression")
                    
                    if not code or not regex_str:
                        continue
                        
                    try:
                        pattern = re.compile(regex_str, re.IGNORECASE)
                        exclude_pattern = None
                        if exclude_regex_str:
                            exclude_pattern = re.compile(exclude_regex_str, re.IGNORECASE)
                            
                        self._patterns.append({
                            "code": code,
                            "tag": row.get("tag"),
                            "pattern": pattern,
                            "exclude_pattern": exclude_pattern
                        })
                    except re.error as e:
                        logger.warning(f"Invalid regex for UKCAT code {code}: {e}")
        except Exception as e:
            logger.error(f"Error loading UKCAT patterns: {e}")

    def tag_text(self, text: str) -> List[str]:
        """
        Returns a list of UKCAT codes that match the given text.
        """
        if not text:
            return []
            
        matches = []
        for p in self._patterns:
            # Check for inclusion
            if p["pattern"].search(text):
                # Check for exclusion
                if p["exclude_pattern"] and p["exclude_pattern"].search(text):
                    continue
                matches.append(p["code"])
                
        return sorted(list(set(matches)))

tagger = UKCATTagger()
