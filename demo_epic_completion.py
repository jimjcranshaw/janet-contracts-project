import sys
import os
from datetime import datetime, timedelta
import uuid

# Setup SQLite for reliable cross-platform demo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Mock pgvector for SQLite
from unittest.mock import MagicMock
import sqlalchemy
import sqlalchemy.types as types
sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()
sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()

# Force SQLAlchemy to use JSON for ARRAY/JSONB/UUID in SQLite
sqlalchemy.ARRAY = lambda x: types.JSON()
from sqlalchemy.dialects import postgresql as pg
pg.JSONB = types.JSON
pg.UUID = types.UUID
pg.ARRAY = lambda x: types.JSON()

from app.models import Base, ServiceProfile, Notice, NoticeMatch, Alert, Buyer

# Create SQLite Engine
engine = create_engine("sqlite:///:memory:", 
                       connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
from app.services.ingestion.normalizer import Normalizer
from app.services.matching.engine import MatchingEngine
from app.services.matching.feed import FeedService
from app.services.matching.tracking import TrackingService
from app.services.alerts.alert_service import AlertService
from app.services.alerts.renewal import RenewalService
from app.services.alerts.digest import DigestService

def run_demo():
    db = SessionLocal()
    normalizer = Normalizer()
    matching_engine = MatchingEngine(db)
    feed_service = FeedService(db)
    tracking_service = TrackingService(db)
    alert_service = AlertService(db)
    renewal_service = RenewalService(db)
    digest_service = DigestService(db)

    print("--- 1. Setup Charity Profile ---")
    org_id = uuid.uuid4()
    profile = ServiceProfile(
        org_id=org_id,
        name="Automated Charity",
        latest_income=500000,
        beneficiary_groups=["Children", "Elderly"],
        profile_embedding=[0.1]*1536
    )
    db.add(profile)
    
    buyer = db.query(Buyer).filter(Buyer.slug == "demo-council").first()
    if not buyer:
        buyer = Buyer(canonical_name="Demo Council", slug="demo-council")
        db.add(buyer)
        db.commit()

    print("--- 2. Ingest Initial Award Notice (for Renewal check) ---")
    # Use unique OCID for each run to avoid collisions
    run_uid = str(uuid.uuid4())[:8]
    ocid = f"ocds-demo-{run_uid}"
    
    release_1 = {
        "ocid": ocid,
        "id": "rel-1",
        "date": "2026-01-01T00:00:00Z",
        "tag": ["contractAward"],
        "tender": {
            "title": "Children's Care Service",
            "description": "Providing care for children.",
            "value": {"amount": 100000, "currency": "GBP"},
            "contractPeriod": {
                "startDate": "2026-01-01T00:00:00Z",
                "endDate": (datetime.utcnow() + timedelta(days=240)).isoformat() # 8 months away
            }
        }
    }
    notice_1 = normalizer.map_release_to_notice(release_1, buyer.id)
    notice_1.embedding = [0.1]*1536
    db.add(notice_1)
    db.commit()
    
    print("--- 3. Calculate Matches ---")
    try:
        matching_engine.calculate_matches(org_id)
        print("✓ Matches calculated")
    except Exception as e:
        print(f"FAILED calculating matches: {e}")
        db.rollback()
        raise e
    
    print("--- 4. Simulate Material Change (Rel-2) ---")
    # New release of same OCID, value increased by 50%
    release_2 = release_1.copy()
    release_2["id"] = "rel-2"
    release_2["tender"]["value"]["amount"] = 150000
    
    existing_notice = db.get(Notice, ocid)
    changes = alert_service.check_for_changes(existing_notice, {
        "value_amount": 150000,
        "deadline_date": None,
        "notice_type": "contractAward"
    })
    
    if changes:
        print(f"Detected changes: {changes}")
        alert_service.process_change(ocid, changes)
        print("✓ Changes processed")

    print("--- 5. Run Renewal Scanner ---")
    renewal_service.scan_for_renewals(months_ahead=12)
    print("✓ Renewal scanner complete")

    print("--- 6. Toggle Tracking ---")
    tracking_service.toggle_tracking(org_id, ocid)
    print("✓ Tracking toggled")

    print("--- 7. Fetch Feed & Digest ---")
    feed = feed_service.get_feed(org_id)
    print(f"Feed Items: {len(feed)}")
    for item in feed:
        print(f"- Match: {item.notice_id}, Status: {item.feedback_status}, Tracked: {item.is_tracked}")
    
    digest = digest_service.generate_daily_digest(org_id)
    print("\n--- DAILY DIGEST ---\n")
    print(digest)

    # Cleanup (optional for demo, but good if running repeatedly)
    # db.delete(profile)
    # ...
    db.commit()
    db.close()

if __name__ == "__main__":
    run_demo()
