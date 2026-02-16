import sys
import os
import logging
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Notice
from app.services.ingestion.normalizer import Normalizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_cpv_codes():
    db = SessionLocal()
    normalizer = Normalizer()
    
    try:
        notices = db.query(Notice).all()
        logger.info(f"Found {len(notices)} notices to review.")
        
        updates = 0
        for notice in notices:
            if notice.raw_json:
                # Re-parse CPV codes using the fixed normalizer logic
                tender = notice.raw_json.get('tender', {})
                new_cpv_codes = [
                    item.get('classification', {}).get('id') 
                    for item in tender.get('items', []) 
                    if item.get('classification')
                ]
                
                if new_cpv_codes != notice.cpv_codes:
                    notice.cpv_codes = new_cpv_codes
                    updates += 1
        
        db.commit()
        logger.info(f"Updated CPV codes for {updates} notices.")
            
    finally:
        db.close()

if __name__ == "__main__":
    fix_cpv_codes()
