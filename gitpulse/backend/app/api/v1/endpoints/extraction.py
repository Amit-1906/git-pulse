from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.core.exceptions import EntityNotFoundException, GitPulseException
from app.extractors.engine import extraction_engine
from app.models.extraction_job import ExtractionJob
from app.schemas.extraction import (
    ExtractionStartRequest,
    ExtractionStatusResponse,
    ExtractionRetryRequest,
)

router = APIRouter(prefix="/extraction", tags=["Data Extraction Engine"])


def execute_extraction_job_background(job_id: str, per_page: int = 100, max_pages: Optional[int] = None):
    """Executes an extraction job in background worker session."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        extraction_engine.run_job(db, job_id, per_page=per_page, max_pages=max_pages)
    finally:
        db.close()


@router.post("/start", response_model=ExtractionStatusResponse, status_code=status.HTTP_202_ACCEPTED, summary="Start an asynchronous GitHub extraction job")
def start_extraction(
    request: ExtractionStartRequest,
    background_tasks: BackgroundTasks,
    run_sync: bool = Query(False, description="Run synchronously for testing/scripts"),
    db: Session = Depends(get_db),
):
    """
    Initializes a new GitHub data extraction job with unique Job ID.
    Enforces concurrency lock: rejects overlapping runs for the same repository.
    Applies incremental checkpoints unless explicitly disabled.
    """
    is_sync = run_sync if isinstance(run_sync, bool) else False

    job = extraction_engine.create_job(
        db=db,
        repository_full_name=request.repository_full_name,
        resources=request.resources,
        incremental=request.incremental,
        since=request.since,
        until=request.until,
    )

    if is_sync:
        job = extraction_engine.run_job(db, job.job_id, max_pages=request.max_pages)
    else:
        background_tasks.add_task(
            execute_extraction_job_background,
            job_id=job.job_id,
            max_pages=request.max_pages,
        )

    return job


@router.get("/status/{job_id}", response_model=ExtractionStatusResponse, summary="Get real-time status and telemetry of an extraction job")
def get_extraction_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.scalar(select(ExtractionJob).where(ExtractionJob.job_id == job_id))
    if not job:
        raise EntityNotFoundException("ExtractionJob", job_id)
    return job


@router.get("/history", response_model=List[ExtractionStatusResponse], summary="List historical extraction jobs")
def list_extraction_history(
    repository: Optional[str] = Query(None, description="Filter by repository full name"),
    status: Optional[str] = Query(None, description="Filter by status (COMPLETED, FAILED, RUNNING, etc.)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(ExtractionJob)
    if isinstance(repository, str) and repository.strip():
        stmt = stmt.where(ExtractionJob.repository_full_name == repository.lower().strip())
    if isinstance(status, str) and status.strip():
        stmt = stmt.where(ExtractionJob.status == status.upper().strip())
    
    limit_val = limit if isinstance(limit, int) else 20
    stmt = stmt.order_by(ExtractionJob.created_at.desc()).limit(limit_val)
    return list(db.scalars(stmt).all())


@router.post("/retry", response_model=ExtractionStatusResponse, status_code=status.HTTP_202_ACCEPTED, summary="Retry a failed or partial extraction job")
def retry_extraction(
    request: ExtractionRetryRequest,
    background_tasks: BackgroundTasks,
    run_sync: bool = Query(False),
    db: Session = Depends(get_db),
):
    is_sync = run_sync if isinstance(run_sync, bool) else False

    prior_job = db.scalar(select(ExtractionJob).where(ExtractionJob.job_id == request.job_id))
    if not prior_job:
        raise EntityNotFoundException("ExtractionJob", request.job_id)

    # Determine resources to retry
    target_resources = request.resources
    if not target_resources:
        if prior_job.error_details:
            target_resources = list(prior_job.error_details.keys())
        else:
            target_resources = prior_job.resources

    # Create new retry job
    new_job = extraction_engine.create_job(
        db=db,
        repository_full_name=prior_job.repository_full_name,
        resources=target_resources,
        incremental=not request.force_full_refresh,
        since=prior_job.since if not request.force_full_refresh else None,
        until=prior_job.until,
    )

    if is_sync:
        new_job = extraction_engine.run_job(db, new_job.job_id)
    else:
        background_tasks.add_task(execute_extraction_job_background, job_id=new_job.job_id)

    return new_job


@router.post("/cancel/{job_id}", response_model=ExtractionStatusResponse, summary="Cancel an active extraction job")
def cancel_extraction(
    job_id: str,
    db: Session = Depends(get_db),
):
    return extraction_engine.cancel_job(db, job_id)
