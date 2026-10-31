from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class PipelineTriggerRequest(BaseModel):
    repository_id: int = Field(..., description="Target repository ID to extract & transform")
    stages: List[str] = Field(
        default=["extract", "load"],
        description="Pipeline stages to execute: ['extract', 'load', 'transform', 'test']",
    )
    max_commits: int = Field(default=30, ge=1, le=100, description="Max commits to fetch in extraction")
    max_pulls: int = Field(default=30, ge=1, le=100, description="Max PRs to fetch in extraction")
    max_issues: int = Field(default=30, ge=1, le=100, description="Max issues to fetch in extraction")


class PipelineRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    pipeline_name: str
    stage: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    records_extracted: int = 0
    records_loaded: int = 0
    error_message: Optional[str] = None
    run_metadata: Optional[Dict[str, Any]] = None


class PipelineStatusSummary(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    in_progress_runs: int
    last_run: Optional[PipelineRunRead] = None

