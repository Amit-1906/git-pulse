"""
Database Telemetry, Statistics & Storage Exploration Endpoints.

Provides deep introspection into:
- Connection pool health and latency.
- Bronze, Silver, and Operational tier storage statistics.
- Table metadata, columns, and indexes.
- Ingestion telemetry and JSONB payload counts.
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, check_db_health, get_db
from app.models.checkpoint import ExtractionCheckpoint
from app.models.extraction_job import ExtractionJob
from app.models.operational import DataQualityResult, ExtractionLog
from app.models.pipeline_run import PipelineRun
from app.models.raw_data import RawCommit, RawIssue, RawPullRequest
from app.models.raw_events import Commit, Issue, PullRequest, RawEvent
from app.models.raw_repositories import RawRepository
from app.models.repository import Repository
from app.schemas.database import (
    ColumnInfo,
    DatabasePoolStatus,
    DatabaseStatisticsResponse,
    DatabaseStatusResponse,
    DatabaseTablesResponse,
    StorageSummaryResponse,
    TableDetail,
    TableStatistics,
    TierSummary,
)

router = APIRouter(prefix="/database", tags=["Database & Storage"])

# Tier categorization mapping
TABLE_TIERS = {
    "raw_repositories": "bronze",
    "raw_commits": "bronze",
    "raw_issues": "bronze",
    "raw_pull_requests": "bronze",
    "raw_events": "bronze",
    "repositories": "silver",
    "commits": "silver",
    "issues": "silver",
    "pull_requests": "silver",
    "extraction_jobs": "operational",
    "extraction_checkpoints": "operational",
    "extraction_logs": "operational",
    "data_quality_results": "operational",
    "pipeline_runs": "operational",
}

MODEL_MAP = {
    "raw_repositories": RawRepository,
    "raw_commits": RawCommit,
    "raw_issues": RawIssue,
    "raw_pull_requests": RawPullRequest,
    "raw_events": RawEvent,
    "repositories": Repository,
    "commits": Commit,
    "issues": Issue,
    "pull_requests": PullRequest,
    "extraction_jobs": ExtractionJob,
    "extraction_checkpoints": ExtractionCheckpoint,
    "extraction_logs": ExtractionLog,
    "data_quality_results": DataQualityResult,
    "pipeline_runs": PipelineRun,
}


@router.get("/status", response_model=DatabaseStatusResponse, summary="Database connection and connection pool status")
def get_database_status(db: Session = Depends(get_db)):
    """
    Returns live connectivity status, latency, database dialect, and connection pool metrics.
    """
    bind = db.get_bind()
    health = check_db_health(bind)
    settings = get_settings()

    dialect_name = bind.dialect.name if hasattr(bind, "dialect") else "unknown"

    # Pool metrics (QueuePool on PostgreSQL)
    pool_stats = None
    pool = getattr(bind, "pool", None)
    if pool is not None:
        try:
            pool_stats = DatabasePoolStatus(
                pool_size=getattr(pool, "size", lambda: 0)() if callable(getattr(pool, "size", None)) else getattr(pool, "_pool", [None]) and len(pool._pool) or 0,
                checked_in=getattr(pool, "checkedin", lambda: 0)() if callable(getattr(pool, "checkedin", None)) else 0,
                checked_out=getattr(pool, "checkedout", lambda: 0)() if callable(getattr(pool, "checkedout", None)) else 0,
                overflow=getattr(pool, "overflow", lambda: 0)() if callable(getattr(pool, "overflow", None)) else 0,
            )
        except Exception:
            pool_stats = DatabasePoolStatus(
                pool_size=settings.DB_POOL_SIZE,
                checked_in=0,
                checked_out=0,
                overflow=0,
            )

    engine_obj = getattr(bind, "engine", bind)
    url_obj = getattr(engine_obj, "url", None) or getattr(bind, "url", None)
    server_host = (getattr(url_obj, "host", None) if url_obj else None) or settings.POSTGRES_SERVER
    server_port = (getattr(url_obj, "port", None) if url_obj else None) or settings.POSTGRES_PORT
    db_name = (getattr(url_obj, "database", None) if url_obj else None) or settings.POSTGRES_DB

    return DatabaseStatusResponse(
        status=health.get("status", "unknown"),
        connected=health.get("connected", False),
        dialect=dialect_name,
        database_name=str(db_name),
        server_host=server_host,
        server_port=server_port,
        latency_ms=health.get("latency_ms", 0.0),
        pool=pool_stats,
        checked_at=datetime.utcnow(),
    )


@router.get("/statistics", response_model=DatabaseStatisticsResponse, summary="Row counts and storage statistics across all tiers")
def get_database_statistics(db: Session = Depends(get_db)):
    """
    Returns exact record counts categorized into Bronze (raw API responses),
    Silver (modeled analytics entities), and Operational telemetry.
    """
    tables_stats: List[TableStatistics] = []
    bronze_total = 0
    silver_total = 0
    operational_total = 0

    for tbl_name, model in MODEL_MAP.items():
        try:
            cnt = db.scalar(select(func.count()).select_from(model)) or 0
        except Exception:
            cnt = 0

        tier = TABLE_TIERS.get(tbl_name, "operational")
        if tier == "bronze":
            bronze_total += cnt
        elif tier == "silver":
            silver_total += cnt
        else:
            operational_total += cnt

        # Find latest record timestamp if model has extracted_at or created_at
        last_dt = None
        for col_name in ("extracted_at", "updated_at", "created_at", "started_at", "logged_at", "evaluated_at"):
            if hasattr(model, col_name):
                try:
                    last_dt = db.scalar(select(func.max(getattr(model, col_name))))
                    if last_dt:
                        break
                except Exception:
                    pass

        tables_stats.append(
            TableStatistics(
                table_name=tbl_name,
                row_count=cnt,
                tier=tier,
                last_updated=last_dt,
            )
        )

    return DatabaseStatisticsResponse(
        total_tables=len(tables_stats),
        total_records=bronze_total + silver_total + operational_total,
        bronze_records=bronze_total,
        silver_records=silver_total,
        operational_records=operational_total,
        tables=tables_stats,
        generated_at=datetime.utcnow(),
    )


@router.get("/tables", response_model=DatabaseTablesResponse, summary="Schema details, columns, indexes for all managed tables")
def get_database_tables(db: Session = Depends(get_db)):
    """
    Introspects the database metadata and returns structural schema definitions,
    including columns, types, nullability, primary keys, and indexes.
    """
    bind = db.get_bind()
    insp = inspect(bind)
    table_names = insp.get_table_names()

    results: List[TableDetail] = []
    for tbl in sorted(table_names):
        tier = TABLE_TIERS.get(tbl, "other")
        cols_info: List[ColumnInfo] = []
        try:
            columns = insp.get_columns(tbl)
            for col in columns:
                cols_info.append(
                    ColumnInfo(
                        name=col["name"],
                        type=str(col["type"]),
                        nullable=col.get("nullable", True),
                        primary_key=bool(col.get("primary_key", False)),
                        default=str(col.get("default", "")) if col.get("default") else None,
                    )
                )
        except Exception:
            pass

        indexes_info: List[str] = []
        try:
            indexes = insp.get_indexes(tbl)
            for idx in indexes:
                idx_name = idx.get("name") or "unnamed"
                col_names = ", ".join(idx.get("column_names", []))
                indexes_info.append(f"{idx_name} ({col_names})")
        except Exception:
            pass

        # Estimate row count
        model = MODEL_MAP.get(tbl)
        est_rows = 0
        if model is not None:
            try:
                est_rows = db.scalar(select(func.count()).select_from(model)) or 0
            except Exception:
                est_rows = 0

        results.append(
            TableDetail(
                name=tbl,
                tier=tier,
                columns=cols_info,
                indexes=indexes_info,
                estimated_row_count=est_rows,
            )
        )

    return DatabaseTablesResponse(
        tables=results,
        count=len(results),
    )


@router.get("/storage-summary", response_model=StorageSummaryResponse, summary="Storage summary partitioned by data architecture tier")
def get_storage_summary(db: Session = Depends(get_db)):
    """
    Returns an architecture-level storage summary grouped by Tier (Bronze, Silver, Operational),
    documenting table memberships, total row allocations, and latest ingestion times.
    """
    bind = db.get_bind()
    dialect_name = bind.dialect.name if hasattr(bind, "dialect") else "unknown"

    tier_groups: Dict[str, Dict[str, Any]] = {
        "bronze": {"tables": [], "rows": 0, "last_dt": None},
        "silver": {"tables": [], "rows": 0, "last_dt": None},
        "operational": {"tables": [], "rows": 0, "last_dt": None},
    }

    raw_payload_count = 0

    for tbl_name, model in MODEL_MAP.items():
        tier = TABLE_TIERS.get(tbl_name, "operational")
        try:
            cnt = db.scalar(select(func.count()).select_from(model)) or 0
        except Exception:
            cnt = 0

        tier_groups[tier]["tables"].append(tbl_name)
        tier_groups[tier]["rows"] += cnt

        if tier == "bronze":
            raw_payload_count += cnt

        for col_name in ("extracted_at", "updated_at", "created_at", "started_at", "logged_at"):
            if hasattr(model, col_name):
                try:
                    dt = db.scalar(select(func.max(getattr(model, col_name))))
                    if dt:
                        curr = tier_groups[tier]["last_dt"]
                        if not curr or dt > curr:
                            tier_groups[tier]["last_dt"] = dt
                except Exception:
                    pass

    tiers_out: Dict[str, TierSummary] = {}
    total_all_rows = 0

    for t_name, data in tier_groups.items():
        total_all_rows += data["rows"]
        tiers_out[t_name] = TierSummary(
            tier=t_name,
            table_count=len(data["tables"]),
            total_rows=data["rows"],
            tables=data["tables"],
            last_ingestion=data["last_dt"],
        )

    return StorageSummaryResponse(
        engine_dialect=dialect_name,
        tiers=tiers_out,
        total_raw_payloads=raw_payload_count,
        total_storage_rows=total_all_rows,
        generated_at=datetime.utcnow(),
    )
