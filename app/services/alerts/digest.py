import logging
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Alert, Notice, ServiceProfile

logger = logging.getLogger(__name__)

class DigestService:
    """
    Generates notification digests (PRD 05).
    """

    def __init__(self, db: Session):
        self.db = db

    def generate_daily_digest(self, org_id: str) -> str:
        """
        Creates a markdown summary of alerts from the last 24 hours.
        """
        yesterday = datetime.utcnow() - timedelta(days=1)
        alerts = self.db.query(Alert)\
            .filter(Alert.org_id == org_id, Alert.created_at >= yesterday)\
            .all()
            
        if not alerts:
            return "No new updates for your profile in the last 24 hours."

        org = self.db.get(ServiceProfile, org_id)
        digest = f"# Daily Opportunity Digest for {org.name}\n"
        digest += f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"

        # Group by type
        changes = [a for a in alerts if a.alert_type == 'MATERIAL_CHANGE']
        renewals = [a for a in alerts if a.alert_type == 'RENEWAL']
        new_matches = [a for a in alerts if a.alert_type == 'NEW_MATCH']

        if changes:
            digest += "## ⚡ Material Changes to Tracked Notices\n"
            for a in changes:
                digest += f"- **{a.message}** (Notice: {a.notice_id})\n"
            digest += "\n"

        if renewals:
            digest += "## 📅 Upcoming Renewals / Re-tenders\n"
            for a in renewals:
                digest += f"- {a.message} (OCID: {a.notice_id})\n"
            digest += "\n"

        if new_matches:
            digest += "## ✨ New High-Score Matches\n"
            for a in new_matches:
                digest += f"- {a.message} (OCID: {a.notice_id})\n"
            digest += "\n"

        digest += "---\n*This is an automated digest from Grants AI (Procurement Module).*"
        return digest
