from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin, JSONField


class Repository(Base, TimestampMixin):
    """
    Tracks registered GitHub repositories monitored by GitPulse.
    """
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(Integer, unique=True, index=True, nullable=True)
    owner = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    full_name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    html_url = Column(String(255), nullable=True)
    default_branch = Column(String(50), default="main", nullable=False)
    visibility = Column(String(20), default="public", nullable=False)
    
    # Metadata metrics
    stargazers_count = Column(Integer, default=0, nullable=False)
    forks_count = Column(Integer, default=0, nullable=False)
    open_issues_count = Column(Integer, default=0, nullable=False)
    watchers_count = Column(Integer, default=0, nullable=False)
    language = Column(String(50), nullable=True, index=True)
    
    # Timestamps from GitHub
    created_at_gh = Column(DateTime, nullable=True)
    updated_at_gh = Column(DateTime, nullable=True)
    
    # State flags
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_synced_at = Column(DateTime, nullable=True)
    
    # Flexible raw metadata
    repo_metadata = Column(JSONField, default=dict, nullable=True)

    # Relationships
    raw_events = relationship("RawEvent", back_populates="repository", cascade="all, delete-orphan")
    pipeline_runs = relationship("PipelineRun", back_populates="repository", cascade="all, delete-orphan")
    extraction_jobs = relationship("ExtractionJob", back_populates="repository", cascade="all, delete-orphan")
    checkpoints = relationship("ExtractionCheckpoint", back_populates="repository", cascade="all, delete-orphan")
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, full_name='{self.full_name}', active={self.is_active})>"
