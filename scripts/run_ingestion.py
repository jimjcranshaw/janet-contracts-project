"""
Run data ingestion from FTS API.
Usage: python scripts/run_ingestion.py [--days 30] [--limit 100]
"""
import sys
import os
from datetime import datetime, timedelta
import argparse
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.workers.ingestion_worker import IngestionWorker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Run FTS data ingestion')
    parser.add_argument('--days', type=int, default=7, help='Number of days to fetch (default: 7)')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of records (for testing)')
    args = parser.parse_args()
    
    start_date = datetime.utcnow() - timedelta(days=args.days)
    
    logger.info(f"=== Starting Ingestion ===")
    logger.info(f"Date range: {start_date.date()} to {datetime.utcnow().date()}")
    logger.info(f"Limit: {args.limit or 'None'}")
    
    worker = IngestionWorker()
    
    try:
        worker.run(limit=args.limit, start_date=start_date)
        logger.info("✓ Ingestion completed successfully")
    except Exception as e:
        logger.error(f"✗ Ingestion failed: {e}")
        raise

if __name__ == "__main__":
    main()
