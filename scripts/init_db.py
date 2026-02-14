"""
Simple schema initialization script - creates all tables manually.
Use this instead of Alembic for MVP.
"""
from app.database import engine
from app.models import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Create all tables defined in models."""
    logger.info("Creating database schema...")
    
    # This creates all tables that inherit from Base
    Base.metadata.create_all(bind=engine)
    
    logger.info("✓ Schema created successfully")
    
    # Enable pgvector extension (must be done manually first)
    from sqlalchemy import text
    with engine.connect() as conn:
        # Check if vector extension exists
        result = conn.execute(text("SELECT * FROM pg_extension WHERE extname = 'vector'"))
        if result.fetchone():
            logger.info("✓ pgvector extension is enabled")
        else:
            logger.warning("⚠ pgvector extension NOT enabled. You must run:")
            logger.warning("  CREATE EXTENSION IF NOT EXISTS vector;")

if __name__ == "__main__":
    init_db()
