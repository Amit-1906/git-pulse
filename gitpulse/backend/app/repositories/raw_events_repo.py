from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.raw_events import RawEvent, Commit, PullRequest, Issue
from app.repositories.base import BaseRepository


class RawEventRepository(BaseRepository[RawEvent, Any, Any]):
    def __init__(self):
        super().__init__(RawEvent)

    def store_event(
        self,
        db: Session,
        repository_id: int,
        event_type: str,
        payload: Dict[str, Any],
        status: str = "pending",
    ) -> RawEvent:
        event = RawEvent(
            repository_id=repository_id,
            event_type=event_type,
            payload=payload,
            status=status,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def bulk_store_events(
        self,
        db: Session,
        repository_id: int,
        event_type: str,
        payloads: List[Dict[str, Any]],
        status: str = "pending",
    ) -> int:
        if not payloads:
            return 0
        events = [
            RawEvent(
                repository_id=repository_id,
                event_type=event_type,
                payload=p,
                status=status,
            )
            for p in payloads
        ]
        db.add_all(events)
        db.commit()
        return len(events)

    def get_by_repository(
        self, db: Session, repository_id: int, event_type: Optional[str] = None, limit: int = 100
    ) -> List[RawEvent]:
        stmt = select(RawEvent).where(RawEvent.repository_id == repository_id)
        if event_type:
            stmt = stmt.where(RawEvent.event_type == event_type)
        stmt = stmt.order_by(RawEvent.fetched_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())


class CommitRepository(BaseRepository[Commit, Any, Any]):
    def __init__(self):
        super().__init__(Commit)

    def get_by_sha(self, db: Session, sha: str) -> Optional[Commit]:
        stmt = select(Commit).where(Commit.sha == sha)
        return db.scalars(stmt).first()

    def get_by_repository(
        self, db: Session, repository_id: int, skip: int = 0, limit: int = 50
    ) -> List[Commit]:
        stmt = (
            select(Commit)
            .where(Commit.repository_id == repository_id)
            .order_by(Commit.author_date.desc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


class PullRequestRepository(BaseRepository[PullRequest, Any, Any]):
    def __init__(self):
        super().__init__(PullRequest)

    def get_by_github_id(self, db: Session, github_id: int) -> Optional[PullRequest]:
        stmt = select(PullRequest).where(PullRequest.github_id == github_id)
        return db.scalars(stmt).first()

    def get_by_repository(
        self, db: Session, repository_id: int, state: Optional[str] = None, skip: int = 0, limit: int = 50
    ) -> List[PullRequest]:
        stmt = select(PullRequest).where(PullRequest.repository_id == repository_id)
        if state:
            stmt = stmt.where(PullRequest.state == state)
        stmt = stmt.order_by(PullRequest.created_at_gh.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())


class IssueRepository(BaseRepository[Issue, Any, Any]):
    def __init__(self):
        super().__init__(Issue)

    def get_by_github_id(self, db: Session, github_id: int) -> Optional[Issue]:
        stmt = select(Issue).where(Issue.github_id == github_id)
        return db.scalars(stmt).first()

    def get_by_repository(
        self, db: Session, repository_id: int, state: Optional[str] = None, skip: int = 0, limit: int = 50
    ) -> List[Issue]:
        stmt = select(Issue).where(Issue.repository_id == repository_id)
        if state:
            stmt = stmt.where(Issue.state == state)
        stmt = stmt.order_by(Issue.created_at_gh.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())


raw_event_repo = RawEventRepository()
commit_repo = CommitRepository()
pull_request_repo = PullRequestRepository()
issue_repo = IssueRepository()

