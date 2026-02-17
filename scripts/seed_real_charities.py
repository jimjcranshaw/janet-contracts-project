"""
Seed 20 real charities from the Charity Commission register into ServiceProfile.
Fetches structured data (activities, income, classifications, regions),
generates semantic embeddings, and optionally infers CPV codes.
"""
import sys
import os
import uuid
import json
import time
import logging
import openai
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal, settings
from app.models import ServiceProfile
from app.services.ingestion.clients.cc_client import CharityCommissionClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 20 real charities — representative of sector diversity
# Distribution: 3 large (£10m+), 4 medium (£1m-£10m), 6 small (£100k-£1m), 7 micro (<£100k)
CHARITIES = [
    # --- LARGE (£10m+) — ~15% of sector ---
    263710,   # Shelter — Housing/Homelessness, £77m, National
    219830,   # Mind — Mental Health, £64m, National
    226171,   # Nacro — Criminal Justice / Rehab, £40m, National
    
    # --- MEDIUM (£1m-£10m) — ~15% of sector ---
    1082947,  # Crisis — Homelessness services, £60m (but regional focus)
    1121105,  # Groundwork London — Environment/Regen, ~£3m, London
    1075040,  # Citizens Advice Lewisham — Advice services, ~£2m, SE London
    1112930,  # Sherwood & Newark Citizens Advice — Advice, ~£1m, East Midlands
    
    # --- SMALL (£100k-£1m) — ~20% of sector ---
    1194314,  # Food Bank Aid — Food poverty/distribution, ~£200k, National
    1018973,  # Community Links — Community Dev, ~£5m, East London
    211234,   # Papworth Trust — Disability/Housing, ~£15m, East England
    291558,   # Groundwork UK — Environment/Regen, ~£5m, National
    1149085,  # St Mungo's — Homelessness, London/SE
    1044489,  # Crockham Hill Village Hall Trust — Community space, ~£48k, Kent
    
    # --- MICRO (<£100k) — ~70% of sector ---
    1070861,  # Redford Village Hall — Community space, <£5k, Rural
    519639,   # Citizens Advice Birmingham — Advice, regional
    1124127,  # Catch22 — Social Enterprise, Multi-region
    234887,   # Turning Point — Substance Abuse/MH, National
    1097940,  # Action for Children — Children/Families, National
    1128267,  # Age UK — Elderly Care, National
    208231,   # Scope — Disability, National
]


def map_where_to_regions(where_list: List[str]) -> List[str]:
    """
    Map CC 'where' classifications to our service_regions format.
    """
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
    
    # Deduplicate
    return list(dict.fromkeys(regions))


def infer_cpv_codes(client: openai.Client, activities_text: str) -> List[str]:
    """
    Use LLM to infer relevant CPV codes from a charity's activities description.
    """
    prompt = f"""Given the following charity activities description, suggest the 3-5 most relevant 
CPV (Common Procurement Vocabulary) codes that this charity could realistically bid for.
Return ONLY a JSON array of CPV code strings (e.g. ["85000000", "85300000"]).

Activities: {activities_text}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        # Handle both {"codes": [...]} and direct [...]
        if isinstance(data, list):
            return data
        return data.get("codes", data.get("cpv_codes", []))
    except Exception as e:
        logger.error(f"CPV inference failed: {e}")
        return []


def generate_embedding(client: openai.Client, text: str) -> list:
    """Generate embedding for a text string."""
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def seed_real_charities():
    db = SessionLocal()
    cc = CharityCommissionClient()
    oai = openai.Client(api_key=settings.OPENAI_API_KEY)
    
    logger.info(f"=== Seeding {len(CHARITIES)} Real Charities ===")
    
    seeded = 0
    for charity_number in CHARITIES:
        # Check if already exists
        existing = db.query(ServiceProfile).filter(
            ServiceProfile.charity_number == str(charity_number)
        ).first()
        if existing:
            logger.info(f"Skipping {charity_number} (already exists: {existing.name})")
            continue
        
        # Fetch from CC register
        data = cc.fetch_charity(charity_number)
        if not data or not data.get("name"):
            logger.error(f"Could not fetch data for {charity_number}, skipping.")
            continue
        
        # Map to ServiceProfile
        activities = data.get("activities", "")
        objects_text = data.get("objects", "")
        who_list = data.get("who", [])
        where_list = data.get("where", [])
        
        # Build embedding text from all available semantic content
        embedding_text = f"{data['name']}. {objects_text} {activities} Beneficiaries: {', '.join(who_list)}"
        
        # Infer CPV codes from activities
        cpv_codes = []
        if activities:
            cpv_codes = infer_cpv_codes(oai, activities)
            logger.info(f"  Inferred CPV codes: {cpv_codes}")
        
        # Generate embedding
        embedding = generate_embedding(oai, embedding_text)
        
        # Map regions
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
        logger.info(f"✓ {seeded}/{len(CHARITIES)}: {data['name']} ({income_str}) — {len(regions)} regions, {len(cpv_codes)} CPVs")
        
        # Be polite to the CC website
        time.sleep(1)
    
    db.commit()
    logger.info(f"\n=== Done: Seeded {seeded} new charity profiles ===")
    db.close()


if __name__ == "__main__":
    seed_real_charities()
