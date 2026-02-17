
print("Starting debug_imports.py...", flush=True)
import time

t0 = time.time()
try:
    from app.database import SessionLocal
    print(f"Imported SessionLocal in {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"Error importing SessionLocal: {e}", flush=True)

t0 = time.time()
try:
    from app.models import ServiceProfile, Notice
    print(f"Imported models in {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"Error importing models: {e}", flush=True)

t0 = time.time()
try:
    print("Pre-importing IdentityMatcher...", flush=True)
    from app.services.matching.identity_matcher import IdentityMatcher
    print(f"Imported IdentityMatcher in {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"Error importing IdentityMatcher: {e}", flush=True)

t0 = time.time()
try:
    print("Pre-importing MatchingEngine...", flush=True)
    from app.services.matching.engine import MatchingEngine
    print(f"Imported MatchingEngine in {time.time()-t0:.2f}s", flush=True)
except Exception as e:
    print(f"Error importing MatchingEngine: {e}", flush=True)

print("Connecting to DB...", flush=True)
t0 = time.time()
try:
    db = SessionLocal()
    print(f"Connected in {time.time()-t0:.2f}s", flush=True)
    
    print("Querying Shelter...", flush=True)
    t0 = time.time()
    shelter = db.query(ServiceProfile).filter(ServiceProfile.name.ilike('%Shelter%')).first()
    print(f"Query returned {shelter.name if shelter else 'None'} in {time.time()-t0:.2f}s", flush=True)
    
    if shelter:
        print("Initializing IdentityMatcher...", flush=True)
        matcher = IdentityMatcher(db)
        
        print("Running pre-flight check...", flush=True)
        dummy = Notice(title="Advice Homeless", description="Support")
        res = matcher._pre_flight_check(shelter, dummy)
        print(f"Pre-flight result: {res}", flush=True)
        
except Exception as e:
    print(f"Error in runtime: {e}", flush=True)
finally:
    if 'db' in locals():
        db.close()
