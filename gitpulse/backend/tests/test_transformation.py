"""
Comprehensive Test Suite for dbt Transformation & Data Quality Layer.

Validates:
- dbt project configuration & model parsing
- Data lineage DAG (sources -> staging -> intermediate -> marts -> dashboard)
- Subprocess execution wrapper, safety boundaries, and timeout handling
- Test result persistence into data_quality_results
- Transformation API endpoints:
  - GET  /api/v1/transformation/status
  - POST /api/v1/transformation/run
  - POST /api/v1/transformation/test
  - GET  /api/v1/transformation/history
  - GET  /api/v1/transformation/lineage
  - GET  /api/v1/quality/results
"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

from app.api.v1.endpoints.transformation import (
    get_data_lineage,
    get_quality_results,
    get_transformation_history,
    get_transformation_status,
    run_transformation,
    test_transformation as run_test_endpoint,
)
from app.models.operational import DataQualityResult
from app.models.pipeline_run import PipelineRun
from app.schemas.transformation import TransformationRunRequest
from app.services.dbt_service import dbt_service


def test_dbt_configuration_and_status(db_session: Session):
    """Verifies that dbt Core is detected and models/tests are discovered."""
    status_resp = dbt_service.get_status(db=db_session)
    assert status_resp.dbt_installed is True
    assert status_resp.dbt_version is not None
    assert status_resp.total_models >= 11
    assert status_resp.total_tests >= 4
    assert status_resp.total_sources >= 5
    assert status_resp.project_name == "gitpulse_transforms"


def test_transformation_status_endpoint(db_session: Session):
    """Tests GET /api/v1/transformation/status endpoint."""
    resp = get_transformation_status(db=db_session)
    assert resp.dbt_installed is True
    assert resp.active_target == "dev"
    assert resp.total_models >= 11


def test_data_lineage_graph():
    """Verifies end-to-end DAG connectivity across all tiers."""
    lineage = dbt_service.get_lineage()
    assert lineage.total_nodes >= 15
    assert lineage.total_edges >= 15

    node_types = {n.type for n in lineage.nodes}
    assert "source" in node_types
    assert "staging" in node_types
    assert "intermediate" in node_types
    assert "mart" in node_types
    assert "dashboard" in node_types

    node_tiers = {n.tier for n in lineage.nodes}
    assert "bronze" in node_tiers
    assert "silver" in node_tiers
    assert "gold" in node_tiers
    assert "presentation" in node_tiers

    node_ids = {n.id for n in lineage.nodes}
    for edge in lineage.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids


def test_data_lineage_endpoint():
    """Tests GET /api/v1/transformation/lineage."""
    resp = get_data_lineage()
    assert resp.total_nodes > 0
    assert resp.total_edges > 0
    assert "GitHub API" in resp.pipeline_flow


def test_dbt_execution_command_validation():
    """Verifies that illegal/unsupported shell commands are rejected."""
    with pytest.raises(ValueError, match="Invalid dbt command 'drop table'"):
        dbt_service.execute_command(command="drop table")


def test_dbt_execution_service_mocked_run(db_session: Session, tmp_path):
    """
    Tests execute_command handles subprocess output, parses results,
    and commits quality results to the database.
    """
    mock_run_results = {
        "results": [
            {
                "status": "pass",
                "unique_id": "test.gitpulse_transforms.not_null_stg_commits_commit_sha",
                "execution_time": 0.042,
                "failures": 0,
                "message": None,
            },
            {
                "status": "fail",
                "unique_id": "test.gitpulse_transforms.unique_fct_commits_commit_sha",
                "execution_time": 0.088,
                "failures": 2,
                "message": "Got 2 results, configured to fail if != 0",
            },
        ]
    }

    # Write temporary run_results.json
    target_dir = dbt_service.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    results_file = target_dir / "run_results.json"
    results_file.write_text(json.dumps(mock_run_results), encoding="utf-8")

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = "Running tests...\nCompleted with 1 failure."
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc):
        resp = dbt_service.execute_command(
            command="test",
            target="dev",
            db=db_session,
        )

    assert resp.command == "test"
    assert resp.total_nodes == 2
    assert resp.passed == 1
    assert resp.failed == 1
    assert len(resp.test_results) == 2

    # Check that test outcome was persisted to data_quality_results in DB
    quality_rows = db_session.scalars(
        DataQualityResult.__table__.select().where(
            DataQualityResult.job_id == resp.run_id
        )
    ).all()
    assert len(quality_rows) == 2


def test_transformation_run_and_test_endpoints(db_session: Session):
    """Tests POST /api/v1/transformation/run and POST /api/v1/transformation/test."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "dbt run completed successfully"
    mock_proc.stderr = ""

    with patch("subprocess.run", return_value=mock_proc):
        run_resp = run_transformation(
            request=TransformationRunRequest(command="run", models=["stg_commits"]),
            db=db_session,
        )
        assert run_resp.command == "run"
        assert run_resp.status == "success"

        test_resp = run_test_endpoint(
            request=TransformationRunRequest(command="test"),
            db=db_session,
        )
        assert test_resp.command == "test"
        assert test_resp.status == "success"


def test_transformation_history_endpoint(db_session: Session):
    """Tests GET /api/v1/transformation/history."""
    # Seed a pipeline run
    pr = PipelineRun(
        repository_id=1,
        pipeline_name="dbt_run",
        stage="transform",
        status="completed",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        duration_seconds=5.2,
        records_loaded=42,
    )
    db_session.add(pr)
    db_session.commit()

    history = get_transformation_history(limit=10, db=db_session)
    assert len(history) >= 1
    assert any(h["pipeline_name"] == "dbt_run" for h in history)


def test_quality_results_endpoint(db_session: Session):
    """Tests GET /api/v1/quality/results with aggregation and filtering."""
    # Seed quality rows
    r1 = DataQualityResult(
        rule_name="not_null:stg_commits.sha",
        resource_type="commits",
        passed=True,
        severity="warn",
        failure_count=0,
        source="dbt",
        evaluated_at=datetime.utcnow(),
    )
    r2 = DataQualityResult(
        rule_name="unique:stg_commits.sha",
        resource_type="commits",
        passed=False,
        severity="error",
        failure_count=3,
        source="dbt",
        evaluated_at=datetime.utcnow(),
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    all_res = get_quality_results(db=db_session)
    assert all_res.total_checks >= 2
    assert all_res.passed >= 1
    assert all_res.failed >= 1
    assert all_res.pass_rate_pct is not None

    passed_only = get_quality_results(status="passed", db=db_session)
    for p in passed_only.results:
        assert p.passed is True

    failed_only = get_quality_results(status="failed", db=db_session)
    for f in failed_only.results:
        assert f.passed is False
