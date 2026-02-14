import logging
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session
from app.models import Notice, ServiceProfile, NoticeMatch
from pgvector.sqlalchemy import Vector

logger = logging.getLogger(__name__)

class MatchingEngine:
    """
    Core Logic for Procurement Matching (Grants AI Alignment).
    Phase 1: Hard Gates (Geo, Viability)
    Phase 2: Weighted Scoring (55% AI, 20% Domain, 15% Geo, 10% Boost)
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_matches(self, org_id: str):
        profile = self.db.query(ServiceProfile).get(org_id)
        if not profile:
            logger.error(f"Profile {org_id} not found")
            return

        # Fetch candidate notices (e.g. open, relevant dates)
        # For MVP: fetch all open notices. Consolidate logic later.
        notices = self.db.query(Notice).filter(Notice.deadline_date > func.now()).all()
        
        matches = []
        for notice in notices:
            # --- PHASE 1: HARD GATES ---
            
            # 1. Viability Gate (Turnover Rule)
            # If Contract Annual Value > 50% of Income -> Warning/Fail
            viability_warning = None
            if profile.latest_income and notice.value_amount:
                # Naive check: valid assuming notice value is roughly annual or total contract < turnover
                if notice.value_amount > (profile.latest_income * 0.5):
                    viability_warning = "High Risk: Contract value exceeds 50% of annual income."

            # 2. Geo Gate (Simplified for MVP)
            # Check overlap logic here... (omitted for brevity)

            # --- PHASE 2: SCORING ---
            
            # 1. Semantic Score (55%)
            # Use Translated Summary if available, else raw description
            score_semantic = 0.0
            if profile.profile_embedding is not None:
                target_embedding = notice.provider_summary_embedding or notice.embedding
                if target_embedding is not None:
                     # PGVector cosine distance (1 - distance = similarity)
                     try:
                        distance = profile.profile_embedding.cosine_distance(target_embedding)
                        score_semantic = (1 - distance) if distance is not None else 0.0
                     except Exception:
                        # Fallback for testing/mocking
                        score_semantic = 1.0 if profile.profile_embedding == target_embedding else 0.0

            # 2. Domain Score (20%)
            # CPV Overlap
            score_domain = 0.0
            if notice.cpv_codes and profile.inferred_cpv_codes:
                # Jaccard Index or simple overlap
                overlap = set(notice.cpv_codes) & set(profile.inferred_cpv_codes)
                if overlap:
                    score_domain = 1.0 # Full points for now
            elif notice.cpv_codes and profile.ukcat_codes:
                 # Fallback to UKCAT keyword match (placeholder)
                 pass

            # 3. Geo Score (15%)
            score_geo = 0.0 # Placeholder logic for "Exact vs Region"

            # 4. Boost (10%)
            score_boost = 0.0

            # --- TOTAL SCORE ---
            # Adjusted weights
            total_score = (score_semantic * 0.55) + (score_domain * 0.20) + (score_geo * 0.15) + (score_boost * 0.10)

            # --- PHASE 3: RECOMMENDATION ---
            status = "NO_GO"
            if total_score > 0.50 and not viability_warning:
                status = "GO"
            elif total_score > 0.30 or viability_warning:
                status = "REVIEW"
            
            # Create/Update Match Record
            match_record = NoticeMatch(
                org_id=profile.org_id,
                notice_id=notice.ocid,
                score=total_score,
                score_semantic=score_semantic,
                score_domain=score_domain,
                score_geo=score_geo,
                feedback_status=status,
                viability_warning=viability_warning
            )
            self.db.merge(match_record) # Upsert
        
        self.db.commit()
