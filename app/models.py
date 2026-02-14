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
    
    # Vector embedding for description (1536 dims for text-embedding-3-small)
    embedding = Column(Vector(1536))
    
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
    
    feedback_status = Column(String(20)) # 'GO', 'NO_GO', 'REVIEW'
    viability_warning = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
