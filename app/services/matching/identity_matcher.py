import logging
import json
import openai
from typing import List, Dict
from sqlalchemy.orm import Session
from app.models import ServiceProfile, Notice
from app.database import settings

logger = logging.getLogger(__name__)

class IdentityMatcher:
    """
    Hybrid AI Layer: Uses DeepSeek to pre-screen tenders for 'Strategic Fit' 
    before mechanical scoring.
    """
    
    def __init__(self, db: Session):
        self.db = db
        # Prioritize DeepSeek for this high-volume task
        if settings.DEEPSEEK_API_KEY:
            self.api_key = settings.DEEPSEEK_API_KEY
            self.base_url = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com"
            self.model = "deepseek-chat"
        else:
            self.api_key = settings.OPENAI_API_KEY
            self.base_url = "https://api.openai.com/v1"
            self.model = "gpt-4o-mini"
            
        self.client = openai.Client(api_key=self.api_key, base_url=self.base_url)

    def batch_screen(self, profile: ServiceProfile, notices: List[Notice]) -> Dict[str, bool]:
        """
        Screen a batch of notices against a charity profile.
        Returns a dict of {ocid: is_strategic_match (bool)}.
        """
        results = {}
        if not notices:
            return results

        # 1. Pre-Flight Check (Cost Optimization)
        # Only send candidates to LLM if they pass a basic keyword/semantic check
        candidates = []
        for n in notices:
            if self._pre_flight_check(profile, n):
                candidates.append(n)
            else:
                results[n.ocid] = False
                
        if not candidates:
            return results

        # 2. Process Candidates in Batches
        chunk_size = 20
        for i in range(0, len(candidates), chunk_size):
            chunk = candidates[i:i+chunk_size]
            results.update(self._process_chunk(profile, chunk))
            
        return results

    def _pre_flight_check(self, profile: ServiceProfile, notice: Notice) -> bool:
        """
        Quick CPU-bound check to see if notice is worth LLM tokens.
        Pass if:
        1. Semantic Score is decent (> 0.25) [requires embedding overlap]
        2. OR Keywords match (simpler)
        """
        # Simple Keyword Match
        # Extract keywords from profile mission/services
        # Ideally cached, but for now generate on fly
        text_source = (profile.mission or "") + " " + (profile.programs_services or "")
        # Get top meaningful words (simple heuristic: length > 4)
        keywords = set(w.lower() for w in text_source.split() if len(w) > 4)
        
        # Add Beneficiaries
        if profile.beneficiary_groups:
            for g in profile.beneficiary_groups:
                keywords.add(g.lower())
                
        # Scrape Notice
        notice_text = (notice.title or "").lower() + " " + (notice.description or "").lower()
        
        # Check overlap
        # If any strong keyword hits, pass
        # This is very permissive to avoid False Negatives
        for kw in keywords:
            if kw in notice_text:
                return True
                
        return False

    def _process_chunk(self, profile: ServiceProfile, chunk: List[Notice]) -> Dict[str, bool]:
        items_str = ""
        for n in chunk:
            items_str += f"- ID: {n.ocid}\n  Title: {n.title}\n  Description: {(n.description or '')[:200]}\n\n"

        prompt = f"""
You are a strategic grant consultant for {profile.name}.
Mission: {profile.mission[:500]}
Activities: {profile.programs_services[:500]}
Beneficiaries: {', '.join(profile.beneficiary_groups or [])}

Which of the following tenders are likely a STRATEGIC FIT for this charity?
Identity Match means: The tender asks for exactly what this charity exists to do (e.g. "Homelessness Support" for Shelter), even if the location or specific codes are vague.
Ignore generic mismatches. Be strict but recognize core mission alignment.

Tenders:
{items_str}

Return ONLY a JSON object mapping IDs to boolean true/false.
Example: {{ "ocds-1": true, "ocds-2": false }}
"""
        return self._call_llm(prompt, chunk)

    def _call_llm(self, prompt: str, chunk: List[Notice]) -> Dict[str, bool]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a JSON-only response bot."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # Use dictionary comprehension to ensure we only return IDs from the chunk (safety)
            # and default to False if missing
            return {n.ocid: data.get(n.ocid, False) for n in chunk}
            
        except Exception as e:
            logger.error(f"Error in IdentityMatcher: {e}")
            # Fail safe: return False for all in this chunk
            return {n.ocid: False for n in chunk}
