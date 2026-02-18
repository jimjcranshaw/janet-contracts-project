from sqlalchemy import Column, String, Integer, DateTime, Boolean, Numeric, ForeignKey, ARRAY, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
from .database import Base

class IngestionLog(Base):
    __tablename__ = "ingestion_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)  # 'FTS', 'CF'
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20))  # 'RUNNING', 'SUCCESS', 'FAILED'
    items_processed = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)

class Buyer(Base):
    __tablename__ = "buyer"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name = Column(Text, nullable=False)
    slug = Column(Text, unique=True)
    identifiers = Column(JSONB)  # { "scheme": "GB-COH", "id": "..." }
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    notices = relationship("Notice", back_populates="buyer")

class Notice(Base):
    __tablename__ = "notice"

    ocid = Column(Text, primary_key=True)  # Open Contracting ID
    release_id = Column(Text)
    title = Column(Text, nullable=False)
    description = Column(Text)
    
    # New: Translated Summary for better matching
    provider_summary = Column(Text) 
    provider_summary_embedding = Column(Vector(1536))

    buyer_id = Column(UUID(as_uuid=True), ForeignKey("buyer.id"))
    
    publication_date = Column(DateTime(timezone=True), nullable=False)
    deadline_date = Column(DateTime(timezone=True))
    
    value_amount = Column(Numeric(18, 2))
    value_currency = Column(String(3), default='GBP')
    
    procurement_method = Column(String(50))  # 'open', 'selective', 'limited'
    notice_type = Column(String(50))  # 'contractNotice', 'contractAward'
    
    raw_json = Column(JSONB, nullable=False)
    source_url = Column(Text)
    cpv_codes = Column(ARRAY(Text)) # Specific Procurement Codes
    inferred_ukcat_codes = Column(ARRAY(Text)) # Auto-tagged via UKCAT regex
    
    # Vector embedding for description (1536 dims for text-embedding-3-small)
    embedding = Column(Vector(1536))
    
    # Contract Period (for Renewal Intelligence PRD 05)
    contract_period_start = Column(DateTime(timezone=True))
    contract_period_end = Column(DateTime(timezone=True))
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)

    buyer = relationship("Buyer", back_populates="notices")

class ServiceProfile(Base):
    __tablename__ = "service_profile"

    org_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identity
    charity_number = Column(String(20), unique=True)
    name = Column(Text, nullable=False)
    website = Column(String(255))
    
    # Financials (for Viability Check)
    latest_income = Column(BigInteger)
    
    # Semantic Variables (from Grants App)
    mission = Column(Text)
    vision = Column(Text)
    programs_services = Column(Text)
    target_population = Column(Text)
    
    # Structured Classification
    ukcat_codes = Column(ARRAY(Text)) # from Grant Seeker logic
    beneficiary_groups = Column(ARRAY(Text))
    
    # Inferred Procurement Data (Auto-Tagging)
    inferred_cpv_codes = Column(ARRAY(Text)) 

    # Contract Gates
    service_regions = Column(JSONB)
    min_contract_value = Column(Integer)
    max_contract_value = Column(Integer)
    
    # Social Value & Outcomes (PRD 08)
    outcomes_evidence = Column(JSONB) # [ {"outcome": "...", "evidence": "...", "verified": bool} ]

    # Embedding (Concat of Mission/Vision/Services/Population)
    profile_embedding = Column(Vector(1536))
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class NoticeMatch(Base):
    __tablename__ = "notice_match"

    org_id = Column(UUID(as_uuid=True), ForeignKey("service_profile.org_id"), primary_key=True)
    notice_id = Column(Text, ForeignKey("notice.ocid"), primary_key=True)
    score = Column(Numeric(5, 4)) # 0.0000 to 1.0000
    
    # Breakdown
    score_semantic = Column(Numeric(5, 4))
    score_domain = Column(Numeric(5, 4))
    score_geo = Column(Numeric(5, 4))
    score_theme = Column(Numeric(5, 4))
    
    feedback_status = Column(String(20)) # 'GO', 'NO_GO', 'REVIEW'
    viability_warning = Column(Text)
    
    # Bid/No-Bid Enhancements (PRD 03)
    risk_flags = Column(JSONB) # { "TUPE": true, "Safeguarding": "High", ... }
    checklist = Column(JSONB) # [ { "item": "Cyber Essentials", "status": "missing" }, ... ]
    recommendation_reasons = Column(ARRAY(Text)) # Reasons for GO/NO_GO
    
    # Deep Review (Tier 2 - PRD 03 Enhancements)
    deep_verdict = Column(String(20)) # 'PASS', 'FAIL'
    deep_rationale = Column(Text)
    
    is_tracked = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Alert(Base):
    """
    Structured alerts for the Opportunity Feed (PRD 04/05).
    """
    __tablename__ = "alert"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("service_profile.org_id"))
    notice_id = Column(Text, ForeignKey("notice.ocid"))
    
    alert_type = Column(String(50))  # 'NEW_MATCH', 'MATERIAL_CHANGE', 'RENEWAL'
    severity = Column(String(20))    # 'info', 'warning', 'critical'
    message = Column(Text)
    details = Column(JSONB)         # { "diff": {...} }
    
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExtractedRequirement(Base):
    """
    Requirements extracted from tender documents via LLM (PRD 07).
    """
    __tablename__ = "extracted_requirement"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notice_id = Column(Text, ForeignKey("notice.ocid"), index=True)
    
    category = Column(String(50)) # 'ELIGIBILITY', 'RISK', 'SOCIAL_VALUE', 'TECHNICAL'
    requirement_text = Column(Text)
    is_mandatory = Column(Boolean, default=False)
    
    # Matching logic metadata
    suitability_flags = Column(ARRAY(Text)) # e.g. ["SME_FRIENDLY", "CHARITY_ONLY"]
    risk_level = Column(String(20)) # 'low', 'medium', 'high'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
