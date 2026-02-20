"""
LLM-based match analysis service.
Replaces mechanical cosine similarity with reasoned AI analysis
that examines charity evidence against tender requirements and
produces structured recommendations with written rationales.
"""
import json
import logging
import openai
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import ServiceProfile, Notice

logger = logging.getLogger(__name__)

# Structured verdict categories
VERDICTS = ["STRONG_MATCH", "GOOD_MATCH", "PARTIAL_MATCH", "NOT_SUITABLE"]


class LLMMatchAnalyzer:
    """
    Uses an LLM to perform reasoned analysis of charity-tender fit.
    Instead of pure vector cosine similarity, this service reads
    the actual evidence and produces a structured recommendation.
    """

    def __init__(self, db: Session, api_key: str = None, model: str = None, base_url: str = None):
        self.db = db
        # Use provided or from settings
        from app.database import settings
        
        # DeepSeek preference if configured
        if settings.DEEPSEEK_API_KEY and not api_key:
            self.api_key = settings.DEEPSEEK_API_KEY
            self.base_url = settings.DEEPSEEK_BASE_URL
            self.model = model or "deepseek-chat"
            logger.info(f"Using DeepSeek analyzer (model: {self.model})")
        else:
            self.api_key = api_key or settings.OPENAI_API_KEY
            self.base_url = base_url or "https://api.openai.com/v1"
            self.model = model or "gpt-4o-mini"
            provider = "OpenAI" if "openai" in self.base_url else "Custom"
            logger.info(f"Using {provider} analyzer (model: {self.model})")
            
        self.client = openai.Client(api_key=self.api_key, base_url=self.base_url)

    def batch_analyze_matches(self, org_id: str, notice_ocids: list[str]) -> Dict[str, Any]:
        """
        Analyse multiple matches in a single batched LLM call for cost/speed optimization.
        Evaluates up to 10 candidates.
        """
        profile = self.db.get(ServiceProfile, org_id)
        notices = self.db.query(Notice).filter(Notice.ocid.in_(notice_ocids)).all()
        
        if not profile or not notices:
            return {}

        charity_evidence = self._build_charity_summary(profile)
        tenders_section = ""
        for i, n in enumerate(notices):
            tenders_section += f"\n--- TENDER #{i+1} (OCID: {n.ocid}) ---\n{self._build_tender_summary(n)}\n"

        prompt = f"""You are an expert procurement advisor for UK charities.
Analyse which of the following {len(notices)} tenders are the BEST fit for this charity to bid for.

CHARITY PROFILE:
{charity_evidence}

{tenders_section}

For EACH tender, provide a PASS or FAIL verdict and a 1-sentence rationale.
A "PASS" means the charity has strong evidence of being able to deliver the service and it is a good strategic fit.
A "FAIL" means there is a significant mismatch in domain, scale, or requirements.

Respond ONLY with a JSON object where keys are OCIDs and values are:
{{
  "verdict": "PASS" | "FAIL",
  "rationale": "Direct explanation of why it passed or failed"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Batched LLM analysis failed for {org_id}: {e}")
            return {}

    def analyze_match(self, org_id, notice_ocid: str, mechanical_scores: dict = None) -> Dict[str, Any]:
        """
        Analyse the fit between a charity and a tender using LLM reasoning.
        
        Returns:
            {
                "verdict": "STRONG_MATCH" | "GOOD_MATCH" | "PARTIAL_MATCH" | "NOT_SUITABLE",
                "confidence": 0.0-1.0,
                "rationale": "2-3 sentence explanation of why this is/isn't a good fit",
                "strengths": ["list of specific alignment points"],
                "risks": ["list of concerns or gaps"],
                "recommendation": "Clear action statement"
            }
        """
        profile = self.db.get(ServiceProfile, org_id)
        notice = self.db.query(Notice).filter(Notice.ocid == notice_ocid).first()

        if not profile or not notice:
            return {"verdict": "NOT_SUITABLE", "rationale": "Missing data", "confidence": 0.0}

        # Build the charity evidence summary
        charity_evidence = self._build_charity_summary(profile)
        tender_summary = self._build_tender_summary(notice)
        
        # Build context about mechanical scores if available
        scores_context = ""
        if mechanical_scores:
            scores_context = f"""
The automated pre-screening produced these scores (for context only — your analysis should be independent):
- Semantic similarity: {mechanical_scores.get('semantic', 'N/A')}
- Domain (CPV) overlap: {mechanical_scores.get('domain', 'N/A')}
- Geographic match: {mechanical_scores.get('geo', 'N/A')}
- Viability warning: {mechanical_scores.get('viability', 'None')}
"""

        prompt = f"""You are an expert procurement advisor for UK charities and voluntary organisations.

Analyse whether this charity is a good fit to bid for this tender. Consider:
1. Does the charity's mission, activities, and expertise align with what the tender requires?
2. Does the charity have the right beneficiary focus and service delivery experience?
3. Is the contract value appropriate for the charity's size (annual income)?
4. Are there geographic alignment considerations?
5. Could the charity realistically deliver this contract?

CHARITY PROFILE:
{charity_evidence}

TENDER DETAILS:
{tender_summary}
{scores_context}

Respond with a JSON object containing:
- "verdict": one of "STRONG_MATCH", "GOOD_MATCH", "PARTIAL_MATCH", or "NOT_SUITABLE"
- "confidence": 0.0 to 1.0
- "rationale": A clear 2-3 sentence explanation of your reasoning. Be specific about what aligns or doesn't. This is the most important field.
- "strengths": Array of 1-3 specific alignment points (e.g. "Direct experience delivering homelessness prevention services")
- "risks": Array of 0-3 specific concerns (e.g. "Contract value is 5x annual income — would require consortium")
- "recommendation": One clear action statement (e.g. "Bid as lead partner in consortium with housing association")
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            result = json.loads(response.choices[0].message.content)
            
            # Validate verdict
            if result.get("verdict") not in VERDICTS:
                result["verdict"] = "PARTIAL_MATCH"
            
            return result

        except Exception as e:
            logger.error(f"LLM match analysis failed for {org_id} / {notice_ocid}: {e}")
            return {
                "verdict": "PARTIAL_MATCH",
                "confidence": 0.0,
                "rationale": f"Analysis failed: {str(e)}",
                "strengths": [],
                "risks": ["LLM analysis unavailable"],
                "recommendation": "Manual review required"
            }

    def _build_charity_summary(self, profile: ServiceProfile) -> str:
        """Build a rich text summary of the charity's evidence."""
        income_str = f"£{profile.latest_income:,.0f}" if profile.latest_income else "Not reported"
        
        parts = [
            f"Name: {profile.name}",
            f"Annual Income: {income_str}",
        ]
        
        if profile.mission:
            parts.append(f"Mission/Objects: {profile.mission[:500]}")
        if profile.programs_services:
            parts.append(f"Activities: {profile.programs_services[:500]}")
        if profile.target_population:
            parts.append(f"Target Population: {profile.target_population}")
        if profile.beneficiary_groups:
            parts.append(f"Beneficiary Groups: {', '.join(profile.beneficiary_groups)}")
        if profile.service_regions:
            parts.append(f"Operating Regions: {', '.join(profile.service_regions)}")
        if profile.inferred_cpv_codes:
            parts.append(f"Relevant CPV Codes: {', '.join(profile.inferred_cpv_codes)}")
        if profile.ukcat_codes:
            parts.append(f"Charity Classifications: {', '.join(profile.ukcat_codes)}")
        
        return "\n".join(parts)

    def _build_tender_summary(self, notice: Notice) -> str:
        """Build a rich text summary of the tender."""
        parts = [
            f"Title: {notice.title}",
        ]
        
        if notice.value_amount:
            parts.append(f"Estimated Value: £{notice.value_amount:,.0f}")
        if notice.description:
            parts.append(f"Description: {notice.description[:800]}")
        if notice.cpv_codes:
            parts.append(f"CPV Codes: {', '.join(notice.cpv_codes)}")
            
        # Extract buyer and more details from raw_json
        if notice.raw_json:
            tender = notice.raw_json.get("tender", {})
            
            # Buyer name from parties or directly if mapped
            parties = notice.raw_json.get("parties", [])
            buyer_id = tender.get("procuringEntity", {}).get("id") or tender.get("buyer", {}).get("id")
            
            buyer_name = "Unknown Buyer"
            if buyer_id:
                for party in parties:
                    if party.get("id") == buyer_id:
                        buyer_name = party.get("name", buyer_name)
                        break
            parts.append(f"Buyer: {buyer_name}")

            # Delivery Region
            delivery_location = tender.get("deliveryLocation", [{}])[0]
            region = delivery_location.get("region") or delivery_location.get("description")
            if region:
                parts.append(f"Delivery Region: {region}")
            
            # Suitability
            suitability = tender.get("suitability", {})
            if suitability.get("vcse"):
                parts.append("Suitability: Marked as suitable for VCSEs/Charities")
            elif suitability.get("sme"):
                parts.append("Suitability: Marked as suitable for SMEs")
            
            regime = tender.get("specialRegime", [])
            if "lightTouch" in regime:
                parts.append("Procurement Regime: Light Touch (Social/Health/Education)")
        
        return "\n".join(parts)

