"""
Raw Commits, Issues, and Pull Requests Bronze Layer Models.

Each model stores the unmodified GitHub API JSON payload alongside:
  - A stable GitHub resource identifier used as the upsert key.
  - Extraction provenance (endpoint, timestamp).
  - A SHA-256 payload hash for change detection.
  - A source_updated_at column derived from the API response.

Unique constraints enforce idempotency:
  raw_commits       → (repository_id, commit_sha)
  raw_issues        → (repository_id, github_issue_id)
  raw_pull_requests → (repository_id, github_pr_id)
"""
import hashlib
import json
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import JSONField, TimestampMixin


# ═══════════════════════════════════════════════════════════════════════════ #
#  Raw Commits                                                                #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawCommit(Base, TimestampMixin):
    """
    Bronze / Raw layer for GitHub commit API responses.
    Upsert key: (repository_id, commit_sha).
    """

    __tablename__ = "raw_commits"

    id = Column(Integer, primary_key=True, index=True)

    repository_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="FK to repositories.id.",
    )

    # Stable identifier — 40-char SHA-1 git hash
    commit_sha = Column(
        String(40),
        nullable=False,
        index=True,
        comment="Full git commit SHA (40 hex chars).",
    )

    # Raw response payload
    raw_payload = Column(
        JSONField,
        nullable=False,
        comment="Complete unmodified GitHub API JSON for this commit.",
    )

    # Provenance
    source_endpoint = Column(
        String(255),
        nullable=False,
        default="/repos/{owner}/{repo}/commits",
        comment="GitHub REST endpoint that returned this record.",
    )
    extracted_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    source_updated_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="Commit author date as reported in the payload.",
    )

    payload_hash = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "commit_sha", name="uq_raw_commits_repo_sha"
        ),
        Index("ix_raw_commits_repo_extracted", "repository_id", "extracted_at"),
        Index("ix_raw_commits_source_updated", "source_updated_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<RawCommit(sha='{self.commit_sha[:7]}', repo_id={self.repository_id})>"
        )

    @staticmethod
    def compute_hash(payload: dict) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════ #
#  Raw Issues                                                                 #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawIssue(Base, TimestampMixin):
    """
    Bronze / Raw layer for GitHub issue API responses.
    Upsert key: (repository_id, github_issue_id).

    Note: GitHub issues and pull requests share the same numbering sequence.
    This table stores ONLY objects where ``pull_request`` key is absent in
    the payload (i.e., genuine issues).
    """

    __tablename__ = "raw_issues"

    id = Column(Integer, primary_key=True, index=True)

    repository_id = Column(Integer, nullable=False, index=True)

    # Stable numeric GitHub identifier
    github_issue_id = Column(
        BigInteger,
        nullable=False,
        index=True,
        comment="GitHub numeric issue ID (globally unique).",
    )
    issue_number = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Repository-scoped issue number.",
    )

    raw_payload = Column(JSONField, nullable=False)
    source_endpoint = Column(
        String(255),
        nullable=False,
        default="/repos/{owner}/{repo}/issues",
    )
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source_updated_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="updated_at from GitHub payload.",
    )
    payload_hash = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "github_issue_id", name="uq_raw_issues_repo_gh_id"
        ),
        Index("ix_raw_issues_repo_extracted", "repository_id", "extracted_at"),
        Index("ix_raw_issues_source_updated", "source_updated_at"),
        Index("ix_raw_issues_repo_number", "repository_id", "issue_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<RawIssue(github_id={self.github_issue_id}, "
            f"#={self.issue_number}, repo_id={self.repository_id})>"
        )

    @staticmethod
    def compute_hash(payload: dict) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════ #
#  Raw Pull Requests                                                          #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawPullRequest(Base, TimestampMixin):
    """
    Bronze / Raw layer for GitHub pull request API responses.
    Upsert key: (repository_id, github_pr_id).
    """

    __tablename__ = "raw_pull_requests"

    id = Column(Integer, primary_key=True, index=True)

    repository_id = Column(Integer, nullable=False, index=True)

    github_pr_id = Column(
        BigInteger,
        nullable=False,
        index=True,
        comment="GitHub numeric pull request ID (globally unique).",
    )
    pr_number = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Repository-scoped PR number.",
    )

    raw_payload = Column(JSONField, nullable=False)
    source_endpoint = Column(
        String(255),
        nullable=False,
        default="/repos/{owner}/{repo}/pulls",
    )
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source_updated_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="updated_at from GitHub payload.",
    )
    payload_hash = Column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "repository_id", "github_pr_id", name="uq_raw_pull_requests_repo_gh_id"
        ),
        Index("ix_raw_prs_repo_extracted", "repository_id", "extracted_at"),
        Index("ix_raw_prs_source_updated", "source_updated_at"),
        Index("ix_raw_prs_repo_number", "repository_id", "pr_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<RawPullRequest(github_id={self.github_pr_id}, "
            f"#={self.pr_number}, repo_id={self.repository_id})>"
        )

    @staticmethod
    def compute_hash(payload: dict) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

