from app.database import SessionLocal
from app.models import Notice
from app.services.matching.renewal_intelligence import RenewalIntelligenceService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo_renewal")

def run_demo():
    db = SessionLocal()
    service = RenewalIntelligenceService(db)
    
    # 1. Fetch our real FTS notices (starts with ocds-h6vhtk)
    test_notices = db.query(Notice).filter(Notice.ocid.like('ocds-h6vhtk-%')).limit(5).all()
    
    # Fallback to dummy for local dev if no FTS
    if not test_notices:
        test_notices = db.query(Notice).filter(Notice.ocid.like('ocds-test-%')).all()
    
    if not test_notices:
        logger.warning("No test notices found in DB. Run the backfill script first.")
        return

    print("\n" + "="*50)
    print("STRATEGIC RENEWAL INTELLIGENCE DEMO")
    print("="*50 + "\n")

    for notice in test_notices:
        print(f"Historical Notice: {notice.title}")
        print(f"Buyer: {notice.buyer.canonical_name if notice.buyer else 'Unknown'}")
        print(f"Publication Date: {notice.publication_date.date()}")
        
        # 2. Predict next lifecycle
        prediction = service.predict_next_lifecycle(notice)
        
        print(f"\nPredicted Cycle: {prediction['cycle_years']} years")
        print(f"Current Incumbent: {prediction['incumbent']}")
        
        print("\n--- STRATEGIC LIFECYCLE GUIDE ---")
        print(f"1. [PLAN]   By {prediction['next_plan_date'].date()}: Identify potential consortium partners.")
        print(f"2. [DEFINE] By {prediction['next_define_date'].date()}: Prepare outcomes data for Market Engagement.")
        print(f"3. [PROCURE] Predicted Re-tender: {prediction['next_procure_date'].date()}")
        
        print("\n" + "-"*30 + "\n")

    db.close()

if __name__ == "__main__":
    run_demo()
