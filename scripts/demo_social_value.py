import sys
import os
import uuid
import json
from unittest.mock import MagicMock, patch

# Setup sys.path for app imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mocking for SQLite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sqlalchemy
import sqlalchemy.types as types

sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()
sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()
sqlalchemy.ARRAY = lambda x: types.JSON()
import sqlalchemy.dialects.postgresql as pg
pg.JSONB = types.JSON
pg.UUID = types.UUID
pg.ARRAY = lambda x: types.JSON()

from app.models import Base, ServiceProfile, ExtractedRequirement
from app.services.matching.social_value_service import SocialValueService

def run_social_value_demo():
    # Setup DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("--- 1. Seed Charity Profile & Evidence ---")
    org_id = uuid.uuid4()
    profile = ServiceProfile(
        org_id=org_id,
        name="Green Care Charity",
        outcomes_evidence=[
            {"outcome": "Local Employment", "evidence": "10 local staff hired in 2024.", "verified": True},
            {"outcome": "Waste Reduction", "evidence": "Reduced office waste by 40% using circular economy practices.", "verified": True}
        ]
    )
    db.add(profile)

    print("--- 2. Seed Extracted SV Requirements ---")
    ocid = "sv-demo-1"
    r1 = ExtractedRequirement(
        notice_id=ocid,
        category="SOCIAL_VALUE",
        requirement_text="10% reduction in carbon footprint across supply chain.",
        is_mandatory=True
    )
    r2 = ExtractedRequirement(
        notice_id=ocid,
        category="SOCIAL_VALUE",
        requirement_text="Local labor usage above 50%.",
        is_mandatory=True
    )
    db.add_all([r1, r2])
    db.commit()

    print("--- 3. Mock LLM Mapping ---")
    mock_llm_response = {
        "matches": [
            {
                "requirement": "Local labor usage above 50%.",
                "matching_evidence": "10 local staff hired in 2024.",
                "confidence": 0.8
            }
        ],
        "gaps": [
            {
                "requirement": "10% reduction in carbon footprint across supply chain.",
                "reason": "Charity evidence focuses on office waste, but lacks supply chain carbon data.",
                "severity": "high"
            }
        ],
        "fit_score": 0.5
    }

    with patch('openai.resources.chat.completions.Completions.create') as mock_openai:
        # Setup mock OpenAI response
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_llm_response)
        mock_openai.return_value.choices = [mock_choice]

        # Execute
        sv_service = SocialValueService(db, api_key="fake-key")
        analysis = sv_service.analyze_social_value_fit(org_id, ocid)

        print(f"\nSocial Value Fit Score: {analysis.get('fit_score')}")
        
        print("\nMatches Found:")
        for m in analysis.get('matches', []):
            print(f"✓ {m['requirement']} matched with: {m['matching_evidence']}")

        print("\nEvidence Gaps (WARNING):")
        for g in analysis.get('gaps', []):
            print(f"⚠ {g['requirement']} - Reason: {g['reason']} (Severity: {g['severity']})")

    db.close()

if __name__ == "__main__":
    run_social_value_demo()
