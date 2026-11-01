import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.raw_events import Commit, PullRequest, Issue
from app.models.pipeline_run import PipelineRun
from app.schemas.analytics import OverviewMetrics, ContributorSummary, ActivityTimepoint
from app.services.base import BaseService

logger = logging.getLogger("gitpulse.services.analytics")


class AnalyticsService(BaseService):
    """
    Computes aggregates and summaries across repositories, commits, PRs, issues, and pipelines.
    """

    def get_overview_metrics(self, db: Session, repository_id: Optional[int] = None) -> OverviewMetrics:
        if not isinstance(repository_id, int):
            repository_id = None
        # Repositories
        if repository_id is not None:
            repo = db.get(Repository, repository_id)
            total_repos = 1 if repo else 0
            active_repos = 1 if (repo and repo.is_active) else 0
            
            commit_filter = Commit.repository_id == repository_id
            pr_filter = PullRequest.repository_id == repository_id
            issue_filter = Issue.repository_id == repository_id
            pipeline_filter = PipelineRun.repository_id == repository_id
        else:
            total_repos = db.scalar(select(func.count(Repository.id))) or 0
            active_repos = db.scalar(select(func.count(Repository.id)).where(Repository.is_active == True)) or 0
            commit_filter = True
            pr_filter = True
            issue_filter = True
            pipeline_filter = True

        # Commits
        total_commits = db.scalar(select(func.count(Commit.id)).where(commit_filter)) or 0

        # Pull Requests
        total_prs = db.scalar(select(func.count(PullRequest.id)).where(pr_filter)) or 0

        # Issues
        total_issues = db.scalar(select(func.count(Issue.id)).where(issue_filter)) or 0

        # Unique Contributors
        unique_authors = db.scalar(select(func.count(distinct(Commit.author_email))).where(commit_filter)) or 0

        # Pipeline stats
        total_runs = db.scalar(select(func.count(PipelineRun.id)).where(pipeline_filter)) or 0
        completed_runs = (
            db.scalar(select(func.count(PipelineRun.id)).where(pipeline_filter).where(PipelineRun.status == "completed")) or 0
        )
        success_rate = round((completed_runs / total_runs * 100), 1) if total_runs > 0 else 100.0

        return OverviewMetrics(
            total_repositories=total_repos,
            active_repositories=active_repos,
            total_commits_tracked=total_commits,
            total_pull_requests=total_prs,
            total_issues=total_issues,
            total_contributors=unique_authors,
            total_pipeline_runs=total_runs,
            pipeline_success_rate=success_rate,
        )

    def get_top_contributors(self, db: Session, repository_id: int = None, limit: int = 10) -> List[ContributorSummary]:
        stmt = (
            select(
                Commit.author_name.label("name"),
                func.count(Commit.id).label("commits"),
                func.min(Commit.author_date).label("first_commit"),
                func.max(Commit.author_date).label("last_commit"),
            )
            .where(Commit.author_name != None)
        )
        if repository_id:
            stmt = stmt.where(Commit.repository_id == repository_id)
        stmt = stmt.group_by(Commit.author_name).order_by(func.count(Commit.id).desc()).limit(limit)

        results = db.execute(stmt).all()
        contributors: List[ContributorSummary] = []
        for row in results:
            first_date = row.first_commit.strftime("%Y-%m-%d") if row.first_commit else None
            last_date = row.last_commit.strftime("%Y-%m-%d") if row.last_commit else None
            contributors.append(
                ContributorSummary(
                    login=row.name or "unknown",
                    commits_count=row.commits,
                    pull_requests_count=0,
                    first_commit_date=first_date,
                    last_commit_date=last_date,
                )
            )
        return contributors

    def get_commits(
        self,
        db: Session,
        repository_id: Optional[int] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        stmt = select(Commit)
        if repository_id:
            stmt = stmt.where(Commit.repository_id == repository_id)
        if author:
            stmt = stmt.where(
                (Commit.author_name.ilike(f"%{author}%")) | (Commit.author_email.ilike(f"%{author}%"))
            )
        if since:
            try:
                dt_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                stmt = stmt.where(Commit.author_date >= dt_since)
            except Exception:
                pass
        if until:
            try:
                dt_until = datetime.fromisoformat(until.replace("Z", "+00:00"))
                stmt = stmt.where(Commit.author_date <= dt_until)
            except Exception:
                pass
        stmt = stmt.order_by(Commit.author_date.desc()).limit(limit)
        commits = db.scalars(stmt).all()
        return [
            {
                "id": c.id,
                "repository_id": c.repository_id,
                "sha": c.sha,
                "author_name": c.author_name,
                "author_email": c.author_email,
                "author_date": c.author_date.isoformat() if c.author_date else None,
                "committer_name": c.committer_name,
                "message": c.message,
                "additions": c.additions,
                "deletions": c.deletions,
                "total_changes": c.total_changes,
                "parent_shas": c.parent_shas or [],
            }
            for c in commits
        ]

    def get_pull_requests(
        self,
        db: Session,
        repository_id: Optional[int] = None,
        state: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        stmt = select(PullRequest)
        if repository_id:
            stmt = stmt.where(PullRequest.repository_id == repository_id)
        if state:
            stmt = stmt.where(PullRequest.state == state.lower())
        if author:
            stmt = stmt.where(PullRequest.user_login.ilike(f"%{author}%"))
        if since:
            try:
                dt_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                stmt = stmt.where(PullRequest.created_at_gh >= dt_since)
            except Exception:
                pass
        stmt = stmt.order_by(PullRequest.created_at_gh.desc()).limit(limit)
        prs = db.scalars(stmt).all()
        results = []
        for pr in prs:
            merged_time_hours = None
            if pr.merged_at_gh and pr.created_at_gh:
                merged_time_hours = round(
                    (pr.merged_at_gh - pr.created_at_gh).total_seconds() / 3600.0, 2
                )
            results.append(
                {
                    "id": pr.id,
                    "repository_id": pr.repository_id,
                    "github_id": pr.github_id,
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "is_merged": pr.is_merged,
                    "user_login": pr.user_login,
                    "base_branch": pr.base_branch,
                    "head_branch": pr.head_branch,
                    "created_at": pr.created_at_gh.isoformat() if pr.created_at_gh else None,
                    "updated_at": pr.updated_at_gh.isoformat() if pr.updated_at_gh else None,
                    "closed_at": pr.closed_at_gh.isoformat() if pr.closed_at_gh else None,
                    "merged_at": pr.merged_at_gh.isoformat() if pr.merged_at_gh else None,
                    "comments_count": pr.comments_count,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "changed_files": pr.changed_files,
                    "merged_time_hours": merged_time_hours,
                }
            )
        return results

    def get_issues(
        self,
        db: Session,
        repository_id: Optional[int] = None,
        state: Optional[str] = None,
        author: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        stmt = select(Issue)
        if repository_id:
            stmt = stmt.where(Issue.repository_id == repository_id)
        if state:
            stmt = stmt.where(Issue.state == state.lower())
        if author:
            stmt = stmt.where(Issue.user_login.ilike(f"%{author}%"))
        if since:
            try:
                dt_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
                stmt = stmt.where(Issue.created_at_gh >= dt_since)
            except Exception:
                pass
        stmt = stmt.order_by(Issue.created_at_gh.desc()).limit(limit)
        issues = db.scalars(stmt).all()
        results = []
        for issue in issues:
            resolution_days = None
            if issue.closed_at_gh and issue.created_at_gh:
                resolution_days = round(
                    (issue.closed_at_gh - issue.created_at_gh).total_seconds() / 86400.0, 2
                )
            results.append(
                {
                    "id": issue.id,
                    "repository_id": issue.repository_id,
                    "github_id": issue.github_id,
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "user_login": issue.user_login,
                    "assignees": issue.assignees or [],
                    "labels": issue.labels or [],
                    "comments_count": issue.comments_count,
                    "created_at": issue.created_at_gh.isoformat() if issue.created_at_gh else None,
                    "updated_at": issue.updated_at_gh.isoformat() if issue.updated_at_gh else None,
                    "closed_at": issue.closed_at_gh.isoformat() if issue.closed_at_gh else None,
                    "resolution_days": resolution_days,
                }
            )
        return results


analytics_service = AnalyticsService()

