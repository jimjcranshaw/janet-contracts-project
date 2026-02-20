"""
Keyword-driven historical backfill for Contracts Finder.
Queries per sector keyword so filtering happens server-side - much faster
than page-by-page pagination and local filtering.

Targets contractAward notices from 2024 so we have real incumbents and
cycles for the Renewal Intelligence / Strategic Coach feature.
"""
import requests
import json
import time
import os
import logging
from datetime import datetime
from app.database import SessionLocal
from app.models import Notice, Buyer
from app.services.ingestion.normalizer import Normalizer
from sqlalchemy.dialects.postgresql import insert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("keyword_backfill")

BASE_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

# Sector keywords derived from our charity profiles
# Covers: Social Work, Health, Housing, Education, Employment, Advice, Community
SECTOR_KEYWORDS = [
    "social care",
    "mental health",
    "housing support",
    "employment support",
    "homelessness",
    "debt advice",
    "community services",
    "disability support",
    "rehabilitation",
    "substance misuse",
    "youth services",
    "older people",
    "domestic abuse",
    "refugee support",
    "advice services",
    "supported living",
    "learning disability",
    "wellbeing services",
    "counselling",
    "outreach services",
]

# Only pull contract awards (completed contracts give us incumbent + cycle data)
NOTICE_TYPES = ["awardedContract", "contractAward"]

MAX_PAGES_PER_QUERY = 10  # 200 records per keyword/quarter - enough for trend analysis

def fetch_keyword_period(keyword, start_date, end_date):
    """Fetch up to MAX_PAGES_PER_QUERY pages for a keyword in a date range."""
    page = 1
    all_releases = []

    while page <= MAX_PAGES_PER_QUERY:
        try:
            params = {
                "publishedFrom": f"{start_date}T00:00:00Z",
                "publishedTo": f"{end_date}T23:59:59Z",
                "keyword": keyword,
                "page": page,
            }
            r = requests.get(BASE_URL, params=params, timeout=20)
            if r.status_code == 429:
                logger.warning("Rate limited. Sleeping 10s...")
                time.sleep(10)
                continue
            r.raise_for_status()

            releases = r.json().get("releases", [])
            if not releases:
                break

            all_releases.extend(releases)
            logger.info(f"  {keyword} / {start_date} page {page}: got {len(releases)} records")

            if len(releases) < 20:
                break

            page += 1
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error fetching '{keyword}' page {page}: {e}")
            break

    return all_releases


def ingest_releases(releases, normalizer, db):
    """Ingest a list of releases into the DB."""
    count = 0
    for release in releases:
        try:
            buyer_data = normalizer.normalize_buyer(release.get("buyer", {}))
            buyer_stmt = insert(Buyer).values(**buyer_data).on_conflict_do_update(
                index_elements=["slug"],
                set_={"canonical_name": buyer_data["canonical_name"]},
            )
            db.execute(buyer_stmt)
            buyer = db.query(Buyer).filter(Buyer.slug == buyer_data["slug"]).first()

            notice = normalizer.map_release_to_notice(release, buyer.id)
            # Mark as historical for the Renewal Intelligence service
            notice.notice_type = "historical"

            notice_data = {c.name: getattr(notice, c.name) for c in notice.__table__.columns}
            stmt = insert(Notice).values(**notice_data).on_conflict_do_update(
                index_elements=["ocid"],
                set_={"notice_type": "historical", "updated_at": datetime.utcnow()},
            )
            db.execute(stmt)
            count += 1

        except Exception as e:
            logger.error(f"Failed to ingest release {release.get('ocid')}: {e}")
            db.rollback()
            continue

    try:
        db.commit()
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        db.rollback()

    return count


def run_keyword_backfill(year=2024):
    db = SessionLocal()
    normalizer = Normalizer()
    total_ingested = 0
    seen_ocids = set()

    # Process quarter by quarter to stay within page limits
    quarters = [
        (f"{year}-01-01", f"{year}-03-31"),
        (f"{year}-04-01", f"{year}-06-30"),
        (f"{year}-07-01", f"{year}-09-30"),
        (f"{year}-10-01", f"{year}-12-31"),
    ]

    try:
        for keyword in SECTOR_KEYWORDS:
            for start, end in quarters:
                logger.info(f"Fetching '{keyword}' from {start} to {end}...")
                releases = fetch_keyword_period(keyword, start, end)

                # De-duplicate by OCID
                new_releases = [r for r in releases if r.get("ocid") not in seen_ocids]
                seen_ocids.update(r.get("ocid") for r in new_releases)

                if new_releases:
                    count = ingest_releases(new_releases, normalizer, db)
                    total_ingested += count
                    logger.info(
                        f"  '{keyword}' {start}: {len(releases)} fetched, "
                        f"{len(new_releases)} new, {count} ingested. Total: {total_ingested}"
                    )
                else:
                    logger.info(f"  '{keyword}' {start}: No new records.")

        logger.info(f"\nKeyword backfill complete. Total ingested: {total_ingested}")

    finally:
        db.close()


if __name__ == "__main__":
    run_keyword_backfill(year=2024)
