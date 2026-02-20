import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, NoticeMatch, Notice
from app.services.matching.llm_match_analyzer import LLMMatchAnalyzer

def trigger_deep_review():
    db = SessionLocal()
    analyzer = LLMMatchAnalyzer(db)
    
    charities = db.query(ServiceProfile).limit(5).all()
    print(f"--- DeepSeek Tier 2 Review for {len(charities)} Charities ---")
    
    for i, charity in enumerate(charities):
        print(f"[{i+1}/{len(charities)}] Processing {charity.name}...")
        
        top_matches = db.query(NoticeMatch).filter(
            NoticeMatch.org_id == charity.org_id,
            NoticeMatch.score > 0
        ).order_by(NoticeMatch.score.desc()).limit(10).all()
        
        if not top_matches: continue
            
        ocids = [m.notice_id for m in top_matches]
        results = analyzer.batch_analyze_matches(str(charity.org_id), ocids)
        
        update_count = 0
        for m in top_matches:
            res = results.get(m.notice_id)
            if res:
                m.deep_verdict = res.get("verdict", "FAIL")
                m.deep_rationale = res.get("rationale")
                db.add(m)
                update_count += 1
        
        db.commit()
        print(f"    -> Updated {update_count} matches.")
        
    db.close()
    print("\n--- Complete ---")

if __name__ == "__main__":
    trigger_deep_review()
