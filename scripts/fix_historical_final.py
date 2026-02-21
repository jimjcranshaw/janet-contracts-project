from app.database import SessionLocal
from app.models import Notice
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_historical")

def fix_all():
    db = SessionLocal()
    notices = db.query(Notice).filter(Notice.notice_type == 'historical').all()
    logger.info(f"Repairing {len(notices)} notices...")
    
    count = 0
    for n in notices:
        try:
            rj = n.raw_json
            if not rj:
                continue
            
            tender = rj.get('tender', {})
            cpv_codes = []
            
            # Extract from classification
            cls = tender.get('classification', {})
            if cls and cls.get('id'):
                cpv_codes.append(cls.get('id'))
            
            # Extract from items
            items = tender.get('items', [])
            for item in items:
                cid = item.get('classification', {}).get('id')
                if cid and cid not in cpv_codes:
                    cpv_codes.append(cid)
            
            # Extract from additionalClassifications
            additional = tender.get('additionalClassifications', [])
            for ac in additional:
                aid = ac.get('id')
                if aid and aid not in cpv_codes:
                    cpv_codes.append(aid)
            
            if cpv_codes:
                n.cpv_codes = cpv_codes
                count += 1
                if count % 50 == 0:
                    db.commit()
                    logger.info(f"Repaired {count}...")
        except Exception as e:
            logger.error(f"Error on {n.ocid}: {e}")
            
    db.commit()
    logger.info(f"Finished. Total repaired: {count}")
    db.close()

if __name__ == "__main__":
    fix_all()
