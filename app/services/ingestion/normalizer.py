from datetime import datetime
from typing import Dict, Optional, Tuple
from app.models import Notice, Buyer
from sqlalchemy.orm import Session

class Normalizer:
    
    def normalize_buyer(self, buyer_data: Dict) -> Dict:
        """
        Normalizes buyer data. Returns a dictionary suitable for Buyer model creation/update.
        """
        raw_name = buyer_data.get('name', 'Unknown Buyer')
        # Basic canonicalization (lowercase, strip)
        canonical_name = raw_name.strip()
        slug = canonical_name.lower().replace(" ", "-")
        
        return {
            "canonical_name": canonical_name,
            "slug": slug,
            "identifiers": buyer_data.get('identifier', {})
        }

    def map_release_to_notice(self, release: Dict, buyer_id: str) -> Notice:
        """
        Maps a raw OCDS release to a Notice model instance.
        """
        tender = release.get('tender', {})
        
        # Parse Dates
        pub_date_str = release.get('date')
        pub_date = datetime.fromisoformat(pub_date_str.replace('Z', '+00:00')) if pub_date_str else datetime.utcnow()
        
        period = tender.get('tenderPeriod', {})
        end_date_str = period.get('endDate')
        deadline_date = None
        if end_date_str:
            try:
                deadline_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except ValueError:
                pass

        # Extract Value
        value_data = tender.get('value', {})
        amount = value_data.get('amount')
        currency = value_data.get('currency', 'GBP')

        # Extract Contract Period (PRD 05)
        contract_start = None
        contract_end = None
        
        # Check tenderPeriod or contractPeriod in tender
        cp = tender.get('contractPeriod', {})
        if not cp: # fallback to awards
            awards = release.get('awards', [])
            if awards: cp = awards[0].get('contractPeriod', {})
            
        if cp.get('startDate'):
            try: contract_start = datetime.fromisoformat(cp.get('startDate').replace('Z', '+00:00'))
            except: pass
        if cp.get('endDate'):
            try: contract_end = datetime.fromisoformat(cp.get('endDate').replace('Z', '+00:00'))
            except: pass

        # Extract CPVs (Enhanced for Contracts Finder + FTS)
        cpv_codes = []
        
        # 1. Standard OCDS / FTS Path (Items)
        items = tender.get('items', [])
        for item in items:
            cid = item.get('classification', {}).get('id')
            if cid and cid not in cpv_codes:
                cpv_codes.append(cid)
                
        # 2. Contracts Finder Path (Top-level Classification)
        main_class = tender.get('classification', {}).get('id')
        if main_class and main_class not in cpv_codes:
            cpv_codes.append(main_class)
            
        additional = tender.get('additionalClassifications', [])
        for ac in additional:
            aid = ac.get('id')
            if aid and aid not in cpv_codes:
                cpv_codes.append(aid)

        # Create Notice
        return Notice(
            ocid=release.get('ocid'),
            release_id=release.get('id'),
            title=tender.get('title', 'Untitled Notice'),
            description=tender.get('description', ''),
            buyer_id=buyer_id,
            publication_date=pub_date,
            deadline_date=deadline_date,
            value_amount=amount,
            value_currency=currency,
            procurement_method=tender.get('procurementMethod'),
            notice_type=release.get('tag', ['contractNotice'])[0], # Default to first tag
            raw_json=release,
            source_url=tender.get('documents', [{}])[0].get('url'), # Approximate
            cpv_codes=cpv_codes,
            contract_period_start=contract_start,
            contract_period_end=contract_end,
            updated_at=datetime.utcnow()
        )
