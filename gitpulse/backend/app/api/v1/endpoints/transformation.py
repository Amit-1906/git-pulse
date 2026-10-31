"""
Transformation & Data Quality API Endpoints.

Provides REST interfaces for:
- GET  /api/v1/transformation/status
- POST /api/v1/transformation/run
- POST /api/v1/transformation/test
- GET  /api/v1/transformation/history
- GET  /api/v1/transformation/lineage
- GET  /api/v1/quality/results
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.operational import DataQualityResult
from app.models.pipeline_run import PipelineRun
from app.schemas.transformation import (
    DataLineageResponse,
    QualityResultsResponse,
    QualitySummaryItem,
    TransformationRunRequest,
    TransformationRunResponse,
    TransformationStatusResponse,
)
from app.services.dbt_service import dbt_service

router = APIRouter(tags=["Transformation & Data Quality"])


# ─────────────────────────────────────────────────────────────────────────── #
#  Transformation Endpoints                                                    #
# ─────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/transformation/status",
    response_model=TransformationStatusResponse,
    summary="Get dbt project configuration, target status, and model discovery metrics",
)
def get_transformation_status(db: Session = Depends(get_db)):
    """
    Returns dbt Core installation status, active target profile, database connectivity,
    and counts of discovered models, sources, and data tests.
    """
    return dbt_service.get_status(db=db)


@router.post(
    "/transformation/run",
    response_model=TransformationRunResponse,
    summary="Execute dbt run or build against target models",
)
def run_transformation(
    request: Optional[TransformationRunRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Executes 'dbt run' (or 'dbt build') with model selection, full-refresh options,
    and automatic telemetry capture.
    """
    req = request or TransformationRunRequest(command="run")
    cmd = req.command if req.command in ("run", "build", "compile") else "run"
    return dbt_service.execute_command(
        command=cmd,
        models=req.models,
        target=req.target or "dev",
        full_refresh=req.full_refresh,
        db=db,
    )


@router.post(
    "/transformation/test",
    response_model=TransformationRunResponse,
    summary="Execute dbt test suite and record validation outcomes",
)
def test_transformation(
    request: Optional[TransformationRunRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Executes 'dbt test' across generic schema tests, referential integrity assertions,
    and custom business-rule checks. Persists outcomes directly into data_quality_results.
    """
    req = request or TransformationRunRequest(command="test")
    return dbt_service.execute_command(
        command="test",
        models=req.models,
        target=req.target or "dev",
        db=db,
    )


@router.get(
    "/transformation/history",
    summary="Retrieve execution history of transformation and testing runs",
)
def get_transformation_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns timeline of previous dbt pipeline runs, execution times, node counts,
    and failure logs from the database.
    """
    limit_val = limit if isinstance(limit, int) else 20
    stmt = (
        select(PipelineRun)
        .where(
            PipelineRun.pipeline_name.like("dbt_%")
            | PipelineRun.stage.in_(["transform", "test"])
        )
        .order_by(PipelineRun.started_at.desc())
        .limit(limit_val)
    )
    runs = db.scalars(stmt).all()

    return [
        {
            "id": r.id,
            "pipeline_name": r.pipeline_name,
            "stage": r.stage,
            "status": r.status,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "duration_seconds": r.duration_seconds,
            "records_loaded": r.records_loaded,
            "error_message": r.error_message,
            "metadata": r.run_metadata,
        }
        for r in runs
    ]


@router.get(
    "/transformation/lineage",
    response_model=DataLineageResponse,
    summary="Expose end-to-end directed acyclic graph (DAG) data lineage",
)
def get_data_lineage():
    """
    Exposes full pipeline lineage:
    GitHub API -> PostgreSQL Raw Tables -> dbt Staging -> Intermediate -> Facts & Dimensions -> Analytics Dashboard.
    """
    return dbt_service.get_lineage()


# ─────────────────────────────────────────────────────────────────────────── #
#  Data Quality Endpoints                                                      #
# ─────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/quality/results",
    response_model=QualityResultsResponse,
    summary="Get aggregated data quality test results, rule evaluations, and pass rates",
)
def get_quality_results(
    resource_type: Optional[str] = Query(None, description="commits | pull_requests | issues | repositories"),
    status: Optional[str] = Query(None, description="'passed' or 'failed'"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Returns data quality test outcomes generated by dbt test assertions,
    including rule names, severity, failure counts, and overall pass rates.
    """
    res_type = resource_type if isinstance(resource_type, str) else None
    stat_val = status if isinstance(status, str) else None
    limit_val = limit if isinstance(limit, int) else 100

    stmt = select(DataQualityResult)
    if res_type:
        stmt = stmt.where(DataQualityResult.resource_type == res_type)
    if stat_val == "passed":
        stmt = stmt.where(DataQualityResult.passed == True)
    elif stat_val == "failed":
        stmt = stmt.where(DataQualityResult.passed == False)

    stmt = stmt.order_by(DataQualityResult.evaluated_at.desc()).limit(limit_val)
    rows = list(db.scalars(stmt).all())

    # Aggregate metrics
    base_count = select(func.count()).select_from(DataQualityResult)
    if res_type:
        base_count = base_count.where(DataQualityResult.resource_type == res_type)

    total_checks = db.scalar(base_count) or 0
    passed_checks = db.scalar(
        base_count.where(DataQualityResult.passed == True)
    ) or 0
    failed_checks = total_checks - passed_checks
    pass_rate = (
        round((passed_checks / total_checks) * 100.0, 1) if total_checks > 0 else None
    )

    items = [
        QualitySummaryItem(
            id=r.id,
            rule_name=r.rule_name,
            resource_type=r.resource_type,
            passed=r.passed,
            severity=r.severity,
            failure_count=r.failure_count or 0,
            total_count=r.total_count,
            failure_rate=r.failure_rate,
            message=r.message,
            source=r.source,
            evaluated_at=r.evaluated_at,
        )
        for r in rows
    ]

    return QualityResultsResponse(
        total_checks=total_checks,
        passed=passed_checks,
        failed=failed_checks,
        pass_rate_pct=pass_rate,
        results=items,
        generated_at=datetime.utcnow(),
    )
