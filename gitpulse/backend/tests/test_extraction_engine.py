import pytest
from datetime import datetime
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.extractors.engine import ExtractionEngine
from app.extractors.client import GitHubClient
from app.models.repository import Repository
from app.models.raw_events import RawEvent, Commit, PullRequest, Issue
from app.models.extraction_job import ExtractionJob
from app.models.checkpoint import ExtractionCheckpoint
from app.core.exceptions import GitPulseException


def create_mock_engine():
    mock_client = MagicMock(spec=GitHubClient)
    engine = ExtractionEngine(client=mock_client)

    # Mock repository extractor response
    engine.repo_extractor.extract_metadata = MagicMock(
        return_value={
            "github_id": 5555,
            "name": "fastapi",
            "full_name": "tiangolo/fastapi",
            "description": "FastAPI framework",
            "owner": "tiangolo",
            "visibility": "public",
            "html_url": "https://github.com/tiangolo/fastapi",
            "language": "Python",
            "stargazers_count": 80000,
            "forks_count": 6500,
            "open_issues_count": 120,
            "watchers_count": 80000,
            "default_branch": "master",
            "created_at_gh": datetime(2018, 12, 8),
            "updated_at_gh": datetime(2026, 10, 31),
            "raw_payload": {"id": 5555, "name": "fastapi"},
        }
    )

    # Mock commits extractor response
    engine.commits_extractor.extract = MagicMock(
        return_value=[
            {
                "sha": "commit_sha_1",
                "author_name": "Dev One",
                "author_email": "dev1@example.com",
                "author_date": datetime(2026, 10, 20),
                "committer_name": "Dev One",
                "committer_date": datetime(2026, 10, 20),
                "message": "feat: initial commit",
                "parent_shas": [],
                "additions": 100,
                "deletions": 0,
                "total_changes": 100,
                "raw_payload": {"sha": "commit_sha_1"},
            },
            {
                "sha": "commit_sha_2",
                "author_name": "Dev Two",
                "author_email": "dev2@example.com",
                "author_date": datetime(2026, 10, 25),
                "committer_name": "Dev Two",
                "committer_date": datetime(2026, 10, 25),
                "message": "fix: bugfix",
                "parent_shas": ["commit_sha_1"],
                "additions": 10,
                "deletions": 5,
                "total_changes": 15,
                "raw_payload": {"sha": "commit_sha_2"},
            },
        ]
    )

    # Mock issues extractor response
    engine.issues_extractor.extract = MagicMock(
        return_value=[
            {
                "github_id": 9001,
                "number": 1,
                "title": "Bug report",
                "body": "Issue details",
                "state": "open",
                "user_login": "reporter",
                "assignees": ["assignee_1"],
                "labels": ["bug"],
                "comments_count": 2,
                "created_at_gh": datetime(2026, 10, 21),
                "updated_at_gh": datetime(2026, 10, 22),
                "closed_at_gh": None,
                "raw_payload": {"id": 9001, "number": 1},
            }
        ]
    )

    # Mock PR extractor response
    engine.prs_extractor.extract = MagicMock(
        return_value=[
            {
                "github_id": 8001,
                "number": 10,
                "title": "Add feature X",
                "body": "PR details",
                "state": "closed",
                "user_login": "contributor",
                "base_branch": "master",
                "head_branch": "feature-x",
                "is_merged": True,
                "comments_count": 4,
                "additions": 50,
                "deletions": 10,
                "changed_files": 2,
                "created_at_gh": datetime(2026, 10, 23),
                "updated_at_gh": datetime(2026, 10, 24),
                "closed_at_gh": datetime(2026, 10, 24),
                "merged_at_gh": datetime(2026, 10, 24),
                "raw_payload": {"id": 8001, "number": 10},
            }
        ]
    )

    return engine


def test_unique_job_id_and_execution(db_session: Session):
    engine = create_mock_engine()

    # 1. Create job
    job = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    assert job.job_id.startswith("job_")
    assert job.status == "PENDING"
    assert job.repository_full_name == "tiangolo/fastapi"

    # 2. Run job
    completed_job = engine.run_job(db=db_session, job_id=job.job_id)
    assert completed_job.status == "COMPLETED"
    assert completed_job.duration_seconds is not None
    assert completed_job.records_extracted["commits"] == 2
    assert completed_job.records_loaded["commits"] == 2
    assert completed_job.records_extracted["issues"] == 1
    assert completed_job.records_extracted["pull_requests"] == 1

    # Verify Bronze Raw Events were stored
    bronze_events = list(db_session.scalars(select(RawEvent)).all())
    assert len(bronze_events) >= 4  # repo, 2 commits, 1 issue, 1 PR

    # Verify Silver Entities were created
    commits = list(db_session.scalars(select(Commit)).all())
    assert len(commits) == 2
    assert commits[0].parent_shas is not None

    prs = list(db_session.scalars(select(PullRequest)).all())
    assert len(prs) == 1
    assert prs[0].base_branch == "master"
    assert prs[0].is_merged is True

    issues = list(db_session.scalars(select(Issue)).all())
    assert len(issues) == 1
    assert issues[0].assignees == ["assignee_1"]


def test_duplicate_prevention_on_second_run(db_session: Session):
    engine = create_mock_engine()

    # Run first extraction
    job1 = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    engine.run_job(db=db_session, job_id=job1.job_id)

    initial_commit_count = db_session.scalar(select(Commit).where(Commit.sha == "commit_sha_1"))
    assert initial_commit_count is not None

    # Run second extraction with same mock data
    job2 = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    engine.run_job(db=db_session, job_id=job2.job_id)

    # Commits loaded should be 0 because SHAs already exist in database
    assert job2.records_loaded["commits"] == 0

    all_commits = list(db_session.scalars(select(Commit)).all())
    # Should still only be 2 total commits, no duplicates
    assert len(all_commits) == 2


def test_concurrency_lock_prevents_overlapping_jobs(db_session: Session):
    engine = create_mock_engine()

    # Create job 1 (status PENDING)
    job1 = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    assert job1.status == "PENDING"

    # Attempt to create job 2 for same repo while job 1 is pending/running
    with pytest.raises(GitPulseException) as exc_info:
        engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")

    assert exc_info.value.code == "DUPLICATE_JOB_IN_PROGRESS"
    assert exc_info.value.status_code == 409


def test_partial_failure_handling(db_session: Session):
    engine = create_mock_engine()
    # Simulate issues extractor failing with 404 or connection error
    engine.issues_extractor.extract = MagicMock(side_effect=Exception("Issues API 404 Not Found"))

    job = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    res = engine.run_job(db=db_session, job_id=job.job_id)

    # Job must complete with PARTIAL_SUCCESS, preserving successful commits & PRs
    assert res.status == "PARTIAL_SUCCESS"
    assert "issues" in res.error_details
    assert res.records_extracted["commits"] == 2
    assert res.records_extracted["pull_requests"] == 1


def test_job_cancellation(db_session: Session):
    engine = create_mock_engine()

    job = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    cancelled = engine.cancel_job(db=db_session, job_id=job.job_id)

    assert cancelled.status == "CANCELLED"
    assert cancelled.cancel_requested is True


def test_incremental_checkpoints_saved(db_session: Session):
    engine = create_mock_engine()

    job = engine.create_job(db=db_session, repository_full_name="tiangolo/fastapi")
    engine.run_job(db=db_session, job_id=job.job_id)

    # Verify checkpoint table has entries for commits, issues, pull_requests
    repo = db_session.scalar(select(Repository).where(Repository.full_name == "tiangolo/fastapi"))
    assert repo is not None

    commit_cp = engine.get_checkpoint(db_session, repo.id, "commits")
    assert commit_cp is not None
    assert commit_cp.last_checkpoint_timestamp == datetime(2026, 10, 25)
    assert commit_cp.last_record_id == "commit_sha_2"

    pr_cp = engine.get_checkpoint(db_session, repo.id, "pull_requests")
    assert pr_cp is not None
    assert pr_cp.last_checkpoint_timestamp == datetime(2026, 10, 24)

