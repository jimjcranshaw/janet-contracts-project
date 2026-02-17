
import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile, Notice, NoticeMatch

def debug_matches():
    db = SessionLocal()
    
    # 1. Get Shelter Profile
    shelter = db.query(ServiceProfile).filter(ServiceProfile.name.ilike('%Shelter%')).first()
    if not shelter:
        print("Error: Shelter profile not found.")
        return

    print(f"\n=== CHARITY: {shelter.name} ===")
    print(f"Income: {shelter.latest_income}")
    print(f"Regions: {shelter.service_regions}")
    print(f"CPVs: {shelter.inferred_cpv_codes}")
    print(f"Beneficiaries: {shelter.beneficiary_groups}")

    # 2. debug specific tenders
    tenders_to_check = [
        "North Area Council Advice", 
        "The Elms"
    ]
    
    for search_term in tenders_to_check:
        print(f"\n--- Checking Tender: '{search_term}' ---")
        tender = db.query(Notice).filter(Notice.title.ilike(f'%{search_term}%')).first()
        
        if not tender:
            print(f"  Tender not found for '{search_term}'")
            continue
            
        print(f"  Title: {tender.title}")
        print(f"  OCID: {tender.ocid}")
        
        # Region from raw_json
        region = "Unknown"
        if tender.raw_json:
            loc = tender.raw_json.get("tender", {}).get("deliveryLocation", [{}])[0]
            region = loc.get("region") or loc.get("description") or "Unknown"
        print(f"  Region: {region}")
        print(f"  CPVs: {tender.cpv_codes}")
        
        # Check match record
        match = db.query(NoticeMatch).filter_by(org_id=shelter.org_id, notice_id=tender.ocid).first()
        if match:
            print(f"  MATCH RECORD FOUND:")
            print(f"    Total Score: {match.score}")
            print(f"    Semantic Score: {match.score_semantic}")
            print(f"    Domain Score: {match.score_domain}")
            print(f"    Geo Score: {match.score_geo}")
            print(f"    Viability Warning: {match.viability_warning}")
        else:
            print("  NO MATCH RECORD FOUND (Likely filtered out before scoring or not in batch)")

    db.close()

if __name__ == "__main__":
    debug_matches()
