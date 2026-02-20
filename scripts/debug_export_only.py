import os
import sys
import pandas as pd
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, Notice, NoticeMatch

def run_debug_export():
    load_dotenv()
    db = SessionLocal()
    
    charities = db.query(ServiceProfile).all()
    print(f"--- Debug Rationale Export for {len(charities)} Charities ---")
    
    all_data = []
    
    for charity in charities:
        print(f"Fetching matches for {charity.name}...")
        
        matches = db.query(NoticeMatch, Notice).join(
            Notice, NoticeMatch.notice_id == Notice.ocid
        ).filter(
            NoticeMatch.org_id == charity.org_id,
            NoticeMatch.deep_verdict.isnot(None) # Only ones with verdicts
        ).all()
        
        print(f"    -> Found {len(matches)} matches with verdicts.")
        
        for m, n in matches:
            all_data.append({
                "Charity": charity.name,
                "Notice": n.title,
                "Verdict": m.deep_verdict,
                "Rationale": m.deep_rationale
            })
            
    if all_data:
        df = pd.DataFrame(all_data)
        out = "debug_rationales.xlsx"
        df.to_excel(out, index=False)
        print(f"Exported {len(all_data)} rows to {out}")
    else:
        print("No rationales found in DB across all charities!")
        
    db.close()

if __name__ == "__main__":
    run_debug_export()
