"""
dbt Transformation & Data Quality Schemas.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TransformationRunRequest(BaseModel):
    command: str = Field(
        default="run",
        description="dbt command: 'run' | 'test' | 'build' | 'debug' | 'deps' | 'docs generate'",
    )
    models: Optional[List[str]] = Field(
        default=None,
        description="Optional list of model selectors, e.g. ['stg_commits', 'tag:marts']",
    )
    target: Optional[str] = Field(
        default="dev",
        description="'dev' or 'prod'",
    )
    full_refresh: bool = Field(
        default=False,
        description="Whether to append --full-refresh flag",
    )


class TestResultItem(BaseModel):
    rule_name: str
    status: str
    resource_type: Optional[str] = None
    failures: int = 0
    message: Optional[str] = None
    execution_time: float = 0.0


class TransformationRunResponse(BaseModel):
    run_id: str
    command: str
    status: str = Field(description="'success' | 'failed' | 'error'")
    target: str
    models_selected: Optional[str] = None
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    total_nodes: int = 0
    passed: int = 0
    failed: int = 0
    warned: int = 0
    error_message: Optional[str] = None
    test_results: List[TestResultItem] = []
    output_log: str = ""


class TransformationStatusResponse(BaseModel):
    dbt_installed: bool
    dbt_version: Optional[str] = None
    project_name: str
    project_dir: str
    active_target: str
    database_connected: bool
    total_models: int
    total_tests: int
    total_sources: int
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None


class LineageNode(BaseModel):
    id: str
    name: str
    type: str = Field(description="'source' | 'staging' | 'intermediate' | 'mart' | 'dashboard'")
    tier: str = Field(description="'bronze' | 'silver' | 'gold' | 'presentation'")
    description: Optional[str] = None


class LineageEdge(BaseModel):
    source: str
    target: str


class DataLineageResponse(BaseModel):
    nodes: List[LineageNode]
    edges: List[LineageEdge]
    total_nodes: int
    total_edges: int
    pipeline_flow: str = "GitHub API -> PostgreSQL Raw Tables -> dbt Staging -> Intermediate -> Facts & Dimensions -> Analytics Dashboard"


class QualitySummaryItem(BaseModel):
    id: int
    rule_name: str
    resource_type: Optional[str] = None
    passed: bool
    severity: str
    failure_count: int
    total_count: Optional[int] = None
    failure_rate: Optional[float] = None
    message: Optional[str] = None
    source: str
    evaluated_at: datetime


class QualityResultsResponse(BaseModel):
    total_checks: int
    passed: int
    failed: int
    pass_rate_pct: Optional[float] = None
    results: List[QualitySummaryItem]
    generated_at: datetime = Field(default_factory=datetime.utcnow)

