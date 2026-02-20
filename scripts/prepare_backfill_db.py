from app.database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prepare_backfill_db")

def run():
    with engine.begin() as conn:
        logger.info("Creating index on notice(buyer_id)...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notice_buyer_id ON notice(buyer_id)"))
        
        logger.info("Creating GIN index on notice(cpv_codes)...")
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notice_cpv_codes ON notice USING GIN(cpv_codes)"))
        
        logger.info("Database preparation complete.")

if __name__ == "__main__":
    run()
