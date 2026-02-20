import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import NoticeMatch

def check():
    print("--- Database Check ---")
    db = SessionLocal()
    try:
        total = db.query(NoticeMatch).count()
        has_verdict = db.query(NoticeMatch).filter(NoticeMatch.deep_verdict.isnot(None)).count()
        has_rationale = db.query(NoticeMatch).filter(NoticeMatch.deep_rationale.isnot(None), NoticeMatch.deep_rationale != '').count()
        
        print(f"Total Matches: {total}")
        print(f"Matches with Verdict: {has_verdict}")
        print(f"Matches with Rationale: {has_rationale}")
        
        if has_rationale > 0:
            sample = db.query(NoticeMatch).filter(NoticeMatch.deep_rationale.isnot(None), NoticeMatch.deep_rationale != '').first()
            print(f"Sample Rationale (first 50 chars): {sample.deep_rationale[:50]}...")
    finally:
        db.close()

    print("\n--- File System Check ---")
    files = [f for f in os.listdir('.') if f.startswith(('fast_gateway_results_v', 'matching_results_v'))]
    files.sort()
    for f in files:
        stats = os.stat(f)
        mtime = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{f:<30} | {stats.st_size:>10} bytes | {mtime}")

if __name__ == "__main__":
    check()
