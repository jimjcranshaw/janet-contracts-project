import sys
import os
import pandas as pd
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, Notice, NoticeMatch
from app.services.matching.engine import MatchingEngine

def run_fast_match():
    db = SessionLocal()
    engine = MatchingEngine(db)
    
    charities = db.query(ServiceProfile).all()
    print(f"--- Fast Gateway Match & Export for {len(charities)} Charities ---")
    
    all_data = []
    
    for i, charity in enumerate(charities):
        print(f"[{i+1}/{len(charities)}] Matching {charity.name}...")
        
        # 1. Run the optimized filter funnel
        engine.calculate_matches(charity.org_id)
        
        # 2. Fetch matches that passed the gates
        matches = db.query(NoticeMatch, Notice).join(
            Notice, NoticeMatch.notice_id == Notice.ocid
        ).filter(
            NoticeMatch.org_id == charity.org_id,
            NoticeMatch.score > 0  # Passed gates
        ).all()
        
        print(f"    -> Found {len(matches)} suitable matches")
        
        for m, n in matches:
            flags = m.risk_flags or {}
            row = {
                "Charity Name": charity.name,
                "Charity Income": f"£{charity.latest_income:,.2f}" if charity.latest_income else "N/A",
                "Tender Title": n.title,
                "Tender Value": f"£{float(n.value_amount):,.2f}" if n.value_amount else "N/A",
                "Overall Score": float(m.score),
                "Semantic Score": float(m.score_semantic) if m.score_semantic else 0.0,
                "UKCAT Score": float(m.score_theme) if m.score_theme else 0.0,
                "Domain Score": float(m.score_domain) if m.score_domain else 0.0,
                "Geo Score": float(m.score_geo) if m.score_geo else 0.0,
                "Notice CPV Codes": ", ".join(n.cpv_codes or []),
                "Charity CPV codes": ", ".join(charity.inferred_cpv_codes or []),
                "Tier 2 Verdict": m.deep_verdict or "PENDING",
                "Tier 2 Rationale": m.deep_rationale or "",
                "SME Suitable": flags.get("is_sme", "N/A"),
                "VCSE Suitable": flags.get("is_vcse", "N/A"),
                "Decision": m.feedback_status,
                "Risk Flags": ", ".join(k for k in flags.keys() if not k.startswith("is_")) if flags else "",
                "Recommendation Reasons": "; ".join(m.recommendation_reasons or []),
                "OCID": n.ocid
            }
            all_data.append(row)

    if all_data:
        # Sort by Charity Name then Overall Score descending
        df = pd.DataFrame(all_data)
        df = df.sort_values(by=["Charity Name", "Overall Score"], ascending=[True, False])
        
        # New: Filter to top 50 matches (Tier 1) vs Deep Matches (Tier 2)
        # For now, we export everything but label them.
        output_file = "fast_gateway_results_v12.xlsx"
        
        # Force refresh of session objects to see fresh DB state
        db.expire_all()
        
        df.to_excel(output_file, index=False)
        print(f"\n--- Export Complete: {output_file} ({len(all_data)} rows) ---")
    else:
        print("\n--- No matches passed the gateways. ---")
    
    db.close()

if __name__ == "__main__":
    run_fast_match()
