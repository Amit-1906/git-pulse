"""
Tests for Database Telemetry and Storage Exploration Endpoints:
- GET /api/v1/database/status
- GET /api/v1/database/statistics
- GET /api/v1/database/tables
- GET /api/v1/database/storage-summary
"""
import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.database import (
    get_database_status,
    get_database_statistics,
    get_database_tables,
    get_storage_summary,
)
from app.models.repository import Repository
from app.models.raw_data import RawCommit
from app.repositories.raw_storage_repo import raw_commit_repo


def test_database_status_endpoint(db_session: Session):
    """Verifies GET /api/v1/database/status response schema and connectivity status."""
    resp = get_database_status(db=db_session)
    assert resp.status == "healthy"
    assert resp.connected is True
    assert resp.dialect in ("sqlite", "postgresql")
    assert resp.latency_ms >= 0.0


def test_database_statistics_endpoint(db_session: Session):
    """Verifies GET /api/v1/database/statistics returns partitioned row counts."""
    # Seed a repo and a raw commit
    repo = Repository(
        github_id=555123,
        owner="test-owner",
        name="test-repo",
        full_name="test-owner/test-repo",
        is_active=True,
    )
    db_session.add(repo)
    db_session.commit()

    raw_commit_repo.upsert(
        db_session,
        repository_id=repo.id,
        commit_sha="abcd" * 10,
        raw_payload={"message": "stat test"},
    )

    resp = get_database_statistics(db=db_session)
    assert resp.total_tables >= 9
    assert resp.total_records >= 2  # 1 repo + 1 raw commit
    assert resp.bronze_records >= 1
    assert resp.silver_records >= 1

    table_names = [t.table_name for t in resp.tables]
    assert "repositories" in table_names
    assert "raw_commits" in table_names
    assert "raw_repositories" in table_names
    assert "extraction_jobs" in table_names


def test_database_tables_endpoint(db_session: Session):
    """Verifies GET /api/v1/database/tables returns column structures and tiers."""
    resp = get_database_tables(db=db_session)
    assert resp.count >= 9

    table_dict = {t.name: t for t in resp.tables}
    assert "raw_commits" in table_dict
    raw_commits_detail = table_dict["raw_commits"]
    assert raw_commits_detail.tier == "bronze"

    col_names = [c.name for c in raw_commits_detail.columns]
    assert "id" in col_names
    assert "repository_id" in col_names
    assert "commit_sha" in col_names
    assert "raw_payload" in col_names


def test_database_storage_summary_endpoint(db_session: Session):
    """Verifies GET /api/v1/database/storage-summary tier architecture summary."""
    resp = get_storage_summary(db=db_session)
    assert "bronze" in resp.tiers
    assert "silver" in resp.tiers
    assert "operational" in resp.tiers

    bronze_tier = resp.tiers["bronze"]
    assert "raw_repositories" in bronze_tier.tables
    assert "raw_commits" in bronze_tier.tables
    assert "raw_issues" in bronze_tier.tables
    assert "raw_pull_requests" in bronze_tier.tables

    assert resp.total_storage_rows >= 0

