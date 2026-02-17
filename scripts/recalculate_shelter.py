
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from app.database import SessionLocal
from app.services.matching.engine import MatchingEngine
from app.models import ServiceProfile

print("Starting Shelter Recalculation...", flush=True)
db = SessionLocal()
shelter = db.query(ServiceProfile).filter(ServiceProfile.name.ilike('%Shelter%')).first()

if shelter:
    print(f"Found Profile: {shelter.name} ({shelter.org_id})", flush=True)
    engine = MatchingEngine(db)
    
    print("running calculate_matches()...", flush=True)
    engine.calculate_matches(shelter.org_id)
    print("Done.", flush=True)
else:
    print("Shelter not found!", flush=True)

db.close()
