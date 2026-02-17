import logging
import json
import openai
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import ExtractedRequirement, ServiceProfile

logger = logging.getLogger(__name__)

class SocialValueService:
    """
    Maps tender social value requirements to charity evidence (PRD 08).
    Identifies evidence gaps and suggests social value outcomes.
    """

    def __init__(self, db: Session, api_key: str = None):
        self.db = db
        self.client = openai.Client(api_key=api_key)

    def analyze_social_value_fit(self, org_id: str, notice_ocid: str) -> Dict[str, Any]:
        """
        Calculates the fit between charity evidence and tender SV requirements.
        """
        # 1. Fetch requirements
        requirements = self.db.query(ExtractedRequirement).filter(
            ExtractedRequirement.notice_id == notice_ocid,
            ExtractedRequirement.category == 'SOCIAL_VALUE'
        ).all()
        
        if not requirements:
            return {"status": "NO_SV_REQUIRED", "matches": [], "gaps": []}

        # 2. Fetch charity evidence
        profile = self.db.get(ServiceProfile, org_id)
        evidence = profile.outcomes_evidence or []

        # 3. Use LLM to map requirements to evidence
        prompt = f"""
        Compare the following Social Value Requirements of a tender with a Charity's Evidence base.
        Identify which requirements are covered by existing evidence and where the "Evidence Gaps" are.

        Requirements:
        {[r.requirement_text for r in requirements]}

        Charity Evidence:
        {json.dumps(evidence)}

        Response FORMAT: JSON object with:
        - "matches": [ {{"requirement": "...", "matching_evidence": "...", "confidence": 0.0-1.0}} ]
        - "gaps": [ {{"requirement": "...", "reason": "...", "severity": "medium/high"}} ]
        - "fit_score": 0.0-1.0
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            return analysis

        except Exception as e:
            logger.error(f"Social value analysis failed for {org_id} on {notice_ocid}: {e}")
            return {"status": "ERROR", "message": str(e)}

    def suggest_social_value_pledges(self, document_text: str) -> List[str]:
        """
        Suggests potential social value pledges based on the tender text.
        """
        # (Future enhancement for the calculator)
        return []
