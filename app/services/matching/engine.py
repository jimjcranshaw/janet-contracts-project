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

    def _calculate_geo_score(self, profile, notice):
        """
        Calculate geo score based on ServiceProfile.service_regions 
        and Notice location info (from raw_json or other fields).
        """
        if not profile.service_regions:
            return 0.0
            
        allowed_regions = profile.service_regions.get("regions", [])
        if not allowed_regions:
            return 0.0
            
        # Extract location from notice
        # Notice might have info in raw_json -> deliveryAddress / regions
        notice_regions = []
        if notice.raw_json:
            # Try to find regions in OCDS
            # This is a bit simplified for now
            execution_location = notice.raw_json.get("execution_location", [])
            for loc in execution_location:
                if loc.get("region"):
                    notice_regions.append(loc.get("region"))
        
        if not notice_regions:
            # Fallback check title/description for keywords? Maybe later.
            return 0.0
            
        # Check overlap
        overlap = set(notice_regions) & set(allowed_regions)
        if overlap:
            return 1.0 # Exact/Region match for now
        return 0.0

    def calculate_matches(self, org_id: str):
        profile = self.db.get(ServiceProfile, org_id)
        if not profile:
            logger.error(f"Profile {org_id} not found")
            return

        # Fetch candidate notices (e.g. open, relevant dates)
        notices = self.db.query(Notice).filter(Notice.deadline_date > func.now()).all()
        
        for notice in notices:
            # --- PHASE 1: HARD GATES ---
            viability_warning = None
            
            # 1. Turnover Rule (50% Income)
            if profile.latest_income and notice.value_amount:
                if notice.value_amount > (profile.latest_income * 0.5):
                    viability_warning = "High Risk: Contract value exceeds 50% of annual income."

            # 2. Value Bounds (Hard Gate)
            if profile.min_contract_value and notice.value_amount:
                if notice.value_amount < profile.min_contract_value:
                    # In a strict "gate" we might skip, but let's just mark it for now
                    pass 
            
            if profile.max_contract_value and notice.value_amount:
                if notice.value_amount > profile.max_contract_value:
                    if not viability_warning:
                        viability_warning = f"High Risk: Value (£{notice.value_amount:,.0f}) exceeds max preference (£{profile.max_contract_value:,.0f})."

            # 3. Geo Gate (Simplified)
            # If notice has location and it doesn't match profile regions, could skip.
            # For now, we calculate score and downgrade if no overlap.

            # --- PHASE 2: SCORING ---
            
            # 1. Semantic Score (55%)
            score_semantic = 0.0
            if profile.profile_embedding is not None:
                target_embedding = notice.provider_summary_embedding or notice.embedding
                if target_embedding is not None:
                     try:
                        score_semantic = self._cosine_similarity(profile.profile_embedding, target_embedding)
                        # Normalize negative cosine similarity if any (unlikely for text but safe)
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
                    # Jaccard Similarity
                    score_domain = len(intersection) / len(union)

            # 3. Geo Score (15%)
            score_geo = self._calculate_geo_score(profile, notice)

            # 4. Boost (10%): Beneficiaries & Context
            score_boost = 0.0
            if profile.beneficiary_groups and (notice.description or notice.title):
                # Simple keyword check for v1 boost
                text_to_check = f"{notice.title} {notice.description}".lower()
                matches_found = 0
                for group in profile.beneficiary_groups:
                    if group.lower() in text_to_check:
                        matches_found += 1
                
                if matches_found > 0:
                    score_boost = min(1.0, 0.5 + (0.1 * matches_found))

            # --- PHASE 3: BID/NO-BID & SUITABILITY (PRD 03) ---
            
            risk_flags = {}
            checklist = []
            recommendation_reasons = []
            
            tender = notice.raw_json.get("tender", {})
            lots = tender.get("lots", [])
            
            # 1. Suitability Highlights
            is_sme_suitable = tender.get("suitability", {}).get("sme") or any(lot.get("suitability", {}).get("sme") for lot in lots)
            is_vcse_suitable = tender.get("suitability", {}).get("vcse") or any(lot.get("suitability", {}).get("vcse") for lot in lots)
            is_light_touch = "lightTouch" in tender.get("specialRegime", [])
            
            if is_vcse_suitable:
                recommendation_reasons.append("Explicitly marked as suitable for VCSEs/Charities.")
            elif is_sme_suitable:
                recommendation_reasons.append("Marked as suitable for SMEs (favorable for small nonprofits).")
            
            if is_light_touch:
                recommendation_reasons.append("Under 'Light Touch' regime (Social/Health/Education services).")

            # 2. Lot-Level Value Analysis
            # Even if total notice value is high, check if individual lots are suitable
            suitable_lots = []
            if lots:
                for lot in lots:
                    lot_value = lot.get("value", {}).get("amountGross") or lot.get("value", {}).get("amount")
                    if lot_value:
                        # Check turnover ratio for this specific lot
                        if profile.latest_income and lot_value > (profile.latest_income * 0.5):
                            continue # Too big
                        
                        # Check user value bounds
                        if profile.min_contract_value and lot_value < profile.min_contract_value:
                            continue
                        if profile.max_contract_value and lot_value > profile.max_contract_value:
                            continue
                        
                        suitable_lots.append(lot.get("title", f"Lot {lot.get('id')}"))
                
                if suitable_lots and len(suitable_lots) < len(lots):
                    recommendation_reasons.append(f"Notice contains {len(suitable_lots)}/{len(lots)} suitable lots based on scale.")
                elif not suitable_lots and viability_warning:
                     recommendation_reasons.append("No individual lots found within turnover/value bounds.")

            # 3. TUPE Detection
            text_to_scan = f"{notice.title} {notice.description}".lower()
            if "tupe" in text_to_scan or "transfer of undertakings" in text_to_scan:
                risk_flags["TUPE"] = "High Risk: Possible staff transfer requirements detected."
                recommendation_reasons.append("Potential TUPE exposure requires legal/HR review.")

            # 4. Safeguarding Detection
            safeguarding_keywords = ["safeguarding", "enhanced dbs", "vulnerable adults", "child protection", "regulated activity"]
            if any(kw in text_to_scan for kw in safeguarding_keywords):
                risk_flags["Safeguarding"] = "Review Required: Enhanced safeguarding standards likely required."
                recommendation_reasons.append("Mandatory safeguarding requirements detected.")

            # 5. Mobilization Timeline
            if notice.publication_date and notice.deadline_date:
                days_to_deadline = (notice.deadline_date - notice.publication_date).days
                if days_to_deadline < 30:
                    risk_flags["Mobilization"] = "Caution: Short bidding/mobilization window."
                    recommendation_reasons.append(f"Tight window ({days_to_deadline} days) for bid preparation.")

            # 6. Eligibility Checklist (Refined)
            if "social care" in text_to_scan or "health" in text_to_scan:
                checklist.append({"item": "Enhanced DBS Checks", "status": "Required"})
            
            if "tree" in text_to_scan or "construction" in text_to_scan:
                checklist.append({"item": "Public Liability Insurance (£10m)", "status": "Check Policy"})
            
            if "software" in text_to_scan or "system" in text_to_scan or "data" in text_to_scan:
                checklist.append({"item": "Cyber Essentials Plus", "status": "Check Certificate"})
            
            if "procurement" in text_to_scan or "framework" in text_to_scan:
                 checklist.append({"item": "Social Value Proposal", "status": "Mandatory"})

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
            
            # Logic: If semantic match is good and turnover is okay for at least one lot
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
