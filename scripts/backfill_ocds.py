import os
import json
import ijson
import gzip
import logging
import requests
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Notice, Buyer, IngestionLog
from app.services.ingestion.enrichment_service import EnrichmentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_ocds")

class BackfillWorker:
    def __init__(self):
        self.db: Session = SessionLocal()
        self.enrichment_service = EnrichmentService(self.db)
        self._buyer_cache = {}

    def get_or_create_buyer(self, name: str, identifiers: Optional[List] = None) -> Buyer:
        """Cache-backed buyer lookup."""
        if name in self._buyer_cache:
            return self._buyer_cache[name]
        
        buyer = self.db.query(Buyer).filter(Buyer.canonical_name == name).first()
        if not buyer:
            buyer = Buyer(canonical_name=name, identifiers=identifiers)
            self.db.add(buyer)
            self.db.commit()
            self.db.refresh(buyer)
        
        self._buyer_cache[name] = buyer
        return buyer

    def process_release(self, release: dict):
        """Maps OCDS release to Notice model."""
        ocid = release.get("ocid")
        if not ocid:
            return

        # 1. Check if already exists
        existing = self.db.query(Notice).filter(Notice.ocid == ocid).first()
        if existing:
            return

        tender = release.get("tender", {})
        buyer_data = release.get("buyer", {})
        
        # 2. Handle Buyer
        buyer_name = buyer_data.get("name") or "Unknown Buyer"
        buyer = self.get_or_create_buyer(buyer_name)

        # 3. Map Fields
        pub_date_str = release.get("date")
        pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")) if pub_date_str else datetime.now()

        # CPV Codes
        cpv_codes = []
        for item in tender.get("items", []):
            cpv = item.get("classification", {}).get("id")
            if cpv and cpv not in cpv_codes:
                cpv_codes.append(cpv)

        # Contract Period
        contract_start = None
        contract_end = None
        
        # Look in tender if explicitly defined (common in FTS)
        period = tender.get("tenderPeriod", {})
        if not period:
             # Look in awards or contracts
             awards = release.get("awards", [])
             if awards:
                 period = awards[0].get("contractPeriod", {})
        
        if period:
            start_str = period.get("startDate")
            end_str = period.get("endDate")
            if start_str: contract_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if end_str: contract_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        # Value
        value_amount = 0
        value_currency = "GBP"
        val_obj = tender.get("value") or (release.get("awards", [{}])[0].get("value") if release.get("awards") else {})
        if val_obj:
            value_amount = val_obj.get("amount", 0)
            value_currency = val_obj.get("currency", "GBP")

        # 4. Create Notice
        notice = Notice(
            ocid=ocid,
            release_id=release.get("id"),
            title=tender.get("title") or "No Title",
            description=tender.get("description"),
            buyer_id=buyer.id,
            publication_date=pub_date,
            deadline_date=None, # Inferred if needed
            value_amount=Decimal(str(value_amount)),
            value_currency=value_currency,
            procurement_method=tender.get("procurementMethod"),
            notice_type="historical", # Mark as historical backfill
            raw_json=release,
            cpv_codes=cpv_codes,
            contract_period_start=contract_start,
            contract_period_end=contract_end
        )

        self.db.add(notice)
        
        # 5. Flush periodically (Commit happens in batches outside)
        return notice

    def run_file(self, file_path: str, batch_size: int = 500):
        """Processes a large OCDS JSON array file."""
        logger.info(f"Starting backfill from {file_path}")
        
        # Determine if compressed
        open_func = gzip.open if file_path.endswith(".gz") else open
        
        count = 0
        batch_count = 0
        
        try:
            with open_func(file_path, "rb") as f:
                # OCDS packages usually wrap releases in a "releases" key or are just an array
                # Use ijson.items to stream objects
                parser = ijson.items(f, "releases.item")
                
                for release in parser:
                    try:
                        self.process_release(release)
                        count += 1
                        batch_count += 1
                        
                        if batch_count >= batch_size:
                            self.db.commit()
                            logger.info(f"Committed batch. Total processed: {count}")
                            batch_count = 0
                            
                    except Exception as e:
                        logger.error(f"Error processing release {release.get('ocid')}: {e}")
                        self.db.rollback()

                self.db.commit()
                logger.info(f"Backfill complete. Total: {count}")

        except Exception as e:
            logger.error(f"Fatal error during backfill: {e}")
        finally:
            self.db.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python backfill_ocds.py <path_to_ocds_file>")
        sys.exit(1)
        
    worker = BackfillWorker()
    worker.run_file(sys.argv[1])
