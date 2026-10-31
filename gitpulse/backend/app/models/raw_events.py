from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin, JSONField


class RawEvent(Base, TimestampMixin):
    """
    ELT Bronze/Raw layer: Stores immutable raw JSON payloads received directly from the GitHub API.
    Enables zero-data-loss replayability and downstream dbt modeling.
    """
    __tablename__ = "raw_events"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # 'commit', 'pull_request', 'issue', 'repository'
    payload = Column(JSONField, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # 'pending', 'processed', 'error'
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    error_message = Column(Text, nullable=True)

    # Relationship
    repository = relationship("Repository", back_populates="raw_events")

    def __repr__(self) -> str:
        return f"<RawEvent(id={self.id}, repo_id={self.repository_id}, type='{self.event_type}')>"


class Commit(Base, TimestampMixin):
    """
    Extracted commit entity.
    """
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    sha = Column(String(40), unique=True, nullable=False, index=True)
    author_name = Column(String(100), nullable=True)
    author_email = Column(String(150), nullable=True, index=True)
    author_date = Column(DateTime, nullable=True, index=True)
    committer_name = Column(String(100), nullable=True)
    committer_date = Column(DateTime, nullable=True)
    message = Column(Text, nullable=True)
    additions = Column(Integer, default=0, nullable=False)
    deletions = Column(Integer, default=0, nullable=False)
    total_changes = Column(Integer, default=0, nullable=False)
    parent_shas = Column(JSONField, default=list, nullable=True)
    raw_payload = Column(JSONField, nullable=True)

    repository = relationship("Repository", back_populates="commits")

    def __repr__(self) -> str:
        return f"<Commit(sha='{self.sha[:7]}', repo_id={self.repository_id})>"


class PullRequest(Base, TimestampMixin):
    """
    Extracted pull request entity.
    """
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_id = Column(BigInteger, unique=True, nullable=False, index=True)
    number = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    state = Column(String(20), nullable=False, index=True)  # 'open', 'closed'
    is_merged = Column(Boolean, default=False, nullable=False)
    created_at_gh = Column(DateTime, nullable=False, index=True)
    updated_at_gh = Column(DateTime, nullable=True)
    closed_at_gh = Column(DateTime, nullable=True)
    merged_at_gh = Column(DateTime, nullable=True)
    user_login = Column(String(100), nullable=True, index=True)
    base_branch = Column(String(100), nullable=True)
    head_branch = Column(String(100), nullable=True)
    comments_count = Column(Integer, default=0, nullable=False)
    additions = Column(Integer, default=0, nullable=False)
    deletions = Column(Integer, default=0, nullable=False)
    changed_files = Column(Integer, default=0, nullable=False)
    raw_payload = Column(JSONField, nullable=True)

    repository = relationship("Repository", back_populates="pull_requests")

    def __repr__(self) -> str:
        return f"<PullRequest(#{self.number}, repo_id={self.repository_id}, state='{self.state}')>"


class Issue(Base, TimestampMixin):
    """
    Extracted issue entity.
    """
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_id = Column(BigInteger, unique=True, nullable=False, index=True)
    number = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    state = Column(String(20), nullable=False, index=True)  # 'open', 'closed'
    created_at_gh = Column(DateTime, nullable=False, index=True)
    updated_at_gh = Column(DateTime, nullable=True)
    closed_at_gh = Column(DateTime, nullable=True)
    user_login = Column(String(100), nullable=True, index=True)
    assignees = Column(JSONField, default=list, nullable=True)
    comments_count = Column(Integer, default=0, nullable=False)
    labels = Column(JSONField, default=list, nullable=True)
    raw_payload = Column(JSONField, nullable=True)

    repository = relationship("Repository", back_populates="issues")

    def __repr__(self) -> str:
        return f"<Issue(#{self.number}, repo_id={self.repository_id}, state='{self.state}')>"
