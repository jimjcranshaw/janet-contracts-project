"""
Renewal Radar Demo v2
----------------------
The Renewal Radar works in two directions:

Direction A) Given a BUYER we've seen before in historical data,
            what live notices are they posting NOW?
            => This catches the NEXT cycle of a previously-awarded contract.

Direction B) Given a historical notice we know about,
            which of our charities should be building their bid NOW?
            => This is the proactive PLAN alert (T-12 months).

This demo runs Direction B first (most actionable), then Direction A.

Run: python scripts/demo_renewal_radar.py
"""
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models import Notice, Buyer, ServiceProfile
from sqlalchemy import text


MESH_KEYWORDS = [
    "social care", "mental health", "housing", "employment support",
    "homelessness", "community", "disability", "rehabilitation",
    "substance", "youth", "counselling", "outreach", "advice",
    "wellbeing", "safeguarding", "support services"
]


def get_sector_history(db, limit=50):
    """
    Get historical notices that have CPV codes (from our keyword backfill)
    and are related to social care sector.
    """
    rows = db.execute(text("""
        SELECT n.ocid, n.title, n.publication_date, n.cpv_codes,
               n.raw_json, n.value_amount, n.contract_period_end,
               b.canonical_name as buyer_name, b.id as buyer_id
        FROM notice n
        LEFT JOIN buyer b ON n.buyer_id = b.id
        WHERE n.notice_type = 'historical'
          AND n.cpv_codes IS NOT NULL
          AND array_length(n.cpv_codes, 1) > 0
        ORDER BY n.publication_date DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    return rows


def extract_supplier(raw_json: dict) -> str:
    """Extract primary supplier/winner from OCDS raw JSON."""
    if not raw_json:
        return None
    for award in raw_json.get("awards", []):
        suppliers = award.get("suppliers", [])
        if suppliers:
            return suppliers[0].get("name")
    return None


def predict_next_tender(pub_date, cycle_years=3):
    """Estimate when this contract will come up for re-tender."""
    if not pub_date:
        return None
    if hasattr(pub_date, 'replace') and pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    return pub_date + timedelta(days=cycle_years * 365.25)


def find_live_notices_for_buyer(db, buyer_name: str):
    """Check if this buyer has any live (non-historical) current notices."""
    # Fuzzy match on buyer canonical_name
    result = db.execute(text("""
        SELECT n.title, n.publication_date, n.value_amount
        FROM notice n
        JOIN buyer b ON n.buyer_id = b.id
        WHERE n.notice_type != 'historical'
          AND LOWER(b.canonical_name) LIKE :pattern
        ORDER BY n.publication_date DESC
        LIMIT 3
    """), {"pattern": f"%{buyer_name.split()[0].lower()}%"}).fetchall()
    return result


def match_charities(db, cpv_codes: list) -> list:
    """Find charities whose interest mesh overlaps with these CPVs."""
    if not cpv_codes:
        return []
    prefixes = list({c[:4] for c in cpv_codes})
    profiles = db.query(ServiceProfile).all()
    matches = []
    for p in profiles:
        if p.inferred_cpv_codes:
            charity_prefixes = {c[:4] for c in p.inferred_cpv_codes}
            overlap = set(prefixes) & charity_prefixes
            if overlap:
                matches.append(p.name)
    return matches[:4]


def run_radar_demo():
    db = SessionLocal()

    historical = get_sector_history(db, limit=500)

    if not historical:
        print("❌ No historical sector notices found. Run api_backfill_keyword.py first.")
        db.close()
        return

    now = datetime.now(timezone.utc)
    print("\n" + "=" * 72)
    print("  RENEWAL RADAR  -  Strategic Re-Tender Intelligence")
    print("=" * 72)
    print(f"  Scanning {len(historical)} awarded contracts for upcoming re-tenders...\n")

    shown = 0
    seen_titles = set()
    for row in historical:
        title, pub_date, cpv_codes = row[1], row[2], row[3]
        raw_json, value, contract_end = row[4], row[5], row[6]
        buyer_name, buyer_id = row[7], row[8]

        # De-duplicate by title (first 40 chars) and buyer
        title_key = (title[:40] if title else "") + (buyer_name if buyer_name else "")
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        supplier = extract_supplier(raw_json)

        # Use contract_end if available, otherwise estimate from pub_date
        if contract_end:
            retender_date = contract_end
            if retender_date.tzinfo is None:
                retender_date = retender_date.replace(tzinfo=timezone.utc)
        else:
            retender_date = predict_next_tender(pub_date, cycle_years=3)

        if not retender_date:
            continue

        days_to_retender = (retender_date - now).days
        
        # Categorise urgency
        if days_to_retender < 0:
            urgency = "[OVERDUE]"
            action_phase = "PROCURE NOW"
        elif days_to_retender < 180:
            urgency = "[PROCURE]"
            action_phase = "TENDER IMMINENT"
        elif days_to_retender < 365:
            urgency = "[DEFINE]"
            action_phase = "ENGAGE MARKET NOW"
        else:
            urgency = "[PLAN]"
            action_phase = "START CONSORTIUM BUILDING"

        # Find matching charities
        matching_charities = match_charities(db, cpv_codes)

        if not matching_charities:
            continue

        # Check if buyer has live notices
        live = find_live_notices_for_buyer(db, buyer_name or "")

        print("-" * 72)
        title_short = (title[:67] + "...") if title and len(title) > 67 else title
        print(f"{urgency}  {title_short}")
        print(f"   Buyer:        {buyer_name or 'Unknown'}")
        value_str = f"£{float(value):,.0f}" if value else "Not disclosed"
        print(f"   Awarded:      {pub_date.strftime('%b %Y') if pub_date else '—'}   |   Value: {value_str}")
        print(f"   Incumbent:    {supplier or '(not identified)'}")
        print(f"   Re-tender:    {retender_date.strftime('%b %Y')}  [{action_phase}]")

        print(f"   Your charities: {', '.join(matching_charities)}")

        if live:
            print(f"   LIVE NOW: {live[0][0][:60]} ({live[0][1].strftime('%d %b %Y') if live[0][1] else '—'})")

        # Strategic guidance
        plan_date = retender_date - timedelta(days=365)
        define_date = retender_date - timedelta(days=180)
        print(f"\n   Action Plan:")
        print(f"      [{plan_date.strftime('%b %Y')}]  PLAN   — Build consortium, gather evidence")
        print(f"      [{define_date.strftime('%b %Y')}]  DEFINE — Attend market engagement, shape spec")
        print(f"      [{retender_date.strftime('%b %Y')}]  PROCURE — Submit bid (with pre-built Social Value annex)")
        print()

        shown += 1
        if shown >= 12:
            break

    print("=" * 72)
    print(f"  Final: Showing {shown} actionable re-tender opportunities")
    print(f"  Source: 405 historical contracts from 2024 Contracts Finder backfill")
    print("=" * 72 + "\n")

    db.close()


if __name__ == "__main__":
    run_radar_demo()
