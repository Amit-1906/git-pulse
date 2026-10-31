"""
Dashboard API Integration Tests.
Verifies that all analytical, metadata, and status endpoints required by Streamlit
return the expected structure and correctly calculate metrics from database tables.
"""
from datetime import datetime
from unittest.mock import patch
from sqlalchemy.orm import Session

from app.api.v1.endpoints.analytics import (
    get_overview,
    get_contributors,
    get_commits,
    get_pull_requests,
    get_issues,
)
from app.api.v1.endpoints.database import (
    get_database_status,
    get_database_statistics,
    get_storage_summary,
)
from app.api.v1.endpoints.github import get_github_status
from app.api.v1.endpoints.transformation import get_data_lineage
from app.core.auth import github_auth_manager
from app.models.repository import Repository
from app.models.raw_events import Commit, PullRequest, Issue
from app.models.pipeline_run import PipelineRun


def test_dashboard_analytical_endpoints_integration(db_session: Session):
    # Seed repository
    repo = Repository(
        github_id=424242,
        owner="tiangolo",
        name="fastapi",
        full_name="tiangolo/fastapi",
        description="FastAPI Web Framework",
        html_url="https://github.com/tiangolo/fastapi",
        stargazers_count=80000,
        forks_count=6500,
        open_issues_count=120,
        language="Python",
        is_active=True,
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    # Seed commits
    c1 = Commit(
        repository_id=repo.id,
        sha="1111111111111111111111111111111111111111",
        author_name="Alice Dev",
        author_email="alice@example.com",
        author_date=datetime(2026, 10, 28, 10, 0, 0),
        message="feat: initial feature",
        additions=100,
        deletions=10,
        total_changes=110,
    )
    c2 = Commit(
        repository_id=repo.id,
        sha="2222222222222222222222222222222222222222",
        author_name="Bob Engineer",
        author_email="bob@example.com",
        author_date=datetime(2026, 10, 29, 11, 0, 0),
        message="fix: resolve bug",
        additions=20,
        deletions=5,
        total_changes=25,
    )
    db_session.add_all([c1, c2])

    # Seed Pull Request
    pr = PullRequest(
        repository_id=repo.id,
        github_id=778899,
        number=1,
        title="PR 1: Feature branch",
        state="closed",
        is_merged=True,
        user_login="alice_gh",
        created_at_gh=datetime(2026, 10, 28, 12, 0, 0),
        closed_at_gh=datetime(2026, 10, 29, 12, 0, 0),
        merged_at_gh=datetime(2026, 10, 29, 12, 0, 0),
        additions=100,
        deletions=10,
        comments_count=3,
    )
    db_session.add(pr)

    # Seed Issue
    iss = Issue(
        repository_id=repo.id,
        github_id=334455,
        number=10,
        title="Bug in request validation",
        state="open",
        user_login="reporter_one",
        created_at_gh=datetime(2026, 10, 29, 9, 0, 0),
        comments_count=2,
    )
    db_session.add(iss)

    # Seed Pipeline Run
    run = PipelineRun(
        repository_id=repo.id,
        pipeline_name="github_repo_sync",
        stage="load",
        status="completed",
        started_at=datetime(2026, 10, 29, 8, 0, 0),
        finished_at=datetime(2026, 10, 29, 8, 1, 0),
        duration_seconds=60.0,
        records_extracted=10,
        records_loaded=10,
    )
    db_session.add(run)
    db_session.commit()

    # 1. Test Overview KPI
    ov_data = get_overview(db=db_session)
    assert ov_data.total_repositories == 1
    assert ov_data.total_commits_tracked == 2
    assert ov_data.total_pull_requests == 1
    assert ov_data.total_issues == 1
    assert ov_data.total_contributors == 2
    assert ov_data.pipeline_success_rate == 100.0

    # 2. Test Contributors Endpoint
    cnt_data = get_contributors(repository_id=repo.id, limit=10, db=db_session)
    assert len(cnt_data) == 2
    assert cnt_data[0].commits_count == 1

    # 3. Test Commits Filter Endpoint
    com_data = get_commits(repository_id=repo.id, author="Alice", db=db_session)
    assert len(com_data) == 1
    assert com_data[0]["author_name"] == "Alice Dev"
    assert com_data[0]["additions"] == 100

    # 4. Test Pull Requests Filter Endpoint
    pr_data = get_pull_requests(repository_id=repo.id, state="closed", db=db_session)
    assert len(pr_data) == 1
    assert pr_data[0]["is_merged"] is True
    assert pr_data[0]["merged_time_hours"] == 24.0  # (29th 12:00 - 28th 12:00 = 24 hours)

    # 5. Test Issues Filter Endpoint
    iss_data = get_issues(repository_id=repo.id, state="open", db=db_session)
    assert len(iss_data) == 1
    assert iss_data[0]["state"] == "open"
    assert iss_data[0]["resolution_days"] is None  # open issue has no resolution days

    # 6. Test Database Telemetry Endpoints
    db_status = get_database_status(db=db_session)
    assert db_status.dialect in ("sqlite", "postgresql")

    stat_data = get_database_statistics(db=db_session)
    assert stat_data.total_records >= 4

    summary_data = get_storage_summary(db=db_session)
    assert "bronze" in summary_data.tiers
    assert "silver" in summary_data.tiers

    # 7. Test GitHub Auth Status
    with patch.object(
        github_auth_manager,
        "get_status",
        return_value={
            "authenticated": False,
            "token_configured": False,
            "token_masked": None,
            "user": None,
            "scopes": [],
            "rate_limit": {"limit": 60, "remaining": 60, "reset_epoch": None, "used": 0},
        },
    ):
        gh_status = get_github_status()
        assert gh_status.authenticated is False
        assert gh_status.rate_limit.limit == 60

    # 8. Test Transformation Lineage
    lin_data = get_data_lineage()
    assert len(lin_data.nodes) > 0
    assert len(lin_data.edges) > 0
