"""
Validate ingested data quality.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Notice, Buyer, IngestionLog
from sqlalchemy import func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_data():
    db = SessionLocal()
    
    try:
        logger.info("=== Data Validation Report ===\n")
        
        # 1. Count records
        notice_count = db.query(Notice).count()
        buyer_count = db.query(Buyer).count()
        log_count = db.query(IngestionLog).count()
        
        logger.info(f"📊 Record Counts:")
        logger.info(f"  Notices: {notice_count}")
        logger.info(f"  Buyers: {buyer_count}")
        logger.info(f"  Ingestion Logs: {log_count}\n")
        
        # 2. Check for nulls in critical fields
        null_embeddings = db.query(Notice).filter(Notice.embedding == None).count()
        null_values = db.query(Notice).filter(Notice.value_amount == None).count()
        
        logger.info(f"⚠ Null Fields:")
        logger.info(f"  Missing embeddings: {null_embeddings}")
        logger.info(f"  Missing value_amount: {null_values}\n")
        
        # 3. Sample records
        sample = db.query(Notice).limit(3).all()
        logger.info(f"📝 Sample Records:")
        for notice in sample:
            logger.info(f"  - {notice.ocid}: {notice.title[:50]}...")
            logger.info(f"    Value: £{notice.value_amount or 0:,.2f}")
            logger.info(f"    Deadline: {notice.deadline_date}")
        
        # 4. Ingestion logs
        latest_log = db.query(IngestionLog).order_by(IngestionLog.started_at.desc()).first()
        if latest_log:
            logger.info(f"\n📋 Latest Ingestion:")
            logger.info(f"  Status: {latest_log.status}")
            logger.info(f"  Items Processed: {latest_log.items_processed}")
            logger.info(f"  Started: {latest_log.started_at}")
            logger.info(f"  Completed: {latest_log.completed_at}")
            if latest_log.error_details:
                logger.info(f"  Error: {latest_log.error_details}")
        
        logger.info("\n✓ Validation complete")
        
    finally:
        db.close()

if __name__ == "__main__":
    validate_data()
