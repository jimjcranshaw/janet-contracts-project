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
        # Lazy load due to circular imports potential
        from app.services.matching.identity_matcher import IdentityMatcher
        self.identity_matcher = IdentityMatcher(db)

    def _cosine_similarity(self, v1, v2):
        import numpy as np
        if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0:
            return 0.0
        a = np.array(v1)
        b = np.array(v2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _is_national_charity(self, profile: ServiceProfile) -> bool:
        """
        Check if charity is National (Income > £10m OR 'National' in regions).
        """
        if profile.latest_income and profile.latest_income > 10_000_000:
            return True
        
        if isinstance(profile.service_regions, dict):
            regions = profile.service_regions.get("regions", [])
        else:
            regions = profile.service_regions or []
            
        return "National" in regions or "United Kingdom" in regions

    def _is_small_charity(self, profile: ServiceProfile) -> bool:
        """
        Check if charity is Small (Income < £1m).
        """
        return profile.latest_income and profile.latest_income < 1_000_000

    def _calculate_geo_score(self, profile, notice):
        """
        Calculate geo score with 'National Catch-All' logic.
        """
        # 1. National Charity Rule: Matches ANY region
        if self._is_national_charity(profile):
            return 1.0
            
        # 2. Extract regions
        if isinstance(profile.service_regions, dict):
            allowed_regions = profile.service_regions.get("regions", [])
        else:
            allowed_regions = profile.service_regions or []
            
        if not allowed_regions:
            return 0.0
            
        notice_regions = []
        if notice.raw_json:
            execution_location = notice.raw_json.get("tender", {}).get("deliveryLocation", []) or \
                               notice.raw_json.get("tender", {}).get("execution_location", [])
            for loc in execution_location:
                # Try region, then description, then address
                r = loc.get("region") or loc.get("description")
                if r:
                    notice_regions.append(r)
        
        # 3. Unknown Location Rule: If tender location unknown, Local charity score depends...
        # User said: "Local Charity: Must match Notice Region OR Notice Region must be 'Unknown'"
        if not notice_regions:
            return 1.0 # Benefit of doubt for now (or 0.5?) user said "matches... Unknown"
            
        # 4. Local Overlap Check
        overlap = set(notice_regions) & set(allowed_regions)
        if overlap:
            return 1.0
            
        return 0.0

    def calculate_matches(self, org_id: str):
        profile = self.db.get(ServiceProfile, org_id)
        if not profile:
            logger.error(f"Profile {org_id} not found")
            return

        # Fetch candidate notices
        notices = self.db.query(Notice).filter(Notice.deadline_date > func.now()).all()
        
        # --- HYBRID AI PRE-SCREENING ---
        strategy_matches = self.identity_matcher.batch_screen(profile, notices)

        for notice in notices:
            # --- INIT VARIABLES ---
            viability_warning = None
            is_excluded = False
            risk_flags = {}
            checklist = []
            recommendation_reasons = []

            tender = notice.raw_json.get("tender", {}) if notice.raw_json else {}
            lots = tender.get("lots", [])

            # --- PHASE 1: HARD GATES & VIABILITY ---
            
            # 1. SME Gate (Income < £1m)
            is_sme_suitable = tender.get("suitability", {}).get("sme") or any(lot.get("suitability", {}).get("sme") for lot in lots)
            is_vcse_suitable = tender.get("suitability", {}).get("vcse") or any(lot.get("suitability", {}).get("vcse") for lot in lots)
            is_light_touch = "lightTouch" in tender.get("specialRegime", [])
            
            if self._is_small_charity(profile):
                val = notice.value_amount or 0
                if not is_sme_suitable and val > 250_000:
                     is_excluded = True
            
            if is_excluded:
                continue

            # 2. Turnover Rule (50% Income)
            if profile.latest_income and notice.value_amount:
                if notice.value_amount > (profile.latest_income * 0.5):
                    viability_warning = "High Risk: Contract value exceeds 50% of annual income."

            # 3. Geo Gate (Hard Exclusion for Locals)
            score_geo = self._calculate_geo_score(profile, notice)
            
            # IDENTITY OVERRIDE: Strategic match bypasses Geo Gate
            is_strategic = strategy_matches.get(notice.ocid, False)
            
            if score_geo == 0.0 and not is_strategic:
                 continue # HARD EXCLUSION (unless strategic)

            # --- PHASE 2: SCORING ---
            
            # 1. Semantic Score (55%)
            score_semantic = 0.0
            if profile.profile_embedding is not None:
                target_embedding = notice.provider_summary_embedding if notice.provider_summary_embedding is not None else notice.embedding
                if target_embedding is not None:
                     try:
                        score_semantic = self._cosine_similarity(profile.profile_embedding, target_embedding)
                        score_semantic = max(0.0, score_semantic)
                     except Exception as e:
                        logger.error(f"Error calculating similarity: {e}")

            # 2. Domain Score (20%): CPV Overlap
            score_domain = 0.0
            if notice.cpv_codes and profile.inferred_cpv_codes:
                notice_set = set(notice.cpv_codes)
                profile_set = set(profile.inferred_cpv_codes)
                intersection = notice_set & profile_set
                union = notice_set | profile_set
                if union:
                    score_domain = len(intersection) / len(union)

            # 3. Geo Score (15%) - Already calc'd

            # 4. Boost (10%)
            score_boost = 0.0
            if profile.beneficiary_groups and (notice.description or notice.title):
                text_to_check = f"{notice.title} {notice.description}".lower()
                matches_found = 0
                for group in profile.beneficiary_groups:
                    if group.lower() in text_to_check:
                        matches_found += 1
                if matches_found > 0:
                    score_boost = min(1.0, 0.5 + (0.1 * matches_found))
            
            # 5. IDENTITY BOOST (Strategy Override)
            if is_strategic:
                # Force semantic score to be at least 0.9 (Perfect Match equivalent)
                score_semantic = max(score_semantic, 0.9)
                recommendation_reasons.append("AI Insight: Identified as a Strategic Fit for this charity.")

            # --- PHASE 3: BID/NO-BID & SUITABILITY ---
            
            # Add Suitability Reasons
            if is_vcse_suitable:
                recommendation_reasons.append("Explicitly marked as suitable for VCSEs/Charities.")
            elif is_sme_suitable:
                recommendation_reasons.append("Marked as suitable for SMEs.")
            if is_light_touch:
                recommendation_reasons.append("Under 'Light Touch' regime.")

            # Lot-Level Check
            suitable_lots = []
            if lots:
                for lot in lots:
                    lot_value = lot.get("value", {}).get("amountGross") or lot.get("value", {}).get("amount")
                    if lot_value:
                        if profile.latest_income and lot_value > (profile.latest_income * 0.5):
                            continue
                        suitable_lots.append(lot.get("title", f"Lot {lot.get('id')}"))
                if suitable_lots:
                    recommendation_reasons.append(f"Contains {len(suitable_lots)} suitable lots based on scale.")

            # Risks & Checklist
            text_to_scan = f"{notice.title} {notice.description}".lower()
            
            if "tupe" in text_to_scan:
                risk_flags["TUPE"] = "High Risk: Staff transfer likely."
            
            if "safeguarding" in text_to_scan:
                risk_flags["Safeguarding"] = "Review Required: Safeguarding standards apply."
                
            if notice.publication_date and notice.deadline_date:
                days = (notice.deadline_date - notice.publication_date).days
                if days < 20:
                    risk_flags["Mobilization"] = f"Short bidding window ({days} days)."

            # Checklist
            if "social care" in text_to_scan: checklist.append({"item": "Enhanced DBS", "status": "Required"})
            if "cyber" in text_to_scan: checklist.append({"item": "Cyber Essentials", "status": "Check"})

            if viability_warning and not suitable_lots:
                 recommendation_reasons.append(viability_warning)

            # --- TOTAL SCORE ---
            # Weights: 55%, 20%, 15%, 10%
            total_score = (score_semantic * 0.55) + (score_domain * 0.20) + (score_geo * 0.15) + (score_boost * 0.10)
            
            # Apply Suitability Boost to Score
            if is_vcse_suitable: total_score = min(1.0, total_score + 0.15)
            elif is_sme_suitable: total_score = min(1.0, total_score + 0.10)
            if is_light_touch: total_score = min(1.0, total_score + 0.05)

            # --- PHASE 4: RECOMMENDATION ---
            status = "NO_GO"
            if total_score > 0.60 and not risk_flags.get("TUPE"):
                if (not viability_warning or suitable_lots):
                    if profile.service_regions and score_geo == 0:
                         status = "REVIEW"
                    else:
                        status = "GO"
                else:
                    status = "REVIEW"
            elif total_score > 0.25 or viability_warning or risk_flags:
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
                viability_warning=viability_warning if not suitable_lots else None,
                risk_flags=risk_flags,
                checklist=checklist,
                recommendation_reasons=recommendation_reasons
            )
            self.db.merge(match_record) # Upsert
        
        self.db.commit()
