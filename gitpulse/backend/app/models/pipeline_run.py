from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin, JSONField


class PipelineRun(Base, TimestampMixin):
    """
    Tracks state and telemetry of ELT pipeline executions (Extract, Load, Transform, Test).
    """
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_name = Column(String(100), default="github_elt_pipeline", nullable=False)
    stage = Column(String(50), default="extract", nullable=False)  # 'extract', 'load', 'transform', 'test'
    status = Column(String(20), default="pending", nullable=False, index=True)  # 'pending', 'running', 'completed', 'failed'
    
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Telemetry metrics
    records_extracted = Column(Integer, default=0, nullable=False)
    records_loaded = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    run_metadata = Column(JSONField, default=dict, nullable=True)

    repository = relationship("Repository", back_populates="pipeline_runs")

    def __repr__(self) -> str:
        return f"<PipelineRun(id={self.id}, repo_id={self.repository_id}, status='{self.status}', stage='{self.stage}')>"

