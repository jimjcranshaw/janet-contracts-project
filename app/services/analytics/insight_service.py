import logging
from typing import List, Dict, Any
from app.services.analytics.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

class InsightService:
    """
    Generates actionable 'Insight Cards' (PRD 06).
    """

    def __init__(self, analytics: AnalyticsService):
        self.analytics = analytics

    def generate_insights(self) -> List[Dict[str, Any]]:
        """
        Runs multiple checks and returns a list of insights.
        """
        insights = []
        
        # 1. Lot size trend
        lot_stats = self.analytics.get_lot_distribution_stats()
        if lot_stats["avg_lot_value"] > 1000000: # Threshold for 'Large'
            insights.append({
                "title": "Large Lot Sizes Detected",
                "message": f"Average lot value is £{lot_stats['avg_lot_value']:,.0f}. Larger bundles often favor consortium bids for smaller charities.",
                "type": "strategy",
                "severity": "info"
            })
        elif lot_stats["avg_lots_per_notice"] > 5:
            insights.append({
                "title": "Highly Partitioned Market",
                "message": f"Notices in your area average {lot_stats['avg_lots_per_notice']:.1f} lots. This is favorable for niche/SME bidding.",
                "type": "opportunity",
                "severity": "success"
            })

        # 2. Route-to-market trend
        route_stats = self.analytics.get_route_to_market_trends()
        framework_count = route_stats.get("framework", 0) + route_stats.get("selective", 0)
        open_count = route_stats.get("open", 0)
        
        if framework_count > open_count:
            insights.append({
                "title": "Restricted Market Signal",
                "message": "More work is being tendered via Selective/Framework routes than Open. Ensure you are on relevant regional frameworks.",
                "type": "risk",
                "severity": "warning"
            })

        # 3. Spend concentration (Top CPVs)
        taxonomy_stats = self.analytics.get_spend_by_taxonomy(years=1)
        if taxonomy_stats:
            top_cpv = taxonomy_stats[0]
            insights.append({
                "title": f"Growth in {top_cpv['cpv']}",
                "message": f"Spend in this category has reached £{top_cpv['value']:,.0f} across {top_cpv['count']} notices.",
                "type": "trend",
                "severity": "info"
            })

        return insights
