import logging
import json
import openai
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import ExtractedRequirement, Notice

logger = logging.getLogger(__name__)

class RequirementService:
    """
    LLM-powered requirement extraction for PRD 07.
    """

    def __init__(self, db: Session, api_key: str = None):
        self.db = db
        self.client = openai.Client(api_key=api_key)

    def extract_requirements(self, notice_ocid: str, document_text: str) -> List[ExtractedRequirement]:
        """
        Uses LLM to identify requirements in tender document text.
        """
        if not document_text:
            return []

        prompt = f"""
Analyze the following text from a public procurement tender document. 
Extract specific requirements that a bidding organization must meet. 

Focus on:
1. ELIGIBILITY: Membership of specific bodies, certifications, SME/Charity restrictions.
2. RISK: Specific insurance levels, TUPE implications, safeguarding requirements.
3. SOCIAL VALUE: Environmental goals, local employment targets.
4. TECHNICAL: Key software or methodology requirements.

For each requirement, identify:
- Category (ELIGIBILITY, RISK, SOCIAL_VALUE, TECHNICAL)
- Brief text of the requirement
- If it is mandatory (Yes/No)
- Suitability flags (e.g. SME_FRIENDLY, CHARITY_ONLY)
- Risk level (low, medium, high)

TEXT:
{document_text[:5000]}

Response FORMAT: JSON array of objects.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # Cost-effective for extraction
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response.choices[0].message.content)
            requirements_raw = data.get("requirements", [])
            
            extracted = []
            for req in requirements_raw:
                db_req = ExtractedRequirement(
                    notice_id=notice_ocid,
                    category=req.get("category", "OTHER"),
                    requirement_text=req.get("requirement_text"),
                    is_mandatory=req.get("is_mandatory", "No").lower() == "yes",
                    suitability_flags=req.get("suitability_flags", []),
                    risk_level=req.get("risk_level", "low")
                )
                self.db.add(db_req)
                extracted.append(db_req)
            
            self.db.commit()
            logger.info(f"Extracted {len(extracted)} requirements for notice {notice_ocid}")
            return extracted

        except Exception as e:
            logger.error(f"LLM requirement extraction failed for {notice_ocid}: {e}")
            self.db.rollback()
            return []
