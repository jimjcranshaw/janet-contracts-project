import logging
from sqlalchemy.orm import Session
from app.models import Notice
from app.services.ingestion.embeddings import EmbeddingService
from app.services.matching.ukcat_tagger import tagger as ukcat_tagger

logger = logging.getLogger(__name__)

class EnrichmentService:
    """
    Handles lazy AI enrichment (embeddings, tags) for notices.
    """
    def __init__(self, db: Session):
        self.db = db
        self.embeddings = EmbeddingService()
        self.ukcat_tagger = ukcat_tagger

    def enrich_notice(self, notice: Notice, force: bool = False):
        """
        Performs AI enrichment on a single notice if not already enriched.
        """
        needs_update = False
        
        # 1. Embeddings
        if force or not notice.embedding:
            if notice.description:
                try:
                    logger.info(f"Generating embedding for {notice.ocid}")
                    notice.embedding = self.embeddings.get_embedding(notice.description)
                    needs_update = True
                except Exception as e:
                    logger.error(f"Failed to embed {notice.ocid}: {e}")

        # 2. UKCAT Tagging
        if force or not notice.inferred_ukcat_codes:
            text_to_tag = f"{notice.title} {notice.description or ''}"
            tags = self.ukcat_tagger.tag_text(text_to_tag)
            if tags:
                logger.info(f"Generated UKCAT tags for {notice.ocid}: {tags}")
                notice.inferred_ukcat_codes = tags
                needs_update = True

        if needs_update:
            self.db.add(notice)
            self.db.commit()
            
    def bulk_enrich_stale(self, limit: int = 100):
        """
        Finds notices without embeddings/tags and enriches them.
        """
        stale_notices = self.db.query(Notice).filter(
            (Notice.embedding == None) | (Notice.inferred_ukcat_codes == None)
        ).limit(limit).all()
        
        logger.info(f"Found {len(stale_notices)} stale notices for enrichment.")
        for notice in stale_notices:
            self.enrich_notice(notice)
