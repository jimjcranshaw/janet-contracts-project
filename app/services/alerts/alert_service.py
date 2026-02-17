import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models import Notice, NoticeMatch, Alert
import uuid

logger = logging.getLogger(__name__)

class AlertService:
    """
    Detects 'Material Changes' between OCDS releases (PRD 04).
    """

    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, org_id: uuid.UUID, notice_id: str, alert_type: str, message: str, severity: str = "info", details: dict = None):
        """Creates a structured alert record."""
        alert = Alert(
            org_id=org_id,
            notice_id=notice_id,
            alert_type=alert_type,
            message=message,
            severity=severity,
            details=details
        )
        self.db.add(alert)
        return alert

    def check_for_changes(self, existing_notice: Notice, new_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # ... logic remains same ...
        changes = {}
        new_deadline = new_data.get("deadline_date")
        if new_deadline and existing_notice.deadline_date:
            if new_deadline != existing_notice.deadline_date:
                changes["deadline"] = {"old": existing_notice.deadline_date.isoformat(), "new": new_deadline.isoformat()}
        
        new_value = new_data.get("value_amount")
        if new_value is not None and existing_notice.value_amount is not None:
            diff_pct = abs(new_value - float(existing_notice.value_amount)) / float(existing_notice.value_amount) if existing_notice.value_amount != 0 else 0
            if diff_pct > 0.10:
                changes["value"] = {"old": float(existing_notice.value_amount), "new": new_value, "diff_pct": round(diff_pct * 100, 2)}
        
        new_type = new_data.get("notice_type")
        if new_type and existing_notice.notice_type != new_type:
            changes["type"] = {"old": existing_notice.notice_type, "new": new_type}
            
        return changes if changes else None

    def process_change(self, notice_ocid: str, changes: Dict[str, Any]):
        """Updates NoticeMatch records and creates Alerts."""
        matches = self.db.query(NoticeMatch).filter(NoticeMatch.notice_id == notice_ocid).all()
        
        for match in matches:
            reasons = list(match.recommendation_reasons) if match.recommendation_reasons else []
            
            for key, val in changes.items():
                msg = ""
                if key == "deadline": msg = f"ALERT: Deadline changed from {val['old'][:10]} to {val['new'][:10]}."
                elif key == "value": msg = f"ALERT: Value changed by {val['diff_pct']}% (Now £{val['new']:,.0f})."
                elif key == "type": msg = f"ALERT: Notice type changed to {val['new']}."
                
                if msg:
                    reasons.append(msg)
                    self.create_alert(match.org_id, notice_ocid, "MATERIAL_CHANGE", msg, "warning", {key: val})

            if "value" in changes and match.feedback_status == "GO":
                match.feedback_status = "REVIEW"
            
            match.recommendation_reasons = reasons
        
        self.db.commit()
