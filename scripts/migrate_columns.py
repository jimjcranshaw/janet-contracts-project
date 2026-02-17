from app.database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    queries = [
        # Notice table
        "ALTER TABLE notice ADD COLUMN IF NOT EXISTS contract_period_start TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE notice ADD COLUMN IF NOT EXISTS contract_period_end TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE notice ADD COLUMN IF NOT EXISTS raw_json JSONB;",
        "ALTER TABLE notice ADD COLUMN IF NOT EXISTS source_url TEXT;",
        
        # Service Profile table
        "ALTER TABLE service_profile ADD COLUMN IF NOT EXISTS outcomes_evidence JSONB;",
        
        # Notice Match table
        "ALTER TABLE notice_match ADD COLUMN IF NOT EXISTS is_tracked BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE notice_match ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        
        # New table for PRD 07
        """
        CREATE TABLE IF NOT EXISTS extracted_requirement (
            id UUID PRIMARY KEY,
            notice_id TEXT REFERENCES notice(ocid),
            category VARCHAR(50),
            requirement_text TEXT,
            is_mandatory BOOLEAN DEFAULT FALSE,
            suitability_flags TEXT[],
            risk_level VARCHAR(20),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    ]
    
    with engine.connect() as conn:
        for query in queries:
            try:
                conn.execute(text(query))
                conn.commit()
                logger.info(f"✓ Executed: {query[:50]}...")
            except Exception as e:
                logger.error(f"✗ Failed: {query[:50]}... Error: {e}")
                conn.rollback()

if __name__ == "__main__":
    migrate()
