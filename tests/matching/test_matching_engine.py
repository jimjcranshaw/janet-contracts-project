import pytest
import sys
import os

# Ensure app module is found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from unittest.mock import MagicMock

# Mock pgvector for local testing if not installed
try:
    import pgvector
except ImportError:
    from unittest.mock import MagicMock
    import sqlalchemy
    sys.modules["pgvector"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"] = MagicMock()
    sys.modules["pgvector.sqlalchemy"] = MagicMock()
    # Mock vector as JSON for SQLite
    sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()

# Mock Postgres JSONB for SQLite
import sqlalchemy.types as types
sys.modules["sqlalchemy.dialects.postgresql"] = MagicMock()
sys.modules["sqlalchemy.dialects.postgresql"].JSONB = types.JSON
sys.modules["sqlalchemy.dialects.postgresql"].UUID = types.UUID

import sqlalchemy
sqlalchemy.ARRAY = sqlalchemy.JSON

from unittest.mock import MagicMock
from app.services.matching.engine import MatchingEngine
from app.models import ServiceProfile, Notice, NoticeMatch
from decimal import Decimal
from datetime import datetime
import uuid

def test_matching_engine_viability_gate(db):
    """
    Test that the Matching Engine correctly flags high-risk contracts
    based on the 50% Turnover Rulte.
    """
    # 1. Setup Data
    # 1. Setup Data
    # Note: Using lists for embeddings which mocked Vector type should handle or ignore
    charity = ServiceProfile(
        org_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        name="Small Charity",
        latest_income=100000, 
        profile_embedding=[0.1]*1536
    )
    
    notice_safe = Notice(
        ocid="ocds-safe",
        title="Safe Contract",
        value_amount=40000, # 40k < 50k (OK)
        publication_date=datetime(2023, 1, 1),
        deadline_date=datetime(2030, 1, 1),
        embedding=[0.1]*1536,
        provider_summary_embedding=[0.1]*1536,
        raw_json={}
    )
    
    notice_risky = Notice(
        ocid="ocds-risky",
        title="Risky Contract",
        value_amount=60000, # 60k > 50k (Ratio > 0.5)
        publication_date=datetime(2023, 1, 1),
        deadline_date=datetime(2030, 1, 1),
        embedding=[0.1]*1536,
        provider_summary_embedding=[0.1]*1536,
        raw_json={}
    )
    
    db.add(charity)
    db.add(notice_safe)
    db.add(notice_risky)
    db.commit()
    
    # 2. Run Engine
    engine = MatchingEngine(db)
    engine.calculate_matches(charity.org_id)
    
    # 3. Assertions
    match_safe = db.query(NoticeMatch).get((charity.org_id, "ocds-safe"))
    assert match_safe.viability_warning is None
    assert match_safe.feedback_status == "REVIEW" # Score is 0.55 (Threshold for GO is 0.60)
    
    match_risky = db.query(NoticeMatch).get((charity.org_id, "ocds-risky"))
    assert match_risky.viability_warning == "High Risk: Contract value exceeds 50% of annual income."
    assert match_risky.feedback_status == "REVIEW" # Downgraded due to risk
