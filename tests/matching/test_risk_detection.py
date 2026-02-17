import pytest
import sys
import os
from datetime import datetime, timedelta
import uuid

# Ensure app module is found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from unittest.mock import MagicMock

# Mock pgvector/postgresql for local testing (consistent with test_matching_engine.py)
try:
    import pgvector
except ImportError:
    import sqlalchemy
    sys.modules["pgvector"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()

import sqlalchemy.types as types
sys.modules["sqlalchemy.dialects.postgresql"] = MagicMock()
sys.modules["sqlalchemy.dialects.postgresql"].JSONB = types.JSON
sys.modules["sqlalchemy.dialects.postgresql"].UUID = types.UUID

import sqlalchemy
sqlalchemy.ARRAY = sqlalchemy.JSON

from app.services.matching.engine import MatchingEngine
from app.models import ServiceProfile, Notice, NoticeMatch

@pytest.fixture
def test_org(db):
    org = ServiceProfile(
        org_id=uuid.uuid4(),
        name="Test Charity",
        latest_income=1000000,
        profile_embedding=[0.1]*1536
    )
    db.add(org)
    db.commit()
    return org

def test_tupe_detection(db, test_org):
    """Test that TUPE keywords trigger risk flags."""
    notices = [
        Notice(
            ocid="tupe-1",
            title="Cleaning Services (Subject to TUPE)",
            description="Regular cleaning needed. Potential staff transfer involved.",
            publication_date=datetime.now(),
            deadline_date=datetime.now() + timedelta(days=60),
            value_amount=50000,
            embedding=[0.1]*1536,
            raw_json={"tender": {}}
        ),
        Notice(
            ocid="tupe-2",
            title="Landscaping",
            description="General maintenance under transfer of undertakings regulations.",
            publication_date=datetime.now(),
            deadline_date=datetime.now() + timedelta(days=60),
            value_amount=50000,
            embedding=[0.1]*1536,
            raw_json={"tender": {}}
        )
    ]
    for n in notices: db.add(n)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match1 = db.query(NoticeMatch).filter_by(notice_id="tupe-1").first()
    assert "TUPE" in match1.risk_flags
    assert match1.feedback_status == "REVIEW"
    assert any("TUPE" in r for r in match1.recommendation_reasons)

    match2 = db.query(NoticeMatch).filter_by(notice_id="tupe-2").first()
    assert "TUPE" in match2.risk_flags
    assert any("TUPE" in r for r in match2.recommendation_reasons)

def test_safeguarding_detection(db, test_org):
    """Test that safeguarding keywords trigger risk flags."""
    notice = Notice(
        ocid="safe-1",
        title="Youth Mentoring",
        description="Providing support to vulnerable adults in social care. Enhanced DBS required.",
        publication_date=datetime.now(),
        deadline_date=datetime.now() + timedelta(days=60),
        value_amount=50000,
        embedding=[0.1]*1536,
        raw_json={"tender": {}}
    )
    db.add(notice)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match = db.query(NoticeMatch).filter_by(notice_id="safe-1").first()
    assert "Safeguarding" in match.risk_flags
    assert any("safeguarding" in r.lower() for r in match.recommendation_reasons)
    # Check checklist items
    assert any(item['item'] == "Enhanced DBS Checks" for item in match.checklist)

def test_mobilization_timeline_risk(db, test_org):
    """Test that tight mobilization windows trigger caution."""
    # 15 day window ( < 30 )
    pub_date = datetime.now()
    deadline = pub_date + timedelta(days=15)
    
    notice = Notice(
        ocid="mob-1",
        title="Quick Turnaround Service",
        description="Standard delivery.",
        publication_date=pub_date,
        deadline_date=deadline,
        value_amount=50000,
        embedding=[0.1]*1536,
        raw_json={"tender": {}}
    )
    db.add(notice)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match = db.query(NoticeMatch).filter_by(notice_id="mob-1").first()
    assert "Mobilization" in match.risk_flags
    assert any("Tight window" in r for r in match.recommendation_reasons)

def test_no_risk_normal_notice(db, test_org):
    """Test that a standard notice without risks is marked as GO."""
    # Add beneficiary match to ensure score > 0.60
    test_org.beneficiary_groups = ["Children"]
    notice = Notice(
        ocid="normal-1",
        title="Office Equipment Supply for Children",
        description="Bulk purchase of stationery and chairs.",
        publication_date=datetime.now(),
        deadline_date=datetime.now() + timedelta(days=60),
        value_amount=50000,
        embedding=[0.1]*1536, # Perfect match to [0.1]*1536
        raw_json={"tender": {}}
    )
    db.add(notice)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match = db.query(NoticeMatch).filter_by(notice_id="normal-1").first()
    assert not match.risk_flags
    assert match.feedback_status == "GO"
