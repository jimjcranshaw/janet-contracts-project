import sys
import os
import pandas as pd
from sqlalchemy.orm import Session
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, Notice, NoticeMatch
from app.services.matching.engine import MatchingEngine
def export_results():
    db = SessionLocal()
    engine = MatchingEngine(db)
    
    charities = db.query(ServiceProfile).all()
    print(f"--- Exporting Match Results for {len(charities)} Charities ---")
    
    all_data = []
    
    for i, charity in enumerate(charities):
        print(f"[{i+1}/{len(charities)}] Processing {charity.name} (Income: {charity.latest_income or 'N/A'})...")
        
        # 1. Trigger batch matching for this charity
        # engine.calculate_matches(charity.org_id)
        
        # 2. Fetch all matches from DB
        matches = db.query(NoticeMatch, Notice).join(
            Notice, NoticeMatch.notice_id == Notice.ocid
        ).filter(
            NoticeMatch.org_id == charity.org_id
        ).all()
        
        for m, n in matches:
            score = float(m.score) if m.score else 0.0
            flags = m.risk_flags or {}
            
            # Format row
            row = {
                "Charity Name": charity.name,
                "Charity Income": f"£{charity.latest_income:,.2f}" if charity.latest_income else "N/A",
                "Tender OCID": n.ocid,
                "Tender Title": n.title,
                "Tender Value": n.value_amount,
                "Overall Score": score,
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
                "Viability Warning": m.viability_warning,
                "Risk Flags": ", ".join(k for k in flags.keys() if not k.startswith("is_")) if flags else "",
                "Recommendation Details": "; ".join(m.recommendation_reasons or []),
                "Checklist Items": len(m.checklist or [])
            }
            all_data.append(row)

            
    df = pd.DataFrame(all_data)
    if not df.empty:
        df = df.sort_values(by=["Charity Name", "Overall Score"], ascending=[True, False])
    
    # Save to Excel
    output_file = "matching_results_v3.xlsx"
    df.to_excel(output_file, index=False)
    print(f"--- Export Complete: {output_file} ({len(all_data)} rows) ---")
    
    db.close()

if __name__ == "__main__":
    export_results()
