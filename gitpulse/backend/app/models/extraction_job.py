from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin, JSONField


class ExtractionJob(Base, TimestampMixin):
    """
    Tracks lifecycle, progress, record counts, and errors for GitHub extraction jobs.
    """
    __tablename__ = "extraction_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True, index=True)
    repository_full_name = Column(String(200), nullable=False, index=True)
    
    # State: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, PARTIAL_SUCCESS
    status = Column(String(30), default="PENDING", nullable=False, index=True)
    resources = Column(JSONField, default=list, nullable=False)
    incremental = Column(Boolean, default=True, nullable=False)
    
    # Window constraints
    since = Column(DateTime, nullable=True)
    until = Column(DateTime, nullable=True)
    
    # Timestamps & Execution Duration
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Granular record metrics per resource type
    records_extracted = Column(JSONField, default=dict, nullable=False)
    records_loaded = Column(JSONField, default=dict, nullable=False)
    
    # Errors & partial failure tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSONField, default=dict, nullable=True)
    
    # Incremental state checkpointing
    checkpoint = Column(JSONField, default=dict, nullable=True)
    
    # Cancellation flag
    cancel_requested = Column(Boolean, default=False, nullable=False)

    repository = relationship("Repository", back_populates="extraction_jobs")

    def __repr__(self) -> str:
        return f"<ExtractionJob(id={self.job_id}, repo='{self.repository_full_name}', status='{self.status}')>"

