"""
RenewalEnrichmentService
-------------------------
Given a *live* notice (a current open tender), look it up against our
historical records to provide competitive intelligence:

  - Who held this contract before? (Incumbent)
  - How long do cycles typically run? (Cycle length)
  - Is this buyer in our history? (Buyer familiarity)
  - How competitive is this market? (Competitor count)

This is the "Renewal Radar" — Design 1 from bid_readiness_designs.md.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text


class RenewalEnrichmentService:
    """Enriches live tender notices with historical procurement intelligence."""

    def __init__(self, db: Session):
        self.db = db

    def enrich(self, notice) -> dict:
        """
        Given a live Notice ORM object, return a dict of strategic intelligence.
        Never raises — always returns a dict (may have empty/None fields).
        """
        result = {
            "buyer_seen_before": False,
            "historical_contract_count": 0,
            "incumbent": None,
            "last_awarded_date": None,
            "estimated_cycle_years": None,
            "unique_suppliers": [],
            "radar_summary": None,
        }

        try:
            buyer_id = notice.buyer_id
            cpv_prefixes = [c[:4] for c in (notice.cpv_codes or [])]

            if not buyer_id:
                result["radar_summary"] = "No buyer ID — cannot perform historical lookup."
                return result

            # --- 1. Has this buyer appeared in history? ---
            buyer_history = self._get_buyer_history(buyer_id, cpv_prefixes)

            if not buyer_history:
                result["radar_summary"] = (
                    "⚪ New buyer — no prior history in this sector. "
                    "First-mover advantage possible."
                )
                return result

            result["buyer_seen_before"] = True
            result["historical_contract_count"] = len(buyer_history)

            # --- 2. Extract incumbents and suppliers ---
            suppliers = []
            dates = []
            for row in buyer_history:
                raw = row.raw_json or {}
                # OCDS awards path
                for award in raw.get("awards", []):
                    for supplier in award.get("suppliers", []):
                        name = supplier.get("name")
                        if name and name not in suppliers:
                            suppliers.append(name)
                if row.publication_date:
                    dates.append(row.publication_date)

            result["unique_suppliers"] = suppliers[:5]  # top 5
            result["incumbent"] = suppliers[0] if suppliers else None

            # --- 3. Estimate cycle from last award date ---
            if dates:
                last_date = max(dates)
                result["last_awarded_date"] = last_date.isoformat() if hasattr(last_date, "isoformat") else str(last_date)
                last_date_utc = last_date.replace(tzinfo=timezone.utc) if last_date.tzinfo is None else last_date
                days_since = (datetime.now(timezone.utc) - last_date_utc).days
                years_since = round(days_since / 365.25, 1)

                # Common cycles: 1, 2, 3, 5 years
                for cycle in [1, 2, 3, 5]:
                    if abs(years_since - cycle) < 0.75:
                        result["estimated_cycle_years"] = cycle
                        break
                if not result["estimated_cycle_years"]:
                    result["estimated_cycle_years"] = 3  # default

            # --- 4. Generate human-readable summary ---
            result["radar_summary"] = self._generate_summary(result, notice)

        except Exception as e:
            result["radar_summary"] = f"⚠️ Enrichment error: {e}"

        return result

    def _get_buyer_history(self, buyer_id, cpv_prefixes: list):
        """Fetch historical notices for this buyer, optionally filtered by CPV prefix."""
        if cpv_prefixes:
            # Match on buyer AND at least one CPV prefix
            query = text("""
                SELECT ocid, title, publication_date, raw_json, cpv_codes
                FROM notice
                WHERE buyer_id = :buyer_id
                  AND notice_type = 'historical'
                  AND (
                    cpv_codes IS NULL
                    OR EXISTS (
                        SELECT 1 FROM unnest(cpv_codes) AS c
                        WHERE LEFT(c, 4) = ANY(:prefixes)
                    )
                  )
                ORDER BY publication_date DESC
                LIMIT 10
            """)
            rows = self.db.execute(
                query, {"buyer_id": str(buyer_id), "prefixes": cpv_prefixes}
            ).fetchall()
        else:
            query = text("""
                SELECT ocid, title, publication_date, raw_json, cpv_codes
                FROM notice
                WHERE buyer_id = :buyer_id
                  AND notice_type = 'historical'
                ORDER BY publication_date DESC
                LIMIT 10
            """)
            rows = self.db.execute(query, {"buyer_id": str(buyer_id)}).fetchall()

        # Convert raw rows to simple objects
        class Row:
            def __init__(self, r):
                self.ocid = r[0]
                self.title = r[1]
                self.publication_date = r[2]
                self.raw_json = r[3] or {}
                self.cpv_codes = r[4] or []

        return [Row(r) for r in rows]

    def _generate_summary(self, result: dict, notice) -> str:
        count = result["historical_contract_count"]
        incumbent = result["incumbent"]
        cycle = result["estimated_cycle_years"]
        last_date = result["last_awarded_date"]
        suppliers = result["unique_suppliers"]

        lines = []

        if incumbent:
            lines.append(f"Incumbent: **{incumbent}**")
        else:
            lines.append("No clear incumbent identified in history.")

        if last_date:
            last_str = last_date.strftime("%b %Y") if hasattr(last_date, "strftime") else str(last_date)
            lines.append(f"Last awarded: {last_str} (est. {cycle}-year cycle)")

        if len(suppliers) > 1:
            competitors = ", ".join(suppliers[1:4])
            lines.append(f"Other competitors seen: {competitors}")

        lines.append(
            f"{count} historical contract(s) found for this buyer in this sector."
        )

        return "\n".join(lines)
