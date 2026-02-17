import pytest
import sys
import os
from datetime import datetime, timedelta
import uuid

# Ensure app module is found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock pgvector for local testing
from unittest.mock import MagicMock
import sqlalchemy
sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()

from app.services.alerts.alert_service import AlertService
from app.models import Notice, NoticeMatch, ServiceProfile

def test_deadline_change_detection(db):
    old_date = datetime(2026, 3, 1)
    new_date = datetime(2026, 4, 1)
    
    notice = Notice(ocid="alert-1", deadline_date=old_date, value_amount=1000)
    service = AlertService(db)
    
    changes = service.check_for_changes(notice, {"deadline_date": new_date})
    assert changes is not None
    assert "deadline" in changes
    assert changes["deadline"]["new"] == new_date.isoformat()

def test_material_value_change_detection(db):
    notice = Notice(ocid="alert-2", value_amount=100000)
    service = AlertService(db)
    
    # 15% change (Material)
    changes = service.check_for_changes(notice, {"value_amount": 115000})
    assert "value" in changes
    
    # 5% change (Not Material)
    changes = service.check_for_changes(notice, {"value_amount": 105000})
    assert changes is None or "value" not in changes

def test_process_change_updates_match(db):
    org_id = uuid.uuid4()
    # Setup profile and match
    profile = ServiceProfile(org_id=org_id, name="Test Org")
    db.add(profile)
    
    match = NoticeMatch(
        org_id=org_id,
        notice_id="alert-3",
        feedback_status="GO",
        recommendation_reasons=["Initial matching looks good."]
    )
    db.add(match)
    db.commit()
    
    service = AlertService(db)
    changes = {
        "value": {"old": 100000, "new": 200000, "diff_pct": 100}
    }
    
    service.process_change("alert-3", changes)
    
    # Verify match was updated
    updated_match = db.query(NoticeMatch).get((org_id, "alert-3"))
    assert updated_match.feedback_status == "REVIEW"
    assert any("ALERT: Value changed" in r for r in updated_match.recommendation_reasons)
