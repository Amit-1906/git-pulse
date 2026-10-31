"""
Extraction Logs and Data Quality Results Models.

extraction_logs  — append-only log of per-resource extraction events.
data_quality_results — stores validation rule outcomes produced by dbt tests
                       or in-pipeline quality checks.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import JSONField, TimestampMixin


# ═══════════════════════════════════════════════════════════════════════════ #
#  Extraction Logs                                                             #
# ═══════════════════════════════════════════════════════════════════════════ #


class ExtractionLog(Base, TimestampMixin):
    """
    Append-only operational log for individual extraction events.

    One row per resource-level activity within an extraction job, enabling
    fine-grained post-mortem analysis without overwriting job-level telemetry.

    Levels: DEBUG | INFO | WARNING | ERROR | CRITICAL
    """

    __tablename__ = "extraction_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Link to the parent job
    job_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="References extraction_jobs.job_id (not a FK to avoid cascade issues).",
    )
    repository_id = Column(Integer, nullable=True, index=True)
    repository_full_name = Column(String(200), nullable=False, index=True)

    # Log metadata
    level = Column(
        String(10),
        nullable=False,
        default="INFO",
        index=True,
        comment="Log severity: DEBUG | INFO | WARNING | ERROR | CRITICAL.",
    )
    resource_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Which resource was being extracted: commits | issues | pull_requests | repository.",
    )
    stage = Column(
        String(50),
        nullable=True,
        comment="Pipeline stage: extract | load | validate | checkpoint.",
    )

    # Message content
    message = Column(Text, nullable=False)
    details = Column(JSONField, nullable=True, comment="Structured context payload.")

    # Telemetry
    records_processed = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=True)
    logged_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_extraction_logs_job_level", "job_id", "level"),
        Index("ix_extraction_logs_repo_logged", "repository_id", "logged_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExtractionLog(job='{self.job_id}', level='{self.level}', "
            f"resource='{self.resource_type}')>"
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  Data Quality Results                                                        #
# ═══════════════════════════════════════════════════════════════════════════ #


class DataQualityResult(Base, TimestampMixin):
    """
    Stores the outcome of individual data-quality rule evaluations.

    Populated by:
    - dbt test runs (parsed from dbt artifacts)
    - In-pipeline pre-load checks (null counts, uniqueness, range checks)

    One row per (rule_name, resource_type, repository_id, evaluated_at) combination.
    """

    __tablename__ = "data_quality_results"

    id = Column(Integer, primary_key=True, index=True)

    # Context
    repository_id = Column(Integer, nullable=True, index=True)
    repository_full_name = Column(String(200), nullable=True, index=True)

    # Provenance
    job_id = Column(String(64), nullable=True, index=True)
    source = Column(
        String(50),
        nullable=False,
        default="pipeline",
        comment="Origin of the check: 'pipeline' | 'dbt' | 'manual'.",
    )

    # Rule identification
    rule_name = Column(
        String(200),
        nullable=False,
        index=True,
        comment="Unique rule identifier, e.g. 'not_null:commits.sha'.",
    )
    resource_type = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Data asset being tested: commits | issues | pull_requests | repositories.",
    )
    column_name = Column(String(100), nullable=True, comment="Column being validated.")

    # Result
    passed = Column(Boolean, nullable=False, index=True)
    severity = Column(
        String(10),
        nullable=False,
        default="warn",
        comment="Rule severity: 'error' | 'warn' | 'info'.",
    )
    failure_count = Column(
        Integer,
        nullable=True,
        default=0,
        comment="Number of rows that failed the rule (0 = all passed).",
    )
    total_count = Column(
        Integer,
        nullable=True,
        comment="Total rows evaluated.",
    )
    failure_rate = Column(Float, nullable=True, comment="failure_count / total_count.")

    # Human-readable summary and machine details
    message = Column(Text, nullable=True)
    details = Column(JSONField, nullable=True)

    evaluated_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_dqr_repo_rule", "repository_id", "rule_name"),
        Index("ix_dqr_passed_evaluated", "passed", "evaluated_at"),
        Index("ix_dqr_source_resource", "source", "resource_type"),
    )

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"<DataQualityResult(rule='{self.rule_name}', "
            f"status={status}, failures={self.failure_count})>"
        )

