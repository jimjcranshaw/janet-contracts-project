import logging
from sqlalchemy.orm import Session
from app.models import NoticeMatch

logger = logging.getLogger(__name__)

class TrackingService:
    """
    Handles 'Tracking' of notices by organizations (PRD 04).
    """

    def __init__(self, db: Session):
        self.db = db

    def toggle_tracking(self, org_id: str, ocid: str) -> bool:
        """Toggles the is_tracked flag for a match."""
        match = self.db.query(NoticeMatch).get((org_id, ocid))
        if not match:
            # Create a shell match if it doesn't exist? 
            # Usually matches are created by the engine, but we can track any notice.
            match = NoticeMatch(org_id=org_id, notice_id=ocid, is_tracked=True, feedback_status="REVIEW")
            self.db.add(match)
            is_now_tracked = True
        else:
            match.is_tracked = not match.is_tracked
            is_now_tracked = match.is_tracked
            
        self.db.commit()
        logger.info(f"Org {org_id} tracking status for {ocid}: {is_now_tracked}")
        return is_now_tracked
