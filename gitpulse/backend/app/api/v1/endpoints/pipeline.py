from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.pipeline_repo import pipeline_run_repo
from app.schemas.pipeline import PipelineTriggerRequest, PipelineRunRead
from app.services.pipeline_service import pipeline_service

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post("/trigger", response_model=PipelineRunRead, status_code=status.HTTP_202_ACCEPTED, summary="Trigger ELT pipeline")
def trigger_pipeline(
    request: PipelineTriggerRequest,
    db: Session = Depends(get_db),
):
    """
    Executes an ELT ingestion cycle for the targeted repository:
    Extracts commits, PRs, and issues; writes to Bronze raw_events; promotes to Silver tables.
    """
    return pipeline_service.run_pipeline(db, request)


@router.get("/runs", response_model=List[PipelineRunRead], summary="List recent pipeline execution runs")
def list_pipeline_runs(
    repository_id: Optional[int] = Query(None, description="Filter by repository ID"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if repository_id:
        return pipeline_run_repo.get_by_repository(db, repository_id=repository_id, limit=limit)
    return pipeline_run_repo.get_recent(db, limit=limit)


@router.get("/runs/{run_id}", response_model=PipelineRunRead, summary="Get details of a specific pipeline run")
def get_pipeline_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = pipeline_run_repo.get(db, run_id)
    if not run:
        from app.core.exceptions import EntityNotFoundException
        raise EntityNotFoundException("PipelineRun", run_id)
    return run

