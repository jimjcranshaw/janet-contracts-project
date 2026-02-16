import sys
import os
import logging
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import Notice
from app.services.ingestion.embeddings import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill_embeddings(batch_size=50):
    db = SessionLocal()
    embeddings_service = EmbeddingService()
    
    try:
        # Count missing embeddings
        missing_count = db.query(Notice).filter(Notice.embedding == None).count()
        logger.info(f"Found {missing_count} notices with missing embeddings.")
        
        if missing_count == 0:
            return

        processed = 0
        while True:
            # Fetch a batch of notices without embeddings
            notices = db.query(Notice).filter(Notice.embedding == None).limit(batch_size).all()
            if not notices:
                break
                
            logger.info(f"Processing batch of {len(notices)} notices...")
            
            # Map descriptions to embeddings
            descriptions = [n.description for n in notices if n.description]
            if not descriptions:
                # If no descriptions, we might want to skip or mark them somehow
                # For now, we'll just skip them in this loop or they'll keep being returned by limit
                for n in notices:
                    if not n.description:
                        n.embedding = [] # Empty vector for notices with no description
                db.commit()
                continue

            try:
                # Get embeddings in batch
                batch_vectors = embeddings_service.get_embeddings_batch(descriptions)
                
                # Update notices
                desc_idx = 0
                for n in notices:
                    if n.description:
                        n.embedding = batch_vectors[desc_idx]
                        desc_idx += 1
                
                db.commit()
                processed += len(notices)
                logger.info(f"Progress: {processed}/{missing_count} processed.")
                
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                db.rollback()
                break
                
        logger.info("Backfill complete.")
        
    finally:
        db.close()

if __name__ == "__main__":
    backfill_embeddings()
