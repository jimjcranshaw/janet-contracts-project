from app.database import SessionLocal
from app.models import Notice
import json

db = SessionLocal()
n = db.query(Notice).first()
if n:
    with open("notice_sample.json", "w") as f:
        json.dump(n.raw_json, f, indent=2)
    print("Sample notice saved to notice_sample.json")
else:
    print("No notices found in database.")
db.close()
