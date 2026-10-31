from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun
from app.repositories.base import BaseRepository
from app.schemas.pipeline import PipelineRunRead


class PipelineRunRepository(BaseRepository[PipelineRun, Any, Any]):
    def __init__(self):
        super().__init__(PipelineRun)

    def create_run(
        self,
        db: Session,
        repository_id: int,
        pipeline_name: str = "github_elt_pipeline",
        stage: str = "extract",
    ) -> PipelineRun:
        run = PipelineRun(
            repository_id=repository_id,
            pipeline_name=pipeline_name,
            stage=stage,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def complete_run(
        self,
        db: Session,
        run_id: int,
        records_extracted: int = 0,
        records_loaded: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[PipelineRun]:
        run = self.get(db, run_id)
        if not run:
            return None
        now = datetime.utcnow()
        run.status = "completed"
        run.finished_at = now
        run.duration_seconds = round((now - run.started_at).total_seconds(), 2)
        run.records_extracted = records_extracted
        run.records_loaded = records_loaded
        if metadata:
            run.run_metadata = metadata
        db.commit()
        db.refresh(run)
        return run

    def fail_run(
        self,
        db: Session,
        run_id: int,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[PipelineRun]:
        run = self.get(db, run_id)
        if not run:
            return None
        now = datetime.utcnow()
        run.status = "failed"
        run.finished_at = now
        run.duration_seconds = round((now - run.started_at).total_seconds(), 2)
        run.error_message = error_message
        if metadata:
            run.run_metadata = metadata
        db.commit()
        db.refresh(run)
        return run

    def get_recent(self, db: Session, limit: int = 20) -> List[PipelineRun]:
        stmt = select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def get_by_repository(self, db: Session, repository_id: int, limit: int = 20) -> List[PipelineRun]:
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.repository_id == repository_id)
            .order_by(PipelineRun.started_at.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


pipeline_run_repo = PipelineRunRepository()

