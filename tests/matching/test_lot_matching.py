import pytest
import sys
import os
from datetime import datetime, timedelta
import uuid

# Ensure app module is found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock pgvector/postgresql for local testing
from unittest.mock import MagicMock
import sqlalchemy
import sqlalchemy.types as types
sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()
sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()
sys.modules["sqlalchemy.dialects.postgresql"] = MagicMock()
sys.modules["sqlalchemy.dialects.postgresql"].JSONB = types.JSON
sys.modules["sqlalchemy.dialects.postgresql"].UUID = types.UUID
sqlalchemy.ARRAY = sqlalchemy.JSON

from app.services.matching.engine import MatchingEngine
from app.models import ServiceProfile, Notice, NoticeMatch

@pytest.fixture
def test_org(db):
    org = ServiceProfile(
        org_id=uuid.uuid4(),
        name="Small Charity",
        latest_income=100000, # 100k income
        min_contract_value=5000,
        max_contract_value=60000,
        profile_embedding=[0.1]*1536
    )
    db.add(org)
    db.commit()
    return org

def test_mixed_lot_suitability_turnover(db, test_org):
    """Test that a high-value total notice is GO if lots are small enough."""
    # Total value 200k ( > 50% of 100k)
    # But Lots are 40k each ( < 50% of 100k)
    # Adding beneficiary match to push score > 0.60
    test_org.beneficiary_groups = ["Children"]
    notice = Notice(
        ocid="lot-test-1",
        title="Big Framework for Children",
        description="A large framework with small lots.",
        publication_date=datetime.now(),
        deadline_date=datetime.now() + timedelta(days=60),
        value_amount=200000,
        embedding=[0.1]*1536,
        raw_json={
            "tender": {
                "lots": [
                    {"id": "1", "title": "Lot 1", "value": {"amount": 40000}},
                    {"id": "2", "title": "Lot 2", "value": {"amount": 40000}}
                ]
            }
        }
    )
    db.add(notice)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match = db.query(NoticeMatch).filter_by(notice_id="lot-test-1").first()
    assert match.feedback_status == "GO"
    assert match.viability_warning is None
    assert any("All 2 lots are suitable" in r for r in match.recommendation_reasons)

def test_lot_filtering_by_value_bounds(db, test_org):
    """Test that lots are filtered if they are too small or too large for the charity."""
    # Charity min: 5k, max: 60k
    # Adding beneficiary match to push score > 0.60
    test_org.beneficiary_groups = ["Vulnerable"]
    notice = Notice(
        ocid="lot-test-2",
        title="Mixed Value Lots for Vulnerable Groups",
        description="Notice with varying lot sizes.",
        publication_date=datetime.now(),
        deadline_date=datetime.now() + timedelta(days=60),
        value_amount=150000,
        embedding=[0.1]*1536,
        raw_json={
            "tender": {
                "lots": [
                    {"id": "small", "title": "Too Small", "value": {"amount": 2000}},
                    {"id": "just-right", "title": "Just Right", "value": {"amount": 30000}},
                    {"id": "too-big", "title": "Too Big", "value": {"amount": 80000}}
                ]
            }
        }
    )
    db.add(notice)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match = db.query(NoticeMatch).filter_by(notice_id="lot-test-2").first()
    # status should be GO because one lot is suitable
    assert match.feedback_status == "GO"
    assert any("1/3 suitable lots" in r for r in match.recommendation_reasons)
    # Check that viability warning is None because suitable lots exist
    assert match.viability_warning is None

def test_no_suitable_lots_results_in_review(db, test_org):
    """Test that if no lots are suitable, it falls back to viability warning/REVIEW."""
    # All lots > 50% income (50k)
    notice = Notice(
        ocid="lot-test-3",
        title="Huge Lots",
        description="Notice where every lot is too big.",
        publication_date=datetime.now(),
        deadline_date=datetime.now() + timedelta(days=60),
        value_amount=300000,
        embedding=[0.1]*1536,
        raw_json={
            "tender": {
                "lots": [
                    {"id": "huge-1", "title": "Huge Lot 1", "value": {"amount": 100000}},
                    {"id": "huge-2", "title": "Huge Lot 2", "value": {"amount": 100000}}
                ]
            }
        }
    )
    db.add(notice)
    db.commit()

    engine = MatchingEngine(db)
    engine.calculate_matches(test_org.org_id)

    match = db.query(NoticeMatch).filter_by(notice_id="lot-test-3").first()
    assert match.feedback_status == "REVIEW"
    assert match.viability_warning == "High Risk: Contract value exceeds 50% of annual income."
    assert any("No individual lots found" in r for r in match.recommendation_reasons)
