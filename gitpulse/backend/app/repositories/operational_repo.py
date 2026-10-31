"""
Extraction Logs and Data Quality repository access layer.

ExtractionLogRepository  — append-only write + queryable read for job logs.
DataQualityRepository    — upsert / append quality check results.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models.operational import ExtractionLog, DataQualityResult
from app.repositories.base import BaseRepository

logger = logging.getLogger("gitpulse.repositories.operational")


class ExtractionLogRepository(BaseRepository[ExtractionLog, Any, Any]):
    """
    Append-only store for per-job extraction log entries.
    """

    def __init__(self):
        super().__init__(ExtractionLog)

    def append(
        self,
        db: Session,
        *,
        job_id: str,
        repository_full_name: str,
        message: str,
        level: str = "INFO",
        resource_type: Optional[str] = None,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        records_processed: Optional[int] = None,
        duration_ms: Optional[float] = None,
        repository_id: Optional[int] = None,
    ) -> ExtractionLog:
        """Append a single log entry. Always commits immediately."""
        entry = ExtractionLog(
            job_id=job_id,
            repository_full_name=repository_full_name,
            message=message,
            level=level.upper(),
            resource_type=resource_type,
            stage=stage,
            details=details,
            records_processed=records_processed,
            duration_ms=duration_ms,
            repository_id=repository_id,
            logged_at=datetime.utcnow(),
        )
        db.add(entry)
        db.commit()
        return entry

    def bulk_append(
        self,
        db: Session,
        entries: List[Dict[str, Any]],
    ) -> int:
        """Bulk insert multiple log entries in a single transaction."""
        if not entries:
            return 0
        objs = [ExtractionLog(**e) for e in entries]
        db.add_all(objs)
        db.commit()
        return len(objs)

    def get_by_job(
        self,
        db: Session,
        job_id: str,
        level: Optional[str] = None,
        limit: int = 200,
    ) -> List[ExtractionLog]:
        stmt = select(ExtractionLog).where(ExtractionLog.job_id == job_id)
        if level:
            stmt = stmt.where(ExtractionLog.level == level.upper())
        stmt = stmt.order_by(ExtractionLog.logged_at.asc()).limit(limit)
        return list(db.scalars(stmt).all())

    def get_errors_for_job(self, db: Session, job_id: str) -> List[ExtractionLog]:
        return self.get_by_job(db, job_id, level="ERROR")

    def get_by_repository(
        self,
        db: Session,
        repository_id: int,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ExtractionLog]:
        stmt = select(ExtractionLog).where(ExtractionLog.repository_id == repository_id)
        if since:
            stmt = stmt.where(ExtractionLog.logged_at >= since)
        stmt = stmt.order_by(ExtractionLog.logged_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def count_by_level(self, db: Session, job_id: str) -> Dict[str, int]:
        """Return {level: count} for a given job."""
        rows = db.execute(
            select(ExtractionLog.level, func.count().label("cnt"))
            .where(ExtractionLog.job_id == job_id)
            .group_by(ExtractionLog.level)
        ).all()
        return {r[0]: r[1] for r in rows}


class DataQualityRepository(BaseRepository[DataQualityResult, Any, Any]):
    """
    Store data quality rule evaluation results.
    """

    def __init__(self):
        super().__init__(DataQualityResult)

    def record_result(
        self,
        db: Session,
        *,
        rule_name: str,
        passed: bool,
        resource_type: Optional[str] = None,
        column_name: Optional[str] = None,
        repository_id: Optional[int] = None,
        repository_full_name: Optional[str] = None,
        job_id: Optional[str] = None,
        source: str = "pipeline",
        severity: str = "warn",
        failure_count: int = 0,
        total_count: Optional[int] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> DataQualityResult:
        """Insert a new quality result row."""
        failure_rate = (
            round(failure_count / total_count, 4)
            if total_count and total_count > 0
            else None
        )
        result = DataQualityResult(
            rule_name=rule_name,
            passed=passed,
            resource_type=resource_type,
            column_name=column_name,
            repository_id=repository_id,
            repository_full_name=repository_full_name,
            job_id=job_id,
            source=source,
            severity=severity.lower(),
            failure_count=failure_count,
            total_count=total_count,
            failure_rate=failure_rate,
            message=message,
            details=details,
            evaluated_at=datetime.utcnow(),
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    def get_latest_for_resource(
        self,
        db: Session,
        resource_type: str,
        repository_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[DataQualityResult]:
        stmt = select(DataQualityResult).where(
            DataQualityResult.resource_type == resource_type
        )
        if repository_id is not None:
            stmt = stmt.where(DataQualityResult.repository_id == repository_id)
        stmt = stmt.order_by(DataQualityResult.evaluated_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def get_failures(
        self,
        db: Session,
        repository_id: Optional[int] = None,
        severity: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[DataQualityResult]:
        stmt = select(DataQualityResult).where(DataQualityResult.passed == False)
        if repository_id is not None:
            stmt = stmt.where(DataQualityResult.repository_id == repository_id)
        if severity:
            stmt = stmt.where(DataQualityResult.severity == severity.lower())
        if since:
            stmt = stmt.where(DataQualityResult.evaluated_at >= since)
        stmt = stmt.order_by(DataQualityResult.evaluated_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def get_summary(
        self, db: Session, repository_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return aggregate quality statistics."""
        base_filter = []
        if repository_id is not None:
            base_filter.append(DataQualityResult.repository_id == repository_id)

        total = db.scalar(
            select(func.count())
            .select_from(DataQualityResult)
            .where(*base_filter)
        ) or 0

        passed = db.scalar(
            select(func.count())
            .select_from(DataQualityResult)
            .where(*base_filter, DataQualityResult.passed == True)
        ) or 0

        failed = total - passed
        pass_rate = round(passed / total * 100, 1) if total else None

        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate_pct": pass_rate,
        }

    def count_by_resource(self, db: Session) -> Dict[str, int]:
        rows = db.execute(
            select(
                DataQualityResult.resource_type,
                func.count().label("cnt"),
            ).group_by(DataQualityResult.resource_type)
        ).all()
        return {r[0] or "unknown": r[1] for r in rows}


# ── Singletons ────────────────────────────────────────────────────────────── #
extraction_log_repo = ExtractionLogRepository()
data_quality_repo = DataQualityRepository()

