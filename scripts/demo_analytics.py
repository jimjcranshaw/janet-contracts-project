import sys
import os
from datetime import datetime, timedelta
import uuid

# Ensure app module is found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup SQLite for reliable cross-platform demo (same as previous demo)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock
import sqlalchemy
import sqlalchemy.types as types

sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()
sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()

# Force SQLAlchemy to use JSON for ARRAY/JSONB/UUID in SQLite
sqlalchemy.ARRAY = lambda x: types.JSON()
from sqlalchemy.dialects import postgresql as pg
pg.JSONB = types.JSON
pg.UUID = types.UUID
pg.ARRAY = lambda x: types.JSON()

from app.models import Base, Notice
from app.services.analytics.analytics_service import AnalyticsService
from app.services.analytics.insight_service import InsightService

def run_analytics_demo():
    engine = create_engine("sqlite:///:memory:", 
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("--- 1. Seed Simulated Data ---")
    
    # 1. High value notice with lots
    n1 = Notice(
        ocid="ana-1",
        title="Major Health Framework",
        description="Health services across London.",
        value_amount=5000000,
        cpv_codes=["85000000"],
        procurement_method="selective", # Selective/Framework
        raw_json={
            "tender": {
                "lots": [
                    {"id": "L1", "title": "Lot 1", "value": {"amount": 2000000}},
                    {"id": "L2", "title": "Lot 2", "value": {"amount": 3000000}}
                ]
            }
        },
        publication_date=datetime.now()
    )
    
    # 2. Open notice with many small lots
    n2 = Notice(
        ocid="ana-2",
        title="Social Care Support",
        description="Daily support services.",
        value_amount=500000,
        cpv_codes=["85310000"],
        procurement_method="open",
        raw_json={
            "tender": {
                "lots": [{"id": str(i), "value": {"amount": 50000}} for i in range(10)]
            }
        },
        publication_date=datetime.now()
    )
    
    db.add_all([n1, n2])
    db.commit()

    print("--- 2. Run Analytics ---")
    analytics = AnalyticsService(db)
    
    taxonomy = analytics.get_spend_by_taxonomy()
    print("\nSpend by Taxonomy:")
    for item in taxonomy:
        print(f"- {item['cpv']}: £{item['value']:,.0f} ({item['count']} notices)")

    routes = analytics.get_route_to_market_trends()
    print(f"\nRoutes to Market: {routes}")

    lots = analytics.get_lot_distribution_stats()
    print(f"\nLot Distribution: {lots}")

    print("\n--- 3. Generate Insights ---")
    insight_service = InsightService(analytics)
    insights = insight_service.generate_insights()
    
    for i in insights:
        print(f"\n[{i['type'].upper()}] {i['title']}")
        print(f"Message: {i['message']}")

    db.close()

if __name__ == "__main__":
    run_analytics_demo()
