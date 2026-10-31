from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class ExtractionStartRequest(BaseModel):
    repository_full_name: str = Field(
        ...,
        examples=["tiangolo/fastapi", "psf/requests"],
        description="Target GitHub repository full name in 'owner/repo' format",
    )
    resources: List[str] = Field(
        default=["repository", "commits", "pull_requests", "issues"],
        description="Subset of resources to extract: ['repository', 'commits', 'pull_requests', 'issues']",
    )
    incremental: bool = Field(
        default=True,
        description="Whether to resume extraction from the last stored high-water mark timestamp",
    )
    since: Optional[datetime] = Field(
        default=None,
        description="Explicit start timestamp boundary (overrides checkpoint if provided)",
    )
    until: Optional[datetime] = Field(
        default=None,
        description="Explicit end timestamp boundary",
    )
    max_pages: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Safety ceiling on number of paginated pages per resource",
    )


class ExtractionStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    repository_full_name: str
    status: str
    resources: List[str]
    incremental: bool
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    records_extracted: Dict[str, int] = {}
    records_loaded: Dict[str, int] = {}
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, str]] = None


class ExtractionRetryRequest(BaseModel):
    job_id: str = Field(..., description="Unique job ID of the failed or partially successful run to retry")
    resources: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific resources to retry. If omitted, retries failed resources.",
    )
    force_full_refresh: bool = Field(
        default=False,
        description="If True, ignores stored checkpoints and re-extracts the full history",
    )

