from datetime import datetime
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.pipeline_run import PipelineRun
from app.models.raw_events import Commit, PullRequest, Issue
from app.schemas.repository import RepositoryCreate
from app.repositories.repository_repo import repository_repo
from app.repositories.pipeline_repo import pipeline_run_repo
from app.repositories.raw_events_repo import raw_event_repo
from app.services.repository_service import RepositoryService
from app.services.analytics_service import AnalyticsService


def test_repository_repository_crud(db_session: Session):
    repo = Repository(
        owner="fastapi",
        name="fastapi",
        full_name="fastapi/fastapi",
        html_url="https://github.com/fastapi/fastapi",
        default_branch="master",
        stargazers_count=75000,
        is_active=True,
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    assert repo.id is not None
    assert repo.full_name == "fastapi/fastapi"

    # Query by full_name
    found = repository_repo.get_by_full_name(db_session, "fastapi/fastapi")
    assert found is not None
    assert found.id == repo.id

    # Active query
    active_repos = repository_repo.get_active(db_session)
    assert len(active_repos) >= 1


def test_repository_service_registration(db_session: Session):
    service = RepositoryService()
    repo_in = RepositoryCreate(
        full_name="psf/requests",
        fetch_initial_metadata=False,
    )
    repo = service.register_repository(db_session, repo_in)
    assert repo.owner == "psf"
    assert repo.name == "requests"
    assert repo.full_name == "psf/requests"
    assert repo.is_active is True

    # Idempotent registration
    same_repo = service.register_repository(db_session, repo_in)
    assert same_repo.id == repo.id


def test_pipeline_run_lifecycle(db_session: Session):
    repo = Repository(
        owner="test-org",
        name="test-repo",
        full_name="test-org/test-repo",
        is_active=True,
    )
    db_session.add(repo)
    db_session.commit()

    # 1. Create run
    run = pipeline_run_repo.create_run(db_session, repository_id=repo.id, stage="extract")
    assert run.id is not None
    assert run.status == "running"
    assert run.stage == "extract"

    # 2. Complete run
    completed = pipeline_run_repo.complete_run(
        db_session,
        run_id=run.id,
        records_extracted=50,
        records_loaded=50,
        metadata={"step": "silver_promotion"},
    )
    assert completed.status == "completed"
    assert completed.records_extracted == 50
    assert completed.records_loaded == 50
    assert completed.duration_seconds is not None


def test_raw_events_bulk_store(db_session: Session):
    repo = Repository(
        owner="octocat",
        name="hello-world",
        full_name="octocat/hello-world",
        is_active=True,
    )
    db_session.add(repo)
    db_session.commit()

    payloads = [
        {"sha": "abc1", "commit": {"message": "Initial commit"}},
        {"sha": "abc2", "commit": {"message": "Update README"}},
    ]
    stored_count = raw_event_repo.bulk_store_events(
        db_session,
        repository_id=repo.id,
        event_type="commit",
        payloads=payloads,
    )
    assert stored_count == 2
    events = raw_event_repo.get_by_repository(db_session, repository_id=repo.id)
    assert len(events) == 2


def test_analytics_service_metrics(db_session: Session):
    analytics = AnalyticsService()
    metrics = analytics.get_overview_metrics(db_session)
    assert hasattr(metrics, "total_repositories")
    assert hasattr(metrics, "total_commits_tracked")
    assert hasattr(metrics, "pipeline_success_rate")

