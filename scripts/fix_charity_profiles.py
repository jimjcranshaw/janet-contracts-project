"""
Fix broken 'Search The Register' profiles by deleting them and re-seeding
with charities we know work (5-6 digit CC numbers).

These replacements specifically target smaller and more diverse charities
to properly represent sector diversity.
"""
import sys, os, uuid, json, time, logging, openai
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, settings
from app.models import ServiceProfile
from app.services.ingestion.clients.cc_client import CharityCommissionClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Also delete the old fake charities
FAKE_NAMES = ["Legal Aid UK", "Automated Charity", "National Health & Care Alliance",
              "Luton Future Youth", "Eco-Urban Regeneration"]

# Replacement charities — all have working 5-6 digit CC numbers
# Deliberately chosen for size diversity (many small/micro) and sector spread
REPLACEMENT_CHARITIES = [
    # MICRO (<£100k) — village halls, small groups, befriending
    305350,   # Stocksfield Village Hall — community space, £30k, Northumberland
    259560,   # St Mary's Befriending Service — elderly care, ~£50k, local
    270209,   # Toynbee Hall — community/settlements, East London
    
    # SMALL (£100k-£500k) — local services
    207544,   # Broadlands Group of Riding for the Disabled — disability sport, £80k
    301011,   # Haslemere Educational Museum — education/culture, Surrey
    268369,   # Disability Rights UK — disability advocacy, national
    
    # MEDIUM (£500k-£5m) — regional services
    265103,   # Womens Aid Federation of England — DV services, national
    212613,   # FareShare — food redistribution, national
    274194,   # Addaction (now We Are With You) — substance misuse, national
    
    # Additional small/local
    247934,   # Coventry Citizens Advice — advice, West Midlands
]


def infer_cpv_codes(client: openai.Client, activities_text: str) -> List[str]:
    prompt = f"""Given the following charity activities description, suggest the 3-5 most relevant 
CPV (Common Procurement Vocabulary) codes that this charity could realistically bid for.
Return ONLY a JSON object with key "codes" containing an array of CPV code strings.

Activities: {activities_text}"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        if isinstance(data, list):
            return data
        return data.get("codes", data.get("cpv_codes", []))
    except Exception as e:
        logger.error(f"CPV inference failed: {e}")
        return []


def generate_embedding(client: openai.Client, text: str) -> list:
    response = client.embeddings.create(input=text, model="text-embedding-3-small")
    return response.data[0].embedding


def map_where_to_regions(where_list: List[str]) -> List[str]:
    regions = []
    region_map = {
        "throughout england and wales": ["England", "Wales"],
        "throughout england": ["England"],
        "throughout london": ["London"],
        "london": ["London"],
        "south east": ["South East"],
        "south west": ["South West"],
        "east midlands": ["East Midlands"],
        "west midlands": ["West Midlands"],
        "north east": ["North East"],
        "north west": ["North West"],
        "yorkshire and the humber": ["Yorkshire and the Humber"],
        "east of england": ["East of England"],
        "scotland": ["Scotland"],
        "northern ireland": ["Northern Ireland"],
    }
    for w in where_list:
        key = w.lower().strip()
        if key in region_map:
            regions.extend(region_map[key])
    return list(dict.fromkeys(regions))


def fix_profiles():
    db = SessionLocal()
    cc = CharityCommissionClient()
    oai = openai.Client(api_key=settings.OPENAI_API_KEY)
    
    from app.models import NoticeMatch
    
    # Collect all org_ids to delete
    ids_to_delete = []
    
    # 1. Find broken profiles (name = "Search The Register Of Charities")
    broken = db.query(ServiceProfile).filter(
        ServiceProfile.name == "Search The Register Of Charities"
    ).all()
    ids_to_delete.extend([p.org_id for p in broken])
    logger.info(f"Found {len(broken)} broken profiles to delete.")
    
    # 2. Find fake charities
    for fake_name in FAKE_NAMES:
        fake = db.query(ServiceProfile).filter(ServiceProfile.name == fake_name).first()
        if fake:
            ids_to_delete.append(fake.org_id)
            logger.info(f"Marked for deletion: {fake_name}")
    
    # Find "Birkdale School" misfit
    misfit = db.query(ServiceProfile).filter(ServiceProfile.name.like("%Birkdale%")).first()
    if misfit:
        ids_to_delete.append(misfit.org_id)
        logger.info("Marked for deletion: Birkdale School")
    
    # 3. Delete notice_match records first (FK constraint)
    if ids_to_delete:
        deleted_matches = db.query(NoticeMatch).filter(
            NoticeMatch.org_id.in_(ids_to_delete)
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {deleted_matches} notice_match records.")
        
        # Now delete the profiles
        deleted_profiles = db.query(ServiceProfile).filter(
            ServiceProfile.org_id.in_(ids_to_delete)
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {deleted_profiles} service profiles.")
    
    db.commit()
    logger.info("Cleanup complete.")

    
    # 3. Seed replacement charities
    seeded = 0
    for charity_number in REPLACEMENT_CHARITIES:
        existing = db.query(ServiceProfile).filter(
            ServiceProfile.charity_number == str(charity_number)
        ).first()
        if existing:
            logger.info(f"Skipping {charity_number} (already exists: {existing.name})")
            continue
        
        data = cc.fetch_charity(charity_number)
        if not data or not data.get("name") or "Search The Register" in data.get("name", ""):
            logger.error(f"Could not fetch data for {charity_number}, skipping.")
            continue
        
        activities = data.get("activities", "")
        objects_text = data.get("objects", "")
        who_list = data.get("who", [])
        where_list = data.get("where", [])
        
        embedding_text = f"{data['name']}. {objects_text} {activities} Beneficiaries: {', '.join(who_list)}"
        
        cpv_codes = []
        if activities:
            cpv_codes = infer_cpv_codes(oai, activities)
            logger.info(f"  Inferred CPV codes: {cpv_codes}")
        
        embedding = generate_embedding(oai, embedding_text)
        regions = map_where_to_regions(where_list)
        
        profile = ServiceProfile(
            org_id=uuid.uuid4(),
            charity_number=str(charity_number),
            name=data["name"],
            latest_income=data.get("income"),
            mission=objects_text or activities,
            programs_services=activities,
            target_population=", ".join(who_list) if who_list else None,
            ukcat_codes=data.get("what", []) or None,
            beneficiary_groups=who_list or None,
            inferred_cpv_codes=cpv_codes or None,
            service_regions=regions or None,
            profile_embedding=embedding,
        )
        
        db.add(profile)
        seeded += 1
        income_str = f"£{data['income']:,}" if data.get('income') else "N/A"
        logger.info(f"✓ {seeded}: {data['name']} ({income_str}) — {len(regions)} regions, {len(cpv_codes)} CPVs")
        
        time.sleep(1)
    
    db.commit()
    logger.info(f"\n=== Done: Seeded {seeded} replacement profiles ===")
    db.close()


if __name__ == "__main__":
    fix_profiles()
