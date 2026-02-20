import sys
import os
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine

def verify():
    with engine.connect() as conn:
        print("Initial check...")
        res = conn.execute(text("SELECT notice_id, deep_verdict FROM notice_match LIMIT 3"))
        rows = res.fetchall()
        for row in rows:
            print(f"Row: {row[0]}, Verdict: {row[1]}")
            
        if not rows:
            print("No rows in notice_match!")
            return

        target_id = rows[0][0]
        print(f"\nUpdating {target_id} to 'SQL_TEST'...")
        conn.execute(text(f"UPDATE notice_match SET deep_verdict='SQL_TEST' WHERE notice_id='{target_id}'"))
        conn.commit()
        
        print("Reading back...")
        res2 = conn.execute(text(f"SELECT deep_verdict FROM notice_match WHERE notice_id='{target_id}'"))
        print(f"Read back result: {res2.fetchone()[0]}")
        
verify()
