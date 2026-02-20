import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, NoticeMatch, Notice
from app.services.matching.llm_match_analyzer import LLMMatchAnalyzer

def trigger_deep_review():
    db = SessionLocal()
    analyzer = LLMMatchAnalyzer(db)
    
    charities = db.query(ServiceProfile).all()
    print(f"--- DeepSeek Tier 2 Review for {len(charities)} Charities ---")
    
    for i, charity in enumerate(charities):
        print(f"[{i+1}/{len(charities)}] Processing {charity.name}...")
        
        # Fetch top 10 matches by score that passed the funnel gates
        top_matches = db.query(NoticeMatch).filter(
            NoticeMatch.org_id == charity.org_id,
            NoticeMatch.score > 0
        ).order_by(NoticeMatch.score.desc()).limit(10).all()
        
        if not top_matches:
            print("    -> No matches found. Skipping.")
            continue
            
        ocids = [m.notice_id for m in top_matches]
        print(f"    -> Analyzing {len(ocids)} candidates...")
        
        # Batch analyze using DeepSeek
        results = analyzer.batch_analyze_matches(str(charity.org_id), ocids)
        
        # Update database
        update_count = 0
        for m in top_matches:
            res = results.get(m.notice_id)
            if res:
                m.deep_verdict = res.get("verdict", "FAIL")
                m.deep_rationale = res.get("rationale")
                db.add(m) # Ensure dirty state for surgical update
                update_count += 1
        
        db.commit()
        print(f"    -> Complete: {update_count} verdicts stored.")
        
    db.close()
    print("\n--- Deep Review Complete ---")

if __name__ == "__main__":
    trigger_deep_review()
