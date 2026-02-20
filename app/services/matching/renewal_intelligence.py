import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import text, and_
from sqlalchemy.orm import Session
from app.models import Notice, Alert, ServiceProfile

logger = logging.getLogger(__name__)

class RenewalIntelligenceService:
    """
    Advanced Procurement Forecasting (Phase 3 of Bid Readiness).
    Analyzes historical clusters to predict future lifecycle stages.
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze_cycles(self, cpv_prefix: str, buyer_id: str) -> Optional[int]:
        """
        Heuristic: Find the average gap (in years) between awards for a specific buyer/CPV.
        """
        query = text("""
            SELECT publication_date 
            FROM notice 
            WHERE buyer_id = :buyer_id 
              AND :cpv_prefix = ANY(cpv_codes)
              AND notice_type IN ('contractAward', 'historical')
            ORDER BY publication_date ASC
        """)
        
        results = self.db.execute(query, {"buyer_id": buyer_id, "cpv_prefix": cpv_prefix}).fetchall()
        
        if len(results) < 2:
            return None # Not enough history to establish a cycle
            
        gaps = []
        for i in range(1, len(results)):
            gap = (results[i][0] - results[i-1][0]).days / 365.25
            # Procurement cycles are typically 1, 2, 3, 4, or 5 years.
            # Round to nearest integer if reasonably close.
            if 0.5 < gap < 6.5:
                gaps.append(round(gap))
                
        if not gaps:
            return None
            
        return int(sum(gaps) / len(gaps))

    def predict_next_lifecycle(self, notice: Notice) -> Dict:
        """
        Given a historical notice, predict its next lifecycle events.
        """
        # 1. Establish Cycle
        cpv_prefix = notice.cpv_codes[0][:4] if notice.cpv_codes else None
        cycle_years = self.analyze_cycles(cpv_prefix, str(notice.buyer_id)) if cpv_prefix else None
        
        # Fallback to contract duration if cycle is unknown
        if not cycle_years and notice.contract_period_start and notice.contract_period_end:
            duration = (notice.contract_period_end - notice.contract_period_start).days / 365.25
            cycle_years = round(duration)

        if not cycle_years:
            cycle_years = 3 # Industry default for service contracts

        # 2. Project Dates
        base_date = notice.publication_date
        next_tender_date = base_date + timedelta(days=cycle_years * 365.25)
        
        return {
            "cycle_years": cycle_years,
            "next_procure_date": next_tender_date,
            "next_define_date": next_tender_date - timedelta(days=180), # 6 months for PME
            "next_plan_date": next_tender_date - timedelta(days=365),    # 1 year for strategic planning
            "incumbent": notice.raw_json.get("awards", [{}])[0].get("suppliers", [{}])[0].get("name") if notice.raw_json else "Unknown"
        }

    def generate_strategic_alerts(self):
        """
        Scan historical data and create prospective alerts for nonprofits.
        """
        # This would eventually run as a background cron job.
        # For now, we'll run it on the last 5 years of data.
        logger.info("Generating Strategic Lifecycle Alerts...")
        
        # Implementation details:
        # Loop over charities -> Match Interest Mesh -> Find Historical cycles -> Create alerts.
        # [Placeholder for full loop logic]
        pass
