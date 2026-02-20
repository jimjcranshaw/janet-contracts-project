import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def extract_fails():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set!")
        return
        
    engine = create_engine(url)
    with engine.connect() as conn:
        print("=== FAIL RATIO ANALYSIS ===")
        # Get total tier 2 count
        total_res = conn.execute(text("SELECT count(*) FROM notice_match WHERE deep_verdict IS NOT NULL"))
        total_t2 = total_res.fetchone()[0]
        
        # Get fail count
        fail_res = conn.execute(text("SELECT count(*) FROM notice_match WHERE deep_verdict = 'FAIL'"))
        fail_t2 = fail_res.fetchone()[0]
        
        print(f"Total Tier 2 Reviews: {total_t2}")
        print(f"Total FAIL Verdicts: {fail_t2}")
        print(f"False Positive Rate (Tier 1 -> Tier 2): {round((fail_t2/total_t2)*100, 2)}%" if total_t2 > 0 else "N/A")
        
        print("\n=== SAMPLE FAIL RATIONALES ===")
        query = text("""
            SELECT s.name as charity, n.title, m.deep_rationale 
            FROM notice_match m 
            JOIN service_profile s ON m.org_id=s.org_id 
            JOIN notice n ON m.notice_id=n.ocid 
            WHERE m.deep_verdict = 'FAIL' 
            ORDER BY s.name ASC
            LIMIT 30
        """)
        res = conn.execute(query)
        rows = res.fetchall()
        for r in rows:
            print(f"Charity: {r[0]}\nTender: {r[1]}\nRationale: {r[2]}\n---")

if __name__ == "__main__":
    extract_fails()
