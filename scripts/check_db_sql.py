import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_db():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set!")
        return
        
    engine = create_engine(url)
    with engine.connect() as conn:
        print("--- DB Integrity Check (SQL) ---")
        
        # Check Total
        res = conn.execute(text("SELECT count(*) FROM notice_match"))
        print(f"Total rows in notice_match: {res.fetchone()[0]}")
        
        # Check Verdicts (Any non-null)
        res = conn.execute(text("SELECT count(*) FROM notice_match WHERE deep_verdict IS NOT NULL"))
        print(f"Rows with deep_verdict IS NOT NULL: {res.fetchone()[0]}")
        
        # Check Rationales (Any non-null)
        res = conn.execute(text("SELECT count(*) FROM notice_match WHERE deep_rationale IS NOT NULL AND deep_rationale != ''"))
        print(f"Rows with non-empty deep_rationale: {res.fetchone()[0]}")
        
        # Sample
        res = conn.execute(text("SELECT org_id, notice_id, deep_verdict, deep_rationale FROM notice_match WHERE deep_verdict IS NOT NULL LIMIT 3"))
        rows = res.fetchall()
        for idx, row in enumerate(rows):
            print(f"Sample {idx+1}: Org={row[0]}, Notice={row[1]}, Verdict={row[2]}, Rationale={row[3][:50]}...")

if __name__ == "__main__":
    check_db()
