"""
Raw-data repository access layer.

Provides idempotent upsert, batch insertion, and query helpers for the four
Bronze raw tables: raw_repositories, raw_commits, raw_issues, raw_pull_requests.

All write operations use INSERT … ON CONFLICT DO UPDATE (dialect-adaptive)
so they are safe to run repeatedly without creating duplicates.

Design decisions:
  - SQLite (test environment) does not support ON CONFLICT on multi-column
    constraints natively via SQLAlchemy Core, so we fall back to a
    SELECT → INSERT-or-UPDATE pattern that is wrapped in a transaction.
  - PostgreSQL uses native JSONB + GIN indexes; SQLite uses JSON without GIN.
  - Batch insertions are collected in memory and flushed in a single
    transaction to minimise round-trips.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.raw_repositories import RawRepository
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest
from app.repositories.base import BaseRepository

logger = logging.getLogger("gitpulse.repositories.raw_storage")

# ─────────────────────────────────────────────────────────────────────────── #
# Internal helpers                                                              #
# ─────────────────────────────────────────────────────────────────────────── #

def _is_postgres(db: Session) -> bool:
    """Return True when the underlying dialect is PostgreSQL."""
    return db.bind.dialect.name == "postgresql"  # type: ignore[union-attr]


def _upsert_raw_postgres(
    db: Session,
    model,
    conflict_columns: List[str],
    values: Dict[str, Any],
    update_columns: List[str],
    commit: bool = True,
) -> Any:
    """
    PostgreSQL-native INSERT … ON CONFLICT DO UPDATE.
    Returns the inserted/updated ORM object.
    """
    stmt = pg_insert(model.__table__).values(**values)
    update_dict = {col: stmt.excluded[col] for col in update_columns}
    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_=update_dict,
    ).returning(model.__table__)
    result = db.execute(stmt)
    if commit:
        db.commit()
    else:
        db.flush()
    row = result.fetchone()
    if row is None:
        return None
    return db.get(model, row[0])


def _upsert_raw_sqlite(
    db: Session,
    model,
    lookup_filter,
    values: Dict[str, Any],
    update_columns: List[str],
    commit: bool = True,
) -> Any:
    """
    SQLite-compatible upsert: SELECT then INSERT-or-UPDATE in one transaction.
    Used exclusively in the test environment.
    """
    obj = db.scalars(select(model).where(*lookup_filter)).first()
    if obj is None:
        # Strip columns that are not settable on INSERT (e.g. id)
        obj = model(**{k: v for k, v in values.items() if k != "id"})
        db.add(obj)
    else:
        for col in update_columns:
            if col in values:
                setattr(obj, col, values[col])
    if commit:
        db.commit()
        db.refresh(obj)
    else:
        db.flush()
    return obj


# ═══════════════════════════════════════════════════════════════════════════ #
#  RawRepositoryRepository                                                    #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawRepositoryRepository(BaseRepository[RawRepository, Any, Any]):
    """
    Storage access for raw_repositories (Bronze layer).

    Upsert key: github_repo_id (globally unique, stable across renames).
    """

    def __init__(self):
        super().__init__(RawRepository)

    # ── Primary upsert ────────────────────────────────────────────────────
    def upsert(
        self,
        db: Session,
        *,
        github_repo_id: int,
        full_name: str,
        raw_payload: Dict[str, Any],
        source_endpoint: str = "/repos/{owner}/{repo}",
        extracted_at: Optional[datetime] = None,
        source_updated_at: Optional[datetime] = None,
        repository_id: Optional[int] = None,
        commit: bool = True,
    ) -> RawRepository:
        """
        Insert a new raw repository record or update the existing one when
        github_repo_id already exists.  Always recalculates payload_hash.
        """
        ts = extracted_at or datetime.utcnow()
        payload_hash = RawRepository.compute_hash(raw_payload)

        values = {
            "github_repo_id": github_repo_id,
            "full_name": full_name,
            "raw_payload": raw_payload,
            "source_endpoint": source_endpoint,
            "extracted_at": ts,
            "source_updated_at": source_updated_at,
            "payload_hash": payload_hash,
            "repository_id": repository_id,
        }
        update_cols = [
            "full_name",
            "raw_payload",
            "source_endpoint",
            "extracted_at",
            "source_updated_at",
            "payload_hash",
            "repository_id",
        ]

        if _is_postgres(db):
            return _upsert_raw_postgres(
                db, RawRepository, ["github_repo_id"], values, update_cols, commit=commit
            )
        return _upsert_raw_sqlite(
            db,
            RawRepository,
            [RawRepository.github_repo_id == github_repo_id],
            values,
            update_cols,
            commit=commit,
        )

    # ── Queries ───────────────────────────────────────────────────────────
    def get_by_github_id(
        self, db: Session, github_repo_id: int
    ) -> Optional[RawRepository]:
        return db.scalars(
            select(RawRepository).where(
                RawRepository.github_repo_id == github_repo_id
            )
        ).first()

    def get_recent(self, db: Session, limit: int = 50) -> List[RawRepository]:
        return list(
            db.scalars(
                select(RawRepository)
                .order_by(RawRepository.extracted_at.desc())
                .limit(limit)
            ).all()
        )

    def count_by_repository(self, db: Session, repository_id: int) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(RawRepository).where(
                    RawRepository.repository_id == repository_id
                )
            )
            or 0
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  RawCommitRepository                                                        #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawCommitRepository(BaseRepository[RawCommit, Any, Any]):
    """
    Storage access for raw_commits (Bronze layer).

    Upsert key: (repository_id, commit_sha).
    Batch insertion is the preferred write path for performance.
    """

    def __init__(self):
        super().__init__(RawCommit)

    def upsert(
        self,
        db: Session,
        *,
        repository_id: int,
        commit_sha: str,
        raw_payload: Dict[str, Any],
        source_endpoint: str = "/repos/{owner}/{repo}/commits",
        extracted_at: Optional[datetime] = None,
        source_updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> RawCommit:
        """Single-record idempotent upsert by (repository_id, commit_sha)."""
        ts = extracted_at or datetime.utcnow()
        payload_hash = RawCommit.compute_hash(raw_payload)

        values = {
            "repository_id": repository_id,
            "commit_sha": commit_sha,
            "raw_payload": raw_payload,
            "source_endpoint": source_endpoint,
            "extracted_at": ts,
            "source_updated_at": source_updated_at,
            "payload_hash": payload_hash,
        }
        update_cols = ["raw_payload", "source_endpoint", "extracted_at", "source_updated_at", "payload_hash"]

        if _is_postgres(db):
            return _upsert_raw_postgres(
                db,
                RawCommit,
                ["repository_id", "commit_sha"],
                values,
                update_cols,
                commit=commit,
            )
        return _upsert_raw_sqlite(
            db,
            RawCommit,
            [
                RawCommit.repository_id == repository_id,
                RawCommit.commit_sha == commit_sha,
            ],
            values,
            update_cols,
            commit=commit,
        )

    def bulk_upsert(
        self,
        db: Session,
        *,
        repository_id: int,
        records: List[Dict[str, Any]],
        source_endpoint: str = "/repos/{owner}/{repo}/commits",
        extracted_at: Optional[datetime] = None,
    ) -> Tuple[int, int]:
        """
        Batch upsert a list of commit records.

        Each record dict must contain:
          - commit_sha  (str)
          - raw_payload (dict)
          - source_updated_at (datetime | None)  — optional

        Returns (inserted_count, updated_count).
        """
        if not records:
            return 0, 0

        ts = extracted_at or datetime.utcnow()
        inserted = 0
        updated = 0

        if _is_postgres(db):
            rows = [
                {
                    "repository_id": repository_id,
                    "commit_sha": r["commit_sha"],
                    "raw_payload": r["raw_payload"],
                    "source_endpoint": source_endpoint,
                    "extracted_at": ts,
                    "source_updated_at": r.get("source_updated_at"),
                    "payload_hash": RawCommit.compute_hash(r["raw_payload"]),
                }
                for r in records
            ]
            stmt = pg_insert(RawCommit.__table__).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["repository_id", "commit_sha"],
                set_={
                    "raw_payload": stmt.excluded.raw_payload,
                    "extracted_at": stmt.excluded.extracted_at,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "payload_hash": stmt.excluded.payload_hash,
                },
            )
            result = db.execute(stmt)
            db.commit()
            # rowcount reflects upserted rows; split unavailable without RETURNING
            inserted = result.rowcount
        else:
            # SQLite: iterate and upsert one by one (test environment only)
            for r in records:
                existing = db.scalars(
                    select(RawCommit).where(
                        RawCommit.repository_id == repository_id,
                        RawCommit.commit_sha == r["commit_sha"],
                    )
                ).first()
                if existing is None:
                    obj = RawCommit(
                        repository_id=repository_id,
                        commit_sha=r["commit_sha"],
                        raw_payload=r["raw_payload"],
                        source_endpoint=source_endpoint,
                        extracted_at=ts,
                        source_updated_at=r.get("source_updated_at"),
                        payload_hash=RawCommit.compute_hash(r["raw_payload"]),
                    )
                    db.add(obj)
                    inserted += 1
                else:
                    existing.raw_payload = r["raw_payload"]
                    existing.extracted_at = ts
                    existing.source_updated_at = r.get("source_updated_at")
                    existing.payload_hash = RawCommit.compute_hash(r["raw_payload"])
                    updated += 1
            db.commit()

        logger.debug(
            "bulk_upsert raw_commits repo=%s: inserted=%d updated=%d",
            repository_id,
            inserted,
            updated,
        )
        return inserted, updated

    # ── Queries ───────────────────────────────────────────────────────────
    def get_by_sha(
        self, db: Session, repository_id: int, commit_sha: str
    ) -> Optional[RawCommit]:
        return db.scalars(
            select(RawCommit).where(
                RawCommit.repository_id == repository_id,
                RawCommit.commit_sha == commit_sha,
            )
        ).first()

    def get_by_repository(
        self,
        db: Session,
        repository_id: int,
        since: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[RawCommit]:
        stmt = select(RawCommit).where(RawCommit.repository_id == repository_id)
        if since:
            stmt = stmt.where(RawCommit.source_updated_at >= since)
        stmt = stmt.order_by(RawCommit.source_updated_at.desc().nullslast()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def count_by_repository(self, db: Session, repository_id: int) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(RawCommit).where(
                    RawCommit.repository_id == repository_id
                )
            )
            or 0
        )

    def get_latest_extracted_at(
        self, db: Session, repository_id: int
    ) -> Optional[datetime]:
        return db.scalar(
            select(func.max(RawCommit.extracted_at)).where(
                RawCommit.repository_id == repository_id
            )
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  RawIssueRepository                                                         #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawIssueRepository(BaseRepository[RawIssue, Any, Any]):
    """
    Storage access for raw_issues (Bronze layer).
    Upsert key: (repository_id, github_issue_id).
    """

    def __init__(self):
        super().__init__(RawIssue)

    def upsert(
        self,
        db: Session,
        *,
        repository_id: int,
        github_issue_id: int,
        issue_number: int,
        raw_payload: Dict[str, Any],
        source_endpoint: str = "/repos/{owner}/{repo}/issues",
        extracted_at: Optional[datetime] = None,
        source_updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> RawIssue:
        ts = extracted_at or datetime.utcnow()
        payload_hash = RawIssue.compute_hash(raw_payload)

        values = {
            "repository_id": repository_id,
            "github_issue_id": github_issue_id,
            "issue_number": issue_number,
            "raw_payload": raw_payload,
            "source_endpoint": source_endpoint,
            "extracted_at": ts,
            "source_updated_at": source_updated_at,
            "payload_hash": payload_hash,
        }
        update_cols = [
            "issue_number",
            "raw_payload",
            "source_endpoint",
            "extracted_at",
            "source_updated_at",
            "payload_hash",
        ]

        if _is_postgres(db):
            return _upsert_raw_postgres(
                db,
                RawIssue,
                ["repository_id", "github_issue_id"],
                values,
                update_cols,
                commit=commit,
            )
        return _upsert_raw_sqlite(
            db,
            RawIssue,
            [
                RawIssue.repository_id == repository_id,
                RawIssue.github_issue_id == github_issue_id,
            ],
            values,
            update_cols,
            commit=commit,
        )

    def bulk_upsert(
        self,
        db: Session,
        *,
        repository_id: int,
        records: List[Dict[str, Any]],
        source_endpoint: str = "/repos/{owner}/{repo}/issues",
        extracted_at: Optional[datetime] = None,
    ) -> Tuple[int, int]:
        """
        Each record dict must contain:
          - github_issue_id (int)
          - issue_number    (int)
          - raw_payload     (dict)
          - source_updated_at (datetime | None)
        """
        if not records:
            return 0, 0

        ts = extracted_at or datetime.utcnow()
        inserted = 0
        updated = 0

        if _is_postgres(db):
            rows = [
                {
                    "repository_id": repository_id,
                    "github_issue_id": r["github_issue_id"],
                    "issue_number": r["issue_number"],
                    "raw_payload": r["raw_payload"],
                    "source_endpoint": source_endpoint,
                    "extracted_at": ts,
                    "source_updated_at": r.get("source_updated_at"),
                    "payload_hash": RawIssue.compute_hash(r["raw_payload"]),
                }
                for r in records
            ]
            stmt = pg_insert(RawIssue.__table__).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["repository_id", "github_issue_id"],
                set_={
                    "issue_number": stmt.excluded.issue_number,
                    "raw_payload": stmt.excluded.raw_payload,
                    "extracted_at": stmt.excluded.extracted_at,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "payload_hash": stmt.excluded.payload_hash,
                },
            )
            result = db.execute(stmt)
            db.commit()
            inserted = result.rowcount
        else:
            for r in records:
                existing = db.scalars(
                    select(RawIssue).where(
                        RawIssue.repository_id == repository_id,
                        RawIssue.github_issue_id == r["github_issue_id"],
                    )
                ).first()
                if existing is None:
                    db.add(
                        RawIssue(
                            repository_id=repository_id,
                            github_issue_id=r["github_issue_id"],
                            issue_number=r["issue_number"],
                            raw_payload=r["raw_payload"],
                            source_endpoint=source_endpoint,
                            extracted_at=ts,
                            source_updated_at=r.get("source_updated_at"),
                            payload_hash=RawIssue.compute_hash(r["raw_payload"]),
                        )
                    )
                    inserted += 1
                else:
                    existing.raw_payload = r["raw_payload"]
                    existing.extracted_at = ts
                    existing.source_updated_at = r.get("source_updated_at")
                    existing.payload_hash = RawIssue.compute_hash(r["raw_payload"])
                    updated += 1
            db.commit()

        return inserted, updated

    # ── Queries ───────────────────────────────────────────────────────────
    def get_by_github_id(
        self, db: Session, repository_id: int, github_issue_id: int
    ) -> Optional[RawIssue]:
        return db.scalars(
            select(RawIssue).where(
                RawIssue.repository_id == repository_id,
                RawIssue.github_issue_id == github_issue_id,
            )
        ).first()

    def get_by_repository(
        self,
        db: Session,
        repository_id: int,
        since: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[RawIssue]:
        stmt = select(RawIssue).where(RawIssue.repository_id == repository_id)
        if since:
            stmt = stmt.where(RawIssue.source_updated_at >= since)
        stmt = stmt.order_by(RawIssue.source_updated_at.desc().nullslast()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def count_by_repository(self, db: Session, repository_id: int) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(RawIssue).where(
                    RawIssue.repository_id == repository_id
                )
            )
            or 0
        )


# ═══════════════════════════════════════════════════════════════════════════ #
#  RawPullRequestRepository                                                   #
# ═══════════════════════════════════════════════════════════════════════════ #


class RawPullRequestRepository(BaseRepository[RawPullRequest, Any, Any]):
    """
    Storage access for raw_pull_requests (Bronze layer).
    Upsert key: (repository_id, github_pr_id).
    """

    def __init__(self):
        super().__init__(RawPullRequest)

    def upsert(
        self,
        db: Session,
        *,
        repository_id: int,
        github_pr_id: int,
        pr_number: int,
        raw_payload: Dict[str, Any],
        source_endpoint: str = "/repos/{owner}/{repo}/pulls",
        extracted_at: Optional[datetime] = None,
        source_updated_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> RawPullRequest:
        ts = extracted_at or datetime.utcnow()
        payload_hash = RawPullRequest.compute_hash(raw_payload)

        values = {
            "repository_id": repository_id,
            "github_pr_id": github_pr_id,
            "pr_number": pr_number,
            "raw_payload": raw_payload,
            "source_endpoint": source_endpoint,
            "extracted_at": ts,
            "source_updated_at": source_updated_at,
            "payload_hash": payload_hash,
        }
        update_cols = [
            "pr_number",
            "raw_payload",
            "source_endpoint",
            "extracted_at",
            "source_updated_at",
            "payload_hash",
        ]

        if _is_postgres(db):
            return _upsert_raw_postgres(
                db,
                RawPullRequest,
                ["repository_id", "github_pr_id"],
                values,
                update_cols,
                commit=commit,
            )
        return _upsert_raw_sqlite(
            db,
            RawPullRequest,
            [
                RawPullRequest.repository_id == repository_id,
                RawPullRequest.github_pr_id == github_pr_id,
            ],
            values,
            update_cols,
            commit=commit,
        )

    def bulk_upsert(
        self,
        db: Session,
        *,
        repository_id: int,
        records: List[Dict[str, Any]],
        source_endpoint: str = "/repos/{owner}/{repo}/pulls",
        extracted_at: Optional[datetime] = None,
    ) -> Tuple[int, int]:
        """
        Each record dict must contain:
          - github_pr_id      (int)
          - pr_number         (int)
          - raw_payload       (dict)
          - source_updated_at (datetime | None)
        """
        if not records:
            return 0, 0

        ts = extracted_at or datetime.utcnow()
        inserted = 0
        updated = 0

        if _is_postgres(db):
            rows = [
                {
                    "repository_id": repository_id,
                    "github_pr_id": r["github_pr_id"],
                    "pr_number": r["pr_number"],
                    "raw_payload": r["raw_payload"],
                    "source_endpoint": source_endpoint,
                    "extracted_at": ts,
                    "source_updated_at": r.get("source_updated_at"),
                    "payload_hash": RawPullRequest.compute_hash(r["raw_payload"]),
                }
                for r in records
            ]
            stmt = pg_insert(RawPullRequest.__table__).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["repository_id", "github_pr_id"],
                set_={
                    "pr_number": stmt.excluded.pr_number,
                    "raw_payload": stmt.excluded.raw_payload,
                    "extracted_at": stmt.excluded.extracted_at,
                    "source_updated_at": stmt.excluded.source_updated_at,
                    "payload_hash": stmt.excluded.payload_hash,
                },
            )
            result = db.execute(stmt)
            db.commit()
            inserted = result.rowcount
        else:
            for r in records:
                existing = db.scalars(
                    select(RawPullRequest).where(
                        RawPullRequest.repository_id == repository_id,
                        RawPullRequest.github_pr_id == r["github_pr_id"],
                    )
                ).first()
                if existing is None:
                    db.add(
                        RawPullRequest(
                            repository_id=repository_id,
                            github_pr_id=r["github_pr_id"],
                            pr_number=r["pr_number"],
                            raw_payload=r["raw_payload"],
                            source_endpoint=source_endpoint,
                            extracted_at=ts,
                            source_updated_at=r.get("source_updated_at"),
                            payload_hash=RawPullRequest.compute_hash(r["raw_payload"]),
                        )
                    )
                    inserted += 1
                else:
                    existing.raw_payload = r["raw_payload"]
                    existing.extracted_at = ts
                    existing.source_updated_at = r.get("source_updated_at")
                    existing.payload_hash = RawPullRequest.compute_hash(r["raw_payload"])
                    updated += 1
            db.commit()

        return inserted, updated

    # ── Queries ───────────────────────────────────────────────────────────
    def get_by_github_id(
        self, db: Session, repository_id: int, github_pr_id: int
    ) -> Optional[RawPullRequest]:
        return db.scalars(
            select(RawPullRequest).where(
                RawPullRequest.repository_id == repository_id,
                RawPullRequest.github_pr_id == github_pr_id,
            )
        ).first()

    def get_by_repository(
        self,
        db: Session,
        repository_id: int,
        since: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[RawPullRequest]:
        stmt = select(RawPullRequest).where(RawPullRequest.repository_id == repository_id)
        if since:
            stmt = stmt.where(RawPullRequest.source_updated_at >= since)
        stmt = stmt.order_by(RawPullRequest.source_updated_at.desc().nullslast()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def count_by_repository(self, db: Session, repository_id: int) -> int:
        return (
            db.scalar(
                select(func.count()).select_from(RawPullRequest).where(
                    RawPullRequest.repository_id == repository_id
                )
            )
            or 0
        )


# ── Singletons ────────────────────────────────────────────────────────────── #
raw_repository_repo = RawRepositoryRepository()
raw_commit_repo = RawCommitRepository()
raw_issue_repo = RawIssueRepository()
raw_pull_request_repo = RawPullRequestRepository()

