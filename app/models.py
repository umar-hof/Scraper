from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.config import Settings

class Base(DeclarativeBase): pass

class QualifiedLead(Base):
    __tablename__ = "qualified_leads"
    __table_args__ = (UniqueConstraint("company_key", "poc_key", name="uq_company_poc"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_key: Mapped[str] = mapped_column(String(128), index=True)
    poc_key: Mapped[str] = mapped_column(String(128), default="unknown")
    poc_name: Mapped[str] = mapped_column(String(255), default="Not Found")
    company_name: Mapped[str] = mapped_column(String(255))
    designation: Mapped[str] = mapped_column(String(255), default="Not Found")
    poc_contact_number: Mapped[str] = mapped_column(String(100), default="Not Found")
    company_contact_number: Mapped[str] = mapped_column(String(100), default="Not Found")
    poc_email_id: Mapped[str] = mapped_column(String(320), default="Not Found")
    department: Mapped[str] = mapped_column(String(100), default="Not Found")
    employee_size: Mapped[str] = mapped_column(String(50), default="Not Found")
    li_poc_profile: Mapped[str] = mapped_column(String(500), default="Not Found")
    icp_score: Mapped[float] = mapped_column(Float, default=0)
    qualification_status: Mapped[str] = mapped_column(String(30), index=True)
    source_url: Mapped[str] = mapped_column(String(500), default="Not Found")
    poc_source_url: Mapped[str] = mapped_column(String(500), default="Not Found")
    business_type: Mapped[str] = mapped_column(String(100), default="Not Found")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DiscoveryJob(Base):
    __tablename__ = "scraping_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    geographic_partition: Mapped[str] = mapped_column(String(100), index=True)
    industry: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(100))
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    last_checkpoint: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class DiscoveryTracking(Base):
    __tablename__ = "discovery_tracking"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    discovery_status: Mapped[str] = mapped_column(String(30), default="discovered")
    source_url: Mapped[str] = mapped_column(String(500), default="Not Found")

class SyncStatus(Base):
    __tablename__ = "sync_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    state: Mapped[str] = mapped_column(String(30), default="pending")
    last_synchronized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

class POCEvidence(Base):
    __tablename__ = "poc_evidence"
    __table_args__ = (UniqueConstraint("company_key", "poc_key", "source_url", name="uq_poc_source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_key: Mapped[str] = mapped_column(String(128), index=True)
    poc_key: Mapped[str] = mapped_column(String(128), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    poc_name: Mapped[str] = mapped_column(String(255))
    designation: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320), default="Not Found")
    phone: Mapped[str] = mapped_column(String(100), default="Not Found")
    source_url: Mapped[str] = mapped_column(String(500))
    extraction_method: Mapped[str] = mapped_column(String(100))
    verification_status: Mapped[str] = mapped_column(String(50), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ResearchQueue(Base):
    __tablename__ = "research_queue"
    company_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(String(500))
    suggested_queries: Mapped[str] = mapped_column(Text)
    official_source_urls: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SourceFailure(Base):
    """Small operational record; raw HTML/query payloads are intentionally not stored."""
    __tablename__ = "source_failures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    scope: Mapped[str] = mapped_column(String(255), default="Not Found")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str] = mapped_column(String(1000))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

def make_session_factory(settings: Settings):
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)

