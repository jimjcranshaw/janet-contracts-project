import logging
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.database import SessionLocal
from app.models import Notice, Buyer, IngestionLog, ServiceProfile
from app.services.ingestion.clients.fts_client import FTSClient
from app.services.ingestion.normalizer import Normalizer
from app.services.ingestion.enrichment_service import EnrichmentService
from app.services.alerts.alert_service import AlertService

logger = logging.getLogger(__name__)

class IngestionWorker:
    def __init__(self):
        self.fts_client = FTSClient()
        self.normalizer = Normalizer()
        self._mesh = None

    def _get_mesh(self, db: Session):
        """Builds a cached Global Interest Mesh from all charity profiles."""
        if self._mesh is not None:
            return self._mesh
            
        profiles = db.query(ServiceProfile).all()
        cpv_pool = set()
        for p in profiles:
            if p.inferred_cpv_codes:
                cpv_pool.update(c[:4] for c in p.inferred_cpv_codes)
        
        self._mesh = {
            "cpv_prefixes": cpv_pool
        }
        logger.info(f"Global Interest Mesh built with {len(cpv_pool)} CPV prefixes.")
        return self._mesh

    def _is_mesh_match(self, db: Session, notice: Notice) -> bool:
        """Checks if a notice matches the global interest criteria."""
        mesh = self._get_mesh(db)
        
        # 1. CPV Check (Strictest filter)
        if not notice.cpv_codes:
            return True # Neutral fallback
            
        notice_prefixes = set(c[:4] for c in notice.cpv_codes)
        if notice_prefixes & mesh["cpv_prefixes"]:
            return True
            
        return False

    def run(self, limit=None, start_date=None):
        db = SessionLocal()
        enrichment_service = EnrichmentService(db)
        alert_service = AlertService(db)
        
        log_entry = IngestionLog(source="FTS", status="RUNNING")
        db.add(log_entry)
        db.commit()

        try:
            # Determine start date (e.g., provided, last run, or default)
            if not start_date:
                last_run = db.query(IngestionLog).filter(IngestionLog.status == "SUCCESS").order_by(IngestionLog.completed_at.desc()).first()
                start_date = last_run.completed_at if last_run else datetime(2023, 1, 1)

            count = 0
            for release in self.fts_client.fetch_releases(updated_after=start_date):
                try:
                    # 1. Process Buyer
                    buyer_data = self.normalizer.normalize_buyer(release.get('buyer', {}))
                    buyer_stmt = insert(Buyer).values(**buyer_data).on_conflict_do_update(
                        index_elements=['slug'],
                        set_={"canonical_name": buyer_data['canonical_name']}
                    )
                    db.execute(buyer_stmt)
                    # Fetch buyer ID
                    buyer = db.query(Buyer).filter(Buyer.slug == buyer_data['slug']).first()
                    
                    # 2. Process Notice (Metadata Only)
                    notice = self.normalizer.map_release_to_notice(release, buyer.id)
                    
                    # --- NEW: Lazy Enrichment Check ---
                    if self._is_mesh_match(db, notice):
                        logger.info(f"Mesh Match! Triggering enrichment for {notice.ocid}")
                        enrichment_service.enrich_notice(notice)
                    else:
                        logger.debug(f"Selective Ingestion: Skipping enrichment for {notice.ocid}")
                    
                    # --- PRD 04: Detect Material Changes ---
                    existing_notice = db.query(Notice).filter(Notice.ocid == notice.ocid).first()
                    if existing_notice:
                        changes = alert_service.check_for_changes(existing_notice, {
                            "deadline_date": notice.deadline_date,
                            "value_amount": notice.value_amount,
                            "notice_type": notice.notice_type
                        })
                        if changes:
                            logger.info(f"Material change detected in notice {notice.ocid}: {changes}")
                            alert_service.process_change(notice.ocid, changes)

                    # 3. Upsert Notice
                    notice_data = {c.name: getattr(notice, c.name) for c in notice.__table__.columns}
                    
                    stmt = insert(Notice).values(**notice_data).on_conflict_do_update(
                        index_elements=['ocid'],
                        set_={
                            'title': notice.title,
                            'description': notice.description,
                            'embedding': notice.embedding,
                            'value_amount': notice.value_amount,
                            'deadline_date': notice.deadline_date,
                            'notice_type': notice.notice_type,
                            'inferred_ukcat_codes': notice.inferred_ukcat_codes,
                            'updated_at': datetime.utcnow()
                        }
                    )
                    db.execute(stmt)
                    db.commit() # Commit each record
                    
                    count += 1
                    
                    if limit and count >= limit:
                        logger.info(f"Limit of {limit} reached, stopping.")
                        break

                except Exception as inner_e:
                    logger.error(f"Failed to process release {release.get('ocid')}: {inner_e}")
                    db.rollback()
                    continue

            log_entry.status = "SUCCESS"
            log_entry.items_processed = count
            log_entry.completed_at = datetime.utcnow()
            db.commit()

        except Exception as e:
            logger.error(f"Ingestion run failed: {e}")
            db.rollback()
            log_entry.status = "FAILED"
            log_entry.error_details = str(e)
            db.commit()
        finally:
            db.close()

if __name__ == "__main__":
    worker = IngestionWorker()
    worker.run()
