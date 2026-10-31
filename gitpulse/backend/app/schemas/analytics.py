from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class MetricDelta(BaseModel):
    value: int
    delta: Optional[float] = None
    delta_percentage: Optional[float] = None


class OverviewMetrics(BaseModel):
    total_repositories: int = 0
    active_repositories: int = 0
    total_commits_tracked: int = 0
    total_pull_requests: int = 0
    total_issues: int = 0
    total_contributors: int = 0
    total_pipeline_runs: int = 0
    pipeline_success_rate: float = 0.0


class ContributorSummary(BaseModel):
    login: str
    avatar_url: Optional[str] = None
    commits_count: int
    pull_requests_count: int
    first_commit_date: Optional[str] = None
    last_commit_date: Optional[str] = None


class ActivityTimepoint(BaseModel):
    date: str
    commits: int = 0
    pull_requests: int = 0
    issues: int = 0

