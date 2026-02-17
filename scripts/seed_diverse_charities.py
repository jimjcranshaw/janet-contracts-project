import sys
import os
import uuid
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import ServiceProfile

def seed_charities():
    db = SessionLocal()
    
    # 1. National Health Giant
    giant = ServiceProfile(
        org_id=uuid.uuid4(),
        name="National Health & Care Alliance",
        charity_number="1234567",
        latest_income=50000000, # £50m
        mission="Providing integrated care and health support services nationwide.",
        vision="A healthier nation through accessible care.",
        programs_services="Large scale community nursing, palliative care centers, national mental health help-lines.",
        target_population="All UK citizens, elderly, mental health patients.",
        service_regions=["London", "South East", "South West", "Midlands", "North East", "North West", "Scotland", "Wales"],
        outcomes_evidence=[
            {"outcome": "Clinical Excellence", "evidence": "CQC Outstanding rating for 5 consecutive years.", "verified": True},
            {"outcome": "National Coverage", "evidence": "Delivered services in 95% of UK local authorities.", "verified": True},
            {"outcome": "Carbon Reduction", "evidence": "ISO 14001 certified with 15% YoY carbon reduction.", "verified": True}
        ]
    )

    # 2. Local Youth Charity (Luton based)
    local = ServiceProfile(
        org_id=uuid.uuid4(),
        name="Luton Future Youth",
        charity_number="7654321",
        latest_income=250000, # £250k (SME)
        mission="Supporting disadvantaged youth in Luton through mentorship and activity.",
        vision="Every young person in Luton reaches their potential.",
        programs_services="Youth clubs, 1-to-1 mentorship, school holiday clubs, employability workshops.",
        target_population="Youth aged 11-19 in Luton and Bedfordshire.",
        service_regions=["Bedfordshire", "East of England"],
        outcomes_evidence=[
            {"outcome": "Local Impact", "evidence": "90% of mentored youth returned to education or employment.", "verified": True},
            {"outcome": "Community Trust", "evidence": "Partnership with Luton Borough Council for 5 years.", "verified": True}
        ]
    )

    # 3. Environment Social Enterprise
    eco = ServiceProfile(
        org_id=uuid.uuid4(),
        name="Eco-Urban Regeneration",
        charity_number="9988776",
        latest_income=1200000, # £1.2m
        mission="Transforming urban spaces into green hubs while providing local jobs.",
        vision="Sustainable cities with vibrant community gardens.",
        programs_services="Urban landscaping, community garden design, vocational training in horticulture.",
        target_population="Urban communities, long-term unemployed.",
        service_regions=["London", "Greater Manchester"],
        outcomes_evidence=[
            {"outcome": "Biodiversity Boost", "evidence": "Created 50+ urban gardens in London.", "verified": True},
            {"outcome": "Local Jobs", "evidence": "Hired 20 local long-term unemployed staff last year.", "verified": True}
        ]
    )

    db.add_all([giant, local, eco])
    db.commit()
    print(f"✓ Seeded 3 diverse charities: {giant.name}, {local.name}, {eco.name}")
    db.close()

if __name__ == "__main__":
    seed_charities()
