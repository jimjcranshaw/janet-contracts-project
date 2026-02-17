"""Quick check of seeded charity profiles."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.database import SessionLocal
from app.models import ServiceProfile

db = SessionLocal()
profiles = db.query(ServiceProfile).all()
print(f"\n{'Name':<55} {'Income':>15} {'CPVs':>5} {'Rgns':>5} {'BenGrps':>8}")
print("=" * 95)
for p in profiles:
    inc = f"£{p.latest_income:,}" if p.latest_income else "N/A"
    cpvs = len(p.inferred_cpv_codes or [])
    rgns = len(p.service_regions or [])
    bens = len(p.beneficiary_groups or [])
    print(f"{p.name[:55]:<55} {inc:>15} {cpvs:>5} {rgns:>5} {bens:>8}")
print(f"\nTotal profiles: {len(profiles)}")
db.close()
