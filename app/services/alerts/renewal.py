import logging
from datetime import datetime, timedelta
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.models import Notice, Alert, ServiceProfile

logger = logging.getLogger(__name__)

class RenewalService:
    """
    Renewal/Expiry Intelligence (PRD 05).
    Identifies contracts approaching end dates and alerts relevant VCSEs.
    """

    def __init__(self, db: Session):
        self.db = db

    def scan_for_renewals(self, months_ahead: int = 12):
        """
        Scans for contract awards ending soon and alerts matched organizations.
        """
        today = datetime.utcnow()
        horizon = today + timedelta(days=months_ahead * 30)
        
        # 1. Find ending contracts
        ending_notices = self.db.query(Notice)\
            .filter(Notice.notice_type == 'contractAward')\
            .filter(and_(Notice.contract_period_end > today, Notice.contract_period_end <= horizon))\
            .all()
            
        logger.info(f"Found {len(ending_notices)} contracts ending within {months_ahead} months.")
        
        for notice in ending_notices:
            # 2. Find organizations with matching Service Profiles
            # For MVP: Alert any org that "could" deliver this (simplified match)
            # In a full system, we'd use the MatchingEngine results.
            
            # Find all profiles (simplified query)
            profiles = self.db.query(ServiceProfile).all()
            
            for profile in profiles:
                # Check if we should alert this org
                # Logic: If it's a high match or they already track it
                
                # Check for existing match/alert to avoid duplicates
                existing_alert = self.db.query(Alert).filter(
                    Alert.org_id == profile.org_id,
                    Alert.notice_id == notice.ocid,
                    Alert.alert_type == 'RENEWAL'
                ).first()
                
                if not existing_alert:
                    days_left = (notice.contract_period_end - today).days
                    alert = Alert(
                        org_id=profile.org_id,
                        notice_id=notice.ocid,
                        alert_type='RENEWAL',
                        severity='info',
                        message=f"Renewal Alert: Contract for '{notice.title}' ends in ~{days_left // 30} months.",
                        details={
                            "end_date": notice.contract_period_end.isoformat(),
                            "days_to_expiry": days_left
                        }
                    )
                    self.db.add(alert)
                    logger.info(f"Created renewal alert for {profile.org_id} on notice {notice.ocid}")

        self.db.commit()
