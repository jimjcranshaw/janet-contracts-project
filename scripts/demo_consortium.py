import sys
import os
import uuid
import json
from datetime import datetime
from unittest.mock import MagicMock

# Setup sys.path for app imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mocking for SQLite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy
import sqlalchemy.types as types

sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()
sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()
sqlalchemy.ARRAY = lambda x: types.JSON()
import sqlalchemy.dialects.postgresql as pg
pg.JSONB = types.JSON
pg.UUID = types.UUID
pg.ARRAY = lambda x: types.JSON()

from app.models import Base, ServiceProfile, Notice, ExtractedRequirement
from app.services.matching.consortium_service import ConsortiumService

def run_consortium_demo():
    # Setup DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("--- 1. Seed Charity Profile (SME Charity) ---")
    org_id = uuid.uuid4()
    profile = ServiceProfile(
        org_id=org_id,
        name="Small Community Support",
        latest_income=200000, # £200k income
        service_regions=["London", "South East"]
    )
    db.add(profile)

    print("--- 2. Seed Large Tender Notice ---")
    ocid = "consortium-demo-1"
    notice = Notice(
        ocid=ocid,
        title="Greater London Social Care Framework",
        description="High-value framework for social care services.",
        value_amount=1000000, # £1m value (way over 50% income)
        publication_date=datetime.now(),
        raw_json={
            "tender": {
                "deliveryAddresses": [
                    {"region": "London"},
                    {"region": "West Midlands"}
                ]
            }
        }
    )
    db.add(notice)
    
    # Add TUPE Risk
    req = ExtractedRequirement(
        notice_id=ocid,
        category="RISK",
        requirement_text="Significant TUPE staff transfers required.",
        risk_level="high"
    )
    db.add(req)
    db.commit()

    print("--- 3. Run Consortium & Proximity Analysis ---")
    service = ConsortiumService(db)
    
    # Check Regional Fit
    reg_fit = service.check_regional_fit(org_id, ocid)
    print(f"\nRegional Fit: {reg_fit['fit'].upper()}")
    print(f"Message: {reg_fit['message']}")

    # Check Consortium Recommendation
    cons_rec = service.recommend_consortium(ocid, org_id)
    print(f"\nConsortium Recommended: {cons_rec['recommended']}")
    if cons_rec['recommended']:
        print("Reasons:")
        for r in cons_rec['reasons']:
            print(f"- {r}")

    db.close()

if __name__ == "__main__":
    run_consortium_demo()
