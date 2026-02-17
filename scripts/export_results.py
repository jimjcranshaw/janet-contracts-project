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
from app.services.matching.consortium_service import ConsortiumService
from app.services.matching.social_value_service import SocialValueService

def export_results():
    db = SessionLocal()
    engine = MatchingEngine(db)
    consortium_service = ConsortiumService(db)
    sv_service = SocialValueService(db)
    
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
            
            # --- OPTIMIZATION (PRD 08/PRD 03) ---
            # Only do expensive LLM analysis for matches with a decent base score
            consortium = {"recommended": False, "reasons": []}
            sv_fit = {"fit_score": 0.0, "gaps": []}
            
            if score > 0.4:
                consortium = consortium_service.recommend_consortium(n.ocid, charity.org_id)
                sv_fit = sv_service.analyze_social_value_fit(charity.org_id, n.ocid)
            
            # Format row
            row = {
                "Charity Name": charity.name,
                "Charity Income": f"£{charity.latest_income:,.2f}" if charity.latest_income else "N/A",
                "Tender OCID": n.ocid,
                "Tender Title": n.title,
                "Tender Value": n.value_amount,
                "Total Score": score,
                "Semantic Score": float(m.score_semantic) if m.score_semantic else 0.0,
                "Geo Score": float(m.score_geo) if m.score_geo else 0.0,
                "Domain Score": float(m.score_domain) if m.score_domain else 0.0,
                "Decision": m.feedback_status,
                "Viability Warning": m.viability_warning,
                "Risk Flags": ", ".join(m.risk_flags.keys()) if m.risk_flags else "",
                "Consortium Recommended": "Yes" if consortium.get('recommended') else "No",
                "Consortium Reason": "; ".join(consortium.get('reasons', [])) if isinstance(consortium.get('reasons'), list) else "",
                "Social Value Fit Score": sv_fit.get('fit_score', 0.0),
                "Social Value Gaps": len(sv_fit.get('gaps', [])) if isinstance(sv_fit.get('gaps'), list) else 0
            }
            all_data.append(row)

            
    df = pd.DataFrame(all_data)
    
    # Save to Excel
    output_file = "matching_results.xlsx"
    df.to_excel(output_file, index=False)
    print(f"--- Export Complete: {output_file} ({len(all_data)} rows) ---")
    
    db.close()

if __name__ == "__main__":
    export_results()
