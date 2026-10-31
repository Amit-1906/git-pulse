from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.analytics import OverviewMetrics, ContributorSummary
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=OverviewMetrics, summary="Get global analytics overview")
def get_overview(db: Session = Depends(get_db)):
    """Computes high-level platform KPI metrics across all connected repositories."""
    return analytics_service.get_overview_metrics(db)


@router.get("/contributors", response_model=List[ContributorSummary], summary="Get top contributors")
def get_contributors(
    repository_id: Optional[int] = Query(None, description="Filter by repository ID"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Computes top contributors sorted by commit volume."""
    return analytics_service.get_top_contributors(db, repository_id=repository_id, limit=limit)


def _clean_int(val: Any, default: int = 200) -> int:
    if isinstance(val, int):
        return val
    if hasattr(val, "default") and isinstance(val.default, int):
        return val.default
    try:
        return int(val)
    except Exception:
        return default


@router.get("/commits", summary="List and filter commits")
def get_commits(
    repository_id: Optional[int] = Query(None, description="Filter by repository ID"),
    author: Optional[str] = Query(None, description="Filter by author name/email"),
    since: Optional[str] = Query(None, description="ISO timestamp since filter"),
    until: Optional[str] = Query(None, description="ISO timestamp until filter"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieves commits matching optional repository, author, and date filters."""
    lim = _clean_int(limit, 200)
    repo_id = repository_id if isinstance(repository_id, int) else None
    auth = author if isinstance(author, str) else None
    s = since if isinstance(since, str) else None
    u = until if isinstance(until, str) else None
    return analytics_service.get_commits(
        db, repository_id=repo_id, author=auth, since=s, until=u, limit=lim
    )


@router.get("/pull-requests", summary="List and filter pull requests")
def get_pull_requests(
    repository_id: Optional[int] = Query(None, description="Filter by repository ID"),
    state: Optional[str] = Query(None, description="Filter by state (open, closed)"),
    author: Optional[str] = Query(None, description="Filter by author login"),
    since: Optional[str] = Query(None, description="ISO timestamp since filter"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieves pull requests matching optional filters."""
    lim = _clean_int(limit, 200)
    repo_id = repository_id if isinstance(repository_id, int) else None
    st = state if isinstance(state, str) else None
    auth = author if isinstance(author, str) else None
    s = since if isinstance(since, str) else None
    return analytics_service.get_pull_requests(
        db, repository_id=repo_id, state=st, author=auth, since=s, limit=lim
    )


@router.get("/issues", summary="List and filter issues")
def get_issues(
    repository_id: Optional[int] = Query(None, description="Filter by repository ID"),
    state: Optional[str] = Query(None, description="Filter by state (open, closed)"),
    author: Optional[str] = Query(None, description="Filter by author login"),
    since: Optional[str] = Query(None, description="ISO timestamp since filter"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Retrieves issues matching optional filters."""
    lim = _clean_int(limit, 200)
    repo_id = repository_id if isinstance(repository_id, int) else None
    st = state if isinstance(state, str) else None
    auth = author if isinstance(author, str) else None
    s = since if isinstance(since, str) else None
    return analytics_service.get_issues(
        db, repository_id=repo_id, state=st, author=auth, since=s, limit=lim
    )

