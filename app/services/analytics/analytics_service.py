import logging
from typing import List, Dict, Any
from sqlalchemy import func, extract, desc
from sqlalchemy.orm import Session
from app.models import Notice

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Detects commissioning trends and packaging shifts (PRD 06).
    """

    def __init__(self, db: Session):
        self.db = db

    def get_spend_by_taxonomy(self, cpv_prefix: str = None, years: int = 1) -> List[Dict[str, Any]]:
        """
        Aggregates notice values by CPV code prefix or full code.
        """
        query = self.db.query(
            Notice.cpv_codes,
            func.sum(Notice.value_amount).label("total_value"),
            func.count(Notice.ocid).label("notice_count")
        )
        
        # This is tricky with ARRAY types in SQL, might need raw SQL or a loop for MVP
        # For MVP: Fetch all and aggregate in Python if DB is small, 
        # or use specialized PG functions for better performance later.
        
        notices = self.db.query(Notice).filter(Notice.value_amount.isnot(None)).all()
        
        stats = {}
        for n in notices:
            for code in (n.cpv_codes or []):
                if cpv_prefix and not code.startswith(cpv_prefix):
                    continue
                
                if code not in stats:
                    stats[code] = {"value": 0.0, "count": 0}
                
                stats[code]["value"] += float(n.value_amount)
                stats[code]["count"] += 1
                
        # Format for output
        result = [{"cpv": k, "value": v["value"], "count": v["count"]} for k, v in stats.items()]
        return sorted(result, key=lambda x: x["value"], reverse=True)

    def get_route_to_market_trends(self) -> Dict[str, Any]:
        """
        Analyzes shifts in procurement methods over time.
        """
        results = self.db.query(
            Notice.procurement_method,
            func.count(Notice.ocid).label("count")
        ).group_by(Notice.procurement_method).all()
        
        return {row[0] or "unknown": row[1] for row in results}

    def get_lot_distribution_stats(self) -> Dict[str, Any]:
        """
        Analyzes lot partitioning trends.
        """
        notices = self.db.query(Notice).filter(Notice.raw_json.isnot(None)).all()
        
        total_lots = 0
        notices_with_lots = 0
        lot_values = []
        
        for n in notices:
            tender = n.raw_json.get("tender", {})
            lots = tender.get("lots", [])
            if lots:
                notices_with_lots += 1
                total_lots += len(lots)
                for lot in lots:
                    val = lot.get("value", {}).get("amount")
                    if val: lot_values.append(float(val))
                    
        return {
            "avg_lots_per_notice": total_lots / notices_with_lots if notices_with_lots > 0 else 0,
            "avg_lot_value": sum(lot_values) / len(lot_values) if lot_values else 0,
            "notices_count": len(notices),
            "notices_with_lots": notices_with_lots
        }
