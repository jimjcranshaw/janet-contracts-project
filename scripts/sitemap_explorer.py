import requests
from xml.etree import ElementTree
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sitemap_explorer")

try:
    r = requests.get('https://data.open-contracting.org/sitemap.xml')
    r.raise_for_status()
    tree = ElementTree.fromstring(r.content)
    # Define namespace
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    locs = [loc.text for loc in tree.findall('.//s:loc', namespaces=ns)]
    matching = [l for l in locs if 'contracts-finder' in l.lower()]
    
    print("\nMatching Sitemap URLs:")
    for m in matching:
        print(m)
        
except Exception as e:
    logger.error(f"Error: {e}")
