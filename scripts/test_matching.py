import sys
import os
import logging
import uuid
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, NoticeMatch, Notice
from app.services.matching.engine import MatchingEngine
from app.services.ingestion.embeddings import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_matching():
    db = SessionLocal()
    embeddings_service = EmbeddingService()
    engine = MatchingEngine(db)
    
    try:
        # 1. Create or get a test profile
        org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        profile = db.query(ServiceProfile).get(org_id)
        
        if not profile:
            logger.info("Creating test profile for 'Legal Aid Charity'...")
            mission = "To provide accessible legal aid and solicitors services to vulnerable populations."
            vision = "A world where everyone has equal access to legal representation."
            programs = "Legal advice centers, refugee support clinics, domestic abuse legal assistance."
            
            # Combine for embedding
            profile_text = f"{mission} {vision} {programs}"
            embedding = embeddings_service.get_embedding(profile_text)
            
            profile = ServiceProfile(
                org_id=org_id,
                name="Legal Aid UK",
                mission=mission,
                vision=vision,
                programs_services=programs,
                latest_income=1000000,
                profile_embedding=embedding,
                # New enhanced fields
                service_regions={"regions": ["London", "South East"]},
                inferred_cpv_codes=["75211000", "75211100", "79100000"], # Legal services
                beneficiary_groups=["vulnerable", "refugees", "domestic abuse"],
                min_contract_value=5000,
                max_contract_value=500000
            )
            db.add(profile)
            db.commit()
            logger.info("Test profile created.")
        else:
            logger.info("Updating existing test profile for enhanced testing...")
            profile.service_regions = {"regions": ["London", "South East"]}
            profile.inferred_cpv_codes = ["75211000", "75211100", "79100000"]
            profile.beneficiary_groups = ["vulnerable", "refugees", "domestic abuse"]
            profile.min_contract_value = 5000
            profile.max_contract_value = 500000
            db.commit()

        # 2. Run matching
        logger.info(f"Running matching for {profile.name}...")
        engine.calculate_matches(profile.org_id)
        
        # 3. Query results
        matches = db.query(NoticeMatch, Notice)\
            .join(Notice, NoticeMatch.notice_id == Notice.ocid)\
            .filter(NoticeMatch.org_id == org_id)\
            .order_by(NoticeMatch.score.desc())\
            .limit(10).all()
            
        logger.info("\n=== Top Matches ===\n")
        for match, notice in matches:
            logger.info(f"Score: {match.score:.4f} | Status: {match.feedback_status}")
            logger.info(f"  Title: {notice.title}")
            if match.viability_warning:
                logger.info(f"  ⚠ Warning: {match.viability_warning}")
            logger.info("-" * 20)
            
    finally:
        db.close()

if __name__ == "__main__":
    test_matching()
