"""
Fix script to repair historical notices in the DB.
Re-extracts CPV codes from raw_json using the updated Normalizer logic.
"""
import sys
import logging
from app.database import SessionLocal
from app.models import Notice
from app.services.ingestion.normalizer import Normalizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_cpvs")

def fix_historical_cpvs():
    db = SessionLocal()
    normalizer = Normalizer()
    
    historical_notices = db.query(Notice).filter(Notice.notice_type == 'historical').all()
    logger.info(f"Found {len(historical_notices)} historical notices to repair.")
    
    fixed_count = 0
    for notice in historical_notices:
        try:
            if not notice.raw_json:
                continue
                
            # Simulate a release to use the normalizer mapping
            # (or just use the logic directly)
            tender = notice.raw_json.get('tender', {})
            
            cpv_codes = []
            
            # 1. Standard OCDS / FTS Path (Items)
            items = tender.get('items', [])
            for item in items:
                cid = item.get('classification', {}).get('id')
                if cid and cid not in cpv_codes:
                    cpv_codes.append(cid)
                    
            # 2. Contracts Finder Path (Top-level Classification)
            main_class = tender.get('classification', {}).get('id')
            if main_class and main_class not in cpv_codes:
                cpv_codes.append(main_class)
                
            additional = tender.get('additionalClassifications', [])
            for ac in additional:
                aid = ac.get('id')
                if aid and aid not in cpv_codes:
                    cpv_codes.append(aid)
            
            if cpv_codes:
                notice.cpv_codes = cpv_codes
                fixed_count += 1
                
        except Exception as e:
            logger.error(f"Failed to fix {notice.ocid}: {e}")
            
    db.commit()
    logger.info(f"Done. Fixed CPVs for {fixed_count} notices.")
    db.close()

if __name__ == "__main__":
    fix_historical_cpvs()
