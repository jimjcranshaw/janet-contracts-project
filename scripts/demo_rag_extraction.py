import sys
import os
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

# Setup sys.path for app imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock pgvector for SQLite
import sqlalchemy
import sqlalchemy.types as types
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.modules["pgvector"] = MagicMock()
sys.modules["pgvector.sqlalchemy"] = MagicMock()
sys.modules["pgvector.sqlalchemy"].Vector = lambda x: sqlalchemy.types.JSON()
sqlalchemy.ARRAY = lambda x: types.JSON()
import sqlalchemy.dialects.postgresql as pg
pg.JSONB = types.JSON
pg.UUID = types.UUID
pg.ARRAY = lambda x: types.JSON()

from app.models import Base, Notice, ExtractedRequirement
from app.services.documents.document_service import DocumentService
from app.services.matching.requirement_service import RequirementService

def run_rag_demo():
    # Setup DB
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("--- 1. Setup Mock Data ---")
    ocid = "rag-demo-1"
    notice = Notice(
        ocid=ocid,
        title="London Cleaning Service",
        description="Daily cleaning for council offices.",
        source_url="https://example.com/tender-docs.pdf",
        publication_date=datetime.now(),
        raw_json={"tender": {"title": "London Cleaning Service"}}
    )
    db.add(notice)
    db.commit()

    # Mock Text Content
    mock_text = """
    TENDER SPECIFICATION: LONDON CLEANING SERVICE
    
    1. ELIGIBILITY CRITERIA
    Bidders must be registered with the British Institute of Cleaning Science (BICSc).
    This contract is reserved for SMEs and VCSE organizations only.
    
    2. RISK & COMPLIANCE
    Bidders must hold Public Liability Insurance of at least £5,000,000.
    TUPE transfers are expected to apply to 15 existing staff members.
    
    3. SOCIAL VALUE
    The contractor must commit to hiring 2 local apprentices from the borough.
    All cleaning products must be 100% biodegradable.
    """

    print("--- 2. Mock LLM Extraction ---")
    import json
    mock_llm_response = {
        "requirements": [
            {
                "category": "ELIGIBILITY",
                "requirement_text": "Registered with BICSc",
                "is_mandatory": "Yes",
                "suitability_flags": ["CERTIFIED"],
                "risk_level": "low"
            },
            {
                "category": "ELIGIBILITY",
                "requirement_text": "Reserved for SMEs/VCSEs",
                "is_mandatory": "Yes",
                "suitability_flags": ["SME_FRIENDLY", "CHARITY_ONLY"],
                "risk_level": "low"
            },
            {
                "category": "RISK",
                "requirement_text": "£5m Public Liability Insurance",
                "is_mandatory": "Yes",
                "suitability_flags": [],
                "risk_level": "medium"
            },
            {
                "category": "RISK",
                "requirement_text": "TUPE applies to 15 staff",
                "is_mandatory": "Yes",
                "suitability_flags": [],
                "risk_level": "high"
            },
            {
                "category": "SOCIAL_VALUE",
                "requirement_text": "2 local apprentices",
                "is_mandatory": "No",
                "suitability_flags": ["LOCAL_EMPLOYMENT"],
                "risk_level": "low"
            }
        ]
    }

    # Patch OpenAI and Document fetching
    with patch('openai.resources.chat.completions.Completions.create') as mock_openai, \
         patch('app.services.documents.document_service.DocumentService.fetch_and_extract_text') as mock_fetch:
        
        mock_fetch.return_value = mock_text
        
        # Setup mock OpenAI response
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_llm_response)
        mock_openai.return_value.choices = [mock_choice]

        import json # Needed for mock_choice above

        # Execute
        doc_service = DocumentService()
        req_service = RequirementService(db, api_key="fake-key")
        
        print(f"Processing docs for {ocid}...")
        extracted_text = doc_service.fetch_and_extract_text(notice.source_url)
        requirements = req_service.extract_requirements(ocid, extracted_text)

        print(f"\nExtracted {len(requirements)} requirements:")
        for r in requirements:
            print(f"- [{r.category}] {r.requirement_text} (Mandatory: {r.is_mandatory}, Risk: {r.risk_level})")
            if r.suitability_flags:
                print(f"  Flags: {r.suitability_flags}")

    db.close()

if __name__ == "__main__":
    run_rag_demo()
