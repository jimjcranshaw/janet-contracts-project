import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Notice, ServiceProfile, ExtractedRequirement

logger = logging.getLogger(__name__)

class ConsortiumService:
    """
    Handles regional targeting and partnership recommendations (PRD 09).
    """

    def __init__(self, db: Session):
        self.db = db

    def check_regional_fit(self, org_id: str, notice_ocid: str) -> Dict[str, Any]:
        """
        Determines if the notice location matches the charity's service regions.
        """
        notice = self.db.get(Notice, notice_ocid)
        profile = self.db.get(ServiceProfile, org_id)
        
        if not notice or not profile:
            return {"fit": "unknown", "score": 0.5}

        # Extract regions from OCDS raw_json
        delivery_locations = notice.raw_json.get("tender", {}).get("deliveryAddresses", [])
        notice_regions = [loc.get("region", "").lower() for loc in delivery_locations if loc.get("region")]
        
        charity_regions = [r.lower() for r in (profile.service_regions or [])]
        
        if not notice_regions: # Fallback: assume national or unknown
            return {"fit": "neutral", "score": 0.7, "message": "No specific delivery regions specified in tender."}
        
        # Check for intersection
        overlap = set(notice_regions).intersection(set(charity_regions))
        if overlap:
            return {"fit": "high", "score": 1.0, "message": f"Matches regions: {', '.join(overlap)}"}
        
        return {"fit": "low", "score": 0.2, "message": "No overlapping delivery regions found."}

    def recommend_consortium(self, notice_ocid: str, org_id: str) -> Dict[str, Any]:
        """
        Flags opportunities that might require a consortium (PRD 09).
        """
        notice = self.db.get(Notice, notice_ocid)
        profile = self.db.get(ServiceProfile, org_id)
        
        reasons = []
        is_recommended = False
        
        # 1. Financial Capacity (Crosses 50% income threshold)
        if notice.value_amount and profile.latest_income:
            if float(notice.value_amount) > (float(profile.latest_income) * 0.5):
                reasons.append("Contract value exceeds 50% of your annual income.")
                is_recommended = True
        
        # 2. Complexity (Multi-category / TUPE Risk)
        requirements = self.db.query(ExtractedRequirement).filter(
            ExtractedRequirement.notice_id == notice_ocid
        ).all()
        
        tupe_risk = any("TUPE" in (r.requirement_text or "") for r in requirements)
        if tupe_risk:
            reasons.append("Significant TUPE staff transfer risk detected.")
            is_recommended = True
            
        # 3. High Risk Requirements
        high_risk_reqs = [r for r in requirements if r.risk_level == 'high']
        if high_risk_reqs:
            reasons.append(f"Multiple high-risk requirements detected ({len(high_risk_reqs)}).")
            is_recommended = True

        return {
            "recommended": is_recommended,
            "reasons": reasons,
            "severity": "high" if is_recommended else "info"
        }
