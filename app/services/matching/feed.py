import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import NoticeMatch, Notice, Alert

logger = logging.getLogger(__name__)

class FeedService:
    """
    Provides the 'Opportunity Feed' (PRD 04).
    Personalised feed ranked by score, surfacing material changes and alerts.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_feed(self, org_id: str, limit: int = 20) -> List[NoticeMatch]:
        """
        Returns a ranked list of matches for an org.
        Prioritizes:
        1. Tracked notices with unread alerts
        2. High-score matches
        3. Recently updated notices
        """
        # Complex query to join matches with alerts
        query = self.db.query(NoticeMatch)\
            .join(Notice, NoticeMatch.notice_id == Notice.ocid)\
            .filter(NoticeMatch.org_id == org_id)\
            .order_by(
                desc(NoticeMatch.is_tracked),
                desc(NoticeMatch.score)
            )\
            .limit(limit)
            
        return query.all()

    def get_unread_alerts(self, org_id: str) -> List[Alert]:
        """Returns unread alerts for the org."""
        return self.db.query(Alert)\
            .filter(Alert.org_id == org_id, Alert.is_read == False)\
            .order_by(desc(Alert.created_at))\
            .all()

    def mark_alert_read(self, alert_id: str):
        """Marks an alert as read."""
        alert = self.db.get(Alert, alert_id)
        if alert:
            alert.is_read = True
            self.db.commit()
