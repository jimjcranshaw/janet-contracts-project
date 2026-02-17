import sys
import os
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, Notice, NoticeMatch
from app.services.matching.engine import MatchingEngine
from app.services.matching.consortium_service import ConsortiumService
from app.services.matching.social_value_service import SocialValueService

def evaluate_matches():
    db = SessionLocal()
    engine = MatchingEngine(db)
    consortium_service = ConsortiumService(db)
    sv_service = SocialValueService(db)
    
    charities = db.query(ServiceProfile).all()
    print(f"--- Evaluating Matches for {len(charities)} Charities ---")
    
    for charity in charities:
        print(f"\n==================================================")
        income_str = f"£{charity.latest_income:,.0f}" if charity.latest_income else "Unknown"
        print(f"CHARITY: {charity.name} (Income: {income_str})")
        print(f"==================================================")
        
        # 1. Trigger batch matching
        engine.calculate_matches(charity.org_id)
        
        # 2. Query top matches from DB
        matches = db.query(NoticeMatch, Notice).join(
            Notice, NoticeMatch.notice_id == Notice.ocid
        ).filter(
            NoticeMatch.org_id == charity.org_id
        ).order_by(NoticeMatch.score.desc()).limit(5).all()
        
        if not matches:
            print("No matches found.")
            continue

        for i, (m, n) in enumerate(matches):
            print(f"\n{i+1}. MATCH: {n.title}")
            print(f"   Score: {float(m.score):.2f} (Semantic: {float(m.score_semantic):.2f}, Geo: {float(m.score_geo):.2f})")
            print(f"   Decision: {m.feedback_status}")
            
            # Enrichment logic
            consortium = consortium_service.recommend_consortium(n.ocid, charity.org_id)
            sv_fit = sv_service.analyze_social_value_fit(charity.org_id, n.ocid)
            
            if consortium['recommended']:
                print(f"   PARTNERSHIP: Consortium Recommended!")
                for r in consortium['reasons']:
                    print(f"     - {r}")
            
            if sv_fit.get('fit_score'):
                print(f"   SOCIAL VALUE FIT: {sv_fit['fit_score']:.1f}")
                if sv_fit.get('gaps'):
                    print(f"     ⚠ Gaps: {len(sv_fit['gaps'])} requirements missing evidence.")
            
            if m.risk_flags:
                print(f"   RISKS: {list(m.risk_flags.keys())}")

    db.close()

    db.close()

if __name__ == "__main__":
    evaluate_matches()
