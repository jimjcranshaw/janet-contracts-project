
import logging
import sys

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from app.database import SessionLocal
from app.services.matching.identity_matcher import IdentityMatcher
from app.models import ServiceProfile, Notice

db = SessionLocal()
matcher = IdentityMatcher(db)

# 1. Get Shelter
shelter = db.query(ServiceProfile).filter(ServiceProfile.name.ilike('%Shelter%')).first()
print(f"Charity: {shelter.name}")

# 2. Get Tender
ocid = "ocds-h6vhtk-05eb01" # North Area Council
tender = db.query(Notice).filter(Notice.ocid == ocid).first()
if not tender:
    print("Tender not found!")
    sys.exit(1)
    
print(f"Tender: {tender.title}")

# 3. Check Pre-flight
print("--- Pre-Flight Check ---")
try:
    pre_check = matcher._pre_flight_check(shelter, tender)
    print(f"Pre-flight Result: {pre_check}")
    
    # Debug keywords
    text_source = (shelter.mission or "") + " " + (shelter.programs_services or "")
    keywords = set(w.lower() for w in text_source.split() if len(w) > 4)
    if shelter.beneficiary_groups:
        for g in shelter.beneficiary_groups:
            keywords.add(g.lower())
    
    tender_text = (tender.title or "").lower() + " " + (tender.description or "").lower()
    matches = [kw for kw in keywords if kw in tender_text]
    print(f"Matched Keywords: {matches}")
    
except Exception as e:
    print(f"Error in Pre-flight: {e}")

# 4. Check LLM
if pre_check:
    print("--- LLM Check ---")
    try:
        # Create a list for batch_screen
        batch = [tender]
        results = matcher.batch_screen(shelter, batch)
        print(f"LLM Result for {ocid}: {results.get(ocid)}")
    except Exception as e:
        print(f"Error in LLM: {e}")
else:
    print("Skipping LLM (Pre-flight failed)")

db.close()
