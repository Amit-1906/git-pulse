import pytest
from unittest.mock import MagicMock
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.api.v1.endpoints.extraction import (
    start_extraction,
    get_extraction_status,
    list_extraction_history,
    retry_extraction,
    cancel_extraction,
)
from app.schemas.extraction import (
    ExtractionStartRequest,
    ExtractionRetryRequest,
)
from app.extractors.engine import extraction_engine
from app.core.exceptions import EntityNotFoundException, GitPulseException


def test_extraction_endpoints_lifecycle(db_session: Session, monkeypatch):
    # Mock the internal extraction_engine.run_job to simulate rapid execution
    orig_run_job = extraction_engine.run_job

    def mock_run_job(db, job_id, per_page=100, max_pages=None):
        job = extraction_engine.cancel_job(db, job_id)  # transition status
        job.status = "COMPLETED"
        job.records_extracted = {"commits": 10, "issues": 5}
        job.records_loaded = {"commits": 10, "issues": 5}
        db.commit()
        return job

    monkeypatch.setattr(extraction_engine, "run_job", mock_run_job)

    bg_tasks = BackgroundTasks()

    # 1. Start extraction synchronously
    start_req = ExtractionStartRequest(
        repository_full_name="tiangolo/fastapi",
        resources=["commits", "issues"],
        incremental=True,
    )
    job = start_extraction(request=start_req, background_tasks=bg_tasks, run_sync=True, db=db_session)
    assert job.job_id.startswith("job_")
    assert job.status == "COMPLETED"
    job_id = job.job_id

    # 2. Get extraction status by job ID
    status_resp = get_extraction_status(job_id=job_id, db=db_session)
    assert status_resp.job_id == job_id
    assert status_resp.status == "COMPLETED"
    assert status_resp.records_extracted["commits"] == 10

    # 3. List history
    history = list_extraction_history(repository="tiangolo/fastapi", limit=10, db=db_session)
    assert len(history) >= 1
    assert any(h.job_id == job_id for h in history)

    # 4. Cancel job endpoint
    # Create another pending job
    req2 = ExtractionStartRequest(repository_full_name="psf/requests", resources=["repository"])
    job2 = start_extraction(request=req2, background_tasks=bg_tasks, run_sync=False, db=db_session)
    cancel_resp = cancel_extraction(job_id=job2.job_id, db=db_session)
    assert cancel_resp.status == "CANCELLED"

    # 5. Non-existent job
    with pytest.raises(EntityNotFoundException):
        get_extraction_status(job_id="job_non_existent", db=db_session)

