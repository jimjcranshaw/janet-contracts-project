import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.database import SessionLocal
from app.models import Notice, Buyer, IngestionLog
from app.services.ingestion.clients.fts_client import FTSClient
from app.services.ingestion.normalizer import Normalizer
from app.services.ingestion.embeddings import EmbeddingService

from app.services.alerts.alert_service import AlertService
from app.services.documents.document_service import DocumentService
from app.services.matching.requirement_service import RequirementService
from app.services.matching.ukcat_tagger import tagger as ukcat_tagger

logger = logging.getLogger(__name__)

class IngestionWorker:
    def __init__(self):
        self.fts_client = FTSClient()
        self.normalizer = Normalizer()
        self.embeddings = EmbeddingService()
        self.alerts = AlertService(SessionLocal())
        self.documents = DocumentService()
        self.requirements = RequirementService(SessionLocal())
        self.ukcat_tagger = ukcat_tagger

    def run(self, limit=None, start_date=None):
        db = SessionLocal()
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
                    
                    # 2. Process Notice
                    notice = self.normalizer.map_release_to_notice(release, buyer.id)
                    
                    # Generate UKCAT tags
                    text_to_tag = f"{notice.title} {notice.description or ''}"
                    notice.inferred_ukcat_codes = self.ukcat_tagger.tag_text(text_to_tag)
                    
                    # Generate embedding for description
                    if notice.description:
                        try:
                            notice.embedding = self.embeddings.get_embedding(notice.description)
                        except Exception as emb_e:
                            logger.error(f"Failed to generate embedding for notice {notice.ocid}: {emb_e}")

                    # --- PRD 04: Detect Material Changes ---
                    existing_notice = db.query(Notice).filter(Notice.ocid == notice.ocid).first()
                    if existing_notice:
                        changes = self.alerts.check_for_changes(existing_notice, {
                            "deadline_date": notice.deadline_date,
                            "value_amount": notice.value_amount,
                            "notice_type": notice.notice_type
                        })
                        if changes:
                            logger.info(f"Material change detected in notice {notice.ocid}: {changes}")
                            self.alerts.process_change(notice.ocid, changes)

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
                    
                    # --- PRD 07: Process Tender Documents (RAG) ---
                    if notice.source_url:
                        try:
                            logger.info(f"Processing tender documents for {notice.ocid}")
                            text = self.documents.fetch_and_extract_text(notice.source_url)
                            if text:
                                self.requirements.extract_requirements(notice.ocid, text)
                        except Exception as doc_e:
                            logger.error(f"Failed RAG processing for {notice.ocid}: {doc_e}")

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
            try:
                db.commit()
            except:
                pass
        finally:
            db.close()

if __name__ == "__main__":
    worker = IngestionWorker()
    worker.run()
