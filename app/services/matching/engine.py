import logging
from decimal import Decimal
from sqlalchemy import select, and_, func, or_, text, cast, Numeric
from sqlalchemy.orm import Session
from app.models import Notice, ServiceProfile, NoticeMatch
from .ukcat_tagger import tagger
from .renewal_enrichment import RenewalEnrichmentService

logger = logging.getLogger(__name__)


class MatchingEngine:
    """
    Filter Funnel Matching Engine (v2.1).
    Stages:
      1. SQL Pre-filter (Status, Deadline, Category)
      2. VCSE/SME Gate (Hard Exclude)
      3. Value Gate (Hard Exclude > 40% income)
      4. Geo Gate (Hard Match unless National)
      5. CPV Division Match (Hard Overlap)
      6. UKCAT Theme Match (Structured Scoring)
      7. Cosine Scoring (Final ranking)
    
    No LLM calls. All AI analysis is deferred to report generation.
    """

    # Mapping of charity-level themes to UKCAT prefixes/codes
    THEME_MAPPING = {
        "Accommodation/housing": "HO",
        "Arts/culture/heritage/science": "AR",
        "Disability": "BE",
        "Economic/community Development/employment": "EC",
        "Education/training": "ED",
        "Environment/conservation/heritage": "EN",
        "General Charitable Purposes": "CA",
        "Human Rights/religious Or Racial Harmony/equality Or Diversity": "SO",
        "Overseas Aid/famine Relief": "EC103",
        "The Advancement Of Health Or Saving Of Lives": "HE",
        "The Prevention Or Relief Of Poverty": "BE"
    }

    def __init__(self, db: Session):
        self.db = db
        self.radar_service = RenewalEnrichmentService(db)

    # ─── Helpers ───

    def _is_national_charity(self, profile: ServiceProfile) -> bool:
        """Determines if a charity is national based on income or explicit region."""
        # Income > £5M often implies national reach in our schema
        if profile.latest_income and profile.latest_income > 5_000_000:
            return True
        
        regions = self._extract_charity_regions(profile)
        return any(r.lower() in ["national", "united kingdom", "uk"] for r in regions)

    def _extract_charity_regions(self, profile: ServiceProfile) -> list:
        if isinstance(profile.service_regions, dict):
            return profile.service_regions.get("regions", [])
        return profile.service_regions or []

    # ─── Main Entry ───

    def calculate_matches(self, org_id: str):
        profile = self.db.get(ServiceProfile, org_id)
        if not profile:
            logger.error(f"Profile {org_id} not found")
            return

        # Fetch existing matches for this charity to manage manually
        # This replaces the destructive DELETE and ensures we preserve Deep Review data
        existing_matches = {
            m.notice_id: m for m in self.db.query(NoticeMatch).filter(NoticeMatch.org_id == org_id).all()
        }

        # ═══════════════════════════════════════════
        # STAGE 1: SQL PRE-FILTER (Fast SQL Gates)
        # ═══════════════════════════════════════════
        
        # Stage 1: Active, Services Only, Not Archived
        # Using or_ for is_archived to handle NULLs in existing data
        query = self.db.query(Notice).filter(
            or_(Notice.is_archived == False, Notice.is_archived == None),
            func.lower(Notice.raw_json['tender']['mainProcurementCategory'].astext) == 'services'
        )

        candidates = query.all()
        logger.info(f"  Stage 1 (SQL): Found {len(candidates)} active service candidates for {profile.name}")

        # ═══════════════════════════════════════════
        # STAGE 2-6: PYTHON STRUCTURED GATES
        # ═══════════════════════════════════════════

        is_national = self._is_national_charity(profile)
        charity_regions = [r.lower() for r in self._extract_charity_regions(profile)]
        charity_cpv_prefixes = set(c[:4] for c in (profile.inferred_cpv_codes or []))
        exclusion_kws = [kw.lower() for kw in (profile.exclusion_keywords or [])]
        
        # Translate human-readable themes to UKCAT prefixes
        charity_ukcat_codes = set()
        for theme in (profile.ukcat_codes or []):
            prefix = self.THEME_MAPPING.get(theme)
            if prefix:
                charity_ukcat_codes.add(prefix)
        
        charity_income = profile.latest_income or 0

        matches_to_write = []

        dropped_vcse = 0
        dropped_value = 0
        dropped_geo = 0
        dropped_cpv = 0
        dropped_exclusion = 0

        for notice in candidates:
            # --- Init Match Context ---
            viability_warning = None
            risk_flags = {}
            checklist = []
            recommendation_reasons = []
            
            tender_raw = notice.raw_json.get("tender", {}) if notice.raw_json else {}
            lots_raw = tender_raw.get("lots", [])

            # ═══════════════════════════════════════════
            # STAGE 2: VCSE/SME GATE (Hard Exclude)
            # ═══════════════════════════════════════════
            is_vcse_suitable = tender_raw.get("suitability", {}).get("vcse") or \
                               any(lot.get("suitability", {}).get("vcse") for lot in lots_raw)
            is_sme_suitable = tender_raw.get("suitability", {}).get("sme") or \
                              any(lot.get("suitability", {}).get("sme") for lot in lots_raw)
            
            # Testing Adjustment: If no suitability flags exist, we allow it (Soft Gate)
            # rather than strictly excluding.
            if not is_vcse_suitable and not is_sme_suitable and \
               (tender_raw.get("suitability") or any(lot.get("suitability") for lot in lots_raw)):
                dropped_vcse += 1
                continue
            
            if is_vcse_suitable:
                recommendation_reasons.append("Explicitly marked for VCSE suitability.")
            elif is_sme_suitable:
                recommendation_reasons.append("Marked for SME suitability.")
            else:
                recommendation_reasons.append("Generic suitability (No specific SME/VCSE flags).")

            # ═══════════════════════════════════════════
            # STAGE 3: VALUE GATE (Hard Exclude > 40%)
            # ═══════════════════════════════════════════
            val = float(notice.value_amount or 0)
            
            # Check lots first (PRD 03: if any lot is suitable, tender is suitable)
            suitable_lots = []
            if lots_raw:
                for lot in lots_raw:
                    lot_val = float(lot.get("value", {}).get("amountGross") or lot.get("value", {}).get("amount") or 0)
                    if charity_income > 0 and lot_val <= (charity_income * 0.4):
                        suitable_lots.append(lot)
            
            # If no suitable lots AND total value > 40% income, exclude
            if not suitable_lots and charity_income > 0 and val > (charity_income * 0.4):
                dropped_value += 1
                continue
            
            if suitable_lots:
                recommendation_reasons.append(f"Contains {len(suitable_lots)}/{len(lots_raw)} suitable lots by value.")
            elif notice.value_amount:
                recommendation_reasons.append(f"Tender value is within 40% of annual income.")

            # ═══════════════════════════════════════════
            # STAGE 4: GEO GATE (Hard Match unless National)
            # ═══════════════════════════════════════════
            notice_regions = []
            delivery_locs = tender_raw.get("items", []) # OCDS regions are often here
            for itm in delivery_locs:
                locs = itm.get("deliveryAddresses", [])
                for l in locs:
                    r = l.get("region")
                    if r: notice_regions.append(r.lower())

            # Fallback to parties if items are empty
            if not notice_regions:
                for p in notice.raw_json.get("parties", []):
                    if "buyer" in p.get("roles", []):
                        r = p.get("address", {}).get("region")
                        if r: notice_regions.append(r.lower())

            geo_overlap = set(notice_regions) & set(charity_regions)
            
            if is_national:
                # National charities get 1.0 if local match, else 0.25 bonus
                score_geo = 1.0 if (geo_overlap or not notice_regions) else 0.25
            else:
                if notice_regions and geo_overlap:
                    score_geo = 1.0
                elif not notice_regions:
                    score_geo = 0.5 # Neutral if geo unknown
                else:
                    dropped_geo += 1
                    continue # No geo overlap for regional charity

            recommendation_reasons.append(f"Geographic Alignment: {'Local Match' if geo_overlap else 'National Reach'}")

            # ═══════════════════════════════════════════
            # STAGE 5: CPV PREFIX MATCH (Hard Gate)
            # ═══════════════════════════════════════════
            # Tier 2 Logic: Use 4-digit prefixes for better precision
            notice_cpv_prefixes = set(c[:4] for c in (notice.cpv_codes or []))
            
            if charity_cpv_prefixes and notice_cpv_prefixes:
                if not (notice_cpv_prefixes & charity_cpv_prefixes):
                    dropped_cpv += 1
                    continue 
                score_domain = 1.0
            else:
                score_domain = 0.5 
            
            recommendation_reasons.append("Sector (CPV) alignment confirmed at prefix level.")

            # ═══════════════════════════════════════════
            # NEW STAGE: EXCLUSION KEYWORDS (Hard Gate)
            # ═══════════════════════════════════════════
            if exclusion_kws:
                content = f"{notice.title} {notice.description}".lower()
                matched_exclusions = [kw for kw in exclusion_kws if kw in content]
                if matched_exclusions:
                    dropped_exclusion += 1
                    continue

            # ═══════════════════════════════════════════
            # STAGE 6: UKCAT THEME MATCH (Scoring)
            # ═══════════════════════════════════════════
            notice_ukcat = set(notice.inferred_ukcat_codes or [])
            # Check if any notice code starts with our charity theme prefixes
            theme_matches = {p for p in charity_ukcat_codes if any(code.startswith(p) for code in notice_ukcat)}
            score_theme = len(theme_matches) / len(charity_ukcat_codes) if charity_ukcat_codes else 0.5
            
            if theme_matches:
                recommendation_reasons.append(f"Thematic overlap: {', '.join(list(theme_matches)[:3])}...")

            # ═══════════════════════════════════════════
            # STAGE 7: FINAL SCORING & ENRICHMENT
            # ═══════════════════════════════════════════
            
            # Semantic (pgvector cosine fallback)
            score_semantic = 0.0
            target_emb = notice.provider_summary_embedding or notice.embedding
            
            # Using is not None for array-safe truth check
            if target_emb is not None and profile.profile_embedding is not None:
                import numpy as np
                a, b = np.array(profile.profile_embedding), np.array(target_emb)
                score_semantic = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
                score_semantic = max(0.0, score_semantic)

            # Combined Mechanical Score
            # Weighting: Semantic 40%, Theme 30%, Domain 20%, Geo 10%
            total_score = (score_semantic * 0.40) + \
                          (score_theme * 0.30) + \
                          (score_domain * 0.20) + \
                          (score_geo * 0.10)

            # Risk Flag Scan (Non-AI)
            text_lc = f"{notice.title} {notice.description}".lower()
            if "tupe" in text_lc: risk_flags["TUPE"] = "Staff transfer (TUPE) detected."
            if "safeguarding" in text_lc: risk_flags["Safeguarding"] = "Review safeguarding requirements."
            
            # Suitability metadata for export preservation
            risk_flags["is_vcse"] = is_vcse_suitable
            risk_flags["is_sme"] = is_sme_suitable

            radar_data = self.radar_service.enrich(notice)
            if radar_data["buyer_seen_before"]:
                risk_flags["renewal_radar"] = radar_data
                recommendation_reasons.append("Historical data found for this buyer/sector - strategy enriched.")

            # Status Decision
            # Tier 2 Override: If we have an existing Deep Verdict, it rules.
            existing = existing_matches.get(notice.ocid)
            deep_verdict = existing.deep_verdict if existing else None
            
            status = "GO" if total_score > 0.65 else "REVIEW"
            if risk_flags.get("TUPE"): status = "REVIEW"
            
            if deep_verdict == "PASS":
                status = "GO"
                recommendation_reasons.append("Status forced to GO via Tier 2 PASS verdict.")
            elif deep_verdict == "FAIL":
                status = "NO-GO"
                recommendation_reasons.append("Status forced to NO-GO via Tier 2 FAIL verdict.")

            # Create Record
            match_record = NoticeMatch(
                org_id=profile.org_id,
                notice_id=notice.ocid,
                score=total_score,
                score_semantic=Decimal(str(round(score_semantic, 4))),
                score_domain=Decimal(str(round(score_domain, 4))),
                score_geo=Decimal(str(round(score_geo, 4))),
                score_theme=Decimal(str(round(score_theme, 4))),
                feedback_status=status,
                risk_flags=risk_flags,
                checklist=checklist,
                recommendation_reasons=recommendation_reasons
            )
            matches_to_write.append(match_record)

        # Bulk Merge with preservation of enrichment metadata
        processed_ocids = {m.notice_id for m in matches_to_write}
        
        for m in matches_to_write:
            # Check if we already have a record for this (preserved in memory at start)
            existing = existing_matches.get(m.notice_id)
            
            if existing:
                # Surgically update only the mechanical fields
                existing.score = m.score
                existing.score_semantic = m.score_semantic
                existing.score_domain = m.score_domain
                existing.score_geo = m.score_geo
                existing.score_theme = m.score_theme
                existing.feedback_status = m.feedback_status
                existing.risk_flags = m.risk_flags
                existing.checklist = m.checklist
                existing.recommendation_reasons = m.recommendation_reasons
                # deep_verdict and deep_rationale remain untouched
            else:
                self.db.add(m)
        
        # Clean up stale matches (no longer passing gates)
        # BUT: Preserve them if they have a Deep Verdict!
        for ocid, em in existing_matches.items():
            if ocid not in processed_ocids and em.deep_verdict is None:
                self.db.delete(em)
        
        self.db.commit()
        
        log_msg = f"  {profile.name} Complete: {len(matches_to_write)} matches processed."
        logger.info(log_msg)
        print(log_msg)
