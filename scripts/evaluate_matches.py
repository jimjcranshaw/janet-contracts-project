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
def evaluate_matches():
    db = SessionLocal()
    engine = MatchingEngine(db)
    
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
            print(f"   Score: {float(m.score):.2f} (Semantic: {float(m.score_semantic):.2f}, UKCAT/Domain: {m.score_domain})")
            print(f"   Decision: {m.feedback_status}")
            
            if m.recommendation_reasons:
                print(f"   REASONS:")
                for r in m.recommendation_reasons:
                    print(f"     - {r}")
            
            if m.risk_flags:
                print(f"   RISKS: {list(m.risk_flags.keys())}")
                for rk, rv in m.risk_flags.items():
                    print(f"     - {rk}: {rv}")

    db.close()

    db.close()

if __name__ == "__main__":
    evaluate_matches()
