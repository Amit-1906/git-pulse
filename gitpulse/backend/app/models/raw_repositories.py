"""
Raw Repositories Bronze Layer Model.

Stores the complete, unmodified GitHub API response for repository metadata.
Kept separate from the RawEvent table for:
  - Indexing efficiency (repo metadata is frequently queried)
  - Clean schema for dbt staging models
  - Independent upsert logic keyed on github_repo_id
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
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import JSONField, TimestampMixin


class RawRepository(Base, TimestampMixin):
    """
    Bronze / Raw layer for GitHub repository API responses.

    Each record is an immutable snapshot of a repository API response keyed
    on (github_repo_id).  Re-extraction updates the payload in place and
    records the new extraction timestamp, preserving the record hash for
    change-detection.
    """

    __tablename__ = "raw_repositories"

    id = Column(Integer, primary_key=True, index=True)

    # FK to the logical repository tracker
    repository_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="FK to repositories.id — nullable until the repo record is created.",
    )

    # Stable GitHub identifier — used as upsert key
    github_repo_id = Column(
        BigInteger,
        nullable=False,
        unique=True,
        index=True,
        comment="GitHub numeric repository ID (stable across renames).",
    )

    # Human-readable key for debugging/querying
    full_name = Column(
        String(255),
        nullable=False,
        index=True,
        comment="owner/repo at the time of extraction.",
    )

    # Raw response payload
    raw_payload = Column(
        JSONField,
        nullable=False,
        comment="Complete unmodified GitHub API JSON response.",
    )

    # Provenance
    source_endpoint = Column(
        String(255),
        nullable=False,
        default="/repos/{owner}/{repo}",
        comment="GitHub REST endpoint that produced this payload.",
    )
    extracted_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="UTC timestamp when this record was fetched from GitHub.",
    )
    source_updated_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="updated_at value reported by GitHub at extraction time.",
    )

    # Change detection
    payload_hash = Column(
        String(64),
        nullable=True,
        comment="SHA-256 of the raw_payload JSON for change detection.",
    )

    __table_args__ = (
        Index("ix_raw_repositories_full_name_extracted", "full_name", "extracted_at"),
        Index("ix_raw_repositories_source_updated", "source_updated_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<RawRepository(github_repo_id={self.github_repo_id}, "
            f"full_name='{self.full_name}', extracted_at={self.extracted_at})>"
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def compute_hash(payload: dict) -> str:
        """Return a deterministic SHA-256 hex digest of the payload dict."""
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

