from app.database import SessionLocal
from sqlalchemy import text
import json

db = SessionLocal()
rows = db.execute(text("SELECT ocid, raw_json FROM notice WHERE notice_type = 'historical' LIMIT 5")).fetchall()

for ocid, rj in rows:
    print(f"--- {ocid} ---")
    if not rj:
        print("Empty raw_json")
        continue
    
    # Check if it's a release or a release-list
    if isinstance(rj, dict):
        if 'releases' in rj:
            print("Structure: OCDS Release Package (releases list)")
            release = rj['releases'][0]
            tender = release.get('tender', {})
            print("Classification in release:", tender.get('classification'))
        elif 'tender' in rj:
            print("Structure: Flat OCDS Release")
            tender = rj.get('tender', {})
            print("Classification in flat:", tender.get('classification'))
        else:
            print("Structure: Dictionary but unknown keys:", list(rj.keys()))
    else:
        print("Structure: Unexpected type:", type(rj))

db.close()
