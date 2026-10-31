from app.repositories.base import BaseRepository
from app.repositories.repository_repo import repository_repo, RepositoryRepository
from app.repositories.pipeline_repo import pipeline_run_repo, PipelineRunRepository
from app.repositories.raw_events_repo import (
    raw_event_repo,
    commit_repo,
    pull_request_repo,
    issue_repo,
    RawEventRepository,
    CommitRepository,
    PullRequestRepository,
    IssueRepository,
)
from app.repositories.raw_storage_repo import (
    raw_repository_repo,
    raw_commit_repo,
    raw_issue_repo,
    raw_pull_request_repo,
    RawRepositoryRepository,
    RawCommitRepository,
    RawIssueRepository,
    RawPullRequestRepository,
)
from app.repositories.operational_repo import (
    extraction_log_repo,
    data_quality_repo,
    ExtractionLogRepository,
    DataQualityRepository,
)

__all__ = [
    "BaseRepository",
    # core entities
    "repository_repo",
    "RepositoryRepository",
    "pipeline_run_repo",
    "PipelineRunRepository",
    # legacy raw + silver
    "raw_event_repo",
    "RawEventRepository",
    "commit_repo",
    "CommitRepository",
    "pull_request_repo",
    "PullRequestRepository",
    "issue_repo",
    "IssueRepository",
    # bronze raw tables
    "raw_repository_repo",
    "RawRepositoryRepository",
    "raw_commit_repo",
    "RawCommitRepository",
    "raw_issue_repo",
    "RawIssueRepository",
    "raw_pull_request_repo",
    "RawPullRequestRepository",
    # operational
    "extraction_log_repo",
    "ExtractionLogRepository",
    "data_quality_repo",
    "DataQualityRepository",
]
