"""
Automated Test Suite for PostgreSQL Storage Architecture (Bronze / Raw Layer).

Covers:
- Raw JSON/JSONB preservation (zero loss of nested structures)
- Idempotency & duplicate prevention via upsert
- Batch insertion operations
- Transaction rollback safety
- Checkpoint persistence and recovery
- Database health check and reconnection handling
- Extraction engine integration into the Bronze storage layer
"""
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.raw_repositories import RawRepository
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest
from app.models.checkpoint import ExtractionCheckpoint
from app.models.operational import ExtractionLog, DataQualityResult
from app.repositories.raw_storage_repo import (
    raw_repository_repo,
    raw_commit_repo,
    raw_issue_repo,
    raw_pull_request_repo,
)
from app.repositories.operational_repo import (
    extraction_log_repo,
    data_quality_repo,
)
from app.extractors.engine import ExtractionEngine
from app.database import check_db_health, create_db_engine


@pytest.fixture
def sample_repo(db_session: Session) -> Repository:
    """Fixture providing an active registered repository."""
    repo = Repository(
        github_id=987654,
        owner="octocat",
        name="Hello-World",
        full_name="octocat/hello-world",
        default_branch="main",
        visibility="public",
        is_active=True,
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)
    return repo


def test_raw_json_preservation(db_session: Session, sample_repo: Repository):
    """
    Validates that complex nested JSON structures from GitHub API responses
    are stored without mutation, flattening, or precision loss.
    """
    nested_payload = {
        "id": 123456,
        "node_id": "MDEwOlJlcG9zaXRvcnkxMjM0NTY=",
        "name": "Hello-World",
        "owner": {
            "login": "octocat",
            "id": 1,
            "site_admin": False,
            "permissions": {"admin": True, "push": True, "pull": True},
        },
        "topics": ["git", "elt", "fastapi"],
        "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"},
        "subscribers_count": 42,
        "is_template": False,
    }

    raw_repo = raw_repository_repo.upsert(
        db_session,
        github_repo_id=123456,
        full_name="octocat/hello-world",
        raw_payload=nested_payload,
        source_endpoint="/repos/octocat/hello-world",
        repository_id=sample_repo.id,
    )

    retrieved = raw_repository_repo.get_by_github_id(db_session, 123456)
    assert retrieved is not None
    assert retrieved.github_repo_id == 123456
    assert retrieved.raw_payload["owner"]["permissions"]["admin"] is True
    assert retrieved.raw_payload["topics"] == ["git", "elt", "fastapi"]
    assert retrieved.payload_hash is not None
    assert len(retrieved.payload_hash) == 64


def test_duplicate_prevention_and_upsert(db_session: Session, sample_repo: Repository):
    """
    Validates idempotency: repeated upserts for the same unique keys update the
    existing row instead of creating duplicates.
    """
    sha = "e1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"
    payload_v1 = {"sha": sha, "commit": {"message": "Initial commit", "author": {"name": "Alice"}}}
    payload_v2 = {"sha": sha, "commit": {"message": "Updated commit message", "author": {"name": "Alice"}}}

    # First write
    c1 = raw_commit_repo.upsert(
        db_session,
        repository_id=sample_repo.id,
        commit_sha=sha,
        raw_payload=payload_v1,
    )
    count_after_first = raw_commit_repo.count_by_repository(db_session, sample_repo.id)
    assert count_after_first == 1
    assert c1.raw_payload["commit"]["message"] == "Initial commit"

    # Second write with changed payload
    c2 = raw_commit_repo.upsert(
        db_session,
        repository_id=sample_repo.id,
        commit_sha=sha,
        raw_payload=payload_v2,
    )
    count_after_second = raw_commit_repo.count_by_repository(db_session, sample_repo.id)
    assert count_after_second == 1
    assert c2.raw_payload["commit"]["message"] == "Updated commit message"


def test_batch_insertion(db_session: Session, sample_repo: Repository):
    """
    Validates batch bulk insertion efficiency and record accuracy.
    """
    records = []
    for i in range(25):
        sha = f"batch_sha_{i:04d}" + "0" * 28
        records.append({
            "commit_sha": sha,
            "raw_payload": {"sha": sha, "index": i, "commit": {"message": f"Batch commit {i}"}},
            "source_updated_at": datetime.utcnow() - timedelta(hours=i),
        })

    inserted, updated = raw_commit_repo.bulk_upsert(
        db_session,
        repository_id=sample_repo.id,
        records=records,
    )

    total_in_db = raw_commit_repo.count_by_repository(db_session, sample_repo.id)
    assert total_in_db == 25
    assert inserted >= 25

    # Run again with same records — should update without increasing count
    inserted_2, updated_2 = raw_commit_repo.bulk_upsert(
        db_session,
        repository_id=sample_repo.id,
        records=records,
    )
    assert raw_commit_repo.count_by_repository(db_session, sample_repo.id) == 25


def test_transaction_rollback():
    """
    Verifies that database operations rolled back on error do not leak partial state.
    Uses SAVEPOINT nested transaction rollback.
    """
    from tests.conftest import engine_test, TestingSessionLocal

    with engine_test.connect() as conn:
        trans = conn.begin()
        session = TestingSessionLocal(bind=conn)
        try:
            repo = Repository(
                github_id=888999,
                owner="rollback-org",
                name="rollback-repo",
                full_name="rollback-org/rollback-repo",
                is_active=True,
            )
            session.add(repo)
            session.flush()
            repo_id = repo.id

            # Begin a nested transaction savepoint
            savepoint = conn.begin_nested()
            raw_issue_repo.upsert(
                session,
                repository_id=repo_id,
                github_issue_id=999999,
                issue_number=1,
                raw_payload={"title": "Test Issue", "body": "Details"},
                commit=False,
            )
            session.flush()
            assert raw_issue_repo.count_by_repository(session, repo_id) == 1

            # Roll back to savepoint
            savepoint.rollback()
            assert raw_issue_repo.count_by_repository(session, repo_id) == 0
        finally:
            trans.rollback()
            session.close()


def test_checkpoint_recovery(db_session: Session, sample_repo: Repository):
    """
    Validates checkpoint creation, high-water mark advancement, and retrieval.
    """
    engine = ExtractionEngine()

    t1 = datetime(2026, 1, 1, 12, 0, 0)
    engine.set_checkpoint(db_session, sample_repo.id, "commits", t1, last_id="sha_1")

    cp = engine.get_checkpoint(db_session, sample_repo.id, "commits")
    assert cp is not None
    assert cp.last_checkpoint_timestamp == t1
    assert cp.last_record_id == "sha_1"

    # Advance checkpoint to newer timestamp
    t2 = datetime(2026, 1, 2, 12, 0, 0)
    engine.set_checkpoint(db_session, sample_repo.id, "commits", t2, last_id="sha_2")

    cp_updated = engine.get_checkpoint(db_session, sample_repo.id, "commits")
    assert cp_updated.last_checkpoint_timestamp == t2
    assert cp_updated.last_record_id == "sha_2"


def test_database_reconnection_and_health(db_session: Session):
    """
    Validates connection probing and degraded response detection.
    """
    health = check_db_health(db_session.get_bind())
    assert health["status"] == "healthy"
    assert health["connected"] is True
    assert health["latency_ms"] >= 0.0

    # Test an unreachable engine
    unreachable_engine = create_db_engine("postgresql+psycopg2://bad:bad@127.0.0.1:59999/bad_db")
    bad_health = check_db_health(unreachable_engine)
    assert bad_health["connected"] is False
    assert bad_health["status"] == "degraded"


def test_extraction_logs_and_data_quality(db_session: Session, sample_repo: Repository):
    """
    Validates operational tables: audit logs and data quality results.
    """
    # 1. Extraction Logs
    extraction_log_repo.append(
        db_session,
        job_id="job_test_01",
        repository_full_name=sample_repo.full_name,
        message="Started commit extraction",
        level="INFO",
        resource_type="commits",
        repository_id=sample_repo.id,
    )
    extraction_log_repo.append(
        db_session,
        job_id="job_test_01",
        repository_full_name=sample_repo.full_name,
        message="Encountered transient rate limit",
        level="WARNING",
        resource_type="commits",
        repository_id=sample_repo.id,
    )

    logs = extraction_log_repo.get_by_job(db_session, "job_test_01")
    assert len(logs) == 2
    counts = extraction_log_repo.count_by_level(db_session, "job_test_01")
    assert counts.get("INFO") == 1
    assert counts.get("WARNING") == 1

    # 2. Data Quality Results
    data_quality_repo.record_result(
        db_session,
        rule_name="not_null:commits.sha",
        passed=True,
        resource_type="commits",
        repository_id=sample_repo.id,
        failure_count=0,
        total_count=100,
    )
    data_quality_repo.record_result(
        db_session,
        rule_name="unique:commits.sha",
        passed=False,
        resource_type="commits",
        repository_id=sample_repo.id,
        failure_count=2,
        total_count=100,
        severity="error",
    )

    summary = data_quality_repo.get_summary(db_session, sample_repo.id)
    assert summary["total_checks"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["pass_rate_pct"] == 50.0
