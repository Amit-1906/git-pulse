"""
GitPulse SQLAlchemy model registry.

Import order matters: models must be imported before Base.metadata.create_all()
is called so SQLAlchemy discovers every Table definition.
"""
from app.database import Base
from app.models.base import TimestampMixin, JSONField

# ── Core entities ────────────────────────────────────────────────────────────
from app.models.repository import Repository
from app.models.pipeline_run import PipelineRun
from app.models.extraction_job import ExtractionJob
from app.models.checkpoint import ExtractionCheckpoint

# ── Bronze / Raw layer (original API response preservation) ──────────────────
from app.models.raw_events import RawEvent, Commit, PullRequest, Issue   # legacy + silver entities
from app.models.raw_repositories import RawRepository                     # dedicated raw repos table
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest       # dedicated raw tables

# ── Operational / Quality ─────────────────────────────────────────────────────
from app.models.operational import ExtractionLog, DataQualityResult

__all__ = [
    # infrastructure
    "Base",
    "TimestampMixin",
    "JSONField",
    # core
    "Repository",
    "PipelineRun",
    "ExtractionJob",
    "ExtractionCheckpoint",
    # legacy raw + silver entities (raw_events table)
    "RawEvent",
    "Commit",
    "PullRequest",
    "Issue",
    # dedicated bronze tables
    "RawRepository",
    "RawCommit",
    "RawIssue",
    "RawPullRequest",
    # operational
    "ExtractionLog",
    "DataQualityResult",
]
