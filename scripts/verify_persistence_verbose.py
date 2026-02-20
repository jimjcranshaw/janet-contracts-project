import os
import sys
import json
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, engine
from app.models import ServiceProfile, NoticeMatch
from app.services.matching.llm_match_analyzer import LLMMatchAnalyzer

def trigger_and_verify():
    print("--- START DEEP REVIEW VERBOSE ---")
    db = SessionLocal()
    analyzer = LLMMatchAnalyzer(db)
    
    # Just do one charity to isolate
    charity = db.query(ServiceProfile).first()
    if not charity:
        print("No charities found!")
        return
        
    print(f"Target Charity: {charity.name} ({charity.org_id})")
    
    top_matches = db.query(NoticeMatch).filter(
        NoticeMatch.org_id == charity.org_id,
        NoticeMatch.score > 0
    ).order_by(NoticeMatch.score.desc()).limit(1).all()
    
    if not top_matches:
        print("No matches found for charity!")
        db.close()
        return
        
    m = top_matches[0]
    print(f"Target Match: {m.notice_id}")
    
    # 1. Clear existing verdict if any
    m.deep_verdict = None
    m.deep_rationale = None
    db.commit()
    print("Cleared existing verdict.")
    
    # 2. Run Analysis
    print("Running LLM analysis (single match)...")
    res = analyzer.analyze_match(str(charity.org_id), m.notice_id)
    
    verdict = res.get("verdict", "FAIL")
    rationale = res.get("rationale", "Test Rationale")
    
    print(f"LLM Result -> Verdict: {verdict}")
    print(f"LLM Result -> Rationale: {rationale[:100]}...")
    
    # 3. Save
    m.deep_verdict = verdict
    m.deep_rationale = rationale
    db.add(m)
    print("Calling db.commit()...")
    db.commit()
    print("db.commit() successful.")
    
    # 4. Verify in SAME session
    print("Verifying in SAME session...")
    db.refresh(m)
    print(f"Same Session Verdict: {m.deep_verdict}")
    print(f"Same Session Rationale: {m.deep_rationale[:50]}...")
    
    db.close()
    
    # 5. Verify in NEW session
    print("\nVerifying in NEW session...")
    db2 = SessionLocal()
    m2 = db2.query(NoticeMatch).get((charity.org_id, m.notice_id))
    print(f"New Session Verdict: {m2.deep_verdict}")
    db2.close()
    
    # 6. Verify via Direct SQL
    print("\nVerifying via DIRECT SQL...")
    with engine.connect() as conn:
        res_sql = conn.execute(text(f"SELECT deep_verdict, deep_rationale FROM notice_match WHERE org_id=:oid AND notice_id=:nid"), 
                               {"oid": charity.org_id, "nid": m.notice_id})
        row = res_sql.fetchone()
        if row:
            print(f"SQL Verdict: {row[0]}")
            print(f"SQL Rationale: {row[1][:50] if row[1] else 'NONE'}...")
        else:
            print("SQL: ROW NOT FOUND!")

if __name__ == "__main__":
    trigger_and_verify()
