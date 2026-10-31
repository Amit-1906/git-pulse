from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin, JSONField


class ExtractionCheckpoint(Base, TimestampMixin):
    """
    Stores incremental checkpoints (high-water marks) per repository and resource type.
    """
    __tablename__ = "extraction_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)  # 'commits', 'issues', 'pull_requests'
    
    last_checkpoint_timestamp = Column(DateTime, nullable=True)
    last_record_id = Column(String(100), nullable=True)
    checkpoint_metadata = Column(JSONField, default=dict, nullable=True)

    __table_args__ = (
        UniqueConstraint("repository_id", "resource_type", name="uq_repo_resource_checkpoint"),
    )

    repository = relationship("Repository", back_populates="checkpoints")

    def __repr__(self) -> str:
        return f"<ExtractionCheckpoint(repo_id={self.repository_id}, resource='{self.resource_type}', timestamp={self.last_checkpoint_timestamp})>"

