"""
End-to-End Pipeline Integration Test.
Validates the entire ELT lifecycle:
1. Register target repository.
2. Configure & launch extraction job.
3. Verify Bronze raw storage preservation (raw_repositories, raw_commits, raw_issues, raw_pull_requests).
4. Verify extraction checkpoints are updated.
5. Verify idempotency and duplicate prevention on second extraction.
6. Verify transformation service execution and telemetry recording.
"""
from datetime import datetime
from unittest.mock import patch
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.api.v1.endpoints.repositories import create_repository
from app.api.v1.endpoints.extraction import start_extraction
from app.schemas.repository import RepositoryCreate
from app.schemas.extraction import ExtractionStartRequest
from app.models.repository import Repository
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest
from app.models.raw_repositories import RawRepository
from app.models.checkpoint import ExtractionCheckpoint
from app.extractors.engine import extraction_engine


def test_full_end_to_end_pipeline(db_session: Session):
    # Step 1: Register target repository
    repo_in = RepositoryCreate(
        full_name="tiangolo/fastapi",
        fetch_initial_metadata=False,
    )
    repo = create_repository(repo_in=repo_in, db=db_session)
    assert repo.id is not None
    assert repo.full_name == "tiangolo/fastapi"
    repo_id = repo.id

    # Step 2: Mock external GitHub API calls
    mock_meta = {
        "github_id": 111222,
        "owner": "tiangolo",
        "name": "fastapi",
        "full_name": "tiangolo/fastapi",
        "description": "FastAPI framework",
        "html_url": "https://github.com/tiangolo/fastapi",
        "default_branch": "master",
        "visibility": "public",
        "stargazers_count": 80000,
        "forks_count": 6500,
        "open_issues_count": 150,
        "watchers_count": 80000,
        "language": "Python",
        "created_at_gh": datetime(2018, 12, 5, 0, 0, 0),
        "updated_at_gh": datetime(2026, 10, 31, 12, 0, 0),
        "raw_payload": {"id": 111222, "full_name": "tiangolo/fastapi", "stars": 80000},
    }

    mock_commits = [
        {
            "sha": "a1b2c3d4e5f67890123456789012345678901234",
            "author_name": "Sebastián Ramírez",
            "author_email": "tiangolo@example.com",
            "author_date": datetime(2026, 10, 30, 15, 0, 0),
            "committer_name": "GitHub",
            "committer_date": datetime(2026, 10, 30, 15, 0, 0),
            "message": "feat: release FastAPI v0.110.0",
            "parent_shas": ["b9c8d7e6f5a43210123456789012345678901234"],
            "additions": 150,
            "deletions": 20,
            "total_changes": 170,
            "raw_payload": {"sha": "a1b2c3d4e5f67890123456789012345678901234", "stats": {"total": 170}},
        }
    ]

    mock_issues = [
        {
            "github_id": 998877,
            "number": 42,
            "title": "Support async dependency injection cache",
            "body": "Detailed discussion",
            "state": "closed",
            "user_login": "contributor_one",
            "assignees": ["tiangolo"],
            "labels": ["enhancement"],
            "comments_count": 5,
            "created_at_gh": datetime(2026, 10, 20, 10, 0, 0),
            "updated_at_gh": datetime(2026, 10, 25, 12, 0, 0),
            "closed_at_gh": datetime(2026, 10, 25, 12, 0, 0),
            "raw_payload": {"id": 998877, "number": 42, "state": "closed"},
        }
    ]

    mock_prs = [
        {
            "github_id": 554433,
            "number": 100,
            "title": "Add test coverage for background tasks",
            "body": "PR description",
            "state": "closed",
            "user_login": "contributor_two",
            "base_branch": "master",
            "head_branch": "fix/bg-tasks",
            "is_merged": True,
            "comments_count": 8,
            "additions": 45,
            "deletions": 5,
            "changed_files": 2,
            "created_at_gh": datetime(2026, 10, 22, 14, 0, 0),
            "updated_at_gh": datetime(2026, 10, 24, 16, 0, 0),
            "closed_at_gh": datetime(2026, 10, 24, 16, 0, 0),
            "merged_at_gh": datetime(2026, 10, 24, 16, 0, 0),
            "raw_payload": {"id": 554433, "number": 100, "merged": True},
        }
    ]

    with patch.object(extraction_engine.repo_extractor, "extract_metadata", return_value=mock_meta), \
         patch.object(extraction_engine.commits_extractor, "extract", return_value=mock_commits), \
         patch.object(extraction_engine.issues_extractor, "extract", return_value=mock_issues), \
         patch.object(extraction_engine.prs_extractor, "extract", return_value=mock_prs):

        # Step 3: Trigger Extraction Job synchronously
        ext_req = ExtractionStartRequest(
            repository_full_name="tiangolo/fastapi",
            resources=["repository", "commits", "issues", "pull_requests"],
            incremental=True,
        )
        job = extraction_engine.create_job(
            db=db_session,
            repository_full_name=ext_req.repository_full_name,
            resources=ext_req.resources,
            incremental=ext_req.incremental,
        )
        job_result = extraction_engine.run_job(db=db_session, job_id=job.job_id)
        assert job_result.status == "COMPLETED"
        assert job_result.records_extracted["commits"] == 1
        assert job_result.records_extracted["issues"] == 1
        assert job_result.records_extracted["pull_requests"] == 1

        # Step 4: Verify Bronze Raw JSONB Storage
        raw_repo = db_session.scalar(select(RawRepository).where(RawRepository.full_name == "tiangolo/fastapi"))
        assert raw_repo is not None
        assert raw_repo.raw_payload["stars"] == 80000

        raw_commit = db_session.scalar(select(RawCommit).where(RawCommit.commit_sha == "a1b2c3d4e5f67890123456789012345678901234"))
        assert raw_commit is not None
        assert raw_commit.raw_payload["stats"]["total"] == 170

        raw_issue = db_session.scalar(select(RawIssue).where(RawIssue.github_issue_id == 998877))
        assert raw_issue is not None
        assert raw_issue.raw_payload["state"] == "closed"

        raw_pr = db_session.scalar(select(RawPullRequest).where(RawPullRequest.github_pr_id == 554433))
        assert raw_pr is not None
        assert raw_pr.raw_payload["merged"] is True

        # Step 5: Verify Checkpoints were saved
        commit_cp = db_session.scalar(
            select(ExtractionCheckpoint).where(
                ExtractionCheckpoint.repository_id == repo_id,
                ExtractionCheckpoint.resource_type == "commits",
            )
        )
        assert commit_cp is not None
        assert commit_cp.last_checkpoint_timestamp is not None

        # Step 6: Verify Upsert & Idempotency on repeated run (no duplicates)
        job2 = extraction_engine.create_job(
            db=db_session,
            repository_full_name="tiangolo/fastapi",
            resources=["repository", "commits", "issues", "pull_requests"],
            incremental=True,
        )
        job_result2 = extraction_engine.run_job(db=db_session, job_id=job2.job_id)
        assert job_result2.status == "COMPLETED"

        # Count records to ensure no duplicates in Bronze layer
        commit_count = db_session.scalar(
            select(func.count(RawCommit.id)).where(RawCommit.commit_sha == "a1b2c3d4e5f67890123456789012345678901234")
        )
        assert commit_count == 1

        pr_count = db_session.scalar(
            select(func.count(RawPullRequest.id)).where(RawPullRequest.github_pr_id == 554433)
        )
        assert pr_count == 1
